"""
Testes da camada de banco de dados.

Cobertura: criação do esquema, inserções, consultas, integridade referencial,
constraints de domínio, unicidade, transações com rollback, atualização de
status e persistência após fechar as conexões.
"""

from __future__ import annotations

import sqlite3

import pytest

from src.database.connection import (
    consultar,
    consultar_escalar,
    fechar_conexoes,
    inicializar_banco,
    transacao,
)
from src.database.models import (
    FonteDados,
    Imagem,
    Ocorrencia,
    Predicao,
    Usuario,
    Validacao,
    agora_iso,
)
from src.database.repositories import (
    AuditoriaRepository,
    FonteDadosRepository,
    ImagemRepository,
    OcorrenciaRepository,
    PredicaoRepository,
    RegistroDuplicado,
    UsuarioRepository,
    ValidacaoRepository,
)
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

TABELAS_ESPERADAS = {
    "usuario",
    "ocorrencia",
    "imagem",
    "predicao",
    "validacao",
    "log_auditoria",
    "fonte_dados",
    "evento_requisicao",
}


def _ocorrencia(protocolo: str = "LG-2026-TST001", **extras) -> Ocorrencia:
    padrao = {
        "protocolo": protocolo,
        "data_hora_avistamento": "2026-11-10T09:30:00",
        "origem_localizacao": OrigemLocalizacao.GPS_DISPOSITIVO,
        "origem_registro": OrigemRegistro.CIDADAO,
        "tipo_dado": TipoDado.REAL,
        "estado": "ES",
        "municipio": "Guarapari",
        "latitude": -20.67,
        "longitude": -40.49,
        "precisao_metros": 12.0,
        "habitat": Habitat.RECIFE,
    }
    padrao.update(extras)
    return Ocorrencia(**padrao)


# ----------------------------------------------------------------- esquema
def test_esquema_cria_todas_as_tabelas(ambiente):
    nomes = {
        linha["name"]
        for linha in consultar(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert TABELAS_ESPERADAS.issubset(nomes)


def test_esquema_cria_indices(ambiente):
    quantidade = consultar_escalar(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    assert quantidade >= 14


def test_inicializar_banco_e_idempotente(ambiente):
    OcorrenciaRepository().criar(_ocorrencia())
    inicializar_banco()  # segunda chamada não deve apagar nada
    inicializar_banco()
    assert OcorrenciaRepository().contar() == 1


def test_chaves_estrangeiras_estao_ativas(ambiente):
    assert consultar_escalar("PRAGMA foreign_keys") == 1


# --------------------------------------------------------------- inserções
def test_insere_e_recupera_ocorrencia(ambiente):
    repositorio = OcorrenciaRepository()
    criada = repositorio.criar(_ocorrencia())

    assert criada.id is not None
    recuperada = repositorio.por_protocolo("LG-2026-TST001")
    assert recuperada is not None
    assert recuperada.municipio == "Guarapari"
    assert recuperada.status == StatusOcorrencia.PENDENTE
    assert recuperada.localizacao_precisa is True


def test_protocolo_e_unico(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia())
    with pytest.raises(RegistroDuplicado):
        repositorio.criar(_ocorrencia())


def test_chave_idempotencia_e_unica(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-AAA111", chave_idempotencia="k"))
    with pytest.raises(RegistroDuplicado):
        repositorio.criar(_ocorrencia("LG-2026-BBB222", chave_idempotencia="k"))


def test_usuario_duplicado_e_recusado(ambiente):
    repositorio = UsuarioRepository()
    repositorio.criar(Usuario(identificador="ana", senha_hash="x", perfil=Perfil.PESQUISADOR))
    with pytest.raises(RegistroDuplicado):
        repositorio.criar(
            Usuario(identificador="ANA", senha_hash="y", perfil=Perfil.ADMINISTRADOR)
        )


# -------------------------------------------------------------- constraints
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("latitude", 120.0),
        ("longitude", -500.0),
        ("profundidade", -3.0),
        ("quantidade_observada", 0),
        ("precisao_metros", -1.0),
    ],
)
def test_constraints_de_dominio_recusam_valores_invalidos(ambiente, campo, valor):
    with pytest.raises(sqlite3.IntegrityError):
        with transacao() as conexao:
            conexao.execute(
                f"""
                INSERT INTO ocorrencia (
                    protocolo, data_hora_avistamento, data_hora_cadastro,
                    origem_localizacao, origem_registro, tipo_dado, status, habitat,
                    {campo}
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "LG-2026-INVLD",
                    "2026-11-10T09:30:00",
                    agora_iso(),
                    "GPS_DISPOSITIVO",
                    "CIDADAO",
                    "REAL",
                    "PENDENTE",
                    "RECIFE",
                    valor,
                ),
            )


def test_status_fora_do_dominio_e_recusado(ambiente):
    with pytest.raises(sqlite3.IntegrityError):
        with transacao() as conexao:
            conexao.execute(
                """
                INSERT INTO ocorrencia (
                    protocolo, data_hora_avistamento, data_hora_cadastro,
                    origem_localizacao, origem_registro, tipo_dado, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "LG-2026-STATUS",
                    "2026-11-10T09:30:00",
                    agora_iso(),
                    "GPS_DISPOSITIVO",
                    "CIDADAO",
                    "REAL",
                    "INVENTADO",
                ),
            )


def test_imagem_exige_ocorrencia_existente(ambiente):
    with pytest.raises(sqlite3.IntegrityError):
        ImagemRepository().criar(
            Imagem(
                ocorrencia_id=9999,
                identificador_arquivo="x.jpg",
                hash_sha256="a" * 64,
                formato="jpeg",
                tamanho_bytes=100,
            )
        )


def test_exclusao_em_cascata_remove_dependentes(ambiente):
    ocorrencia = OcorrenciaRepository().criar(_ocorrencia(tipo_dado=TipoDado.DEMO))
    ImagemRepository().criar(
        Imagem(
            ocorrencia_id=ocorrencia.id,
            identificador_arquivo="y.jpg",
            hash_sha256="b" * 64,
            formato="jpeg",
            tamanho_bytes=200,
        )
    )
    PredicaoRepository().criar(
        Predicao(
            ocorrencia_id=ocorrencia.id,
            modelo="m",
            versao="1",
            classe=ClassePredicao.PEIXE_LEAO,
            score=0.9,
        )
    )

    removidos = OcorrenciaRepository().remover_demonstracao()

    assert removidos == 1
    assert consultar_escalar("SELECT COUNT(*) FROM imagem") == 0
    assert consultar_escalar("SELECT COUNT(*) FROM predicao") == 0


# -------------------------------------------------------------- transações
def test_transacao_faz_rollback_em_erro(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-OK0001"))

    with pytest.raises(RuntimeError):
        with transacao():
            repositorio.criar(_ocorrencia("LG-2026-OK0002"))
            raise RuntimeError("falha simulada no meio da transação")

    assert repositorio.contar() == 1
    assert repositorio.por_protocolo("LG-2026-OK0002") is None


def test_transacao_aninhada_confirma_tudo_junto(ambiente):
    repositorio = OcorrenciaRepository()
    with transacao():
        ocorrencia = repositorio.criar(_ocorrencia("LG-2026-NEST01"))
        ImagemRepository().criar(
            Imagem(
                ocorrencia_id=ocorrencia.id,
                identificador_arquivo="z.jpg",
                hash_sha256="c" * 64,
                formato="jpeg",
                tamanho_bytes=300,
            )
        )
    assert repositorio.contar() == 1
    assert consultar_escalar("SELECT COUNT(*) FROM imagem") == 1


# ----------------------------------------------------------------- consultas
def test_listar_aplica_filtros_compostos(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-F00001", estado="ES"))
    repositorio.criar(_ocorrencia("LG-2026-F00002", estado="BA", municipio="Ilhéus"))
    repositorio.criar(
        _ocorrencia("LG-2026-F00003", estado="ES", status=StatusOcorrencia.CONFIRMADO)
    )

    assert len(repositorio.listar(estados=["ES"])) == 2
    assert len(repositorio.listar(status=["CONFIRMADO"])) == 1
    assert len(repositorio.listar(estados=["ES"], status=["PENDENTE"])) == 1
    assert len(repositorio.listar(municipios=["Ilhéus"])) == 1
    assert len(repositorio.listar(limite=2)) == 2


def test_listar_filtra_por_periodo(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-D00001", data_hora_avistamento="2026-01-15T10:00:00"))
    repositorio.criar(_ocorrencia("LG-2026-D00002", data_hora_avistamento="2026-11-15T10:00:00"))

    assert len(repositorio.listar(data_inicio="2026-06-01")) == 1
    assert len(repositorio.listar(data_fim="2026-06-01")) == 1
    assert len(repositorio.listar(data_inicio="2026-01-01", data_fim="2026-12-31")) == 2


def test_ordenacao_invalida_cai_no_padrao(ambiente):
    """Proteção contra injeção pela cláusula ORDER BY."""
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-ORD001"))
    resultado = repositorio.listar(ordem="protocolo; DROP TABLE ocorrencia")
    assert len(resultado) == 1
    assert consultar_escalar("SELECT COUNT(*) FROM ocorrencia") == 1


def test_possiveis_duplicatas_detecta_pares_proximos(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(
        _ocorrencia("LG-2026-DUP001", latitude=-20.670, longitude=-40.490,
                    data_hora_avistamento="2026-11-10T09:00:00")
    )
    repositorio.criar(
        _ocorrencia("LG-2026-DUP002", latitude=-20.672, longitude=-40.491,
                    data_hora_avistamento="2026-11-10T15:00:00")
    )
    repositorio.criar(
        _ocorrencia("LG-2026-DUP003", latitude=-12.970, longitude=-38.500,
                    data_hora_avistamento="2026-11-10T09:00:00", estado="BA",
                    municipio="Salvador")
    )

    pares = repositorio.possiveis_duplicatas()
    assert ("LG-2026-DUP001", "LG-2026-DUP002") in pares
    assert all("LG-2026-DUP003" not in par for par in pares)


# ------------------------------------------------------- atualização de status
def test_atualizar_status_grava_primeira_decisao(ambiente):
    repositorio = OcorrenciaRepository()
    ocorrencia = repositorio.criar(_ocorrencia())
    assert ocorrencia.data_primeira_decisao is None

    repositorio.atualizar_status(ocorrencia.id, StatusOcorrencia.CONFIRMADO)
    primeira = repositorio.por_id(ocorrencia.id)
    assert primeira.status == StatusOcorrencia.CONFIRMADO
    assert primeira.data_primeira_decisao is not None

    repositorio.atualizar_status(ocorrencia.id, StatusOcorrencia.REJEITADO)
    segunda = repositorio.por_id(ocorrencia.id)
    assert segunda.status == StatusOcorrencia.REJEITADO
    # a data da primeira decisão não é sobrescrita
    assert segunda.data_primeira_decisao == primeira.data_primeira_decisao


def test_status_pendente_nao_marca_data_de_decisao(ambiente):
    repositorio = OcorrenciaRepository()
    ocorrencia = repositorio.criar(_ocorrencia(status=StatusOcorrencia.CONFIRMADO))
    repositorio.atualizar_status(ocorrencia.id, StatusOcorrencia.AGUARDANDO_INFO)
    assert repositorio.por_id(ocorrencia.id).data_primeira_decisao is None


# ----------------------------------------------------------- outras entidades
def test_historico_de_validacao_e_preservado(ambiente):
    ocorrencia = OcorrenciaRepository().criar(_ocorrencia())
    usuario = UsuarioRepository().criar(
        Usuario(identificador="rev", senha_hash="x", perfil=Perfil.PESQUISADOR)
    )
    repositorio = ValidacaoRepository()
    for decisao, anterior, novo in (
        (Decisao.SOLICITAR_INFO, StatusOcorrencia.PENDENTE, StatusOcorrencia.AGUARDANDO_INFO),
        (Decisao.CONFIRMAR, StatusOcorrencia.AGUARDANDO_INFO, StatusOcorrencia.CONFIRMADO),
    ):
        repositorio.registrar(
            Validacao(
                ocorrencia_id=ocorrencia.id,
                avaliador_id=usuario.id,
                decisao=decisao,
                justificativa="justificativa suficiente para o teste",
                status_anterior=anterior,
                status_novo=novo,
            )
        )

    historico = repositorio.historico(ocorrencia.id)
    assert len(historico) == 2
    assert historico[0].decisao == Decisao.SOLICITAR_INFO
    assert historico[1].status_novo == StatusOcorrencia.CONFIRMADO
    assert repositorio.contar_decisoes(Decisao.CONFIRMAR) == 1


def test_auditoria_registra_detalhes_em_json(ambiente):
    repositorio = AuditoriaRepository()
    repositorio.registrar(
        entidade="ocorrencia",
        acao="TESTE",
        entidade_id="LG-2026-AUD001",
        detalhes={"origem": "pytest", "quantidade": 3},
    )
    registros = repositorio.listar()
    assert len(registros) == 1
    assert "pytest" in registros[0].detalhes
    assert repositorio.contar() == 1


def test_fonte_dados_nao_duplica(ambiente):
    repositorio = FonteDadosRepository()
    fonte = FonteDados(nome="GBIF", tipo_fonte="BASE_EXTERNA", data_importacao="2026-11-01")
    primeira = repositorio.criar(fonte)
    segunda = repositorio.criar(
        FonteDados(nome="GBIF", tipo_fonte="BASE_EXTERNA", data_importacao="2026-11-01")
    )
    assert primeira.id == segunda.id
    assert len(repositorio.listar()) == 1


def test_imagem_por_hash_encontra_reenvio(ambiente):
    ocorrencia_a = OcorrenciaRepository().criar(_ocorrencia("LG-2026-IMG001"))
    ocorrencia_b = OcorrenciaRepository().criar(_ocorrencia("LG-2026-IMG002"))
    repositorio = ImagemRepository()
    for ocorrencia, nome in ((ocorrencia_a, "a.jpg"), (ocorrencia_b, "b.jpg")):
        repositorio.criar(
            Imagem(
                ocorrencia_id=ocorrencia.id,
                identificador_arquivo=nome,
                hash_sha256="d" * 64,
                formato="jpeg",
                tamanho_bytes=100,
            )
        )
    assert len(repositorio.por_hash("d" * 64)) == 2


# -------------------------------------------------------------- persistência
def test_dados_persistem_apos_fechar_conexoes(ambiente):
    repositorio = OcorrenciaRepository()
    repositorio.criar(_ocorrencia("LG-2026-PER001"))
    repositorio.criar(_ocorrencia("LG-2026-PER002"))

    fechar_conexoes()  # simula reinicialização da aplicação

    assert OcorrenciaRepository().contar() == 2
    assert OcorrenciaRepository().por_protocolo("LG-2026-PER001") is not None


def test_arquivo_do_banco_existe_em_disco(ambiente):
    OcorrenciaRepository().criar(_ocorrencia())
    fechar_conexoes()
    from pathlib import Path

    assert Path(ambiente.database_url).is_file()
    assert Path(ambiente.database_url).stat().st_size > 0
