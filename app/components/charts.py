"""
Construtores de gráficos (Plotly).

Regras seguidas em todos os gráficos:
  * **nunca dois eixos y**. Duas medidas de escalas diferentes viram dois
    gráficos, não um gráfico de eixo duplo;
  * série única usa um matiz só; séries categóricas usam a ordem fixa da
    paleta, limitada a cinco — a sexta em diante é agregada em "Outros";
  * a cor nunca carrega sozinha a informação: há legenda quando existem duas ou
    mais séries e rótulo direto nas barras;
  * magnitude usa rampa de um matiz do claro ao escuro, nunca arco-íris;
  * quando não há dados, o gráfico não é desenhado: a função devolve `None` e a
    página exibe um estado vazio explicativo;
  * texto (eixos, rótulos, legendas) usa cor de texto, não a cor da série.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.styles.theme import (
    CINZA_BORDA,
    CINZA_TEXTO,
    COR_SERIE_UNICA,
    LIMITE_SERIES_CATEGORICAS,
    RAMPA_SEQUENCIAL,
    SEQUENCIA_GRAFICOS,
    estilo_status,
    layout_plotly,
)

CONFIG_PLOTLY = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
    "locale": "pt-BR",
}

_EIXO = {
    "showgrid": True,
    "gridcolor": CINZA_BORDA,
    "gridwidth": 1,
    "zeroline": False,
    "linecolor": CINZA_BORDA,
    "tickfont": {"color": CINZA_TEXTO, "size": 11},
    "title": {"font": {"color": CINZA_TEXTO, "size": 11}},
}


def _eixo(titulo: str | None = None, grade: bool = True) -> dict:
    eixo = dict(_EIXO)
    eixo["showgrid"] = grade
    if titulo:
        eixo["title"] = {"text": titulo, "font": {"color": CINZA_TEXTO, "size": 11}}
    else:
        eixo["title"] = None
    return eixo


def exibir(figura: go.Figure | None, mensagem_vazia: str = "Sem dados para este gráfico.") -> None:
    """Renderiza a figura ou um estado vazio explicativo."""
    from app.components.ui import estado_vazio

    if figura is None:
        estado_vazio(mensagem_vazia, "Ajuste os filtros ou aguarde novos registros.", "📊")
        return
    st.plotly_chart(figura, use_container_width=True, config=CONFIG_PLOTLY)


def agrupar_outros(
    dados: pd.DataFrame,
    coluna_categoria: str,
    coluna_valor: str,
    limite: int = LIMITE_SERIES_CATEGORICAS,
) -> pd.DataFrame:
    """
    Mantém as `limite` maiores categorias e soma as demais em "Outros".

    Evita gerar cores novas para séries adicionais.
    """
    if dados.empty or len(dados) <= limite:
        return dados
    ordenado = dados.sort_values(coluna_valor, ascending=False)
    principais = ordenado.head(limite - 1).copy()
    resto = ordenado.iloc[limite - 1 :]
    linha_outros = pd.DataFrame(
        {
            coluna_categoria: [f"Outros ({len(resto)})"],
            coluna_valor: [int(resto[coluna_valor].sum())],
        }
    )
    return pd.concat([principais, linha_outros], ignore_index=True)


# ------------------------------------------------------------------- barras
def barras(
    dados: pd.DataFrame,
    coluna_categoria: str,
    coluna_valor: str,
    titulo: str | None = None,
    horizontal: bool = False,
    altura: int = 340,
    cor: str = COR_SERIE_UNICA,
    cores_por_categoria: dict[str, str] | None = None,
    rotulo_valor: str = "Registros",
) -> go.Figure | None:
    """
    Barras de série única, com o valor rotulado em cada barra.

    `cores_por_categoria` é usado quando a categoria é um status (paleta
    reservada); nesse caso cada barra recebe a cor do seu status.
    """
    if dados is None or dados.empty or dados[coluna_valor].sum() == 0:
        return None

    categorias = dados[coluna_categoria].astype(str).tolist()
    valores = dados[coluna_valor].tolist()
    cores = (
        [cores_por_categoria.get(categoria, cor) for categoria in categorias]
        if cores_por_categoria
        else cor
    )

    figura = go.Figure(
        go.Bar(
            x=valores if horizontal else categorias,
            y=categorias if horizontal else valores,
            orientation="h" if horizontal else "v",
            marker={"color": cores, "line": {"width": 0}},
            text=valores,
            textposition="outside",
            textfont={"color": CINZA_TEXTO, "size": 11},
            cliponaxis=False,
            hovertemplate=f"<b>%{{{'y' if horizontal else 'x'}}}</b><br>"
            f"{rotulo_valor}: %{{{'x' if horizontal else 'y'}}}<extra></extra>",
        )
    )
    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = _eixo(rotulo_valor if horizontal else None, grade=horizontal)
    layout["yaxis"] = _eixo(None if horizontal else rotulo_valor, grade=not horizontal)
    layout["showlegend"] = False  # série única: o título já a identifica
    layout["bargap"] = 0.28
    if horizontal:
        layout["yaxis"]["autorange"] = "reversed"
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


def barras_percentuais(
    dados: pd.DataFrame,
    coluna_categoria: str,
    coluna_valor: str,
    titulo: str | None = None,
    altura: int = 360,
) -> go.Figure | None:
    """Barras horizontais de 0 a 100% — usado no painel de qualidade dos dados."""
    if dados is None or dados.empty:
        return None
    limpo = dados.dropna(subset=[coluna_valor])
    if limpo.empty:
        return None

    valores = limpo[coluna_valor].tolist()
    figura = go.Figure(
        go.Bar(
            x=valores,
            y=limpo[coluna_categoria].astype(str).tolist(),
            orientation="h",
            marker={"color": COR_SERIE_UNICA},
            text=[f"{valor:.1f}%" for valor in valores],
            textposition="outside",
            textfont={"color": CINZA_TEXTO, "size": 11},
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:.1f}% dos registros<extra></extra>",
        )
    )
    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = {**_eixo("% dos registros"), "range": [0, 105]}
    layout["yaxis"] = {**_eixo(None, grade=False), "autorange": "reversed"}
    layout["showlegend"] = False
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


# -------------------------------------------------------------------- linhas
def linha_temporal(
    dados: pd.DataFrame,
    coluna_x: str,
    colunas_series: list[str],
    titulo: str | None = None,
    altura: int = 340,
    rotulo_y: str = "Registros",
) -> go.Figure | None:
    """
    Série temporal com uma ou mais séries na **mesma** unidade e mesmo eixo.

    Com duas ou mais séries, a legenda é obrigatória (identidade nunca só por
    cor) e o hover é unificado por ponto do eixo x.
    """
    if dados is None or dados.empty:
        return None
    series_validas = [coluna for coluna in colunas_series if coluna in dados.columns]
    if not series_validas or dados[series_validas].to_numpy().sum() == 0:
        return None

    figura = go.Figure()
    for indice, coluna in enumerate(series_validas):
        figura.add_trace(
            go.Scatter(
                x=dados[coluna_x],
                y=dados[coluna],
                name=coluna,
                mode="lines+markers",
                line={"width": 2, "color": SEQUENCIA_GRAFICOS[indice % len(SEQUENCIA_GRAFICOS)]},
                marker={"size": 8},
                hovertemplate=f"{coluna}: %{{y}}<extra></extra>",
            )
        )

    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = _eixo(None, grade=False)
    layout["yaxis"] = {**_eixo(rotulo_y), "rangemode": "tozero"}
    layout["hovermode"] = "x unified"
    layout["showlegend"] = len(series_validas) >= 2
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


def multiplas_series_temporais(
    dados: pd.DataFrame,
    coluna_x: str,
    coluna_serie: str,
    coluna_valor: str,
    titulo: str | None = None,
    altura: int = 360,
) -> go.Figure | None:
    """
    Comparação de regiões ao longo do tempo (formato longo).

    Mantém no máximo cinco séries — as demais são somadas em "Outros", em vez
    de receberem cores novas.
    """
    if dados is None or dados.empty:
        return None

    totais = (
        dados.groupby(coluna_serie)[coluna_valor].sum().sort_values(ascending=False)
    )
    principais = list(totais.head(LIMITE_SERIES_CATEGORICAS - 1).index)
    copia = dados.copy()
    if len(totais) > LIMITE_SERIES_CATEGORICAS:
        copia[coluna_serie] = copia[coluna_serie].where(
            copia[coluna_serie].isin(principais), "Outros"
        )
    agregado = copia.groupby([coluna_x, coluna_serie], as_index=False)[coluna_valor].sum()

    ordem = principais + (["Outros"] if len(totais) > LIMITE_SERIES_CATEGORICAS else [])
    figura = go.Figure()
    for indice, nome in enumerate(ordem):
        recorte = agregado[agregado[coluna_serie] == nome].sort_values(coluna_x)
        if recorte.empty:
            continue
        figura.add_trace(
            go.Scatter(
                x=recorte[coluna_x],
                y=recorte[coluna_valor],
                name=str(nome),
                mode="lines+markers",
                line={"width": 2, "color": SEQUENCIA_GRAFICOS[indice % len(SEQUENCIA_GRAFICOS)]},
                marker={"size": 7},
                hovertemplate=f"{nome}: %{{y}}<extra></extra>",
            )
        )
    if not figura.data:
        return None

    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = _eixo(None, grade=False)
    layout["yaxis"] = {**_eixo("Registros"), "rangemode": "tozero"}
    layout["hovermode"] = "x unified"
    layout["showlegend"] = True
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


# --------------------------------------------------------------------- rosca
def rosca_status(
    registros: list[dict],
    titulo: str | None = None,
    altura: int = 330,
) -> go.Figure | None:
    """
    Distribuição por status, com a paleta reservada de status.

    Cada fatia traz ícone, rótulo e percentual — a cor é reforço, não a
    informação.
    """
    if not registros:
        return None
    total = sum(item.get("total", 0) for item in registros)
    if total == 0:
        return None

    rotulos, valores, cores = [], [], []
    for item in registros:
        estilo = estilo_status(item.get("status"))
        rotulos.append(f"{estilo['icone']} {estilo['rotulo']}")
        valores.append(item.get("total", 0))
        cores.append(estilo["cor"])

    figura = go.Figure(
        go.Pie(
            labels=rotulos,
            values=valores,
            hole=0.58,
            marker={"colors": cores, "line": {"color": "#FFFFFF", "width": 2}},
            textinfo="percent",
            textfont={"size": 12, "color": "#FFFFFF"},
            hovertemplate="<b>%{label}</b><br>%{value} registros (%{percent})<extra></extra>",
            sort=False,
        )
    )
    layout = layout_plotly(titulo, altura)
    layout["showlegend"] = True
    layout["annotations"] = [
        {
            "text": f"<b>{total}</b><br><span style='font-size:11px'>registros</span>",
            "x": 0.5,
            "y": 0.5,
            "showarrow": False,
            "font": {"size": 20, "color": CINZA_TEXTO},
        }
    ]
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


# ---------------------------------------------------------------- histograma
def histograma(
    dados_histograma: dict,
    titulo: str | None = None,
    rotulo_x: str = "Faixa",
    altura: int = 340,
) -> go.Figure | None:
    """Histograma a partir do dicionário produzido por `analytics.histograma`."""
    if not dados_histograma or not dados_histograma.get("disponivel"):
        return None

    classes = dados_histograma["classes"]
    contagens = dados_histograma["contagens"]
    figura = go.Figure(
        go.Bar(
            x=classes,
            y=contagens,
            marker={"color": COR_SERIE_UNICA},
            text=contagens,
            textposition="outside",
            textfont={"color": CINZA_TEXTO, "size": 11},
            cliponaxis=False,
            hovertemplate=f"{rotulo_x} %{{x}}<br>%{{y}} registros<extra></extra>",
        )
    )
    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = _eixo(rotulo_x, grade=False)
    layout["yaxis"] = _eixo("Registros")
    layout["showlegend"] = False
    layout["bargap"] = 0.08
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


# ------------------------------------------------------------ matriz/IA
def matriz_confusao(
    matriz: list[list[int]],
    rotulos: tuple[str, str] = ("Não peixe-leão", "Peixe-leão"),
    titulo: str | None = None,
    altura: int = 360,
) -> go.Figure | None:
    """
    Matriz de confusão como mapa de calor de matiz único.

    Cada célula exibe a contagem, de modo que a leitura não depende da cor.
    """
    if not matriz or len(matriz) != 2 or any(len(linha) != 2 for linha in matriz):
        return None
    if sum(sum(linha) for linha in matriz) == 0:
        return None

    textos = [
        [f"VN<br><b>{matriz[0][0]}</b>", f"FP<br><b>{matriz[0][1]}</b>"],
        [f"FN<br><b>{matriz[1][0]}</b>", f"VP<br><b>{matriz[1][1]}</b>"],
    ]
    figura = go.Figure(
        go.Heatmap(
            z=matriz,
            x=[f"Previsto: {rotulos[0]}", f"Previsto: {rotulos[1]}"],
            y=[f"Real: {rotulos[0]}", f"Real: {rotulos[1]}"],
            colorscale=[[0, RAMPA_SEQUENCIAL[0]], [1, RAMPA_SEQUENCIAL[-1]]],
            text=textos,
            texttemplate="%{text}",
            textfont={"size": 14},
            showscale=False,
            hovertemplate="%{y}<br>%{x}<br>%{z} imagens<extra></extra>",
        )
    )
    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = {**_eixo(None, grade=False), "side": "bottom"}
    layout["yaxis"] = {**_eixo(None, grade=False), "autorange": "reversed"}
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


def curvas_treinamento(historico: dict, altura: int = 340) -> tuple[go.Figure | None, go.Figure | None]:
    """
    Curvas de treinamento.

    Perda e métricas vão em **gráficos separados** porque têm escalas
    diferentes — nunca em eixo duplo.
    """
    if not historico or not historico.get("epocas"):
        return None, None

    epocas = historico["epocas"]

    figura_perda = go.Figure()
    for indice, (chave, nome) in enumerate(
        (("perda_treino", "Perda — treino"), ("perda_validacao", "Perda — validação"))
    ):
        if historico.get(chave):
            figura_perda.add_trace(
                go.Scatter(
                    x=epocas,
                    y=historico[chave],
                    name=nome,
                    mode="lines+markers",
                    line={"width": 2, "color": SEQUENCIA_GRAFICOS[indice]},
                    marker={"size": 7},
                    hovertemplate=f"{nome}: %{{y:.4f}}<extra></extra>",
                )
            )
    layout = layout_plotly("Curva de perda por época", altura)
    layout["xaxis"] = _eixo("Época", grade=False)
    layout["yaxis"] = {**_eixo("Perda"), "rangemode": "tozero"}
    layout["hovermode"] = "x unified"
    layout["showlegend"] = True
    figura_perda.update_layout(**{k: v for k, v in layout.items() if v is not None})

    figura_metricas = go.Figure()
    series = (
        ("acuracia_treino", "Acurácia — treino"),
        ("acuracia_validacao", "Acurácia — validação"),
        ("f1_validacao", "F1 — validação"),
    )
    for indice, (chave, nome) in enumerate(series):
        if historico.get(chave):
            figura_metricas.add_trace(
                go.Scatter(
                    x=epocas,
                    y=historico[chave],
                    name=nome,
                    mode="lines+markers",
                    line={"width": 2, "color": SEQUENCIA_GRAFICOS[indice]},
                    marker={"size": 7},
                    hovertemplate=f"{nome}: %{{y:.4f}}<extra></extra>",
                )
            )
    layout2 = layout_plotly("Métricas por época", altura)
    layout2["xaxis"] = _eixo("Época", grade=False)
    layout2["yaxis"] = {**_eixo("Valor"), "range": [0, 1.02]}
    layout2["hovermode"] = "x unified"
    layout2["showlegend"] = True
    figura_metricas.update_layout(**{k: v for k, v in layout2.items() if v is not None})

    return (
        figura_perda if figura_perda.data else None,
        figura_metricas if figura_metricas.data else None,
    )


def distribuicao_scores_por_classe(
    scores: list[dict], titulo: str | None = None, altura: int = 340
) -> go.Figure | None:
    """
    Distribuição dos scores, separada por resultado atribuído.

    Caixas (box plot) com os pontos sobrepostos: mostram onde o modelo fica
    confiante e onde fica indeciso, inclusive quantos pontos sustentam cada
    grupo.
    """
    if not scores:
        return None

    from app.styles.theme import estilo_classe_ia

    por_classe: dict[str, list[float]] = {}
    for item in scores:
        por_classe.setdefault(str(item.get("classe")), []).append(float(item["score"]))
    if not por_classe:
        return None

    figura = go.Figure()
    for classe, valores in por_classe.items():
        estilo = estilo_classe_ia(classe)
        figura.add_trace(
            go.Box(
                y=valores,
                name=f"{estilo['icone']} {estilo['rotulo']} (n={len(valores)})",
                marker={"color": estilo["cor"], "size": 6},
                boxpoints="all",
                jitter=0.4,
                pointpos=0,
                line={"width": 2},
                hovertemplate="score %{y:.3f}<extra></extra>",
            )
        )
    layout = layout_plotly(titulo, altura)
    layout["xaxis"] = _eixo(None, grade=False)
    layout["yaxis"] = {**_eixo("Score do modelo"), "range": [0, 1.02]}
    layout["showlegend"] = len(por_classe) >= 2
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


def metricas_por_limiar(por_limiar: list[dict], altura: int = 340) -> go.Figure | None:
    """Precisão, revocação e F1 em função do limiar — todas na mesma escala 0–1."""
    if not por_limiar:
        return None
    limiares = [item["limiar"] for item in por_limiar]
    figura = go.Figure()
    for indice, (chave, nome) in enumerate(
        (("precisao", "Precisão"), ("revocacao", "Revocação"), ("f1", "F1"))
    ):
        figura.add_trace(
            go.Scatter(
                x=limiares,
                y=[item[chave] for item in por_limiar],
                name=nome,
                mode="lines",
                line={"width": 2, "color": SEQUENCIA_GRAFICOS[indice]},
                hovertemplate=f"{nome}: %{{y:.3f}}<extra></extra>",
            )
        )
    layout = layout_plotly("Desempenho por limiar de decisão", altura)
    layout["xaxis"] = _eixo("Limiar", grade=False)
    layout["yaxis"] = {**_eixo("Valor"), "range": [0, 1.02]}
    layout["hovermode"] = "x unified"
    layout["showlegend"] = True
    figura.update_layout(**{k: v for k, v in layout.items() if v is not None})
    return figura


def barras_clusters(clusters: list, titulo: str | None = None, altura: int = 340) -> go.Figure | None:
    """Tamanho de cada agrupamento espacial identificado pelo DBSCAN."""
    if not clusters:
        return None
    dados = pd.DataFrame(
        {
            "Área": [cluster.nome for cluster in clusters],
            "Registros": [cluster.quantidade for cluster in clusters],
        }
    )
    return barras(
        dados, "Área", "Registros", titulo=titulo, horizontal=True, altura=altura
    )
