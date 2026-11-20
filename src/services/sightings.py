"""
Serviço de registro de avistamentos — fluxo central da plataforma.

Garantias implementadas:
  * **atomicidade**: ocorrência, imagem e predição são gravadas na mesma
    transação; se qualquer passo falhar, nada é persistido;
  * **idempotência**: um duplo clique (ou um recarregamento da página) reenvia
    a mesma chave de idempotência e devolve o registro já criado em vez de
    duplicá-lo;
  * **sucesso verificado**: o serviço relê a ocorrência pelo protocolo depois
    do commit e só então declara sucesso (seção 4.6 do escopo);
  * **status inicial sempre PENDENTE**, independentemente do score da IA.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.ai.inference import ResultadoInferencia
from src.database.connection import transacao
from src.database.models import Imagem, Ocorrencia, Predicao, agora_iso
from src.database.repositories import (
    AuditoriaRepository,
    ImagemRepository,
    OcorrenciaRepository,
    PredicaoRepository,
    RegistroDuplicado,
)
from src.database.schema import (
    Habitat,
    OrigemLocalizacao,
    OrigemRegistro,
    StatusOcorrencia,
    TipoDado,
)
from src.security.sanitize import hash_contato, limpar_texto
from src.services.geolocation import Localizacao
from src.services.image_storage import ArmazenamentoImagens
from src.security.uploads import ImagemValidada

# Alfabeto sem caracteres ambíguos (0/O, 1/I), para protocolos ditos por voz.
_ALFABETO_PROTOCOLO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_TENTATIVAS_PROTOCOLO = 12


class ErroRegistro(Exception):
    """Falha ao registrar o avistamento."""


@dataclass(slots=True)
class DadosAvistamento:
    """Entrada do registro, já validada pelas camadas anteriores."""

    localizacao: Localizacao
    data_hora_avistamento: str
    origem_registro: OrigemRegistro = OrigemRegistro.CIDADAO
    tipo_dado: TipoDado = TipoDado.REAL
    imagem: ImagemValidada | None = None
    nome_arquivo_original: str | None = None
    inferencia: ResultadoInferencia | None = None
    profundidade: float | None = None
    habitat: Habitat = Habitat.NAO_INFORMADO
    quantidade_observada: int | None = None
    descricao: str | None = None
    autoriza_publicar_imagem: bool = False
    contato: str | None = None
    chave_idempotencia: str | None = None
    fonte_dados_id: int | None = None


@dataclass(slots=True)
class ResultadoRegistro:
    """Saída do registro — o que a interface precisa para dar o retorno."""

    sucesso: bool
    protocolo: str | None = None
    ocorrencia_id: int | None = None
    duplicado: bool = False
    status: StatusOcorrencia | None = None
    mensagem: str = ""
    avisos: list[str] = field(default_factory=list)


class ServicoAvistamentos:
    def __init__(
        self,
        caminho_banco: str | Path | None = None,
        armazenamento: ArmazenamentoImagens | None = None,
    ) -> None:
        self.caminho = caminho_banco
        self.ocorrencias = OcorrenciaRepository(caminho_banco)
        self.imagens = ImagemRepository(caminho_banco)
        self.predicoes = PredicaoRepository(caminho_banco)
        self.auditoria = AuditoriaRepository(caminho_banco)
        self.armazenamento = armazenamento or ArmazenamentoImagens()

    # ----------------------------------------------------------- protocolo
    def gerar_protocolo(self, referencia: datetime | None = None) -> str:
        """
        Protocolo público no formato `LG-AAAA-XXXXXX`.

        Usa gerador criptográfico e confere a unicidade no banco; se houver
        colisão, tenta novamente.
        """
        ano = (referencia or datetime.now()).year
        for _ in range(_TENTATIVAS_PROTOCOLO):
            sufixo = "".join(secrets.choice(_ALFABETO_PROTOCOLO) for _ in range(6))
            protocolo = f"LG-{ano}-{sufixo}"
            if not self.ocorrencias.protocolo_existe(protocolo):
                return protocolo
        raise ErroRegistro(
            "não foi possível gerar um protocolo único; tente novamente"
        )  # pragma: no cover

    @staticmethod
    def calcular_chave_idempotencia(
        hash_imagem: str | None,
        data_hora_avistamento: str,
        latitude: float | None,
        longitude: float | None,
        sessao: str,
    ) -> str:
        """
        Chave estável para o mesmo envio.

        Deriva de conteúdo da foto + data/hora + ponto + identificador de
        sessão do navegador. Dois cliques no mesmo botão produzem a mesma
        chave; dois avistamentos realmente diferentes produzem chaves
        diferentes.
        """
        bruto = "|".join(
            [
                hash_imagem or "sem-imagem",
                data_hora_avistamento or "",
                f"{latitude:.5f}" if latitude is not None else "",
                f"{longitude:.5f}" if longitude is not None else "",
                sessao or "",
            ]
        )
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------- registro
    def registrar(self, dados: DadosAvistamento) -> ResultadoRegistro:
        """Grava o avistamento. Nunca marca como confirmado automaticamente."""
        avisos: list[str] = []

        # 1. Idempotência — devolve o registro existente sem criar outro.
        if dados.chave_idempotencia:
            existente = self.ocorrencias.por_chave_idempotencia(dados.chave_idempotencia)
            if existente:
                return ResultadoRegistro(
                    sucesso=True,
                    protocolo=existente.protocolo,
                    ocorrencia_id=existente.id,
                    duplicado=True,
                    status=existente.status,
                    mensagem=(
                        "Este avistamento já havia sido registrado. "
                        f"Protocolo {existente.protocolo}."
                    ),
                )

        # 2. Validações de domínio antes de tocar o banco.
        if not dados.localizacao or not dados.localizacao.tem_coordenadas:
            raise ErroRegistro(
                "É necessário informar a localização do avistamento "
                "(GPS, ponto no mapa ou região)."
            )
        if not dados.data_hora_avistamento:
            raise ErroRegistro("A data do avistamento é obrigatória.")
        if dados.quantidade_observada is not None and dados.quantidade_observada <= 0:
            raise ErroRegistro("A quantidade observada deve ser maior que zero.")
        if dados.profundidade is not None and dados.profundidade < 0:
            raise ErroRegistro("A profundidade não pode ser negativa.")
        try:
            if datetime.fromisoformat(dados.data_hora_avistamento) > datetime.now():
                raise ErroRegistro("A data do avistamento não pode estar no futuro.")
        except ValueError as erro:
            raise ErroRegistro("Data do avistamento em formato inválido.") from erro

        # 3. Imagem: grava o arquivo antes da transação (I/O fora do lock) e
        #    remove o arquivo caso a transação falhe.
        arquivo = None
        if dados.imagem is not None:
            arquivo = self.armazenamento.salvar(dados.imagem, dados.nome_arquivo_original)
            avisos.extend(dados.imagem.avisos)
            iguais = self.imagens.por_hash(arquivo.hash_sha256)
            if iguais:
                avisos.append(
                    "Esta mesma foto já consta em outro registro — "
                    "a equipe de validação será notificada para conferência."
                )

        protocolo = self.gerar_protocolo()
        ocorrencia = Ocorrencia(
            protocolo=protocolo,
            chave_idempotencia=dados.chave_idempotencia,
            data_hora_avistamento=dados.data_hora_avistamento,
            data_hora_cadastro=agora_iso(),
            estado=dados.localizacao.estado,
            municipio=dados.localizacao.municipio,
            latitude=dados.localizacao.latitude,
            longitude=dados.localizacao.longitude,
            precisao_metros=dados.localizacao.precisao_metros,
            origem_localizacao=dados.localizacao.origem,
            profundidade=dados.profundidade,
            habitat=dados.habitat,
            quantidade_observada=dados.quantidade_observada,
            descricao=limpar_texto(dados.descricao),
            origem_registro=dados.origem_registro,
            tipo_dado=dados.tipo_dado,
            status=StatusOcorrencia.PENDENTE,  # sempre pendente de validação
            fonte_dados_id=dados.fonte_dados_id,
            autoriza_publicar_imagem=dados.autoriza_publicar_imagem,
            contato_hash=hash_contato(dados.contato),
        )

        try:
            # Transação única: ocorrência + imagem + predição + auditoria.
            with transacao(self.caminho):
                self.ocorrencias.criar(ocorrencia)

                imagem_id = None
                if arquivo is not None:
                    registro_imagem = self.imagens.criar(
                        Imagem(
                            ocorrencia_id=ocorrencia.id,
                            identificador_arquivo=arquivo.identificador_arquivo,
                            nome_original_sanitizado=arquivo.nome_original_sanitizado,
                            hash_sha256=arquivo.hash_sha256,
                            formato=arquivo.formato,
                            largura=arquivo.largura,
                            altura=arquivo.altura,
                            tamanho_bytes=arquivo.tamanho_bytes,
                            exif_removido=bool(
                                dados.imagem.exif_removido if dados.imagem else True
                            ),
                        )
                    )
                    imagem_id = registro_imagem.id

                if dados.inferencia is not None:
                    self.predicoes.criar(
                        Predicao(
                            ocorrencia_id=ocorrencia.id,
                            imagem_id=imagem_id,
                            modelo=dados.inferencia.modelo,
                            versao=dados.inferencia.versao,
                            classe=dados.inferencia.classe,
                            score=dados.inferencia.score,
                            tempo_inferencia_ms=dados.inferencia.tempo_inferencia_ms,
                            detalhes=dados.inferencia.detalhes_json(),
                        )
                    )

                self.auditoria.registrar(
                    entidade="ocorrencia",
                    acao="CADASTRO",
                    entidade_id=protocolo,
                    detalhes={
                        "origem_localizacao": str(dados.localizacao.origem),
                        "origem_registro": str(dados.origem_registro),
                        "tipo_dado": str(dados.tipo_dado),
                        "tem_imagem": arquivo is not None,
                        "classe_ia": str(dados.inferencia.classe)
                        if dados.inferencia
                        else None,
                    },
                )
        except RegistroDuplicado:
            # Corrida entre dois envios simultâneos com a mesma chave.
            if arquivo is not None:
                self.armazenamento.remover(arquivo.identificador_arquivo)
            if dados.chave_idempotencia:
                existente = self.ocorrencias.por_chave_idempotencia(dados.chave_idempotencia)
                if existente:
                    return ResultadoRegistro(
                        sucesso=True,
                        protocolo=existente.protocolo,
                        ocorrencia_id=existente.id,
                        duplicado=True,
                        status=existente.status,
                        mensagem=f"Avistamento já registrado. Protocolo {existente.protocolo}.",
                    )
            raise ErroRegistro("Não foi possível gravar o avistamento (registro duplicado).")
        except Exception as erro:
            if arquivo is not None:
                self.armazenamento.remover(arquivo.identificador_arquivo)
            raise ErroRegistro(f"Falha ao gravar o avistamento: {erro}") from erro

        # 4. Confirmação de gravação: relê do banco antes de declarar sucesso.
        gravada = self.ocorrencias.por_protocolo(protocolo)
        if gravada is None:  # pragma: no cover - indicaria falha grave de I/O
            if arquivo is not None:
                self.armazenamento.remover(arquivo.identificador_arquivo)
            raise ErroRegistro(
                "O avistamento não pôde ser confirmado no banco de dados. Tente novamente."
            )

        return ResultadoRegistro(
            sucesso=True,
            protocolo=gravada.protocolo,
            ocorrencia_id=gravada.id,
            duplicado=False,
            status=gravada.status,
            mensagem=f"Avistamento registrado com sucesso! Protocolo {gravada.protocolo}.",
            avisos=avisos,
        )

    # -------------------------------------------------------------- consultas
    def consultar_por_protocolo(self, protocolo: str) -> dict | None:
        """Dados públicos de acompanhamento de um protocolo."""
        ocorrencia = self.ocorrencias.por_protocolo(protocolo or "")
        if ocorrencia is None:
            return None
        predicao = self.predicoes.ultima_por_ocorrencia(ocorrencia.id)
        imagem = self.imagens.primeira_por_ocorrencia(ocorrencia.id)
        return {
            "protocolo": ocorrencia.protocolo,
            "status": ocorrencia.status,
            "data_hora_avistamento": ocorrencia.data_hora_avistamento,
            "data_hora_cadastro": ocorrencia.data_hora_cadastro,
            "municipio": ocorrencia.municipio,
            "estado": ocorrencia.estado,
            "origem_localizacao": ocorrencia.origem_localizacao,
            "tipo_dado": ocorrencia.tipo_dado,
            "classe_ia": predicao.classe if predicao else None,
            "score_ia": predicao.score if predicao else None,
            "tem_imagem": imagem is not None,
            "arquivo_imagem": imagem.identificador_arquivo if imagem else None,
            "autoriza_publicar_imagem": ocorrencia.autoriza_publicar_imagem,
        }
