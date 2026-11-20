"""
Testes das ilustrações vetoriais do projeto.

As ilustrações são geradas por código, e por isso dá para testá-las: o SVG é
texto. O que se verifica aqui:

  * o XML fecha corretamente (um SVG malformado some da tela sem erro, o que
    seria difícil de perceber em revisão);
  * os identificadores internos (gradientes, máscaras) são únicos por chamada,
     porque a mesma ilustração aparece mais de uma vez na mesma página — ids
     repetidos fazem um desenho herdar o gradiente do outro;
  * a geometria responde aos parâmetros (tamanho pedido = tamanho entregue);
  * nada é carregado de fora: sem `<image>`, sem `href` externo. Isso sustenta
     a afirmação de que a arte é original e não tem questão de licença.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from app.styles.ilustracoes import (
    _espinhos,
    _leque,
    _ponto,
    icone_svg,
    logo_svg,
    onda_svg,
    padrao_oceano_svg,
    peixe_leao_svg,
)

ILUSTRACOES = {
    "peixe": lambda: peixe_leao_svg(),
    "logo": lambda: logo_svg(),
    "onda": lambda: onda_svg(),
    "icone": lambda: icone_svg("camera"),
    "padrao": lambda: padrao_oceano_svg(),
}


# ================================================================== XML válido
@pytest.mark.parametrize("nome", sorted(ILUSTRACOES))
def test_svg_e_xml_bem_formado(nome):
    arvore = ET.fromstring(ILUSTRACOES[nome]())
    assert arvore.tag.endswith("svg")


NAMESPACE_SVG = "http://www.w3.org/2000/svg"


@pytest.mark.parametrize("nome", sorted(ILUSTRACOES))
def test_svg_nao_carrega_recurso_externo(nome):
    """Arte original: nenhum arquivo de fora, nenhuma requisição de rede."""
    # O namespace do SVG é uma URI de identificação, não um recurso buscado.
    marcacao = ILUSTRACOES[nome]().replace(NAMESPACE_SVG, "")

    assert "<image" not in marcacao
    assert "http://" not in marcacao
    assert "https://" not in marcacao


@pytest.mark.parametrize("nome", sorted(ILUSTRACOES))
def test_svg_nao_contem_script(nome):
    marcacao = ILUSTRACOES[nome]().lower()
    assert "<script" not in marcacao
    assert "onload" not in marcacao


@pytest.mark.parametrize("nome", sorted(ILUSTRACOES))
def test_ilustracao_se_declara_para_leitores_de_tela(nome):
    """
    Cada SVG precisa dizer o que é para a tecnologia assistiva: ou se declara
    decorativo (`aria-hidden`), ou se declara imagem com descrição
    (`role="img"` + `aria-label`). Um SVG sem nenhum dos dois é lido como um
    bloco de ruído pelo leitor de tela.
    """
    marcacao = ILUSTRACOES[nome]()
    decorativo = 'aria-hidden="true"' in marcacao
    descrito = 'role="img"' in marcacao and "aria-label=" in marcacao

    assert decorativo or descrito


# =========================================================== ids independentes
def _ids(marcacao: str) -> set[str]:
    return set(re.findall(r'id="([^"]+)"', marcacao))


def test_dois_peixes_na_mesma_pagina_nao_compartilham_ids():
    primeiro = peixe_leao_svg(id_unico="um")
    segundo = peixe_leao_svg(id_unico="dois")

    assert _ids(primeiro)
    assert _ids(primeiro).isdisjoint(_ids(segundo))


def test_todo_id_declarado_no_peixe_e_referenciado():
    """Um gradiente definido e não usado é resto de edição."""
    marcacao = peixe_leao_svg(id_unico="x")
    referencias = set(re.findall(r'url\(#([^)]+)\)', marcacao))
    referencias |= set(re.findall(r'mask="url\(#([^)]+)\)"', marcacao))

    assert _ids(marcacao) <= referencias | {"x"}


def test_toda_referencia_do_peixe_aponta_para_um_id_existente():
    """O inverso: uma referência órfã apaga a forma que a usa."""
    marcacao = peixe_leao_svg(id_unico="y")
    referencias = set(re.findall(r'url\(#([^)]+)\)', marcacao))

    assert referencias <= _ids(marcacao)


def test_padrao_oceano_isola_ids():
    assert _ids(padrao_oceano_svg("a")).isdisjoint(_ids(padrao_oceano_svg("b")))


# ==================================================================== geometria
@pytest.mark.parametrize("largura", [160, 300, 520, 900])
def test_peixe_respeita_a_largura_pedida(largura):
    marcacao = peixe_leao_svg(largura)
    assert f'width="{largura}"' in marcacao


def test_peixe_mantem_proporcao_pelo_viewbox():
    """Mudar a largura não deve distorcer o desenho."""
    primeiro = re.search(r'viewBox="([^"]+)"', peixe_leao_svg(200)).group(1)
    segundo = re.search(r'viewBox="([^"]+)"', peixe_leao_svg(800)).group(1)
    assert primeiro == segundo


@pytest.mark.parametrize("tamanho", [16, 28, 64])
def test_icone_respeita_o_tamanho(tamanho):
    marcacao = icone_svg("mapa", tamanho=tamanho)
    assert f'width="{tamanho}"' in marcacao
    assert f'height="{tamanho}"' in marcacao


@pytest.mark.parametrize(
    "nome", ["camera", "ia", "mapa", "escudo", "aviso", "grafico", "lupa", "relogio"]
)
def test_todo_icone_do_conjunto_desenha_algo(nome):
    marcacao = icone_svg(nome)
    assert "<path" in marcacao
    ET.fromstring(marcacao)


def test_icone_desconhecido_nao_quebra_a_pagina():
    """Erro de digitação em um nome de ícone não deve derrubar a interface."""
    marcacao = icone_svg("nome-que-nao-existe")
    ET.fromstring(marcacao)
    assert "<path" in marcacao


def test_icone_usa_a_cor_pedida():
    assert 'stroke="#123456"' in icone_svg("lupa", cor="#123456")


def test_onda_virada_difere_da_onda_normal():
    assert onda_svg(virada=False) != onda_svg(virada=True)


def test_onda_usa_a_cor_pedida():
    assert "#ABCDEF" in onda_svg(cor="#ABCDEF")


# ========================================================= funções auxiliares
def test_ponto_no_angulo_zero_fica_a_direita_do_centro():
    x, y = _ponto(100, 100, 10, 0)
    assert x == pytest.approx(110)
    assert y == pytest.approx(100)


def test_ponto_em_noventa_graus_desce_na_tela():
    """No SVG o eixo Y cresce para baixo."""
    _, y = _ponto(100, 100, 10, 90)
    assert y == pytest.approx(110)


def _quantidade_de_tracos(d: str) -> int:
    """Cada traço de um leque começa com um comando `M` próprio."""
    return len(re.findall(r"\bM ", d))


@pytest.mark.parametrize("quantidade", [2, 7, 12])
def test_leque_gera_a_quantidade_pedida_de_raios(quantidade):
    _, raios = _leque(100, 100, 50, 0, 90, quantidade=quantidade)
    assert _quantidade_de_tracos(raios) == quantidade


def test_leque_com_um_raio_nao_divide_por_zero():
    """`quantidade=1` zeraria o denominador da interpolação."""
    membrana, raios = _leque(100, 100, 50, 0, 90, quantidade=1)
    assert _quantidade_de_tracos(raios) == 1
    assert membrana.endswith("Z")


def test_leque_devolve_membrana_fechada_e_raios_curvos():
    """São duas camadas: a membrana translúcida embaixo, os raios por cima."""
    membrana, raios = _leque(100, 100, 50, 10, 100, quantidade=5)

    assert membrana.endswith("Z")  # polígono fechado, para poder ter preenchimento
    assert "Q" in raios  # raios são curvas, não retas
    assert "Z" not in raios  # linhas abertas, sem preenchimento


def test_raios_do_leque_ficam_dentro_do_comprimento_pedido():
    _, raios = _leque(100, 100, 50, 0, 90, quantidade=9)
    coordenadas = [float(valor) for valor in re.findall(r"-?\d+\.\d+", raios)]
    # Nenhum ponto pode cair além do centro mais o comprimento e a curvatura.
    assert max(coordenadas) <= 100 + 50 * 1.3


@pytest.mark.parametrize("quantidade", [2, 6, 12])
def test_espinhos_geram_a_quantidade_pedida(quantidade):
    _, espinhos = _espinhos(
        inicio=(100, 200),
        controle=(200, 160),
        fim=(300, 200),
        quantidade=quantidade,
        angulo_inicial=-120,
        angulo_final=-60,
        comprimento_inicial=140,
        comprimento_final=90,
    )
    assert _quantidade_de_tracos(espinhos) == quantidade


def test_espinhos_com_um_unico_traco_nao_divide_por_zero():
    membrana, espinhos = _espinhos(
        inicio=(100, 200),
        controle=(200, 160),
        fim=(300, 200),
        quantidade=1,
        angulo_inicial=-120,
        angulo_final=-60,
        comprimento_inicial=140,
        comprimento_final=90,
    )
    assert _quantidade_de_tracos(espinhos) == 1
    assert membrana.endswith("Z")


def test_espinhos_nascem_em_pontos_diferentes_do_dorso():
    """
    O que diferencia o dorso espinhoso de um leque comum: as bases são
    distribuídas ao longo da curva, não concentradas em um ponto.
    """
    _, espinhos = _espinhos(
        inicio=(100, 200),
        controle=(200, 160),
        fim=(300, 200),
        quantidade=8,
        angulo_inicial=-120,
        angulo_final=-60,
        comprimento_inicial=140,
        comprimento_final=90,
    )
    bases = re.findall(r"M (-?\d+\.\d+) (-?\d+\.\d+)", espinhos)

    assert len(bases) == 8
    assert len(set(bases)) == 8


def test_membrana_dos_espinhos_nao_alcanca_as_pontas():
    """
    A membrana sobe só parte do espinho — é isso que deixa as pontas livres,
    como no animal. Uma membrana inteira pareceria uma vela sólida.
    """
    membrana, espinhos = _espinhos(
        inicio=(100, 300),
        controle=(200, 260),
        fim=(300, 300),
        quantidade=6,
        angulo_inicial=-90,
        angulo_final=-90,
        comprimento_inicial=100,
        comprimento_final=100,
        curvatura=0.0,
        fracao_membrana=0.4,
    )
    altura_membrana = min(float(y) for y in re.findall(r"L -?\d+\.\d+ (-?\d+\.\d+)", membrana))
    altura_pontas = min(float(y) for y in re.findall(r"-?\d+\.\d+ (-?\d+\.\d+)$", espinhos))

    # No SVG, menor Y é mais alto na tela.
    assert altura_membrana > altura_pontas


def test_leque_e_espinhos_produzem_coordenadas_finitas():
    """`nan` em um `d=` apaga a forma silenciosamente, sem erro no console."""
    partes = list(_leque(100, 100, 60, -40, 40, quantidade=8)) + list(
        _espinhos(
            inicio=(100, 200),
            controle=(200, 160),
            fim=(300, 200),
            quantidade=8,
            angulo_inicial=-124,
            angulo_final=-64,
            comprimento_inicial=152,
            comprimento_final=92,
        )
    )
    for parte in partes:
        assert "nan" not in parte.lower()
        assert "inf" not in parte.lower()


def test_peixe_desenha_todas_as_camadas():
    """
    A página aponta espinhos dorsais, peitorais em leque, caudal e faixas. Se
    o desenho perder uma camada, o texto passa a descrever o que não está ali.
    Contar os grupos é a forma de detectar isso sem olhar a imagem.
    """
    marcacao = peixe_leao_svg(id_unico="z")

    # Corpo, pedúnculo, 4 nadadeiras (membrana + traços), faixas, cabeça.
    assert marcacao.count("<path") >= 10
    assert marcacao.count("<g") >= 3
