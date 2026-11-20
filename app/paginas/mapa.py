"""Mapa público de avistamentos — Dashboard 2."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.auth_ui import sessao_atual
from app.components.charts import barras_clusters, exibir
from app.components.filters import barra_de_filtros, resumo_filtros
from app.components.maps import CAMADAS_BASE, mapa_ocorrencias
from app.components.tables import tabela_ocorrencias
from app.components.ui import (
    banner_demonstracao,
    cabecalho,
    linha_kpis,
    ressalva_cientifica,
    rodape_institucional,
    titulo_secao,
)
from src.database import queries
from src.security.permissions import Permissao, tem_permissao
from src.services.spatial import agrupar_ocorrencias

sessao = sessao_atual()
pode_ver_preciso = tem_permissao(sessao, Permissao.VER_COORDENADAS_PRECISAS)

cabecalho(
    "Mapa de avistamentos",
    "Distribuição espacial dos registros no litoral brasileiro. "
    + (
        "Você está autenticado: as coordenadas exibidas são as precisas."
        if pode_ver_preciso
        else "As posições são aproximadas (~1 km) para proteger o local exato."
    ),
)

filtros = barra_de_filtros(prefixo="mapa", expandido=False)
st.caption(resumo_filtros(filtros))

pontos = queries.dados_geograficos(filtros, publico=not pode_ver_preciso)
banner_demonstracao(
    quantidade=sum(1 for ponto in pontos if str(ponto.get("tipo_dado")) == "DEMO"),
    visivel=filtros.inclui_demonstracao
    and any(str(ponto.get("tipo_dado")) == "DEMO" for ponto in pontos),
)

# ------------------------------------------------------------- indicadores
contagem_status: dict[str, int] = {}
for ponto in pontos:
    chave = str(ponto.get("status"))
    contagem_status[chave] = contagem_status.get(chave, 0) + 1

linha_kpis(
    [
        {"rotulo": "Registros no mapa", "valor": len(pontos), "nota": "com coordenadas"},
        {"rotulo": "Confirmados", "valor": contagem_status.get("CONFIRMADO", 0)},
        {"rotulo": "Pendentes", "valor": contagem_status.get("PENDENTE", 0)},
        {
            "rotulo": "Municípios",
            "valor": len({ponto.get("municipio") for ponto in pontos if ponto.get("municipio")}),
        },
    ]
)

# ------------------------------------------------------------------- mapa
titulo_secao(
    "Visualização",
    "A camada padrão é a batimetria do oceano — em um projeto marinho, "
    "profundidade e plataforma continental dizem mais que um mapa de ruas.",
)

coluna_camada, coluna_agrupar, coluna_calor, coluna_areas = st.columns(
    [1.5, 1, 1, 1.2], gap="medium"
)
with coluna_camada:
    camada_base = st.selectbox(
        "Camada de base",
        list(CAMADAS_BASE),
        index=0,
        key="mapa_camada",
        help="Satélite ajuda a reconhecer o ponto; batimetria mostra o relevo submarino.",
    )
with coluna_agrupar:
    agrupar_marcadores = st.toggle(
        "Agrupar marcadores", value=True, key="mapa_cluster"
    )
with coluna_calor:
    mapa_de_calor = st.toggle("Mapa de calor", value=False, key="mapa_calor")
with coluna_areas:
    mostrar_areas = st.toggle(
        "Áreas (DBSCAN)", value=False, key="mapa_areas"
    )

if mapa_de_calor:
    st.caption(
        "⚠️ O mapa de calor mostra densidade **de notificações**, não densidade "
        "da espécie: áreas com mais mergulhadores e mais acesso à internet "
        "produzem mais registros."
    )

agrupamento = None
if mostrar_areas:
    coluna_raio, coluna_minimo = st.columns(2)
    with coluna_raio:
        raio = st.slider("Raio de vizinhança (km)", 5, 100, 25, 5, key="mapa_eps")
    with coluna_minimo:
        minimo = st.slider("Mínimo de registros por área", 2, 10, 3, 1, key="mapa_min")
    agrupamento = agrupar_ocorrencias(pontos, eps_km=float(raio), minimo_amostras=int(minimo))

mapa_ocorrencias(
    pontos,
    publico=not pode_ver_preciso,
    agrupar=agrupar_marcadores,
    clusters=agrupamento.clusters if (agrupamento and agrupamento.executado) else None,
    mapa_de_calor=mapa_de_calor,
    camada_base=camada_base,
    altura=600,
    chave="mapa_publico",
)

if agrupamento is not None:
    titulo_secao("Áreas de concentração de notificações")
    if not agrupamento.executado:
        st.info(agrupamento.motivo)
    else:
        st.markdown(
            f"**{agrupamento.quantidade_clusters} área(s)** identificadas por "
            f"{agrupamento.biblioteca}, com {agrupamento.ruido} registro(s) "
            f"isolado(s) (ruído), sobre {agrupamento.total_pontos} pontos."
        )
        exibir(
            barras_clusters(agrupamento.clusters, "Registros por área identificada"),
            "Nenhuma área com registros suficientes.",
        )
        st.warning(f"⚠️ {agrupamento.ressalva}")

# ---------------------------------------------------------------- tabela
st.divider()
titulo_secao("Registros do recorte atual")
tabela_ocorrencias(
    queries.registros_recentes(filtros, limite=50),
    altura=380,
)

ressalva_cientifica()
rodape_institucional()
