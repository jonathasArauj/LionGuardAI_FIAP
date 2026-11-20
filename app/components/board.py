"""
Peças do painel ("board"): blocos de número, barras de proporção e medidor.

Todas devolvem HTML/SVG desenhado aqui, sem depender de biblioteca de
gráficos. O motivo é prático: são peças pequenas, que aparecem em quase toda
página, e desenhá-las à mão evita carregar um gráfico inteiro para mostrar um
número — além de deixá-las testáveis sem navegador.

Gráficos de verdade (séries, distribuições, correlações) continuam em
`app/components/charts.py`, com Plotly.

Regra que vale para todas: **nenhuma informação só por cor**. Toda barra traz
o número ao lado, todo bloco traz rótulo, e o medidor traz o valor escrito no
centro.
"""

from __future__ import annotations

import html as _html
import math

import streamlit as st

from app.styles.markup import escrever_html
from app.styles.theme import (
    AZUL_OCEANO,
    BORDA,
    SUPERFICIE,
    TEXTO,
    TEXTO_FRACO,
    TURQUESA,
    VERDE_DESTAQUE,
    VERMELHO,
)

SETA_SUBIDA = "↗"
SETA_DESCIDA = "↘"


def _numero(valor) -> str:
    """Milhar com ponto, como se escreve em português."""
    if isinstance(valor, float) and not valor.is_integer():
        return f"{valor:,.1f}".replace(",", "·").replace(".", ",").replace("·", ".")
    if isinstance(valor, (int, float)):
        return f"{int(valor):,}".replace(",", ".")
    return str(valor)


def tile(
    rotulo: str,
    valor,
    nota: str | None = None,
    icone: str = "",
    cor: str = TURQUESA,
    delta: float | None = None,
) -> str:
    """
    Um bloco de número. `delta` é variação percentual: positiva sobe, negativa
    desce, e a seta acompanha o sinal (a informação não depende da cor).
    """
    linha_delta = ""
    if delta is not None:
        seta = SETA_SUBIDA if delta >= 0 else SETA_DESCIDA
        cor_delta = VERDE_DESTAQUE if delta >= 0 else VERMELHO
        linha_delta = (
            f'<span class="lg-tile-delta" style="color:{cor_delta}">'
            f"{seta} {abs(delta):.0f}%</span>"
        )

    bloco_nota = (
        f'<div class="lg-kpi-nota">{_html.escape(nota)}</div>' if nota else ""
    )
    prefixo_icone = f"{icone} " if icone else ""

    return (
        f'<div class="lg-tile" style="border-left-color:{cor}">'
        f'<div class="lg-kpi-rotulo">{prefixo_icone}{_html.escape(rotulo)}</div>'
        f'<div class="lg-tile-linha">'
        f'<span class="lg-kpi-valor">{_numero(valor)}</span>{linha_delta}'
        f"</div>{bloco_nota}</div>"
    )


def linha_de_tiles(itens: list[dict], colunas: int = 4) -> None:
    """Fileira de blocos de número, em colunas do Streamlit."""
    if not itens:
        return
    for inicio in range(0, len(itens), colunas):
        faixa = itens[inicio : inicio + colunas]
        for coluna, item in zip(st.columns(len(faixa), gap="medium"), faixa):
            with coluna:
                escrever_html(st, tile(**item))


def barras_percentuais(
    itens: list[dict],
    titulo: str | None = None,
    maximo: float | None = None,
) -> None:
    """
    Barras de proporção, uma por item: `{"rotulo", "valor", "cor"?, "nota"?}`.

    `valor` é o número real; a largura é calculada contra `maximo` (ou o maior
    valor da lista). O número aparece escrito ao lado do rótulo — a barra é
    apoio visual, não a única forma de ler o dado.
    """
    if not itens:
        return

    teto = maximo if maximo is not None else max(
        (float(item["valor"]) for item in itens), default=0.0
    )
    linhas: list[str] = []

    for item in itens:
        valor = float(item["valor"])
        largura = 0.0 if teto <= 0 else max(3.0, min(100.0, valor / teto * 100))
        cor = item.get("cor", TURQUESA)
        sufixo = item.get("sufixo", "")
        nota = item.get("nota")
        bloco_nota = (
            f'<div style="font-size:.74rem;color:{TEXTO_FRACO};margin-top:.2rem">'
            f"{_html.escape(str(nota))}</div>"
            if nota
            else ""
        )
        linhas.append(
            f"<div>"
            f'<div class="lg-barra-rotulo">'
            f'<span>{_html.escape(str(item["rotulo"]))}</span>'
            f"<b>{_numero(valor)}{_html.escape(sufixo)}</b></div>"
            f'<div class="lg-barra-trilho">'
            f'<div class="lg-barra-preenchida" '
            f'style="width:{largura:.1f}%;background:linear-gradient(90deg,'
            f'{cor} 0%,{cor}CC 100%)"></div>'
            f"</div>{bloco_nota}</div>"
        )

    cabecalho = (
        f'<div class="lg-card-titulo">{_html.escape(titulo)}</div>' if titulo else ""
    )
    escrever_html(
        st,
        f'<div class="lg-card">{cabecalho}'
        f'<div class="lg-barras">{"".join(linhas)}</div></div>',
    )


def medidor_svg(
    valor: float,
    maximo: float,
    legenda: str = "",
    tamanho: int = 196,
    cor: str = TURQUESA,
    id_unico: str = "med",
) -> str:
    """
    Medidor em arco, desenhado em SVG.

    O arco cobre 270°, começando embaixo à esquerda. O valor aparece escrito no
    centro — quem não distingue a cor do arco lê o número do mesmo jeito.
    """
    maximo = max(float(maximo), 1e-9)
    fracao = min(1.0, max(0.0, float(valor) / maximo))

    raio = tamanho / 2 - 16
    centro = tamanho / 2
    abertura = 270.0
    inicio = 135.0  # graus, sentido horário a partir do eixo x

    def ponto(graus: float) -> tuple[float, float]:
        radianos = math.radians(graus)
        return (centro + raio * math.cos(radianos), centro + raio * math.sin(radianos))

    def arco(de: float, ate: float) -> str:
        x0, y0 = ponto(de)
        x1, y1 = ponto(ate)
        grande = 1 if abs(ate - de) > 180 else 0
        return f"M {x0:.2f} {y0:.2f} A {raio:.2f} {raio:.2f} 0 {grande} 1 {x1:.2f} {y1:.2f}"

    trilho = arco(inicio, inicio + abertura)
    preenchido = arco(inicio, inicio + abertura * fracao) if fracao > 0.002 else ""

    bloco_preenchido = (
        f'<path d="{preenchido}" stroke="url(#{id_unico}-grad)" stroke-width="16" '
        f'fill="none" stroke-linecap="round"/>'
        if preenchido
        else ""
    )
    bloco_legenda = (
        f'<text x="{centro}" y="{centro + 30}" text-anchor="middle" '
        f'font-size="12" fill="{TEXTO_FRACO}">{_html.escape(legenda)}</text>'
        if legenda
        else ""
    )

    return (
        f'<svg viewBox="0 0 {tamanho} {tamanho}" width="{tamanho}" '
        f'height="{tamanho}" role="img" '
        f'aria-label="{_html.escape(legenda or "medidor")}: {_numero(valor)} de {_numero(maximo)}">'
        f"<defs>"
        f'<linearGradient id="{id_unico}-grad" x1="0" y1="1" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{AZUL_OCEANO}"/>'
        f'<stop offset="100%" stop-color="{cor}"/>'
        f"</linearGradient></defs>"
        f'<path d="{trilho}" stroke="{BORDA}" stroke-width="16" fill="none" '
        f'stroke-linecap="round"/>'
        f"{bloco_preenchido}"
        f'<text x="{centro}" y="{centro + 8}" text-anchor="middle" '
        f'font-size="34" font-weight="800" fill="{TEXTO}">{_numero(valor)}</text>'
        f"{bloco_legenda}</svg>"
    )


def medidor(
    valor: float,
    maximo: float,
    titulo: str,
    legenda: str = "",
    nota: str | None = None,
    cor: str = TURQUESA,
    id_unico: str = "med",
) -> None:
    """Medidor dentro de um cartão, com título e nota explicativa."""
    bloco_nota = (
        f'<div style="font-size:.78rem;color:{TEXTO_FRACO};text-align:center">'
        f"{_html.escape(nota)}</div>"
        if nota
        else ""
    )
    escrever_html(
        st,
        f'<div class="lg-card">'
        f'<div class="lg-card-titulo">{_html.escape(titulo)}</div>'
        f'<div style="display:flex;justify-content:center">'
        f"{medidor_svg(valor, maximo, legenda, cor=cor, id_unico=id_unico)}</div>"
        f"{bloco_nota}</div>",
    )


def cartao_texto(titulo: str, corpo_html: str, icone: str = "") -> None:
    """Cartão genérico com título e conteúdo já em HTML."""
    prefixo = f"{icone} " if icone else ""
    escrever_html(
        st,
        f'<div class="lg-card">'
        f'<div class="lg-card-titulo">{prefixo}{_html.escape(titulo)}</div>'
        f"{corpo_html}</div>",
    )


def legenda_status(itens: list[dict]) -> str:
    """
    Legenda de status em HTML: ponto colorido + ícone + rótulo + contagem.

    O ícone e o texto acompanham a cor em todos os itens — é a codificação
    secundária exigida para status.
    """
    partes: list[str] = []
    for item in itens:
        partes.append(
            f'<div style="display:flex;align-items:center;gap:.5rem;'
            f'padding:.3rem 0;border-bottom:1px solid {BORDA}">'
            f'<span style="width:10px;height:10px;border-radius:50%;'
            f'background:{item["cor"]};flex:none"></span>'
            f'<span style="flex:1;font-size:.88rem">{item["icone"]} '
            f'{_html.escape(str(item["rotulo"]))}</span>'
            f'<b style="color:{TEXTO};font-variant-numeric:tabular-nums">'
            f'{_numero(item["total"])}</b></div>'
        )
    return f'<div style="background:{SUPERFICIE};border-radius:12px">{"".join(partes)}</div>'
