"""Dashboard 3 — análise científica e ambiental (exploração de dados)."""

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
    barras_clusters,
    barras_percentuais,
    exibir,
    histograma,
    linha_temporal,
    multiplas_series_temporais,
)
from app.components.filters import barra_de_filtros, resumo_filtros
from app.components.ui import (
    banner_demonstracao,
    linha_kpis,
    ressalva_cientifica,
    rodape_institucional,
    titulo_secao,
)
from app.styles.theme import TURQUESA
from src.database import queries
from src.security.permissions import Permissao, tem_permissao
from src.services.analytics import exportar_csv, painel_cientifico
from src.services.spatial import agrupar_ocorrencias, evolucao_por_cluster

sessao = proteger(Permissao.VER_DASHBOARD_CIENTIFICO, "Análise científica")

faixa_especialista(
    sessao,
    "Análise científica e ambiental",
    "Distribuições temporal, batimétrica, de habitat e espacial, com "
    "indicadores de completude e exportação em CSV.",
)

filtros = barra_de_filtros(prefixo="dc", expandido=False)
st.caption(resumo_filtros(filtros))

painel = painel_cientifico(filtros)
completude = painel["completude"]

banner_demonstracao(
    quantidade=queries.kpis_gerais(filtros)["demonstrativos"],
    visivel=filtros.inclui_demonstracao,
)

if completude["total"] == 0:
    from app.components.ui import estado_vazio

    estado_vazio(
        "Nenhum registro no recorte selecionado.",
        "Amplie o período ou remova filtros para explorar os dados.",
        "🔬",
    )
    rodape_institucional()
    st.stop()

# ------------------------------------------------------------- indicadores
linha_kpis(
    [
        {
            "rotulo": "Registros analisáveis",
            "valor": completude["total"],
            "nota": "no recorte atual",
        },
        {
            "rotulo": "Com localização válida",
            "valor": completude["com_coordenadas"],
            "nota": f"{completude['pct_coordenadas']}% do total",
        },
        {
            "rotulo": "Com fotografia",
            "valor": completude["com_imagem"],
            "nota": f"{completude['pct_imagem']}% do total",
        },
        {
            "rotulo": "Campos completos (média)",
            "valor": round(
                sum(
                    valor
                    for valor in (
                        completude["pct_coordenadas"],
                        completude["pct_imagem"],
                        completude["pct_profundidade"],
                        completude["pct_habitat"],
                        completude["pct_quantidade"],
                    )
                    if valor is not None
                )
                / 5,
                1,
            ),
            "nota": "média dos cinco campos",
            "formato": "{:.1f}%",
            "cor_borda": TURQUESA,
        },
    ]
)

resumo_profundidade = painel["resumo_profundidade"]
resumo_quantidade = painel["resumo_quantidade"]
linha_kpis(
    [
        {
            "rotulo": "Profundidade mediana",
            "valor": resumo_profundidade.get("mediana"),
            "nota": f"n = {resumo_profundidade['n']} registros informados",
            "formato": "{:.1f} m",
        },
        {
            "rotulo": "Profundidade máxima",
            "valor": resumo_profundidade.get("maximo"),
            "nota": "valor informado mais profundo",
            "formato": "{:.1f} m",
        },
        {
            "rotulo": "Quantidade mediana observada",
            "valor": resumo_quantidade.get("mediana"),
            "nota": f"n = {resumo_quantidade['n']} registros informados",
            "formato": "{:.1f}",
        },
        {
            "rotulo": "Pendentes de validação",
            "valor": completude["pct_pendente"],
            "nota": "do recorte atual",
            "formato": "{:.1f}%",
        },
    ]
)
st.caption(
    "Campos não informados são **descartados** das estatísticas, nunca "
    "substituídos por zero. O `n` de cada indicador mostra quantos registros o "
    "sustentam."
)

# --------------------------------------------------------- 1. temporal
st.divider()
titulo_secao(
    "Gráfico 1 — Distribuição temporal",
    "Registros por mês do avistamento, e comparação entre estados.",
)
exibir(
    linha_temporal(painel["mensal"], "Mês", ["Registros", "Confirmados"]),
    "Série temporal insuficiente.",
)

if st.toggle("Comparar estados ao longo do tempo", value=False, key="dc_comparar"):
    exibir(
        multiplas_series_temporais(
            painel["mensal_por_estado"], "Mês", "Estado", "Registros"
        ),
        "Sem dados suficientes por estado.",
    )
    st.caption(
        "Até cinco estados são mostrados individualmente; os demais são somados "
        "em “Outros”."
    )

# ------------------------------------------------- 2 e 3. profundidade/habitat
st.divider()
coluna_profundidade, coluna_habitat = st.columns(2)

with coluna_profundidade:
    titulo_secao("Gráfico 2 — Distribuição por profundidade")
    exibir(
        histograma(
            painel["histograma_profundidade"],
            rotulo_x="Profundidade (m)",
        ),
        "Nenhum registro informou profundidade neste recorte.",
    )
    if resumo_profundidade.get("disponivel"):
        st.caption(
            f"n = {resumo_profundidade['n']} | "
            f"mín {resumo_profundidade['minimo']} m · "
            f"Q1 {resumo_profundidade['quartil_1']} m · "
            f"mediana {resumo_profundidade['mediana']} m · "
            f"Q3 {resumo_profundidade['quartil_3']} m · "
            f"máx {resumo_profundidade['maximo']} m. "
            f"Classes de {painel['histograma_profundidade']['largura_classe']:.0f} m. "
            f"{completude['total'] - resumo_profundidade['n']} registro(s) sem "
            "profundidade informada foram excluídos deste gráfico."
        )

with coluna_habitat:
    titulo_secao("Gráfico 3 — Tipo de habitat")
    exibir(
        barras(painel["por_habitat"], "Habitat", "Registros", horizontal=True, altura=340),
        "Nenhum registro informou habitat neste recorte.",
    )
    st.caption(
        "“Não informado” é mantido como categoria própria — o sistema não "
        "atribui habitat a quem não informou."
    )

# ------------------------------------------------------------ 4. horário
st.divider()
titulo_secao(
    "Gráfico 4 — Distribuição por horário",
    "Hora do avistamento informada pelo usuário (não a hora de cadastro).",
)
exibir(barras(painel["por_hora"], "Hora", "Registros"), "Sem horários registrados.")
st.caption(
    "A concentração em determinadas horas reflete o horário em que as pessoas "
    "estão na água, e não necessariamente o padrão de atividade da espécie."
)

# ---------------------------------------------------------- 5. qualidade
st.divider()
titulo_secao(
    "Gráfico 5 — Qualidade dos dados",
    "Percentual de preenchimento dos campos relevantes para análise.",
)
exibir(
    barras_percentuais(painel["qualidade"], "Indicador", "Percentual"),
    "Sem registros para avaliar completude.",
)

# ------------------------------------------------------------ 6. espacial
st.divider()
titulo_secao(
    "Gráfico 6 — Análise espacial (DBSCAN)",
    "Agrupamento geográfico dos registros com métrica haversine.",
)

coluna_raio, coluna_minimo = st.columns(2)
with coluna_raio:
    raio = st.slider("Raio de vizinhança (km)", 5, 100, 25, 5, key="dc_eps")
with coluna_minimo:
    minimo = st.slider("Mínimo de registros por agrupamento", 2, 10, 3, 1, key="dc_min")

pontos = queries.dados_geograficos(
    filtros, publico=not tem_permissao(sessao, Permissao.VER_COORDENADAS_PRECISAS)
)
agrupamento = agrupar_ocorrencias(pontos, eps_km=float(raio), minimo_amostras=int(minimo))

if not agrupamento.executado:
    st.info(agrupamento.motivo)
else:
    coluna_grafico, coluna_detalhes = st.columns([3, 2])
    with coluna_grafico:
        exibir(barras_clusters(agrupamento.clusters, "Registros por agrupamento"))
    with coluna_detalhes:
        st.markdown(
            f"**{agrupamento.quantidade_clusters}** agrupamento(s) · "
            f"**{agrupamento.ruido}** ponto(s) isolado(s) (ruído) · "
            f"**{agrupamento.total_pontos}** pontos analisados  \n"
            f"Parâmetros: eps = {agrupamento.eps_km} km, "
            f"min_samples = {agrupamento.minimo_amostras}  \n"
            f"Biblioteca: {agrupamento.biblioteca}"
        )
        import pandas as pd

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Área": cluster.nome,
                        "Registros": cluster.quantidade,
                        "Confirmados": cluster.confirmados,
                        "Raio (km)": cluster.raio_maximo_km,
                        "UFs": ", ".join(cluster.estados) or "—",
                    }
                    for cluster in agrupamento.clusters
                ]
            ),
            use_container_width=True,
            hide_index=True,
            height=240,
        )

    evolucao = evolucao_por_cluster(agrupamento, pontos)
    if evolucao:
        import pandas as pd

        titulo_secao("Evolução temporal por área identificada")
        exibir(
            multiplas_series_temporais(
                pd.DataFrame(evolucao).rename(
                    columns={"area": "Área", "mes": "Mês", "total": "Registros"}
                ),
                "Mês",
                "Área",
                "Registros",
            ),
            "Sem série temporal por área.",
        )

    st.warning(f"⚠️ {agrupamento.ressalva}")

# ---------------------------------------------------------- exportação
st.divider()
titulo_secao("Exportação dos dados filtrados")

if tem_permissao(sessao, Permissao.EXPORTAR_DADOS):
    conteudo, nome_arquivo = exportar_csv(filtros, sessao)
    coluna_botao, coluna_nota = st.columns([1, 2])
    with coluna_botao:
        st.download_button(
            "⬇️ Baixar CSV do recorte atual",
            data=conteudo,
            file_name=nome_arquivo,
            mime="text/csv",
            use_container_width=True,
        )
    with coluna_nota:
        precisas = tem_permissao(sessao, Permissao.EXPORTAR_COORDENADAS_PRECISAS)
        st.caption(
            f"{len(conteudo.splitlines()) - 6} registro(s). Coordenadas "
            f"{'**precisas**' if precisas else '**arredondadas**'} conforme o seu "
            "perfil. O arquivo traz cabeçalho com data de geração, aviso sobre "
            "dados de demonstração e a ressalva de viés de observação. "
            "Nenhum dado de contato é exportado."
        )
else:
    st.info("Seu perfil não tem permissão de exportação.")

ressalva_cientifica()
rodape_institucional()
