"""
Serviço de inferência — identificação preliminar de peixe-leão em fotografias.

Princípios (seções 4.3 e 6.7 do escopo):
  * a inferência é **real**: executa um modelo treinado carregado de arquivo.
    Não existe caminho de código que invente uma classe ou um score;
  * se não houver modelo disponível, o serviço informa o estado
    `SEM_MODELO` e a interface continua permitindo o registro — a ocorrência é
    gravada para revisão humana, sem classificação;
  * o modelo é carregado **uma vez** por processo e reutilizado;
  * toda predição carrega a versão do modelo que a produziu;
  * três respostas possíveis: possível peixe-leão, não identificado e
    inconclusivo. O limiar de cada faixa é configurável e registrado.

Formatos aceitos: ONNX (`onnxruntime`) e TorchScript (`torch`). Um classificador
CNN **não** produz caixas de detecção; o campo `caixas` só é preenchido quando o
modelo em uso for um detector.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.ai.preprocessing import (
    EntradaModelo,
    PreprocessamentoInvalido,
    estatisticas_imagem,
    preparar,
    sigmoide,
    softmax,
)
from src.config import get_config
from src.database.schema import ClassePredicao

ARQUIVO_CARTAO_MODELO = "model_card.json"

MENSAGENS = {
    ClassePredicao.PEIXE_LEAO: (
        "Possível peixe-leão identificado. Esta é uma indicação preliminar "
        "automática e precisa ser validada por um avaliador."
    ),
    ClassePredicao.NAO_PEIXE_LEAO: (
        "O modelo não identificou peixe-leão nesta imagem. Isso não garante "
        "que a espécie não esteja presente — você pode seguir com o registro."
    ),
    ClassePredicao.INCONCLUSIVO: (
        "Análise inconclusiva: a imagem não permite uma classificação "
        "suficientemente confiável. O registro segue para revisão humana."
    ),
    ClassePredicao.SEM_MODELO: (
        "A identificação automática está indisponível neste momento. "
        "Seu registro será salvo e analisado por um avaliador."
    ),
    ClassePredicao.ERRO: (
        "Não foi possível analisar a imagem automaticamente. "
        "Seu registro será salvo e analisado por um avaliador."
    ),
}


@dataclass(slots=True)
class CaixaDeteccao:
    """Caixa de detecção, em coordenadas da imagem original."""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    classe: str = "peixe-leao"


@dataclass(slots=True)
class ResultadoInferencia:
    """Resultado de uma classificação, pronto para persistir e exibir."""

    classe: ClassePredicao
    modelo: str
    versao: str
    score: float | None = None
    tempo_inferencia_ms: float | None = None
    limiar_positivo: float | None = None
    limiar_inconclusivo: float | None = None
    caixas: list[CaixaDeteccao] = field(default_factory=list)
    qualidade_imagem: dict = field(default_factory=dict)
    erro: str | None = None

    @property
    def disponivel(self) -> bool:
        return self.classe not in (ClassePredicao.SEM_MODELO, ClassePredicao.ERRO)

    @property
    def positivo(self) -> bool:
        return self.classe == ClassePredicao.PEIXE_LEAO

    @property
    def mensagem_usuario(self) -> str:
        return MENSAGENS.get(self.classe, MENSAGENS[ClassePredicao.ERRO])

    @property
    def score_percentual(self) -> str:
        return f"{self.score * 100:.1f}%" if self.score is not None else "—"

    def detalhes_json(self) -> str:
        """Serializa os metadados da predição para a coluna `detalhes`."""
        return json.dumps(
            {
                "limiar_positivo": self.limiar_positivo,
                "limiar_inconclusivo": self.limiar_inconclusivo,
                "qualidade_imagem": self.qualidade_imagem,
                "caixas": [vars(c) for c in self.caixas],
                "erro": self.erro,
            },
            ensure_ascii=False,
        )


@dataclass(slots=True)
class CartaoModelo:
    """Metadados do modelo publicado (`models/model_card.json`)."""

    nome: str
    versao: str
    arquitetura: str
    arquivo: str
    formato: str  # "onnx" | "torchscript"
    entrada: int = 224
    classes: tuple[str, ...] = ("NAO_PEIXE_LEAO", "PEIXE_LEAO")
    indice_positivo: int = 1
    ativacao: str = "softmax"  # "softmax" (2 saídas) | "sigmoide" (1 saída)
    detector: bool = False
    arquivo_metricas: str | None = None
    treinado_em: str | None = None
    observacoes: str | None = None

    @classmethod
    def carregar(cls, caminho: Path) -> CartaoModelo:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return cls(
            nome=dados["nome"],
            versao=str(dados["versao"]),
            arquitetura=dados.get("arquitetura", "desconhecida"),
            arquivo=dados["arquivo"],
            formato=dados.get("formato", "onnx"),
            entrada=int(dados.get("entrada", 224)),
            classes=tuple(dados.get("classes", ("NAO_PEIXE_LEAO", "PEIXE_LEAO"))),
            indice_positivo=int(dados.get("indice_positivo", 1)),
            ativacao=dados.get("ativacao", "softmax"),
            detector=bool(dados.get("detector", False)),
            arquivo_metricas=dados.get("arquivo_metricas"),
            treinado_em=dados.get("treinado_em"),
            observacoes=dados.get("observacoes"),
        )


class _BackendONNX:
    """Execução via onnxruntime (formato recomendado para a POC)."""

    def __init__(self, caminho: Path) -> None:
        import onnxruntime as ort  # importado só quando necessário

        provedores = ["CPUExecutionProvider"]
        disponiveis = ort.get_available_providers()
        if "CUDAExecutionProvider" in disponiveis:
            provedores.insert(0, "CUDAExecutionProvider")
        self.sessao = ort.InferenceSession(str(caminho), providers=provedores)
        self.nome_entrada = self.sessao.get_inputs()[0].name

    def __call__(self, tensor: np.ndarray) -> np.ndarray:
        saidas = self.sessao.run(None, {self.nome_entrada: tensor})
        return np.asarray(saidas[0], dtype=np.float32)


class _BackendTorchScript:
    """Execução via TorchScript, quando o PyTorch estiver instalado."""

    def __init__(self, caminho: Path) -> None:
        import torch

        self.torch = torch
        self.dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        self.modelo = torch.jit.load(str(caminho), map_location=self.dispositivo)
        self.modelo.eval()

    def __call__(self, tensor: np.ndarray) -> np.ndarray:
        with self.torch.no_grad():
            entrada = self.torch.from_numpy(tensor).to(self.dispositivo)
            saida = self.modelo(entrada)
        return saida.detach().cpu().numpy().astype(np.float32)


class ServicoInferencia:
    """
    Fachada de inferência.

    `preditor` permite injetar uma função `tensor -> logits` nos testes, sem
    arquivo de modelo. Em produção o preditor vem do backend ONNX/TorchScript.
    """

    def __init__(
        self,
        cartao: CartaoModelo | None = None,
        preditor=None,
        diretorio_modelos: Path | None = None,
    ) -> None:
        config = get_config()
        self.diretorio = Path(diretorio_modelos or config.diretorio_modelos)
        self.limiar_positivo = config.limiar_positivo
        self.limiar_inconclusivo = config.limiar_inconclusivo
        self._lock = threading.Lock()
        self._preditor = preditor
        self._erro_carregamento: str | None = None

        if cartao is not None:
            self.cartao = cartao
        elif preditor is not None:
            self.cartao = CartaoModelo(
                nome="preditor-injetado",
                versao="teste",
                arquitetura="injetado",
                arquivo="",
                formato="memoria",
            )
        else:
            self.cartao = self._descobrir_cartao()

        # A versão experimental foi treinada com pouquíssimas imagens.
        # Para reduzir falsas afirmações, resultados intermediários são
        # INCONCLUSIVOS: sem conjunto de teste externo, não há limiar calibrado.
        if self.cartao and "experimental" in self.cartao.versao.lower():
            self.limiar_positivo = max(self.limiar_positivo, 0.995)
            self.limiar_inconclusivo = min(self.limiar_inconclusivo, 0.05)

    # ------------------------------------------------------------ descoberta
    def _descobrir_cartao(self) -> CartaoModelo | None:
        caminho = self.diretorio / ARQUIVO_CARTAO_MODELO
        if not caminho.is_file():
            return None
        try:
            return CartaoModelo.carregar(caminho)
        except (KeyError, ValueError, OSError) as erro:
            self._erro_carregamento = f"cartão do modelo inválido: {erro}"
            return None

    @property
    def estado(self) -> str:
        """`DISPONIVEL`, `SEM_MODELO` ou `ERRO_CARREGAMENTO`."""
        if self._erro_carregamento:
            return "ERRO_CARREGAMENTO"
        if self.cartao is None:
            return "SEM_MODELO"
        if self._preditor is not None:
            return "DISPONIVEL"
        caminho = self.diretorio / self.cartao.arquivo
        return "DISPONIVEL" if caminho.is_file() else "SEM_MODELO"

    @property
    def disponivel(self) -> bool:
        return self.estado == "DISPONIVEL"

    @property
    def descricao_estado(self) -> str:
        if self.estado == "DISPONIVEL":
            return f"{self.cartao.nome} v{self.cartao.versao} ({self.cartao.formato})"
        if self.estado == "ERRO_CARREGAMENTO":
            return f"indisponível — {self._erro_carregamento}"
        return (
            "nenhum modelo publicado em models/. Treine com "
            "`python scripts/treinar_modelo.py` e publique o model_card.json."
        )

    # ------------------------------------------------------------ carregamento
    def _obter_preditor(self):
        """Carrega o backend na primeira chamada e o mantém em memória."""
        if self._preditor is not None:
            return self._preditor
        with self._lock:
            if self._preditor is not None:  # outra thread carregou
                return self._preditor
            if self.cartao is None:
                return None
            caminho = self.diretorio / self.cartao.arquivo
            if not caminho.is_file():
                self._erro_carregamento = f"arquivo do modelo não encontrado: {caminho.name}"
                return None
            try:
                if self.cartao.formato == "onnx":
                    self._preditor = _BackendONNX(caminho)
                elif self.cartao.formato in ("torchscript", "pt", "pth"):
                    self._preditor = _BackendTorchScript(caminho)
                else:
                    self._erro_carregamento = f"formato não suportado: {self.cartao.formato}"
                    return None
            except Exception as erro:  # ImportError, falha de leitura, etc.
                self._erro_carregamento = f"{type(erro).__name__}: {erro}"
                return None
        return self._preditor

    # --------------------------------------------------------------- inferência
    def _score_positivo(self, saida: np.ndarray) -> float:
        """Extrai a probabilidade da classe positiva a partir da saída bruta."""
        vetor = np.asarray(saida, dtype=np.float32).reshape(-1)
        if vetor.size == 1 or self.cartao.ativacao == "sigmoide":
            return float(sigmoide(vetor)[0])
        probabilidades = softmax(vetor)
        indice = min(self.cartao.indice_positivo, probabilidades.size - 1)
        return float(probabilidades[indice])

    def _classificar_score(self, score: float) -> ClassePredicao:
        if score >= self.limiar_positivo:
            return ClassePredicao.PEIXE_LEAO
        if score < self.limiar_inconclusivo:
            return ClassePredicao.NAO_PEIXE_LEAO
        return ClassePredicao.INCONCLUSIVO

    def _resultado_indisponivel(
        self, classe: ClassePredicao, erro: str | None = None, qualidade: dict | None = None
    ) -> ResultadoInferencia:
        return ResultadoInferencia(
            classe=classe,
            modelo=self.cartao.nome if self.cartao else "indisponivel",
            versao=self.cartao.versao if self.cartao else "0",
            score=None,
            qualidade_imagem=qualidade or {},
            erro=erro,
        )

    def classificar(self, dados: bytes, avaliar_qualidade: bool = True) -> ResultadoInferencia:
        """
        Classifica a fotografia.

        Nunca levanta exceção para a interface: falhas viram `ERRO` /
        `SEM_MODELO`, de modo que o avistamento ainda possa ser registrado.
        """
        qualidade: dict = {}
        if avaliar_qualidade:
            try:
                qualidade = estatisticas_imagem(dados)
            except PreprocessamentoInvalido:
                qualidade = {}

        preditor = self._obter_preditor()
        if preditor is None:
            return self._resultado_indisponivel(
                ClassePredicao.SEM_MODELO, self._erro_carregamento, qualidade
            )

        try:
            entrada: EntradaModelo = preparar(dados, self.cartao.entrada)
        except PreprocessamentoInvalido as erro:
            return self._resultado_indisponivel(ClassePredicao.ERRO, str(erro), qualidade)

        inicio = time.perf_counter()
        try:
            saida = preditor(entrada.tensor)
        except Exception as erro:
            return self._resultado_indisponivel(
                ClassePredicao.ERRO, f"{type(erro).__name__}: {erro}", qualidade
            )
        duracao_ms = (time.perf_counter() - inicio) * 1000.0

        score = self._score_positivo(saida)
        classe = self._classificar_score(score)

        # Imagem muito desfocada ou escura: rebaixa um positivo para
        # inconclusivo, porque o modelo não foi validado nessa condição.
        if classe == ClassePredicao.PEIXE_LEAO and (
            qualidade.get("provavel_desfoque") or qualidade.get("provavel_subexposicao")
        ):
            classe = ClassePredicao.INCONCLUSIVO

        return ResultadoInferencia(
            classe=classe,
            modelo=self.cartao.nome,
            versao=self.cartao.versao,
            score=round(score, 4),
            tempo_inferencia_ms=round(duracao_ms, 2),
            limiar_positivo=self.limiar_positivo,
            limiar_inconclusivo=self.limiar_inconclusivo,
            caixas=[],  # classificador não localiza indivíduos na imagem
            qualidade_imagem=qualidade,
        )


# ------------------------------------------------------------------ singleton
_servico: ServicoInferencia | None = None
_lock_servico = threading.Lock()


def obter_servico_inferencia() -> ServicoInferencia:
    """
    Instância única por processo — evita recarregar o modelo a cada interação
    do Streamlit (seção 6.7 do escopo).
    """
    global _servico
    if _servico is None:
        with _lock_servico:
            if _servico is None:
                _servico = ServicoInferencia()
    return _servico


def resetar_servico_inferencia() -> None:
    """Usado em testes e após publicar um novo modelo."""
    global _servico
    with _lock_servico:
        _servico = None
