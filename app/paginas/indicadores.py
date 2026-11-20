"""
Painel público — a visão geral que qualquer pessoa vê, sem login.

O que esta página mostra é deliberadamente o recorte aberto: números agregados,
posição aproximada e a situação da validação. O que ela **não** mostra —
coordenada precisa, fila de revisão, desempenho do modelo, auditoria — está na
área de monitoramento, atrás de login, porque depende de quem está olhando.

Dados de demonstração ficam de fora desta página por construção: o filtro
considera apenas registros de usuários e importações de fontes documentadas.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.board import (
    barras_percentuais,
    cartao_texto,
    legenda_status,
    linha_de_tiles,
    medidor,
)
from app.components.charts import exibir, linha_temporal
from app.components.maps import mapa_ocorrencias
from app.components.tables import tabela_ocorrencias
from app.components.ui import (
    estado_vazio,
    hero,
    ressalva_cientifica,
    rodape_institucional,
    secao,
)
from app.styles.theme import AZUL_OCEANO, LARANJA_ALERTA, TURQUESA, estilo_status
from src.database import queries
from src.database.queries import Filtros
from src.database.schema import TipoDado
from src.services.analytics import serie_mensal_completa

hero(
    "Painel público",
    "Os números abertos do monitoramento colaborativo do peixe-leão no "
    "litoral brasileiro. Sem login, sem cadastro.",
    selos=[
        "Sem dados de demonstração",
        "Posição aproximada (~1 km)",
        "Atualiza a cada registro",
    ],
    com_ilustracao=True,
)

filtros = Filtros(tipos_dado=[str(TipoDado.REAL), str(TipoDado.IMPORTADO)])
kpis = queries.kpis_gerais(filtros)

if kpis["total"] == 0:
    estado_vazio(
        "Ainda não há registros reais na base.",
        "Os indicadores aparecem assim que o primeiro avistamento for registrado. "
        "Os painéis internos podem ser testados com dados de demonstração.",
        "🌊",
    )
    if st.button("📷 Registrar o primeiro avistamento", type="primary", key="ind_vazio"):
        st.switch_page("paginas/registrar.py")
    rodape_institucional()
    st.stop()

# ============================================================ blocos de número
linha_de_tiles(
    [
        {
            "rotulo": "Avistamentos registrados",
            "valor": kpis["total"],
            "icone": "📍",
            "cor": AZUL_OCEANO,
        },
        {
            "rotulo": "Confirmados por avaliador",
            "valor": kpis["confirmados"],
            "icone": "✅",
            "cor": "#E06A6A",
            "nota": "validação humana, nunca automática",
        },
        {
            "rotulo": "Pendentes de validação",
            "valor": kpis["pendentes"],
            "icone": "⏳",
            "cor": LARANJA_ALERTA,
        },
        {
            "rotulo": "Municípios alcançados",
            "valor": kpis["municipios"],
            "icone": "🗺️",
            "cor": TURQUESA,
            "nota": f"em {kpis['estados']} estado(s)",
        },
    ]
)

st.markdown("")

# ================================================= série temporal + proporções
coluna_serie, coluna_estados = st.columns([1.55, 1], gap="medium")

with coluna_serie:
    secao("Evolução", "Registros por mês")
    exibir(
        linha_temporal(serie_mensal_completa(filtros), "Mês", ["Registros", "Confirmados"]),
        "Sem série temporal suficiente.",
    )
    st.caption(
        "A linha conta a **data do avistamento** informada, não a data de "
        "cadastro. Meses sem registro aparecem com zero apenas dentro do "
        "intervalo observado."
    )

with coluna_estados:
    por_estado = queries.total_por_estado(filtros)[:5]
    if por_estado:
        barras_percentuais(
            [
                {
                    "rotulo": str(linha["estado"] or "—"),
                    "valor": linha["total"],
                    "cor": TURQUESA,
                }
                for linha in por_estado
            ],
            titulo="🏖️ Estados com mais registros",
        )
    st.caption(
        "Mais registros não significa mais peixes: significa mais gente "
        "olhando e notificando naquele trecho de litoral."
    )

# ======================================================== medidor + status + mapa
coluna_medidor, coluna_status = st.columns([1, 1.25], gap="medium")

with coluna_medidor:
    medidor(
        round(float(kpis["percentual_validado"]), 1),
        100,
        "⚖️ Validação concluída",
        legenda="% do total elegível",
        nota=(
            f"Tempo mediano entre o cadastro e a decisão: "
            f"{kpis['tempo_mediano_revisao_horas']:.1f} h"
            if kpis.get("tempo_mediano_revisao_horas") is not None
            else "Ainda sem decisões suficientes para calcular o tempo mediano."
        ),
        id_unico="g_validacao",
    )

with coluna_status:
    contagens = queries.contagem_por_status(filtros)
    cartao_texto(
        "Situação dos registros",
        legenda_status(
            [
                {
                    "rotulo": estilo_status(item["status"])["rotulo"],
                    "icone": estilo_status(item["status"])["icone"],
                    "cor": estilo_status(item["status"])["cor"],
                    "total": item["total"],
                }
                for item in contagens
            ]
        ),
        icone="📋",
    )
    st.caption(
        "Todo registro entra como **pendente**. Só um avaliador humano muda "
        "esse estado — nem a IA nem uma importação confirmam nada sozinhas."
    )

# ============================================================================ mapa
st.markdown("")
secao(
    "Distribuição",
    "Onde os avistamentos foram notificados",
    "As posições são arredondadas para cerca de 1 km. A coordenada precisa "
    "existe no banco, mas não sai para a camada pública.",
)
pontos = queries.dados_geograficos(filtros, publico=True)
mapa_ocorrencias(pontos, publico=True, altura=520, chave="mapa_indicadores")

coluna_cta_mapa, coluna_cta_registrar = st.columns(2, gap="medium")
with coluna_cta_mapa:
    if st.button("🗺️ Abrir o mapa completo", use_container_width=True, key="ind_mapa"):
        st.switch_page("paginas/mapa.py")
with coluna_cta_registrar:
    if st.button(
        "📷 Registrar um avistamento",
        type="primary",
        use_container_width=True,
        key="ind_registrar",
    ):
        st.switch_page("paginas/registrar.py")

# ====================================================================== tabela
st.markdown("")
secao("Últimos registros", "Os 20 mais recentes")
tabela_ocorrencias(queries.registros_recentes(filtros, limite=20), altura=320)

cartao_texto(
    "Quer ver mais que isto?",
    (
        '<p style="font-size:.9rem;margin:0 0 .6rem 0">'
        "Coordenadas precisas, fila de validação, desempenho do modelo de IA e "
        "trilha de auditoria ficam na área de monitoramento, com login de "
        "pesquisador ou administrador."
        "</p>"
    ),
    icone="🔐",
)
if st.button("Ver os perfis de acesso", use_container_width=True, key="ind_acesso"):
    st.switch_page("paginas/acesso.py")

ressalva_cientifica()
rodape_institucional()
