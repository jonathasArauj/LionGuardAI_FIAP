"""
Modelos de domínio.

São `dataclasses` simples que representam as linhas das tabelas. A persistência
fica nos repositórios (`repositories.py`), mantendo o domínio independente de
qualquer framework — o que permite testar regra de negócio sem banco real.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from src.database.schema import (
    ClassePredicao,
    Decisao,
    Habitat,
    OrigemLocalizacao,
    OrigemRegistro,
    Perfil,
    StatusOcorrencia,
    TipoDado,
)


def agora_iso() -> str:
    """Instante atual em ISO-8601, segundos de precisão (padrão de gravação)."""
    return datetime.now().replace(microsecond=0).isoformat()


def _para_datetime(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


@dataclass(slots=True)
class Usuario:
    identificador: str
    senha_hash: str
    perfil: Perfil
    id: int | None = None
    nome: str | None = None
    ativo: bool = True
    criado_em: str = field(default_factory=agora_iso)
    ultimo_acesso: str | None = None

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> Usuario:
        return cls(
            id=linha["id"],
            identificador=linha["identificador"],
            nome=linha["nome"],
            senha_hash=linha["senha_hash"],
            perfil=Perfil(linha["perfil"]),
            ativo=bool(linha["ativo"]),
            criado_em=linha["criado_em"],
            ultimo_acesso=linha["ultimo_acesso"],
        )


@dataclass(slots=True)
class Ocorrencia:
    """Um avistamento registrado na plataforma."""

    protocolo: str
    data_hora_avistamento: str
    origem_localizacao: OrigemLocalizacao
    origem_registro: OrigemRegistro
    tipo_dado: TipoDado
    status: StatusOcorrencia = StatusOcorrencia.PENDENTE
    id: int | None = None
    chave_idempotencia: str | None = None
    data_hora_cadastro: str = field(default_factory=agora_iso)
    estado: str | None = None
    municipio: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    precisao_metros: float | None = None
    profundidade: float | None = None
    habitat: Habitat = Habitat.NAO_INFORMADO
    quantidade_observada: int | None = None
    descricao: str | None = None
    fonte_dados_id: int | None = None
    autoriza_publicar_imagem: bool = False
    contato_hash: str | None = None
    data_primeira_decisao: str | None = None

    # ------------------------------------------------------------------ regras
    @property
    def tem_coordenadas(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def localizacao_precisa(self) -> bool:
        """Coordenada vinda de GPS ou de ponto marcado no mapa pelo usuário."""
        return self.tem_coordenadas and self.origem_localizacao in (
            OrigemLocalizacao.GPS_DISPOSITIVO,
            OrigemLocalizacao.MAPA_MANUAL,
        )

    @property
    def e_demonstracao(self) -> bool:
        return self.tipo_dado == TipoDado.DEMO

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> Ocorrencia:
        return cls(
            id=linha["id"],
            protocolo=linha["protocolo"],
            chave_idempotencia=linha["chave_idempotencia"],
            data_hora_avistamento=linha["data_hora_avistamento"],
            data_hora_cadastro=linha["data_hora_cadastro"],
            estado=linha["estado"],
            municipio=linha["municipio"],
            latitude=linha["latitude"],
            longitude=linha["longitude"],
            precisao_metros=linha["precisao_metros"],
            origem_localizacao=OrigemLocalizacao(linha["origem_localizacao"]),
            profundidade=linha["profundidade"],
            habitat=Habitat(linha["habitat"]),
            quantidade_observada=linha["quantidade_observada"],
            descricao=linha["descricao"],
            origem_registro=OrigemRegistro(linha["origem_registro"]),
            tipo_dado=TipoDado(linha["tipo_dado"]),
            status=StatusOcorrencia(linha["status"]),
            fonte_dados_id=linha["fonte_dados_id"],
            autoriza_publicar_imagem=bool(linha["autoriza_publicar_imagem"]),
            contato_hash=linha["contato_hash"],
            data_primeira_decisao=linha["data_primeira_decisao"],
        )


@dataclass(slots=True)
class Imagem:
    ocorrencia_id: int
    identificador_arquivo: str
    hash_sha256: str
    formato: str
    tamanho_bytes: int
    id: int | None = None
    nome_original_sanitizado: str | None = None
    largura: int | None = None
    altura: int | None = None
    exif_removido: bool = True
    fonte: str | None = None
    licenca: str | None = None
    criado_em: str = field(default_factory=agora_iso)

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> Imagem:
        return cls(
            id=linha["id"],
            ocorrencia_id=linha["ocorrencia_id"],
            identificador_arquivo=linha["identificador_arquivo"],
            nome_original_sanitizado=linha["nome_original_sanitizado"],
            hash_sha256=linha["hash_sha256"],
            formato=linha["formato"],
            largura=linha["largura"],
            altura=linha["altura"],
            tamanho_bytes=linha["tamanho_bytes"],
            exif_removido=bool(linha["exif_removido"]),
            fonte=linha["fonte"],
            licenca=linha["licenca"],
            criado_em=linha["criado_em"],
        )


@dataclass(slots=True)
class Predicao:
    ocorrencia_id: int
    modelo: str
    versao: str
    classe: ClassePredicao
    id: int | None = None
    imagem_id: int | None = None
    score: float | None = None
    tempo_inferencia_ms: float | None = None
    detalhes: str | None = None
    criado_em: str = field(default_factory=agora_iso)

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> Predicao:
        return cls(
            id=linha["id"],
            ocorrencia_id=linha["ocorrencia_id"],
            imagem_id=linha["imagem_id"],
            modelo=linha["modelo"],
            versao=linha["versao"],
            classe=ClassePredicao(linha["classe"]),
            score=linha["score"],
            tempo_inferencia_ms=linha["tempo_inferencia_ms"],
            detalhes=linha["detalhes"],
            criado_em=linha["criado_em"],
        )


@dataclass(slots=True)
class Validacao:
    ocorrencia_id: int
    avaliador_id: int
    decisao: Decisao
    justificativa: str
    status_anterior: StatusOcorrencia
    status_novo: StatusOcorrencia
    id: int | None = None
    data_validacao: str = field(default_factory=agora_iso)

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> Validacao:
        return cls(
            id=linha["id"],
            ocorrencia_id=linha["ocorrencia_id"],
            avaliador_id=linha["avaliador_id"],
            decisao=Decisao(linha["decisao"]),
            justificativa=linha["justificativa"],
            status_anterior=StatusOcorrencia(linha["status_anterior"]),
            status_novo=StatusOcorrencia(linha["status_novo"]),
            data_validacao=linha["data_validacao"],
        )


@dataclass(slots=True)
class FonteDados:
    nome: str
    tipo_fonte: str
    id: int | None = None
    url: str | None = None
    data_importacao: str = field(default_factory=agora_iso)
    licenca: str | None = None
    observacoes: str | None = None

    @classmethod
    def de_linha(cls, linha: sqlite3.Row) -> FonteDados:
        return cls(
            id=linha["id"],
            nome=linha["nome"],
            url=linha["url"],
            data_importacao=linha["data_importacao"],
            licenca=linha["licenca"],
            tipo_fonte=linha["tipo_fonte"],
            observacoes=linha["observacoes"],
        )


@dataclass(slots=True)
class LogAuditoria:
    entidade: str
    acao: str
    id: int | None = None
    usuario_id: int | None = None
    entidade_id: str | None = None
    data_hora: str = field(default_factory=agora_iso)
    detalhes: str | None = None


__all__ = [
    "Usuario",
    "Ocorrencia",
    "Imagem",
    "Predicao",
    "Validacao",
    "FonteDados",
    "LogAuditoria",
    "agora_iso",
]
