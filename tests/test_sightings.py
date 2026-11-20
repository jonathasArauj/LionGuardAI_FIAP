"""
Testes do serviço de registro de avistamentos — o fluxo central da plataforma.

Cobertura: geração de protocolo, atomicidade da transação, idempotência
(duplo clique), status inicial sempre pendente, confirmação de gravação,
validações de domínio, limpeza de arquivo em caso de falha, hash de contato e
consulta pública por protocolo.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.database.repositories import ImagemRepository, OcorrenciaRepository, PredicaoRepository
from src.database.schema import Habitat, OrigemLocalizacao, OrigemRegistro, StatusOcorrencia, TipoDado
from src.services.image_storage import ArmazenamentoImagens, calcular_hash
from src.services.sightings import (
    DadosAvistamento,
    ErroRegistro,
    ServicoAvistamentos,
)


def _dados(localizacao, imagem=None, **extras):
    padrao = {
        "localizacao": localizacao,
        "data_hora_avistamento": (datetime.now() - timedelta(hours=2))
        .replace(microsecond=0)
        .isoformat(),
        "imagem": imagem,
    }
    padrao.update(extras)
    return DadosAvistamento(**padrao)


# ----------------------------------------------------------------- protocolo
def test_protocolo_tem_formato_esperado(ambiente):
    protocolo = ServicoAvistamentos().gerar_protocolo()
    partes = protocolo.split("-")
    assert partes[0] == "LG"
    assert partes[1] == str(datetime.now().year)
    assert len(partes[2]) == 6
    # alfabeto sem caracteres ambíguos
    assert not set(partes[2]) & set("01IO")


def test_protocolos_sao_unicos(ambiente):
    servico = ServicoAvistamentos()
    protocolos = {servico.gerar_protocolo() for _ in range(50)}
    assert len(protocolos) == 50


# ------------------------------------------------------------- registro básico
def test_registro_completo_grava_tudo(ambiente, localizacao_guarapari, imagem_validada):
    servico = ServicoAvistamentos()
    resultado = servico.registrar(
        _dados(
            localizacao_guarapari,
            imagem_validada,
            profundidade=9.4,
            habitat=Habitat.COSTAO_ROCHOSO,
            quantidade_observada=2,
            descricao="  avistado perto da pedra  ",
            origem_registro=OrigemRegistro.MERGULHADOR,
            chave_idempotencia="k1",
        )
    )

    assert resultado.sucesso is True
    assert resultado.duplicado is False
    assert resultado.protocolo

    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    assert ocorrencia is not None
    assert ocorrencia.status == StatusOcorrencia.PENDENTE
    assert ocorrencia.municipio == "Guarapari"
    assert ocorrencia.profundidade == 9.4
    assert ocorrencia.habitat == Habitat.COSTAO_ROCHOSO
    assert ocorrencia.quantidade_observada == 2
    assert ocorrencia.descricao == "avistado perto da pedra"  # texto limpo
    assert ocorrencia.origem_registro == OrigemRegistro.MERGULHADOR
    assert ocorrencia.tipo_dado == TipoDado.REAL
    assert ocorrencia.origem_localizacao == OrigemLocalizacao.GPS_DISPOSITIVO

    imagem = ImagemRepository().primeira_por_ocorrencia(ocorrencia.id)
    assert imagem is not None
    assert imagem.exif_removido is True
    assert imagem.hash_sha256 == calcular_hash(imagem_validada.conteudo)
    assert ArmazenamentoImagens().existe(imagem.identificador_arquivo)


def test_status_inicial_e_sempre_pendente(ambiente, localizacao_guarapari, imagem_validada):
    """Nem um score alto confirma: a confirmação é ato humano."""
    from src.ai.inference import ClassePredicao, ResultadoInferencia

    inferencia = ResultadoInferencia(
        classe=ClassePredicao.PEIXE_LEAO,
        modelo="teste",
        versao="1",
        score=0.999,
        tempo_inferencia_ms=5.0,
    )
    resultado = ServicoAvistamentos().registrar(
        _dados(localizacao_guarapari, imagem_validada, inferencia=inferencia)
    )
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    assert ocorrencia.status == StatusOcorrencia.PENDENTE

    predicao = PredicaoRepository().ultima_por_ocorrencia(ocorrencia.id)
    assert predicao.score == pytest.approx(0.999)
    assert predicao.versao == "1"


def test_registro_sem_imagem_e_aceito(ambiente, localizacao_guarapari):
    resultado = ServicoAvistamentos().registrar(_dados(localizacao_guarapari))
    assert resultado.sucesso is True
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    assert ImagemRepository().primeira_por_ocorrencia(ocorrencia.id) is None


def test_registro_sem_inferencia_e_aceito(ambiente, localizacao_guarapari, imagem_validada):
    """Modelo indisponível não pode bloquear o registro."""
    resultado = ServicoAvistamentos().registrar(
        _dados(localizacao_guarapari, imagem_validada, inferencia=None)
    )
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    assert resultado.sucesso is True
    assert PredicaoRepository().ultima_por_ocorrencia(ocorrencia.id) is None


# ------------------------------------------------------------- idempotência
def test_duplo_clique_nao_duplica(ambiente, localizacao_guarapari, imagem_validada):
    servico = ServicoAvistamentos()
    dados = _dados(localizacao_guarapari, imagem_validada, chave_idempotencia="mesma-chave")

    primeiro = servico.registrar(dados)
    segundo = servico.registrar(dados)
    terceiro = servico.registrar(dados)

    assert primeiro.protocolo == segundo.protocolo == terceiro.protocolo
    assert primeiro.duplicado is False
    assert segundo.duplicado is True
    assert OcorrenciaRepository().contar() == 1


def test_avistamentos_diferentes_geram_registros_diferentes(
    ambiente, localizacao_guarapari, imagem_validada
):
    servico = ServicoAvistamentos()
    primeiro = servico.registrar(
        _dados(localizacao_guarapari, imagem_validada, chave_idempotencia="a")
    )
    segundo = servico.registrar(
        _dados(localizacao_guarapari, imagem_validada, chave_idempotencia="b")
    )
    assert primeiro.protocolo != segundo.protocolo
    assert OcorrenciaRepository().contar() == 2


def test_chave_de_idempotencia_depende_do_conteudo(ambiente):
    servico = ServicoAvistamentos()
    base = {
        "hash_imagem": "abc",
        "data_hora_avistamento": "2026-11-10T10:00:00",
        "latitude": -20.67,
        "longitude": -40.49,
        "sessao": "s1",
    }
    chave = servico.calcular_chave_idempotencia(**base)

    assert chave == servico.calcular_chave_idempotencia(**base)
    assert chave != servico.calcular_chave_idempotencia(**{**base, "hash_imagem": "xyz"})
    assert chave != servico.calcular_chave_idempotencia(**{**base, "latitude": -21.0})
    assert chave != servico.calcular_chave_idempotencia(**{**base, "sessao": "s2"})
    assert chave != servico.calcular_chave_idempotencia(
        **{**base, "data_hora_avistamento": "2026-11-10T11:00:00"}
    )


def test_registro_sem_chave_nao_e_bloqueado(ambiente, localizacao_guarapari):
    """Sem chave de idempotência, cada chamada é um registro novo."""
    servico = ServicoAvistamentos()
    servico.registrar(_dados(localizacao_guarapari, chave_idempotencia=None))
    servico.registrar(_dados(localizacao_guarapari, chave_idempotencia=None))
    assert OcorrenciaRepository().contar() == 2


# --------------------------------------------------------------- validações
def test_registro_sem_localizacao_e_recusado(ambiente):
    from src.services.geolocation import Localizacao

    vazia = Localizacao(latitude=None, longitude=None, origem=OrigemLocalizacao.MAPA_MANUAL)
    with pytest.raises(ErroRegistro, match="localização"):
        ServicoAvistamentos().registrar(_dados(vazia))


def test_data_no_futuro_e_recusada(ambiente, localizacao_guarapari):
    futuro = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    with pytest.raises(ErroRegistro, match="futuro"):
        ServicoAvistamentos().registrar(
            _dados(localizacao_guarapari, data_hora_avistamento=futuro)
        )


def test_data_em_formato_invalido_e_recusada(ambiente, localizacao_guarapari):
    with pytest.raises(ErroRegistro, match="formato"):
        ServicoAvistamentos().registrar(
            _dados(localizacao_guarapari, data_hora_avistamento="10/11/2026")
        )


def test_data_vazia_e_recusada(ambiente, localizacao_guarapari):
    with pytest.raises(ErroRegistro):
        ServicoAvistamentos().registrar(
            _dados(localizacao_guarapari, data_hora_avistamento="")
        )


@pytest.mark.parametrize("quantidade", [0, -1, -10])
def test_quantidade_invalida_e_recusada(ambiente, localizacao_guarapari, quantidade):
    with pytest.raises(ErroRegistro, match="quantidade"):
        ServicoAvistamentos().registrar(
            _dados(localizacao_guarapari, quantidade_observada=quantidade)
        )


def test_profundidade_negativa_e_recusada(ambiente, localizacao_guarapari):
    with pytest.raises(ErroRegistro, match="[Pp]rofundidade"):
        ServicoAvistamentos().registrar(_dados(localizacao_guarapari, profundidade=-5.0))


def test_nada_e_gravado_quando_a_validacao_falha(ambiente, localizacao_guarapari, imagem_validada):
    """Falha de validação não deixa ocorrência nem arquivo órfão."""
    armazenamento = ArmazenamentoImagens()
    antes = len(list(Path(armazenamento.diretorio).glob("*")))

    with pytest.raises(ErroRegistro):
        ServicoAvistamentos().registrar(
            _dados(localizacao_guarapari, imagem_validada, profundidade=-1.0)
        )

    assert OcorrenciaRepository().contar() == 0
    assert len(list(Path(armazenamento.diretorio).glob("*"))) == antes


# ------------------------------------------------------------- privacidade
def test_contato_e_guardado_apenas_como_hash(ambiente, localizacao_guarapari):
    resultado = ServicoAvistamentos().registrar(
        _dados(localizacao_guarapari, contato="pessoa@exemplo.com")
    )
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    assert ocorrencia.contato_hash is not None
    assert "pessoa@exemplo.com" not in ocorrencia.contato_hash
    assert len(ocorrencia.contato_hash) == 64


def test_contato_igual_gera_hash_igual(ambiente, localizacao_guarapari):
    servico = ServicoAvistamentos()
    primeiro = servico.registrar(
        _dados(localizacao_guarapari, contato="Pessoa@Exemplo.com ", chave_idempotencia="c1")
    )
    segundo = servico.registrar(
        _dados(localizacao_guarapari, contato="pessoa@exemplo.com", chave_idempotencia="c2")
    )
    repositorio = OcorrenciaRepository()
    assert (
        repositorio.por_protocolo(primeiro.protocolo).contato_hash
        == repositorio.por_protocolo(segundo.protocolo).contato_hash
    )


def test_sem_contato_nao_grava_hash(ambiente, localizacao_guarapari):
    resultado = ServicoAvistamentos().registrar(_dados(localizacao_guarapari, contato="   "))
    assert OcorrenciaRepository().por_protocolo(resultado.protocolo).contato_hash is None


def test_autorizacao_de_imagem_e_falsa_por_padrao(ambiente, localizacao_guarapari, imagem_validada):
    resultado = ServicoAvistamentos().registrar(_dados(localizacao_guarapari, imagem_validada))
    assert (
        OcorrenciaRepository().por_protocolo(resultado.protocolo).autoriza_publicar_imagem
        is False
    )


# --------------------------------------------------------- aviso de reenvio
def test_mesma_foto_em_outro_registro_gera_aviso(
    ambiente, localizacao_guarapari, imagem_validada
):
    servico = ServicoAvistamentos()
    servico.registrar(_dados(localizacao_guarapari, imagem_validada, chave_idempotencia="p1"))
    segundo = servico.registrar(
        _dados(localizacao_guarapari, imagem_validada, chave_idempotencia="p2")
    )
    assert any("mesma foto" in aviso.lower() for aviso in segundo.avisos)


# ------------------------------------------------------------ consulta pública
def test_consulta_por_protocolo(ambiente, localizacao_guarapari, imagem_validada):
    servico = ServicoAvistamentos()
    resultado = servico.registrar(_dados(localizacao_guarapari, imagem_validada))

    consulta = servico.consultar_por_protocolo(resultado.protocolo)
    assert consulta is not None
    assert consulta["protocolo"] == resultado.protocolo
    assert consulta["status"] == StatusOcorrencia.PENDENTE
    assert consulta["tem_imagem"] is True
    assert "contato_hash" not in consulta  # nunca exposto


def test_consulta_aceita_protocolo_em_minusculas(ambiente, localizacao_guarapari):
    servico = ServicoAvistamentos()
    resultado = servico.registrar(_dados(localizacao_guarapari))
    assert servico.consultar_por_protocolo(resultado.protocolo.lower()) is not None
    assert servico.consultar_por_protocolo(f"  {resultado.protocolo}  ") is not None


def test_consulta_de_protocolo_inexistente(ambiente):
    assert ServicoAvistamentos().consultar_por_protocolo("LG-2026-ZZZZZZ") is None
    assert ServicoAvistamentos().consultar_por_protocolo("") is None


# ------------------------------------------------------------- persistência
def test_registro_sobrevive_a_reinicializacao(ambiente, localizacao_guarapari, imagem_validada):
    from src.database.connection import fechar_conexoes

    resultado = ServicoAvistamentos().registrar(_dados(localizacao_guarapari, imagem_validada))
    fechar_conexoes()

    relido = ServicoAvistamentos().consultar_por_protocolo(resultado.protocolo)
    assert relido is not None
    assert relido["status"] == StatusOcorrencia.PENDENTE
    assert ArmazenamentoImagens().existe(relido["arquivo_imagem"])
