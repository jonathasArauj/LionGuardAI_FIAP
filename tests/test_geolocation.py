"""
Testes do serviço de geolocalização.

Cobertura: validação de coordenadas, área de interesse, sugestão de município,
arredondamento para o mapa público, classificação de precisão, origem da
posição e o caminho de fallback por região.
"""

from __future__ import annotations

import math

import pytest

from src.database.schema import OrigemLocalizacao
from src.services.geolocation import (
    ESTADOS_LITORANEOS,
    LIMITES_BRASIL,
    MUNICIPIOS_LITORANEOS,
    REFERENCIAS_LITORAL,
    CoordenadaInvalida,
    arredondar_para_publico,
    classificar_precisao,
    construir_localizacao,
    coordenadas_do_municipio,
    dentro_da_area_monitorada,
    dentro_do_brasil,
    distancia_km,
    localizacao_por_regiao,
    municipio_mais_proximo,
    municipios_do_estado,
    validar_coordenadas,
)


# ----------------------------------------------------------- validação básica
@pytest.mark.parametrize(
    "latitude,longitude",
    [(-20.67, -40.49), (0.0, 0.0), (-33.75, -53.37), (3.84, -51.83)],
)
def test_coordenadas_validas_sao_aceitas(latitude, longitude):
    assert validar_coordenadas(latitude, longitude) == (latitude, longitude)


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (None, -40.0),
        (-20.0, None),
        (91.0, -40.0),
        (-20.0, 181.0),
        ("abc", -40.0),
        (float("nan"), -40.0),
        (float("inf"), -40.0),
    ],
)
def test_coordenadas_invalidas_sao_recusadas(latitude, longitude):
    with pytest.raises(CoordenadaInvalida):
        validar_coordenadas(latitude, longitude)


def test_coordenadas_em_texto_sao_convertidas():
    assert validar_coordenadas("-20.67", "-40.49") == (-20.67, -40.49)


# ------------------------------------------------------------ área do Brasil
@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (-20.67, -40.49),  # Guarapari
        (-3.85, -32.42),  # Fernando de Noronha
        (-20.50, -29.32),  # Ilha da Trindade
        (3.84, -51.83),  # Oiapoque
    ],
)
def test_pontos_do_litoral_estao_na_area(latitude, longitude):
    assert dentro_do_brasil(latitude, longitude) is True


@pytest.mark.parametrize(
    "latitude,longitude",
    [(48.85, 2.35), (25.76, -80.19), (0.0, 0.0), (10.0, -60.0)],
)
def test_pontos_fora_da_caixa_sao_identificados(latitude, longitude):
    assert dentro_do_brasil(latitude, longitude) is False


@pytest.mark.parametrize(
    "latitude,longitude,descricao",
    [
        (-34.60, -58.38, "Buenos Aires — dentro da caixa, fora da área monitorada"),
        (-15.78, -47.93, "Brasília — interior do continente"),
        (-3.10, -60.02, "Manaus — interior do continente"),
        (-20.00, -25.00, "Atlântico aberto, longe de qualquer referência"),
    ],
)
def test_pontos_dentro_da_caixa_mas_fora_da_area_sao_recusados(latitude, longitude, descricao):
    """A caixa envolvente sozinha não basta: o filtro por distância completa."""
    dentro, motivo = dentro_da_area_monitorada(latitude, longitude)
    assert dentro is False, descricao
    assert motivo


@pytest.mark.parametrize(
    "latitude,longitude",
    [(-20.67, -40.49), (-3.85, -32.42), (-20.50, -29.32), (-27.60, -48.55)],
)
def test_pontos_do_litoral_e_ilhas_sao_aceitos_na_area(latitude, longitude):
    dentro, motivo = dentro_da_area_monitorada(latitude, longitude)
    assert dentro is True
    assert motivo is None


def test_construir_localizacao_recusa_ponto_fora_da_area():
    with pytest.raises(CoordenadaInvalida):
        construir_localizacao(48.85, 2.35, OrigemLocalizacao.MAPA_MANUAL)


def test_construir_localizacao_recusa_ponto_no_interior_do_continente():
    with pytest.raises(CoordenadaInvalida):
        construir_localizacao(-15.78, -47.93, OrigemLocalizacao.MAPA_MANUAL)


def test_construir_localizacao_pode_aceitar_fora_da_area_quando_pedido():
    localizacao = construir_localizacao(
        48.85, 2.35, OrigemLocalizacao.IMPORTADA, exigir_area_brasil=False
    )
    assert localizacao.tem_coordenadas


# ------------------------------------------------------------------ distância
def test_distancia_de_ponto_para_si_mesmo_e_zero():
    assert distancia_km(-20.67, -40.49, -20.67, -40.49) == pytest.approx(0.0, abs=1e-9)


def test_distancia_e_simetrica():
    ida = distancia_km(-20.67, -40.49, -12.97, -38.50)
    volta = distancia_km(-12.97, -38.50, -20.67, -40.49)
    assert ida == pytest.approx(volta, abs=1e-9)


def test_distancia_conhecida_vitoria_salvador():
    """Vitória–Salvador em linha reta fica em torno de 840 km."""
    distancia = distancia_km(-20.32, -40.34, -12.97, -38.50)
    assert 800 < distancia < 880


def test_um_grau_de_latitude_tem_cerca_de_111_km():
    assert distancia_km(-20.0, -40.0, -21.0, -40.0) == pytest.approx(111.2, abs=1.0)


# ------------------------------------------------------- sugestão de município
def test_municipio_mais_proximo_encontra_guarapari():
    municipio, uf, distancia = municipio_mais_proximo(-20.6712, -40.4985)
    assert municipio == "Guarapari"
    assert uf == "ES"
    assert distancia < 2.0


def test_municipio_mais_proximo_para_ponto_em_alto_mar():
    """Mesmo longe da costa, devolve a referência mais próxima com a distância."""
    municipio, uf, distancia = municipio_mais_proximo(-20.0, -35.0)
    assert municipio and uf in ESTADOS_LITORANEOS
    assert distancia > 100  # a interface usa isso para avisar o usuário


def test_construir_localizacao_sugere_municipio():
    localizacao = construir_localizacao(
        -20.6712, -40.4985, OrigemLocalizacao.GPS_DISPOSITIVO, precisao_metros=10.0
    )
    assert localizacao.municipio == "Guarapari"
    assert localizacao.estado == "ES"
    assert localizacao.municipio_sugerido is True
    assert localizacao.distancia_referencia_km is not None


def test_municipio_informado_tem_prioridade_sobre_a_sugestao():
    localizacao = construir_localizacao(
        -20.6712,
        -40.4985,
        OrigemLocalizacao.MAPA_MANUAL,
        estado="ES",
        municipio="Anchieta",
    )
    assert localizacao.municipio == "Anchieta"
    assert localizacao.municipio_sugerido is False


def test_municipios_do_estado_vem_ordenados():
    municipios = municipios_do_estado("ES")
    assert "Guarapari" in municipios
    assert municipios == sorted(municipios)


def test_coordenadas_do_municipio():
    assert coordenadas_do_municipio("Guarapari", "ES") is not None
    assert coordenadas_do_municipio("Guarapari", "es") is not None
    assert coordenadas_do_municipio("Cidade Inexistente", "ES") is None


def test_tabela_de_referencia_tem_coordenadas_coerentes():
    """Toda referência precisa estar na caixa envolvente monitorada."""
    for municipio, uf, latitude, longitude in REFERENCIAS_LITORAL:
        assert uf in ESTADOS_LITORANEOS, municipio
        assert dentro_do_brasil(latitude, longitude), municipio
        assert LIMITES_BRASIL["lat_min"] <= latitude <= LIMITES_BRASIL["lat_max"]


def test_toda_uf_litoranea_tem_referencia():
    ufs = {uf for _, uf, _, _ in REFERENCIAS_LITORAL}
    assert set(ESTADOS_LITORANEOS) == ufs


# ------------------------------------------------------- precisão da posição
def test_localizacao_de_gps_e_considerada_precisa():
    localizacao = construir_localizacao(
        -20.67, -40.49, OrigemLocalizacao.GPS_DISPOSITIVO, precisao_metros=8.0
    )
    assert localizacao.precisa is True


def test_localizacao_de_regiao_nao_e_considerada_precisa():
    localizacao = localizacao_por_regiao("ES", "Guarapari")
    assert localizacao.origem == OrigemLocalizacao.REGIAO_APROXIMADA
    assert localizacao.precisa is False
    assert localizacao.precisao_metros is None


def test_regiao_sem_municipio_usa_centro_do_estado():
    localizacao = localizacao_por_regiao("BA")
    assert localizacao.estado == "BA"
    assert localizacao.municipio is None
    assert localizacao.tem_coordenadas


def test_regiao_recusa_uf_nao_litoranea():
    for uf in ("MG", "GO", "XX", ""):
        with pytest.raises(CoordenadaInvalida):
            localizacao_por_regiao(uf)


@pytest.mark.parametrize(
    "precisao,trecho",
    [
        (None, "não informada"),
        (8.0, "alta precisão"),
        (60.0, "moderada"),
        (500.0, "baixa"),
        (5000.0, "muito baixa"),
    ],
)
def test_classificacao_de_precisao(precisao, trecho):
    assert trecho in classificar_precisao(precisao)


# ------------------------------------------------------------- privacidade
def test_arredondamento_publico_reduz_precisao(ambiente):
    latitude, longitude = arredondar_para_publico(-20.671234, -40.498765)
    assert latitude == -20.67
    assert longitude == -40.5


def test_arredondamento_publico_mantem_erro_na_ordem_de_1km(ambiente):
    original = (-20.671234, -40.498765)
    publica = arredondar_para_publico(*original)
    erro = distancia_km(*original, *publica)
    assert erro < 1.6  # duas casas decimais ≈ até ~1,1 km por eixo


def test_arredondamento_aceita_casas_explicitas(ambiente):
    assert arredondar_para_publico(-20.671234, -40.498765, casas=1) == (-20.7, -40.5)


# --------------------------------------------------------------- descrições
def test_descricao_da_origem_e_legivel():
    for origem in OrigemLocalizacao:
        localizacao = construir_localizacao(
            -20.67, -40.49, origem, exigir_area_brasil=False
        )
        descricao = localizacao.descricao_origem()
        assert descricao and not descricao.isupper()
        assert "_" not in descricao


def test_localizacao_sem_coordenadas_nao_e_precisa():
    from src.services.geolocation import Localizacao

    vazia = Localizacao(latitude=None, longitude=None, origem=OrigemLocalizacao.MAPA_MANUAL)
    assert vazia.tem_coordenadas is False
    assert vazia.precisa is False


def test_centro_geografico_usa_trigonometria_correta():
    """O cálculo do centro não deve ser média aritmética ingênua."""
    from src.services.spatial import _centro

    latitude, longitude = _centro([(-20.0, -40.0), (-21.0, -41.0)])
    assert latitude == pytest.approx(-20.5, abs=0.02)
    assert longitude == pytest.approx(-40.5, abs=0.02)
    assert not math.isnan(latitude)
