"""Dashboard 1 — visão geral do monitoramento (painel executivo)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.auth_ui import faixa_especialista, proteger
from app.components.charts import (
    barras,
    exibir,
    linha_temporal,
    rosca_status,
)
from app.components.filters import barra_de_filtros, resumo_filtros
from app.components.tables import tabela, tabela_ocorrencias
from app.components.ui import (
    banner_demonstracao,
    linha_kpis,
    ressalva_cientifica,
    rodape_institucional,
    titulo_secao,
)
from app.styles.theme import LARANJA_ALERTA, TURQUESA, VERMELHO
from src.database import queries
from src.security.permissions import Permissao
from src.services.analytics import painel_geral

sessao = proteger(Permissao.VER_DASHBOARD_GERAL, "Visão geral do monitoramento")

faixa_especialista(
    sessao,
    "Visão geral do monitoramento",
    "Todos os números vêm de agregações sobre o banco, com os mesmos filtros "
    "aplicados ao mesmo tempo a blocos, gráficos e tabelas.",
)

filtros = barra_de_filtros(prefixo="dg", expandido=False)
st.caption(resumo_filtros(filtros))

painel = painel_geral(filtros)
kpis = painel["kpis"]

banner_demonstracao(
    quantidade=kpis["demonstrativos"],
    visivel=filtros.inclui_demonstracao and kpis["demonstrativos"] > 0,
)

# ------------------------------------------------------------------- KPIs
linha_kpis(
    [
        {
            "rotulo": "Total de avistamentos",
            "valor": kpis["total"],
            "nota": "ocorrências únicas cadastradas",
        },
        {
            "rotulo": "Confirmados",
            "valor": kpis["confirmados"],
            "nota": "confirmados por avaliador",
            "cor_borda": VERMELHO,
        },
        {
            "rotulo": "Pendentes",
            "valor": kpis["pendentes"],
            "nota": "aguardando revisão",
            "cor_borda": LARANJA_ALERTA,
        },
        {"rotulo": "Rejeitados", "valor": kpis["rejeitados"], "nota": "revisados e descartados"},
    ]
)
linha_kpis(
    [
        {
            "rotulo": "Municípios com registro",
            "valor": kpis["municipios"],
            "nota": f"em {kpis['estados']} estado(s)",
            "cor_borda": TURQUESA,
        },
        {
            "rotulo": "Novos no período",
            "valor": kpis["novos_no_periodo"],
            "nota": "pela data de cadastro",
        },
        {
            "rotulo": "Registros validados",
            "valor": kpis["percentual_validado"],
            "nota": "decisões finais ÷ total",
            "formato": "{:.1f}%",
        },
        {
            "rotulo": "Tempo mediano de revisão",
            "valor": kpis["tempo_mediano_revisao_horas"],
            "nota": "horas até a 1ª decisão",
            "formato": "{:.1f}",
        },
    ]
)

with st.expander("Como cada indicador é calculado"):
    st.markdown(
        """
- **Total de avistamentos** — ocorrências únicas que satisfazem os filtros.
- **Confirmados / Pendentes / Rejeitados / Inconclusivos** — contagem por
  `status`. "Confirmado" significa decisão humana de avaliador, nunca
  classificação automática.
- **Novos no período** — registros cuja **data de cadastro** cai na janela de
  datas (os demais indicadores usam a **data do avistamento**).
- **Registros validados (%)** — (confirmados + rejeitados + inconclusivos) ÷
  total do recorte.
- **Tempo mediano de revisão** — mediana de
  `data_primeira_decisao − data_hora_cadastro`, considerando apenas ocorrências
  que já tiveram decisão final. Mediana, e não média, porque a distribuição é
  assimétrica.
- Indicadores sem dados suficientes aparecem como **—**, nunca como zero.
        """
    )

# ---------------------------------------------------------------- gráficos
st.divider()
coluna_esquerda, coluna_direita = st.columns(2)

with coluna_esquerda:
    titulo_secao("Avistamentos por estado")
    exibir(
        barras(painel["por_estado"], "Estado", "Registros"),
        "Nenhum registro por estado neste recorte.",
    )

with coluna_direita:
    titulo_secao("Distribuição por status")
    exibir(
        rosca_status(queries.contagem_por_status(filtros)),
        "Nenhum registro para distribuir por status.",
    )

titulo_secao("Evolução temporal dos registros")
exibir(
    linha_temporal(painel["mensal"], "Mês", ["Registros", "Confirmados"]),
    "Série temporal insuficiente para este recorte.",
)
st.caption(
    "Eixo horizontal: mês do **avistamento**. As duas séries estão na mesma "
    "unidade (número de registros) e compartilham um único eixo vertical."
)

st.divider()
coluna_municipios, coluna_origem = st.columns(2)

with coluna_municipios:
    titulo_secao("Municípios com mais registros")
    exibir(
        barras(painel["por_municipio"], "Município", "Registros", horizontal=True, altura=380),
        "Nenhum município com registros neste recorte.",
    )

with coluna_origem:
    titulo_secao("Registros por origem")
    exibir(
        barras(painel["por_origem"], "Origem", "Registros", horizontal=True, altura=380),
        "Sem informação de origem neste recorte.",
    )

st.divider()
coluna_procedencia, coluna_tabela = st.columns([1, 2])
with coluna_procedencia:
    titulo_secao("Procedência do dado")
    tabela(
        painel["por_tipo_dado"],
        mensagem_vazia="Sem registros no recorte.",
    )
    st.caption(
        "Registros de demonstração aparecem como categoria própria e podem ser "
        "removidos no filtro “Procedência do dado”."
    )
with coluna_tabela:
    titulo_secao("Últimos avistamentos")
    tabela_ocorrencias(queries.registros_recentes(filtros, limite=10), altura=330)

ressalva_cientifica()
rodape_institucional()
