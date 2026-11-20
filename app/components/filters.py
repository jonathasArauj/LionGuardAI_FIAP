"""
Filtros globais dos dashboards.

Um único componente alimenta todos os painéis: os mesmos `Filtros` são
passados a cards, gráficos, tabelas e mapa, o que garante que todos mostrem o
mesmo recorte simultaneamente (seção 5.1 do escopo).

Inclui o filtro de **procedência do dado**, que permite remover por completo os
registros de demonstração.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from src.database import queries
from src.database.queries import Filtros
from src.database.schema import OrigemRegistro, StatusOcorrencia, TipoDado
from src.services.analytics import (
    ROTULOS_ORIGEM,
    ROTULOS_STATUS,
    ROTULOS_TIPO_DADO,
)

PERIODOS = {
    "Últimos 30 dias": 30,
    "Últimos 90 dias": 90,
    "Últimos 12 meses": 365,
    "Todo o período": None,
    "Personalizado": -1,
}


def _intervalo_padrao(valores: dict) -> tuple[date | None, date | None]:
    minima = valores.get("data_minima")
    maxima = valores.get("data_maxima")
    try:
        inicio = datetime.strptime(minima, "%Y-%m-%d").date() if minima else None
        fim = datetime.strptime(maxima, "%Y-%m-%d").date() if maxima else None
    except (ValueError, TypeError):
        return None, None
    return inicio, fim


def barra_de_filtros(
    prefixo: str = "f",
    incluir_status: bool = True,
    incluir_procedencia: bool = True,
    expandido: bool = False,
) -> Filtros:
    """
    Renderiza os filtros e devolve o objeto `Filtros` correspondente.

    Os seletores são populados com os valores que existem no banco — nada de
    listas fixas que oferecem municípios sem registro.
    """
    valores = queries.valores_de_filtro()
    data_minima, data_maxima = _intervalo_padrao(valores)

    with st.expander("🔎 Filtros", expanded=expandido):
        coluna_periodo, coluna_datas = st.columns([1, 2])
        with coluna_periodo:
            escolha = st.selectbox(
                "Período", options=list(PERIODOS), index=3, key=f"{prefixo}_periodo"
            )

        dias = PERIODOS[escolha]
        inicio = fim = None
        if dias is None:
            inicio, fim = data_minima, data_maxima
        elif dias == -1:
            with coluna_datas:
                faixa = st.date_input(
                    "Intervalo de datas (do avistamento)",
                    value=(data_minima or date.today() - timedelta(days=365), data_maxima or date.today()),
                    key=f"{prefixo}_intervalo",
                    format="DD/MM/YYYY",
                )
            if isinstance(faixa, (list, tuple)) and len(faixa) == 2:
                inicio, fim = faixa
            elif isinstance(faixa, date):
                inicio = fim = faixa
        else:
            fim = date.today()
            inicio = fim - timedelta(days=dias)
            with coluna_datas:
                st.caption(
                    f"De **{inicio.strftime('%d/%m/%Y')}** a **{fim.strftime('%d/%m/%Y')}** "
                    "(data do avistamento)."
                )

        coluna_uf, coluna_municipio = st.columns(2)
        with coluna_uf:
            estados = st.multiselect(
                "Estado", options=valores["estados"], key=f"{prefixo}_estados"
            )
        with coluna_municipio:
            opcoes_municipios = valores["municipios"]
            municipios = st.multiselect(
                "Município", options=opcoes_municipios, key=f"{prefixo}_municipios"
            )

        status_escolhidos: list[str] = []
        if incluir_status:
            coluna_status, coluna_origem = st.columns(2)
            with coluna_status:
                rotulos = [ROTULOS_STATUS[str(s)] for s in StatusOcorrencia]
                selecionados = st.multiselect(
                    "Status da validação", options=rotulos, key=f"{prefixo}_status"
                )
                inverso = {ROTULOS_STATUS[str(s)]: str(s) for s in StatusOcorrencia}
                status_escolhidos = [inverso[rotulo] for rotulo in selecionados]
            with coluna_origem:
                rotulos_origem = [ROTULOS_ORIGEM[str(o)] for o in OrigemRegistro]
                selecionadas = st.multiselect(
                    "Origem do registro", options=rotulos_origem, key=f"{prefixo}_origens"
                )
                inverso_origem = {ROTULOS_ORIGEM[str(o)]: str(o) for o in OrigemRegistro}
                origens = [inverso_origem[rotulo] for rotulo in selecionadas]
        else:
            origens = []

        tipos_dado = [str(t) for t in TipoDado]
        if incluir_procedencia:
            rotulos_tipo = {ROTULOS_TIPO_DADO[str(t)]: str(t) for t in TipoDado}
            padrao = list(rotulos_tipo)
            escolhidos = st.multiselect(
                "Procedência do dado",
                options=padrao,
                default=padrao,
                key=f"{prefixo}_tipos",
                help=(
                    "Desmarque 'Demonstração' para ver apenas registros reais e "
                    "importados de fontes documentadas."
                ),
            )
            tipos_dado = [rotulos_tipo[rotulo] for rotulo in escolhidos] or [
                str(TipoDado.REAL)
            ]

        somente_coordenadas = st.toggle(
            "Apenas registros com coordenadas",
            value=False,
            key=f"{prefixo}_coord",
        )

    return Filtros(
        data_inicio=inicio.isoformat() if isinstance(inicio, date) else None,
        data_fim=fim.isoformat() if isinstance(fim, date) else None,
        estados=estados,
        municipios=municipios,
        status=status_escolhidos,
        origens=origens,
        tipos_dado=tipos_dado,
        somente_com_coordenadas=somente_coordenadas,
    )


def resumo_filtros(filtros: Filtros) -> str:
    """Texto curto descrevendo o recorte ativo — exibido acima dos gráficos."""
    partes = []
    if filtros.data_inicio or filtros.data_fim:
        inicio = filtros.data_inicio or "início"
        fim = filtros.data_fim or "hoje"
        partes.append(f"período {inicio} → {fim}")
    if filtros.estados:
        partes.append(f"{len(filtros.estados)} estado(s)")
    if filtros.municipios:
        partes.append(f"{len(filtros.municipios)} município(s)")
    if filtros.status:
        partes.append(f"status: {', '.join(ROTULOS_STATUS[s] for s in filtros.status)}")
    if filtros.origens:
        partes.append(f"{len(filtros.origens)} origem(ns)")
    if not filtros.inclui_demonstracao:
        partes.append("**sem** dados de demonstração")
    if filtros.somente_com_coordenadas:
        partes.append("apenas com coordenadas")
    return "Recorte atual: " + ("; ".join(partes) if partes else "todos os registros")
