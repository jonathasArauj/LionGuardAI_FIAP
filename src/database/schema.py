"""
Esquema relacional do LionGuard AI (SQLite / compatível com PostgreSQL).

O DDL é escrito em SQL explícito para evidenciar a modelagem relacional:
chaves primárias e estrangeiras, constraints de domínio (CHECK), índices de
consulta e unicidade onde o domínio exige.

Migração para PostgreSQL: as únicas adaptações necessárias são
`INTEGER PRIMARY KEY AUTOINCREMENT` -> `SERIAL`/`IDENTITY` e `TEXT` de datas ->
`TIMESTAMPTZ`. As consultas de `queries.py` usam SQL padrão.
"""

from __future__ import annotations

from enum import StrEnum

SCHEMA_VERSION = 1


class StatusOcorrencia(StrEnum):
    """Ciclo de vida de uma ocorrência."""

    PENDENTE = "PENDENTE"
    AGUARDANDO_INFO = "AGUARDANDO_INFO"
    CONFIRMADO = "CONFIRMADO"
    REJEITADO = "REJEITADO"
    INCONCLUSIVO = "INCONCLUSIVO"

    @classmethod
    def finais(cls) -> tuple[StatusOcorrencia, ...]:
        """Status que representam uma decisão final do avaliador."""
        return (cls.CONFIRMADO, cls.REJEITADO, cls.INCONCLUSIVO)


class TipoDado(StrEnum):
    """Procedência do dado — exigência da seção 11 do escopo."""

    REAL = "REAL"  # enviado por usuário da plataforma
    IMPORTADO = "IMPORTADO"  # importado de fonte documentada (GBIF, iNaturalist)
    DEMO = "DEMO"  # gerado para demonstração; nunca é dado oficial


class OrigemLocalizacao(StrEnum):
    GPS_DISPOSITIVO = "GPS_DISPOSITIVO"
    MAPA_MANUAL = "MAPA_MANUAL"
    REGIAO_APROXIMADA = "REGIAO_APROXIMADA"
    IMPORTADA = "IMPORTADA"


class OrigemRegistro(StrEnum):
    CIDADAO = "CIDADAO"
    PESCADOR = "PESCADOR"
    MERGULHADOR = "MERGULHADOR"
    PESQUISADOR = "PESQUISADOR"
    IMPORTACAO = "IMPORTACAO"
    DEMONSTRACAO = "DEMONSTRACAO"


class ClassePredicao(StrEnum):
    PEIXE_LEAO = "PEIXE_LEAO"
    NAO_PEIXE_LEAO = "NAO_PEIXE_LEAO"
    INCONCLUSIVO = "INCONCLUSIVO"
    SEM_MODELO = "SEM_MODELO"
    ERRO = "ERRO"


class Perfil(StrEnum):
    CIDADAO = "CIDADAO"
    PESQUISADOR = "PESQUISADOR"
    ADMINISTRADOR = "ADMINISTRADOR"


class Decisao(StrEnum):
    CONFIRMAR = "CONFIRMAR"
    REJEITAR = "REJEITAR"
    INCONCLUSIVO = "INCONCLUSIVO"
    SOLICITAR_INFO = "SOLICITAR_INFO"


class Habitat(StrEnum):
    RECIFE = "RECIFE"
    COSTAO_ROCHOSO = "COSTAO_ROCHOSO"
    AREA_ARENOSA = "AREA_ARENOSA"
    MANGUEZAL = "MANGUEZAL"
    OUTRO = "OUTRO"
    NAO_INFORMADO = "NAO_INFORMADO"


def _lista_sql(enum_cls) -> str:
    return ", ".join(f"'{membro.value}'" for membro in enum_cls)


DDL: tuple[str, ...] = (
    # ------------------------------------------------------------------ usuario
    f"""
    CREATE TABLE IF NOT EXISTS usuario (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        identificador   TEXT    NOT NULL UNIQUE,
        nome            TEXT,
        senha_hash      TEXT    NOT NULL,
        perfil          TEXT    NOT NULL CHECK (perfil IN ({_lista_sql(Perfil)})),
        ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em       TEXT    NOT NULL,
        ultimo_acesso   TEXT
    )
    """,
    # -------------------------------------------------------------- fonte_dados
    """
    CREATE TABLE IF NOT EXISTS fonte_dados (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nome            TEXT    NOT NULL,
        url             TEXT,
        data_importacao TEXT    NOT NULL,
        licenca         TEXT,
        tipo_fonte      TEXT    NOT NULL,
        observacoes     TEXT,
        UNIQUE (nome, data_importacao)
    )
    """,
    # --------------------------------------------------------------- ocorrencia
    f"""
    CREATE TABLE IF NOT EXISTS ocorrencia (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        protocolo               TEXT    NOT NULL UNIQUE,
        chave_idempotencia      TEXT    UNIQUE,
        data_hora_avistamento   TEXT    NOT NULL,
        data_hora_cadastro      TEXT    NOT NULL,
        estado                  TEXT,
        municipio               TEXT,
        latitude                REAL    CHECK (latitude IS NULL OR (latitude BETWEEN -90 AND 90)),
        longitude               REAL    CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180)),
        precisao_metros         REAL    CHECK (precisao_metros IS NULL OR precisao_metros >= 0),
        origem_localizacao      TEXT    NOT NULL
                                CHECK (origem_localizacao IN ({_lista_sql(OrigemLocalizacao)})),
        profundidade            REAL    CHECK (profundidade IS NULL OR profundidade >= 0),
        habitat                 TEXT    NOT NULL DEFAULT 'NAO_INFORMADO'
                                CHECK (habitat IN ({_lista_sql(Habitat)})),
        quantidade_observada    INTEGER CHECK (quantidade_observada IS NULL OR quantidade_observada > 0),
        descricao               TEXT,
        origem_registro         TEXT    NOT NULL
                                CHECK (origem_registro IN ({_lista_sql(OrigemRegistro)})),
        tipo_dado               TEXT    NOT NULL CHECK (tipo_dado IN ({_lista_sql(TipoDado)})),
        status                  TEXT    NOT NULL
                                CHECK (status IN ({_lista_sql(StatusOcorrencia)})),
        fonte_dados_id          INTEGER REFERENCES fonte_dados (id) ON DELETE SET NULL,
        autoriza_publicar_imagem INTEGER NOT NULL DEFAULT 0
                                CHECK (autoriza_publicar_imagem IN (0, 1)),
        contato_hash            TEXT,
        data_primeira_decisao   TEXT
    )
    """,
    # ------------------------------------------------------------------ imagem
    """
    CREATE TABLE IF NOT EXISTS imagem (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        ocorrencia_id           INTEGER NOT NULL
                                REFERENCES ocorrencia (id) ON DELETE CASCADE,
        identificador_arquivo   TEXT    NOT NULL UNIQUE,
        nome_original_sanitizado TEXT,
        hash_sha256             TEXT    NOT NULL,
        formato                 TEXT    NOT NULL,
        largura                 INTEGER,
        altura                  INTEGER,
        tamanho_bytes           INTEGER NOT NULL CHECK (tamanho_bytes > 0),
        exif_removido           INTEGER NOT NULL DEFAULT 1 CHECK (exif_removido IN (0, 1)),
        fonte                   TEXT,
        licenca                 TEXT,
        criado_em               TEXT    NOT NULL
    )
    """,
    # ---------------------------------------------------------------- predicao
    f"""
    CREATE TABLE IF NOT EXISTS predicao (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        ocorrencia_id       INTEGER NOT NULL
                            REFERENCES ocorrencia (id) ON DELETE CASCADE,
        imagem_id           INTEGER REFERENCES imagem (id) ON DELETE SET NULL,
        modelo              TEXT    NOT NULL,
        versao              TEXT    NOT NULL,
        classe              TEXT    NOT NULL CHECK (classe IN ({_lista_sql(ClassePredicao)})),
        score               REAL    CHECK (score IS NULL OR (score BETWEEN 0 AND 1)),
        tempo_inferencia_ms REAL    CHECK (tempo_inferencia_ms IS NULL OR tempo_inferencia_ms >= 0),
        detalhes            TEXT,
        criado_em           TEXT    NOT NULL
    )
    """,
    # --------------------------------------------------------------- validacao
    f"""
    CREATE TABLE IF NOT EXISTS validacao (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ocorrencia_id   INTEGER NOT NULL
                        REFERENCES ocorrencia (id) ON DELETE CASCADE,
        avaliador_id    INTEGER NOT NULL REFERENCES usuario (id) ON DELETE RESTRICT,
        decisao         TEXT    NOT NULL CHECK (decisao IN ({_lista_sql(Decisao)})),
        justificativa   TEXT    NOT NULL,
        status_anterior TEXT    NOT NULL,
        status_novo     TEXT    NOT NULL,
        data_validacao  TEXT    NOT NULL
    )
    """,
    # ----------------------------------------------------------- log_auditoria
    """
    CREATE TABLE IF NOT EXISTS log_auditoria (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER REFERENCES usuario (id) ON DELETE SET NULL,
        entidade    TEXT    NOT NULL,
        entidade_id TEXT,
        acao        TEXT    NOT NULL,
        data_hora   TEXT    NOT NULL,
        detalhes    TEXT
    )
    """,
    # ------------------------------------------------------- evento_requisicao
    # Suporte à limitação de requisições (seção 10 — proteção contra abuso).
    """
    CREATE TABLE IF NOT EXISTS evento_requisicao (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chave       TEXT    NOT NULL,
        acao        TEXT    NOT NULL,
        data_hora   TEXT    NOT NULL
    )
    """,
)


INDICES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_status ON ocorrencia (status)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_estado ON ocorrencia (estado)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_municipio ON ocorrencia (municipio)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_tipo_dado ON ocorrencia (tipo_dado)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_avistamento ON ocorrencia (data_hora_avistamento)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_cadastro ON ocorrencia (data_hora_cadastro)",
    "CREATE INDEX IF NOT EXISTS idx_ocorrencia_geo ON ocorrencia (latitude, longitude)",
    "CREATE INDEX IF NOT EXISTS idx_imagem_ocorrencia ON imagem (ocorrencia_id)",
    "CREATE INDEX IF NOT EXISTS idx_imagem_hash ON imagem (hash_sha256)",
    "CREATE INDEX IF NOT EXISTS idx_predicao_ocorrencia ON predicao (ocorrencia_id)",
    "CREATE INDEX IF NOT EXISTS idx_predicao_versao ON predicao (versao)",
    "CREATE INDEX IF NOT EXISTS idx_validacao_ocorrencia ON validacao (ocorrencia_id)",
    "CREATE INDEX IF NOT EXISTS idx_validacao_data ON validacao (data_validacao)",
    "CREATE INDEX IF NOT EXISTS idx_auditoria_entidade ON log_auditoria (entidade, entidade_id)",
    "CREATE INDEX IF NOT EXISTS idx_evento_chave ON evento_requisicao (chave, acao, data_hora)",
)
