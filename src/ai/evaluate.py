"""
Avaliação do modelo no conjunto de teste.

Gera `reports/metricas_modelo.json`, que é **a única fonte** dos números do
Dashboard de IA. Se este arquivo não existir, o painel exibe o estado
"modelo não avaliado" — nenhuma métrica é inventada.

O cálculo das métricas está isolado em `calcular_metricas`, uma função pura
(rótulos + scores -> métricas) que roda sem modelo e sem imagens e é coberta
por testes automatizados.

Execução (após o treinamento):
    python scripts/avaliar_modelo.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from src.ai.inference import CartaoModelo, ServicoInferencia
from src.ai.preprocessing import preparar
from src.ai.train import CLASSES, EXTENSOES_IMAGEM


@dataclass
class Metricas:
    """Métricas de classificação binária em um limiar específico."""

    limiar: float
    acuracia: float
    precisao: float
    revocacao: float
    f1: float
    especificidade: float
    verdadeiros_positivos: int
    verdadeiros_negativos: int
    falsos_positivos: int
    falsos_negativos: int
    total: int

    @property
    def matriz_confusao(self) -> list[list[int]]:
        """[[VN, FP], [FN, VP]] — formato linha=real, coluna=previsto."""
        return [
            [self.verdadeiros_negativos, self.falsos_positivos],
            [self.falsos_negativos, self.verdadeiros_positivos],
        ]

    def como_dicionario(self) -> dict:
        return {
            "limiar": round(self.limiar, 4),
            "acuracia": round(self.acuracia, 4),
            "precisao": round(self.precisao, 4),
            "revocacao": round(self.revocacao, 4),
            "f1": round(self.f1, 4),
            "especificidade": round(self.especificidade, 4),
            "verdadeiros_positivos": self.verdadeiros_positivos,
            "verdadeiros_negativos": self.verdadeiros_negativos,
            "falsos_positivos": self.falsos_positivos,
            "falsos_negativos": self.falsos_negativos,
            "total": self.total,
            "matriz_confusao": self.matriz_confusao,
        }


def calcular_metricas(
    rotulos: list[int] | np.ndarray,
    scores: list[float] | np.ndarray,
    limiar: float = 0.5,
) -> Metricas:
    """
    Calcula as métricas a partir dos rótulos verdadeiros e dos scores.

    `rotulos`: 1 = peixe-leão, 0 = não peixe-leão.
    `scores`: probabilidade atribuída pelo modelo à classe positiva.
    """
    y = np.asarray(rotulos, dtype=int).reshape(-1)
    s = np.asarray(scores, dtype=float).reshape(-1)
    if y.size != s.size:
        raise ValueError("rótulos e scores têm tamanhos diferentes")
    if y.size == 0:
        raise ValueError("conjunto de avaliação vazio")

    previsto = (s >= limiar).astype(int)
    vp = int(np.sum((previsto == 1) & (y == 1)))
    vn = int(np.sum((previsto == 0) & (y == 0)))
    fp = int(np.sum((previsto == 1) & (y == 0)))
    fn = int(np.sum((previsto == 0) & (y == 1)))

    total = int(y.size)
    precisao = vp / (vp + fp) if (vp + fp) else 0.0
    revocacao = vp / (vp + fn) if (vp + fn) else 0.0
    f1 = 2 * precisao * revocacao / (precisao + revocacao) if (precisao + revocacao) else 0.0

    return Metricas(
        limiar=float(limiar),
        acuracia=(vp + vn) / total,
        precisao=precisao,
        revocacao=revocacao,
        f1=f1,
        especificidade=vn / (vn + fp) if (vn + fp) else 0.0,
        verdadeiros_positivos=vp,
        verdadeiros_negativos=vn,
        falsos_positivos=fp,
        falsos_negativos=fn,
        total=total,
    )


def varrer_limiares(
    rotulos, scores, limiares: list[float] | None = None
) -> list[dict]:
    """
    Métricas em vários limiares.

    Permite escolher o ponto de operação com conhecimento do custo de cada
    erro: em detecção precoce de espécie invasora, perder uma ocorrência
    (falso negativo) costuma custar mais que uma checagem extra (falso
    positivo), o que favorece limiares mais baixos.
    """
    limiares = limiares or [round(0.05 * i, 2) for i in range(1, 20)]
    return [calcular_metricas(rotulos, scores, limiar).como_dicionario() for limiar in limiares]


def area_sob_roc(rotulos, scores) -> float | None:
    """AUC-ROC via scikit-learn; `None` se houver apenas uma classe."""
    y = np.asarray(rotulos, dtype=int).reshape(-1)
    if len(np.unique(y)) < 2:
        return None
    from sklearn.metrics import roc_auc_score

    return round(float(roc_auc_score(y, np.asarray(scores, dtype=float).reshape(-1))), 4)


@dataclass
class ResultadoAvaliacao:
    metricas_principais: Metricas
    por_limiar: list[dict] = field(default_factory=list)
    auc_roc: float | None = None
    tempos_ms: list[float] = field(default_factory=list)
    erros: list[dict] = field(default_factory=list)
    distribuicao_scores: list[dict] = field(default_factory=list)
    imagens_por_classe: dict[str, int] = field(default_factory=dict)
    modelo: dict = field(default_factory=dict)

    def como_dicionario(self) -> dict:
        tempos = sorted(self.tempos_ms)
        return {
            "gerado_em": datetime.now().replace(microsecond=0).isoformat(),
            "modelo": self.modelo,
            "conjunto_teste": {
                "total": self.metricas_principais.total,
                "imagens_por_classe": self.imagens_por_classe,
            },
            "metricas": self.metricas_principais.como_dicionario(),
            "auc_roc": self.auc_roc,
            "por_limiar": self.por_limiar,
            "tempo_inferencia_ms": {
                "n": len(tempos),
                "media": round(sum(tempos) / len(tempos), 2) if tempos else None,
                "mediana": round(tempos[len(tempos) // 2], 2) if tempos else None,
                "minimo": round(tempos[0], 2) if tempos else None,
                "maximo": round(tempos[-1], 2) if tempos else None,
            },
            "distribuicao_scores": self.distribuicao_scores,
            "erros": self.erros,
            "observacoes": [
                "Scores são saídas de softmax e não probabilidades calibradas.",
                "As métricas valem para o conjunto de teste descrito acima; "
                "desempenho em campo pode diferir (iluminação, turbidez, distância).",
                "Nenhuma imagem do conjunto de teste foi usada em treino ou validação.",
            ],
        }


def avaliar(
    diretorio_teste: Path | str = Path("data/processed/test"),
    diretorio_modelos: Path | str = Path("models"),
    arquivo_saida: Path | str = Path("reports/metricas_modelo.json"),
    limiar: float | None = None,
    maximo_erros: int = 20,
) -> dict:
    """
    Roda o modelo publicado sobre o conjunto de teste e grava as métricas.

    Funciona com o backend ONNX (sem necessidade de PyTorch instalado).
    """
    diretorio_teste = Path(diretorio_teste)
    if not diretorio_teste.is_dir():
        raise FileNotFoundError(
            f"Conjunto de teste não encontrado em {diretorio_teste}. "
            "Execute `python scripts/preparar_dataset.py`."
        )

    caminho_cartao = Path(diretorio_modelos) / "model_card.json"
    if not caminho_cartao.is_file():
        raise FileNotFoundError(
            f"Nenhum modelo publicado em {diretorio_modelos} (model_card.json ausente). "
            "Treine o modelo antes de avaliar."
        )

    cartao = CartaoModelo.carregar(caminho_cartao)
    servico = ServicoInferencia(cartao=cartao, diretorio_modelos=Path(diretorio_modelos))
    if not servico.disponivel:
        raise FileNotFoundError(f"Modelo indisponível: {servico.descricao_estado}")

    preditor = servico._obter_preditor()  # backend já carregado e validado
    if preditor is None:  # pragma: no cover
        raise FileNotFoundError(f"Modelo indisponível: {servico.descricao_estado}")

    rotulos: list[int] = []
    scores: list[float] = []
    tempos: list[float] = []
    erros: list[dict] = []
    contagem: dict[str, int] = {}

    for indice_classe, nome_classe in enumerate(CLASSES):
        pasta = diretorio_teste / nome_classe
        arquivos = (
            sorted(
                arquivo
                for arquivo in pasta.iterdir()
                if arquivo.suffix.lower() in EXTENSOES_IMAGEM
            )
            if pasta.is_dir()
            else []
        )
        contagem[nome_classe] = len(arquivos)

        for arquivo in arquivos:
            try:
                entrada = preparar(arquivo.read_bytes(), cartao.entrada)
            except Exception as erro:  # imagem corrompida no conjunto de teste
                erros.append(
                    {"arquivo": arquivo.name, "tipo": "falha_preprocessamento", "erro": str(erro)}
                )
                continue

            inicio = time.perf_counter()
            saida = preditor(entrada.tensor)
            tempos.append((time.perf_counter() - inicio) * 1000.0)
            scores.append(servico._score_positivo(saida))
            rotulos.append(indice_classe)

    if not rotulos:
        raise ValueError(f"Nenhuma imagem avaliável em {diretorio_teste}")

    limiar_final = limiar if limiar is not None else servico.limiar_positivo
    metricas = calcular_metricas(rotulos, scores, limiar_final)

    # Exemplos de erro, dos mais confiantes para os menos — úteis no painel.
    classificados = [(r, s, i) for i, (r, s) in enumerate(zip(rotulos, scores))]
    for rotulo, score, _ in sorted(classificados, key=lambda t: -abs(t[1] - limiar_final)):
        previsto = int(score >= limiar_final)
        if previsto != rotulo and len(erros) < maximo_erros:
            erros.append(
                {
                    "tipo": "falso_positivo" if previsto == 1 else "falso_negativo",
                    "rotulo_real": CLASSES[rotulo],
                    "score": round(score, 4),
                }
            )

    resultado = ResultadoAvaliacao(
        metricas_principais=metricas,
        por_limiar=varrer_limiares(rotulos, scores),
        auc_roc=area_sob_roc(rotulos, scores),
        tempos_ms=tempos,
        erros=erros,
        distribuicao_scores=[
            {"classe": CLASSES[rotulo], "score": round(score, 4)}
            for rotulo, score in zip(rotulos, scores)
        ],
        imagens_por_classe=contagem,
        modelo={
            "nome": cartao.nome,
            "versao": cartao.versao,
            "arquitetura": cartao.arquitetura,
            "formato": cartao.formato,
            "entrada": cartao.entrada,
            "treinado_em": cartao.treinado_em,
        },
    )

    saida = Path(arquivo_saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    dados = resultado.como_dicionario()
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return dados
