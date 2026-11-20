"""
Tabelas com formatação consistente.

Datas em formato brasileiro, status com ícone e rótulo, scores em percentual e
procedência sempre visível. Quando não há linhas, exibe estado vazio em vez de
uma grade vazia.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.ui import estado_vazio
from app.styles.theme import estilo_classe_ia, estilo_status

COLUNAS_OCORRENCIA = {
    "protocolo": "Protocolo",
    "data_hora_avistamento": "Avistamento",
    "data_hora_cadastro": "Cadastro",
    "municipio": "Município",
    "estado": "UF",
    "status": "Status",
    "classe_ia": "Resultado da IA",
    "score_ia": "Score",
    "origem_registro": "Origem",
    "tipo_dado": "Procedência",
}


def formatar_data(valor) -> str:
    """ISO-8601 para `dd/mm/aaaa hh:mm`, tolerante a valores ausentes."""
    if valor is None or str(valor).strip() == "":
        return "—"
    texto = str(valor)
    try:
        data, _, hora = texto.partition("T")
        ano, mes, dia = data.split("-")
        return f"{dia}/{mes}/{ano}" + (f" {hora[:5]}" if hora else "")
    except ValueError:
        return texto


def formatar_status(valor) -> str:
    estilo = estilo_status(valor)
    return f"{estilo['icone']} {estilo['rotulo']}"


def formatar_classe_ia(valor) -> str:
    if valor is None or str(valor).strip() == "":
        return "— sem análise"
    estilo = estilo_classe_ia(valor)
    return f"{estilo['icone']} {estilo['rotulo']}"


def formatar_score(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    try:
        return f"{float(valor) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def tabela_ocorrencias(
    registros: list[dict],
    titulo: str | None = None,
    altura: int = 360,
    colunas: dict[str, str] | None = None,
) -> None:
    """Tabela de ocorrências com formatação pronta para leitura."""
    if titulo:
        st.markdown(f"**{titulo}**")
    if not registros:
        estado_vazio(
            "Nenhuma ocorrência neste recorte.",
            "Ajuste os filtros para ampliar a busca.",
            "📋",
        )
        return

    colunas = colunas or COLUNAS_OCORRENCIA
    linhas = []
    for registro in registros:
        linha = {}
        for chave, titulo_coluna in colunas.items():
            valor = registro.get(chave)
            if chave in ("data_hora_avistamento", "data_hora_cadastro", "criado_em"):
                linha[titulo_coluna] = formatar_data(valor)
            elif chave == "status":
                linha[titulo_coluna] = formatar_status(valor)
            elif chave == "classe_ia":
                linha[titulo_coluna] = formatar_classe_ia(valor)
            elif chave == "score_ia":
                linha[titulo_coluna] = formatar_score(valor)
            elif chave in ("origem_registro", "tipo_dado", "origem_localizacao", "habitat"):
                linha[titulo_coluna] = str(valor or "—").replace("_", " ").capitalize()
            else:
                linha[titulo_coluna] = valor if valor is not None else "—"
        linhas.append(linha)

    st.dataframe(
        pd.DataFrame(linhas),
        use_container_width=True,
        hide_index=True,
        height=altura,
    )


def tabela(
    dados: pd.DataFrame,
    titulo: str | None = None,
    altura: int | None = None,
    mensagem_vazia: str = "Sem dados para exibir.",
) -> None:
    """Exibe um DataFrame já formatado, tratando o caso vazio."""
    if titulo:
        st.markdown(f"**{titulo}**")
    if dados is None or dados.empty:
        estado_vazio(mensagem_vazia, None, "📋")
        return
    st.dataframe(dados, use_container_width=True, hide_index=True, height=altura)
