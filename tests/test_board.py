"""
Testes das peças do painel e da coerência do tema escuro.

O que se verifica aqui:

  * os blocos de número e as barras não dependem de cor para serem lidos — o
    valor aparece escrito em todos eles;
  * o medidor produz geometria válida nos extremos (0, máximo, acima do
    máximo) e não divide por zero com máximo nulo;
  * o tema do Streamlit (`.streamlit/config.toml`) e o CSS do projeto falam
    das mesmas cores. Se um for alterado e o outro não, a interface fica com
    duas paletas ao mesmo tempo — algo que ninguém percebe lendo o diff.
"""

from __future__ import annotations

import pathlib
import re
import sys
import types
import xml.etree.ElementTree as ET

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def board(monkeypatch):
    """Importa `app.components.board` com um Streamlit falso no lugar do real."""
    registro: list[str] = []

    falso = types.SimpleNamespace(
        markdown=lambda texto, **_k: registro.append(str(texto)),
        caption=lambda texto, **_k: registro.append(str(texto)),
    )
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    for nome in [n for n in list(sys.modules) if n.startswith("app.components.board")]:
        monkeypatch.delitem(sys.modules, nome, raising=False)

    import importlib

    modulo = importlib.reload(importlib.import_module("app.components.board"))
    return modulo, registro


# ================================================================== números
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        (0, "0"),
        (7, "7"),
        (1234, "1.234"),
        (45303, "45.303"),
        (1234567, "1.234.567"),
        (12.0, "12"),
        (87.5, "87,5"),
    ],
)
def test_numero_em_formato_brasileiro(board, entrada, esperado):
    modulo, _ = board
    assert modulo._numero(entrada) == esperado


# =============================================================== blocos
def test_bloco_traz_rotulo_e_valor_escritos(board):
    modulo, _ = board
    marcacao = modulo.tile("Avistamentos", 45303, nota="desde 2026")

    assert "Avistamentos" in marcacao
    assert "45.303" in marcacao
    assert "desde 2026" in marcacao


def test_bloco_escapa_html_do_rotulo(board):
    """Rótulo vem de dado; não pode injetar marcação."""
    modulo, _ = board
    marcacao = modulo.tile("<script>alerta</script>", 1)

    assert "<script>" not in marcacao
    assert "&lt;script&gt;" in marcacao


def test_variacao_positiva_e_negativa_usam_setas_diferentes(board):
    modulo, _ = board
    sobe = modulo.tile("x", 10, delta=12.0)
    desce = modulo.tile("x", 10, delta=-12.0)

    assert modulo.SETA_SUBIDA in sobe
    assert modulo.SETA_DESCIDA in desce
    # A direção não depende da cor: a seta carrega o sinal sozinha.
    assert modulo.SETA_SUBIDA not in desce


def test_bloco_sem_variacao_nao_inventa_seta(board):
    modulo, _ = board
    marcacao = modulo.tile("x", 10)
    assert modulo.SETA_SUBIDA not in marcacao and modulo.SETA_DESCIDA not in marcacao


# ================================================================== barras
def test_barras_escrevem_o_valor_ao_lado_do_rotulo(board):
    modulo, registro = board
    modulo.barras_percentuais(
        [{"rotulo": "ES", "valor": 18}, {"rotulo": "BA", "valor": 42}],
        titulo="Estados",
    )
    saida = "".join(registro)

    assert "ES" in saida and "18" in saida
    assert "BA" in saida and "42" in saida


def test_barra_do_maior_valor_ocupa_a_largura_total(board):
    modulo, registro = board
    modulo.barras_percentuais([{"rotulo": "a", "valor": 10}, {"rotulo": "b", "valor": 5}])
    larguras = [float(v) for v in re.findall(r"width:([\d.]+)%", "".join(registro))]

    assert larguras[0] == pytest.approx(100.0)
    assert larguras[1] == pytest.approx(50.0)


def test_barra_de_valor_zero_ainda_aparece(board):
    """Largura zero some da tela e parece dado faltando, não dado igual a zero."""
    modulo, registro = board
    modulo.barras_percentuais([{"rotulo": "a", "valor": 0}, {"rotulo": "b", "valor": 9}])
    larguras = [float(v) for v in re.findall(r"width:([\d.]+)%", "".join(registro))]

    assert larguras[0] > 0


def test_barras_com_todos_os_valores_zerados_nao_dividem_por_zero(board):
    modulo, registro = board
    modulo.barras_percentuais([{"rotulo": "a", "valor": 0}, {"rotulo": "b", "valor": 0}])
    assert registro


def test_barras_sem_itens_nao_desenham_cartao_vazio(board):
    modulo, registro = board
    modulo.barras_percentuais([])
    assert registro == []


def test_barras_aceitam_maximo_explicito(board):
    """Com máximo fixo em 100, um valor de 25 ocupa um quarto — não tudo."""
    modulo, registro = board
    modulo.barras_percentuais([{"rotulo": "a", "valor": 25}], maximo=100)
    largura = float(re.findall(r"width:([\d.]+)%", "".join(registro))[0])

    assert largura == pytest.approx(25.0)


# ================================================================= medidor
@pytest.mark.parametrize("valor,maximo", [(0, 100), (50, 100), (100, 100), (641, 1000)])
def test_medidor_gera_svg_valido(board, valor, maximo):
    modulo, _ = board
    arvore = ET.fromstring(modulo.medidor_svg(valor, maximo, "legenda"))
    assert arvore.tag.endswith("svg")


def test_medidor_escreve_o_valor_no_centro(board):
    """Quem não distingue a cor do arco lê o número."""
    modulo, _ = board
    assert "641" in modulo.medidor_svg(641, 1000, "")


def test_medidor_em_zero_nao_desenha_arco_preenchido(board):
    modulo, _ = board
    marcacao = modulo.medidor_svg(0, 100, "")
    assert marcacao.count("<path") == 1  # só o trilho


def test_medidor_cheio_desenha_arco_preenchido(board):
    modulo, _ = board
    assert modulo.medidor_svg(100, 100, "").count("<path") == 2


def test_medidor_com_maximo_zero_nao_quebra(board):
    modulo, _ = board
    ET.fromstring(modulo.medidor_svg(5, 0, ""))


def test_medidor_acima_do_maximo_nao_passa_da_volta(board):
    """Um valor fora da escala não pode desenhar um arco de mais de 270°."""
    modulo, _ = board
    cheio = modulo.medidor_svg(100, 100, "", id_unico="a")
    estourado = modulo.medidor_svg(500, 100, "", id_unico="a")

    def pontos(marcacao: str) -> list[str]:
        return re.findall(r'd="(M [^"]+)"', marcacao)

    assert pontos(cheio)[1] == pontos(estourado)[1]


def test_medidor_tem_descricao_para_leitor_de_tela(board):
    modulo, _ = board
    marcacao = modulo.medidor_svg(30, 100, "validados")
    assert 'role="img"' in marcacao and "aria-label=" in marcacao
    assert "validados" in marcacao


def test_medidores_na_mesma_pagina_nao_compartilham_gradiente(board):
    modulo, _ = board
    ids = lambda m: set(re.findall(r'id="([^"]+)"', m))  # noqa: E731

    assert ids(modulo.medidor_svg(1, 2, "", id_unico="um")).isdisjoint(
        ids(modulo.medidor_svg(1, 2, "", id_unico="dois"))
    )


# ========================================================== legenda de status
def test_legenda_de_status_traz_icone_e_texto_junto_da_cor(board):
    modulo, _ = board
    marcacao = modulo.legenda_status(
        [{"rotulo": "Confirmado", "icone": "✅", "cor": "#E06A6A", "total": 12}]
    )

    assert "Confirmado" in marcacao
    assert "✅" in marcacao
    assert "12" in marcacao


# ===================================================== coerência do tema
def _config_streamlit() -> dict[str, str]:
    texto = (RAIZ / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    return dict(re.findall(r'^(\w+)\s*=\s*"([^"]+)"', texto, re.M))


def test_streamlit_usa_o_tema_escuro():
    assert _config_streamlit()["base"] == "dark"


def test_cores_do_config_batem_com_as_do_tema():
    """
    Duas fontes de cor para a mesma interface só funcionam se andarem juntas.
    """
    from app.styles import theme

    config = _config_streamlit()

    assert config["backgroundColor"].upper() == theme.FUNDO.upper()
    assert config["secondaryBackgroundColor"].upper() == theme.SUPERFICIE.upper()
    assert config["textColor"].upper() == theme.TEXTO.upper()
    assert config["primaryColor"].upper() == theme.TURQUESA.upper()


def test_graficos_desenham_sobre_fundo_transparente():
    """O cartão é que dá o fundo; um fundo branco no gráfico abriria um buraco."""
    from app.styles.theme import layout_plotly

    layout = layout_plotly("título")

    assert layout["paper_bgcolor"] == "rgba(0,0,0,0)"
    assert layout["plot_bgcolor"] == "rgba(0,0,0,0)"


def test_texto_dos_graficos_e_claro_o_bastante_para_o_fundo_escuro():
    from app.styles.theme import layout_plotly

    cor = layout_plotly()["font"]["color"].lstrip("#")
    luminancia = int(cor[0:2], 16) * 0.299 + int(cor[2:4], 16) * 0.587 + int(cor[4:6], 16) * 0.114

    assert luminancia > 140, "texto escuro sobre fundo escuro"


def test_paleta_categorica_nao_repete_cor():
    from app.styles.theme import SEQUENCIA_GRAFICOS

    assert len(set(SEQUENCIA_GRAFICOS)) == len(SEQUENCIA_GRAFICOS)


def test_rampa_sequencial_vai_do_escuro_ao_claro():
    """
    No tema escuro a rampa cresce em direção ao claro: é o claro que avança
    sobre o fundo. Invertê-la faria o valor alto sumir.
    """
    from app.styles.theme import RAMPA_SEQUENCIAL

    def luminancia(cor: str) -> float:
        cor = cor.lstrip("#")
        return int(cor[0:2], 16) * 0.299 + int(cor[2:4], 16) * 0.587 + int(cor[4:6], 16) * 0.114

    valores = [luminancia(cor) for cor in RAMPA_SEQUENCIAL]
    assert valores == sorted(valores)
