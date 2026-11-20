"""
Identidade visual do LionGuard AI — tema escuro "board".

A interface é um painel de monitoramento, e painéis de monitoramento são lidos
em ambientes escuros (centro de operação, cabine de barco, celular à noite no
costão). O tema escuro foi **escolhido e verificado**, não obtido invertendo o
tema claro: as cores dos gráficos e dos status foram revalidadas contra a
superfície escura (`SUPERFICIE`) com o validador de contraste e daltonismo.
Ver `docs/acessibilidade_cores.md`.

Acessibilidade: nenhuma informação é transmitida apenas por cor. Cada status
aparece com ícone e texto junto da cor, e as combinações de texto sobre fundo
seguem contraste mínimo de 4,5:1.
"""

from __future__ import annotations

# --------------------------------------------------------- superfícies
# Índigo profundo com brilho radial: o fundo do board.
FUNDO = "#120D33"
FUNDO_TOPO = "#1B1450"
SUPERFICIE = "#1C1757"  # cartões
SUPERFICIE_ALTA = "#262073"  # cartões em destaque, cabeçalhos de cartão
BORDA = "#352E86"
BORDA_FORTE = "#4B43AC"
BRILHO = "#5B4BD6"  # halo roxo do fundo

# ------------------------------------------------------------- tipografia
TEXTO = "#EDEEFF"
TEXTO_SECUNDARIO = "#B4B8E8"
TEXTO_FRACO = "#8186C2"

# ------------------------------------------------------------------ cores
# Os nomes abaixo são os da identidade do projeto; os valores são os passos
# calibrados para a superfície escura.
AZUL_MARINHO = "#0C0826"  # fundo mais profundo (texto sobre claro, sombras)
AZUL_OCEANO = "#1E9CB8"  # ciano-oceano, cor de apoio
TURQUESA = "#22A077"  # verde-mar: a cor de ação da interface
BRANCO = "#FFFFFF"
CINZA_CLARO = "#E8EAFF"
LARANJA_ALERTA = "#C8831A"

CINZA_TEXTO = TEXTO_SECUNDARIO
CINZA_BORDA = BORDA
VERMELHO = "#E06A6A"
AZUL_INFO = "#5B8BF5"
CINZA_NEUTRO = "#7D82A8"

VERDE_AGUARDANDO = "#22A077"

# Verde claro de destaque — usado só em superfícies grandes (barras, botões),
# nunca como cor de série em gráfico.
VERDE_DESTAQUE = "#34D399"

# Cor, ícone e rótulo de cada status — usados no mapa, nos cards e nas tabelas.
#
# As quatro primeiras seguem a seção 5.2 do escopo (pendente laranja,
# confirmado vermelho, rejeitado cinza, inconclusivo azul). `AGUARDANDO_INFO`
# é um status adicional do nosso fluxo operacional.
#
# Exceções documentadas, as mesmas do tema claro e pelo mesmo motivo:
#   * o cinza de "rejeitado" fica abaixo do piso de croma do validador — cinza
#     é o neutro que comunica "descartado";
#   * laranja ↔ vermelho e azul ↔ cinza ficam abaixo do piso de separação para
#     visão normal quando comparados todos contra todos.
# Nos dois casos a cor **nunca** aparece sozinha: a interface sempre desenha
# ícone e texto ao lado, que é a codificação secundária exigida para status.
ESTILO_STATUS: dict[str, dict[str, str]] = {
    "PENDENTE": {"cor": LARANJA_ALERTA, "icone": "⏳", "rotulo": "Pendente de validação"},
    "AGUARDANDO_INFO": {"cor": VERDE_AGUARDANDO, "icone": "❓", "rotulo": "Aguardando informações"},
    "CONFIRMADO": {"cor": VERMELHO, "icone": "✅", "rotulo": "Confirmado"},
    "REJEITADO": {"cor": CINZA_NEUTRO, "icone": "🚫", "rotulo": "Rejeitado"},
    "INCONCLUSIVO": {"cor": AZUL_INFO, "icone": "🔎", "rotulo": "Inconclusivo"},
}

ESTILO_CLASSE_IA: dict[str, dict[str, str]] = {
    "PEIXE_LEAO": {"cor": VERMELHO, "icone": "⚠️", "rotulo": "Possível peixe-leão"},
    "NAO_PEIXE_LEAO": {"cor": AZUL_OCEANO, "icone": "➖", "rotulo": "Não identificado"},
    "INCONCLUSIVO": {"cor": AZUL_INFO, "icone": "🔎", "rotulo": "Análise inconclusiva"},
    "SEM_MODELO": {"cor": CINZA_NEUTRO, "icone": "⚙️", "rotulo": "Identificação indisponível"},
    "ERRO": {"cor": CINZA_NEUTRO, "icone": "⚙️", "rotulo": "Erro na análise"},
}

# Sequência para séries categóricas nos gráficos Plotly.
#
# Ordem fixa — nunca reciclada. Cinco posições é o limite: uma sexta série é
# agrupada em "Outros" (ver `charts.agrupar_outros`) em vez de ganhar uma cor
# nova, porque hues adicionais deixam de ser distinguíveis.
#
# Verificada contra a superfície escura (`SUPERFICIE`): faixa de luminosidade,
# piso de croma, separação entre pares adjacentes em protanopia, deuteranopia
# e tritanopia, e contraste contra o fundo — todos aprovados. O par
# verde ↔ âmbar fica na faixa de piso em tritanopia (ΔE 6,3), o que exige
# codificação secundária; os gráficos sempre desenham legenda e rótulo direto.
SEQUENCIA_GRAFICOS = [
    "#1E9CB8",  # ciano-oceano
    "#C8831A",  # âmbar de alerta
    "#22A077",  # verde-mar
    "#7C83E8",  # índigo
    "#D85F9E",  # magenta
]

# Rampa sequencial (magnitude): um único matiz, do escuro ao claro — a direção
# se inverte no tema escuro, porque o claro é que avança sobre o fundo.
RAMPA_SEQUENCIAL = ["#15334A", "#16506B", "#19708F", "#1E9CB8", "#5FC4D8", "#A7E3EE"]

# Cor única para gráficos de série simples (a maioria dos painéis).
COR_SERIE_UNICA = "#1E9CB8"

LIMITE_SERIES_CATEGORICAS = len(SEQUENCIA_GRAFICOS)

# Grade e eixos dos gráficos: visíveis o bastante para ler, discretos o
# bastante para não competir com os dados.
GRADE = "rgba(180,184,232,0.14)"
EIXO = "rgba(180,184,232,0.34)"


def estilo_status(status: str | None) -> dict[str, str]:
    return ESTILO_STATUS.get(
        str(status), {"cor": CINZA_NEUTRO, "icone": "•", "rotulo": str(status or "—")}
    )


def estilo_classe_ia(classe: str | None) -> dict[str, str]:
    return ESTILO_CLASSE_IA.get(
        str(classe), {"cor": CINZA_NEUTRO, "icone": "•", "rotulo": str(classe or "—")}
    )


CSS = f"""
<style>
/* ===================================================== base e superfícies */
.stApp {{
    background:
        radial-gradient(1200px 620px at 78% -8%, {BRILHO}66 0%, transparent 62%),
        radial-gradient(900px 520px at 6% 4%, #3C2E9E55 0%, transparent 58%),
        linear-gradient(170deg, {FUNDO_TOPO} 0%, {FUNDO} 46%, #0D0926 100%);
    background-attachment: fixed;
    color: {TEXTO};
}}
.block-container {{
    padding-top: 1.4rem;
    padding-bottom: 3.5rem;
    max-width: 1500px;
}}
h1, h2, h3, h4, h5, h6 {{ color: {TEXTO}; letter-spacing: -.01em; }}
p, li, span, label, div {{ color: {TEXTO_SECUNDARIO}; }}
a {{ color: {AZUL_OCEANO}; }}
a:hover {{ color: #5FC4D8; }}
hr {{ border-color: {BORDA}; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* ------------------------------------------------------------ sidebar */
[data-testid="stSidebar"] {{
    background: linear-gradient(185deg, #241C6E 0%, #171148 100%);
    border-right: 1px solid {BORDA};
}}
[data-testid="stSidebar"] * {{ color: {TEXTO_SECUNDARIO}; }}
[data-testid="stSidebar"] h3 {{ color: {TEXTO}; }}

/* =============================================================== cartões */
.lg-card {{
    background: linear-gradient(168deg, {SUPERFICIE_ALTA} 0%, {SUPERFICIE} 70%);
    border: 1px solid {BORDA};
    border-radius: 18px;
    padding: 1.15rem 1.25rem;
    box-shadow: 0 18px 40px -26px #000000CC, inset 0 1px 0 #FFFFFF14;
    margin-bottom: .9rem;
}}
.lg-card-titulo {{
    display: flex; align-items: center; gap: .55rem;
    font-size: .95rem; font-weight: 700; color: {TEXTO};
    padding-bottom: .6rem; margin-bottom: .85rem;
    border-bottom: 1px solid {BORDA};
}}
.lg-card-icone {{
    width: 38px; height: 38px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    background: #FFFFFF12; border: 1px solid {BORDA};
    margin-bottom: .65rem;
}}

/* ============================================================ KPI / tiles */
.lg-kpi, .lg-tile {{
    background: linear-gradient(168deg, {SUPERFICIE_ALTA} 0%, {SUPERFICIE} 72%);
    border: 1px solid {BORDA};
    border-left: 3px solid {TURQUESA};
    border-radius: 16px;
    padding: .95rem 1.05rem;
    box-shadow: 0 16px 34px -26px #000000CC, inset 0 1px 0 #FFFFFF14;
    height: 100%;
}}
.lg-kpi-rotulo {{
    font-size: .74rem; text-transform: uppercase; letter-spacing: .09em;
    color: {TEXTO_FRACO}; font-weight: 700; margin-bottom: .3rem;
}}
.lg-kpi-valor {{
    font-size: 1.95rem; font-weight: 800; color: {TEXTO};
    line-height: 1.1; font-variant-numeric: tabular-nums;
}}
.lg-kpi-nota {{ font-size: .78rem; color: {TEXTO_FRACO}; margin-top: .22rem; }}
.lg-tile-linha {{ display: flex; align-items: baseline; gap: .5rem; }}
.lg-tile-delta {{ font-size: .86rem; font-weight: 700; }}

/* =========================================================== barras de % */
.lg-barras {{ display: flex; flex-direction: column; gap: .85rem; }}
.lg-barra-rotulo {{
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: .84rem; color: {TEXTO_SECUNDARIO}; margin-bottom: .3rem;
}}
.lg-barra-rotulo b {{ color: {TEXTO}; font-variant-numeric: tabular-nums; }}
.lg-barra-trilho {{
    height: 26px; border-radius: 8px; background: #FFFFFF14;
    border: 1px solid {BORDA}; overflow: hidden;
}}
.lg-barra-preenchida {{
    height: 100%; border-radius: 7px;
    display: flex; align-items: center; justify-content: flex-end;
    padding-right: .5rem; font-size: .78rem; font-weight: 800; color: #06241B;
    min-width: 2.2rem;
}}

/* ================================================================ hero */
.lg-hero {{
    position: relative; overflow: hidden;
    border-radius: 24px; padding: 2rem 2.1rem;
    background:
        radial-gradient(760px 320px at 88% 0%, {BRILHO}55 0%, transparent 60%),
        linear-gradient(140deg, #2A2180 0%, #1A1358 58%, #140F3D 100%);
    border: 1px solid {BORDA_FORTE};
    box-shadow: 0 30px 70px -40px #000000;
    margin-bottom: 1.1rem;
}}
.lg-hero-grade {{
    display: grid; grid-template-columns: 1.35fr .85fr;
    gap: 1.6rem; align-items: center;
}}
@media (max-width: 860px) {{
    .lg-hero-grade {{ grid-template-columns: 1fr; }}
    .lg-hero-arte {{ display: none; }}
}}
.lg-hero h1 {{
    font-size: 2.15rem; font-weight: 800; margin: .35rem 0 .55rem 0;
    line-height: 1.15; color: {BRANCO};
}}
.lg-hero p {{ font-size: 1.04rem; color: #D6D9FF; margin: 0; line-height: 1.6; }}
.lg-hero-arte {{ display: flex; justify-content: center; }}
.lg-hero-selos {{ display: flex; flex-wrap: wrap; gap: .45rem; margin-top: 1rem; }}
.lg-marca {{
    display: flex; align-items: center; gap: .6rem;
    font-weight: 800; letter-spacing: .04em; color: {BRANCO};
}}
.lg-selo {{
    display: inline-flex; align-items: center; gap: .3rem;
    background: #FFFFFF16; border: 1px solid #FFFFFF2E;
    color: #DFE2FF; border-radius: 999px;
    padding: .24rem .72rem; font-size: .76rem; font-weight: 600;
}}
.lg-sobrenome {{
    font-size: .74rem; text-transform: uppercase; letter-spacing: .12em;
    color: {TEXTO_FRACO}; font-weight: 700;
}}

/* ============================================================== foto hero */
.lg-foto-hero {{
    position: relative; border-radius: 20px; overflow: hidden;
    border: 1px solid {BORDA_FORTE};
    box-shadow: 0 26px 60px -34px #000000;
}}
.lg-foto-hero img {{ width: 100%; display: block; aspect-ratio: 16/10; object-fit: cover; }}
.lg-foto-hero figcaption {{
    position: absolute; left: 0; right: 0; bottom: 0;
    padding: .5rem .75rem; font-size: .7rem; color: #E6E8FF;
    background: linear-gradient(transparent, #0B0824E6);
}}
.lg-foto-hero figcaption a {{ color: #BFC4FF; }}

/* ================================================================ faixas */
.lg-faixa {{
    background: {SUPERFICIE}; border: 1px solid {BORDA};
    border-radius: 18px; padding: 1.15rem 1.3rem; margin: .8rem 0;
}}
.lg-faixa-escura {{
    background: linear-gradient(140deg, #2A2180 0%, #171148 100%);
    border: 1px solid {BORDA_FORTE}; color: #E3E5FF;
    border-radius: 18px; padding: 1.2rem 1.35rem; margin: .8rem 0;
}}
.lg-faixa-escura p, .lg-faixa-escura li {{ color: #D6D9FF; }}

/* ================================================= passos / stepper */
.lg-passos {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .8rem; }}
@media (max-width: 860px) {{ .lg-passos {{ grid-template-columns: 1fr 1fr; }} }}
.lg-passo {{
    background: {SUPERFICIE}; border: 1px solid {BORDA};
    border-radius: 16px; padding: 1rem; position: relative;
}}
.lg-passo b {{ color: {TEXTO}; display: block; margin-bottom: .25rem; }}
.lg-passo-num {{
    width: 26px; height: 26px; border-radius: 50%;
    background: {TURQUESA}; color: #06241B;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: .82rem; margin-bottom: .55rem;
}}
.lg-stepper {{
    display: flex; align-items: center; gap: .3rem;
    margin: .2rem 0 1.1rem 0; flex-wrap: wrap;
}}
.lg-stepper-item {{
    display: flex; align-items: center; gap: .4rem;
    font-size: .82rem; color: {TEXTO_FRACO}; font-weight: 600;
}}
.lg-stepper-bolha {{
    width: 24px; height: 24px; border-radius: 50%;
    background: #FFFFFF14; border: 1px solid {BORDA};
    display: flex; align-items: center; justify-content: center;
    font-size: .76rem; font-weight: 800; color: {TEXTO_FRACO};
}}
.lg-stepper-item.lg-ativo {{ color: {TEXTO}; }}
.lg-stepper-item.lg-ativo .lg-stepper-bolha {{
    background: {AZUL_OCEANO}; color: #04212A; border-color: {AZUL_OCEANO};
    box-shadow: 0 0 0 4px {AZUL_OCEANO}33;
}}
.lg-stepper-item.lg-feito {{ color: {VERDE_DESTAQUE}; }}
.lg-stepper-item.lg-feito .lg-stepper-bolha {{
    background: {TURQUESA}; color: #06241B; border-color: {TURQUESA};
}}
.lg-stepper-traco {{ flex: 1; height: 2px; background: {BORDA}; min-width: 14px; }}

/* ================================================================ perfis */
.lg-perfis {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .9rem; }}
@media (max-width: 860px) {{ .lg-perfis {{ grid-template-columns: 1fr; }} }}
.lg-perfil {{
    background: {SUPERFICIE}; border: 1px solid {BORDA};
    border-radius: 18px; padding: 1.1rem 1.2rem;
}}
.lg-perfil.lg-ativo {{ border-color: {TURQUESA}; box-shadow: 0 0 0 3px {TURQUESA}26; }}
.lg-perfil h4 {{ margin: .5rem 0 .3rem 0; font-size: 1rem; color: {TEXTO}; }}
.lg-perfil-chip {{
    display: inline-flex; align-items: center; gap: .35rem;
    border-radius: 999px; padding: .2rem .7rem;
    font-size: .74rem; font-weight: 800; letter-spacing: .04em;
}}
.lg-chip-publico {{ background: {AZUL_OCEANO}2E; color: #7FD6E8; border: 1px solid {AZUL_OCEANO}66; }}
.lg-chip-pesquisador {{ background: {TURQUESA}2E; color: {VERDE_DESTAQUE}; border: 1px solid {TURQUESA}66; }}
.lg-chip-admin {{ background: #7C83E82E; color: #AEB3FF; border: 1px solid #7C83E866; }}

/* ================================================================= galeria */
.lg-galeria {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
    gap: .75rem; margin: .4rem 0 .7rem 0;
}}
.lg-foto {{
    border-radius: 14px; overflow: hidden;
    border: 1px solid {BORDA}; background: {SUPERFICIE};
}}
.lg-foto img {{ width: 100%; height: 148px; object-fit: cover; display: block; }}
.lg-foto-credito {{ padding: .45rem .6rem; font-size: .68rem; color: {TEXTO_FRACO}; line-height: 1.35; }}
.lg-foto-credito a {{ color: {AZUL_OCEANO}; }}

/* ============================================================== comparação */
.lg-comparacao {{ display: grid; grid-template-columns: 1fr 1fr; gap: .9rem; margin: .5rem 0; }}
@media (max-width: 860px) {{ .lg-comparacao {{ grid-template-columns: 1fr; }} }}
.lg-sinal-positivo, .lg-sinal-negativo {{
    border-radius: 16px; padding: 1rem 1.15rem; border: 1px solid {BORDA};
}}
.lg-sinal-positivo {{ background: {TURQUESA}1A; border-color: {TURQUESA}59; }}
.lg-sinal-negativo {{ background: {LARANJA_ALERTA}1A; border-color: {LARANJA_ALERTA}59; }}
.lg-sinal-positivo h4, .lg-sinal-negativo h4 {{ margin: 0 0 .5rem 0; font-size: .95rem; }}
.lg-lista-marcada {{ margin: 0; padding-left: 1.1rem; }}
.lg-lista-marcada li {{ margin-bottom: .35rem; font-size: .9rem; line-height: 1.5; }}

/* ================================================================= avisos */
.lg-aviso, .lg-aviso-privacidade, .lg-aviso-demo, .lg-aviso-perigo {{
    border-radius: 14px; padding: .8rem 1rem; margin: .5rem 0;
    font-size: .88rem; border: 1px solid; line-height: 1.55;
}}
.lg-aviso {{ background: {AZUL_INFO}1A; border-color: {AZUL_INFO}59; color: #C3D4FF; }}
.lg-aviso-privacidade {{ background: {TURQUESA}1A; border-color: {TURQUESA}59; color: #A6E6CE; }}
.lg-aviso-demo {{ background: {LARANJA_ALERTA}22; border-color: {LARANJA_ALERTA}66; color: #F0C98A; }}
.lg-aviso-perigo {{
    background: {VERMELHO}1F; border-color: {VERMELHO}66; color: #FFC9C9;
    font-weight: 600;
}}

/* ================================================================ etiquetas */
.lg-etiqueta {{
    display: inline-flex; align-items: center; gap: .3rem;
    border-radius: 999px; padding: .16rem .62rem;
    font-size: .76rem; font-weight: 700;
}}
.lg-etiqueta-g {{ font-size: .88rem; padding: .3rem .9rem; }}

/* ================================================================== vazio */
.lg-vazio {{
    border: 1px dashed {BORDA_FORTE}; border-radius: 18px;
    padding: 2rem 1.4rem; text-align: center; background: #FFFFFF08;
}}

/* ================================================================ widgets */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
    border-radius: 12px; font-weight: 700; min-height: 2.9rem;
    border: 1px solid {BORDA_FORTE}; background: #FFFFFF10; color: {TEXTO};
    transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {{
    background: #FFFFFF1C; border-color: {TURQUESA}; color: {BRANCO};
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {VERDE_DESTAQUE} 0%, {TURQUESA} 100%);
    color: #06241B; border: none;
    box-shadow: 0 12px 26px -14px {TURQUESA};
}}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {{
    color: #06241B; box-shadow: 0 16px 30px -12px {TURQUESA};
}}
.lg-botao-destaque {{ font-weight: 800; }}

[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea, [data-baseweb="select"] > div {{
    background: #FFFFFF0F !important;
    border-color: {BORDA} !important;
    color: {TEXTO} !important;
    border-radius: 12px !important;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{ color: {TEXTO_FRACO} !important; }}

[data-testid="stExpander"] {{
    border: 1px solid {BORDA}; border-radius: 14px;
    background: {SUPERFICIE}; overflow: hidden;
}}
[data-testid="stExpander"] summary {{ color: {TEXTO}; font-weight: 600; }}
.lg-faq-p {{ font-weight: 600; }}

[data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stTable"] {{
    background: {SUPERFICIE}; border: 1px solid {BORDA};
    border-radius: 14px; padding: .4rem;
}}
[data-testid="stTabs"] button {{ color: {TEXTO_FRACO}; font-weight: 600; }}
[data-testid="stTabs"] button[aria-selected="true"] {{ color: {TEXTO}; }}

[data-testid="stAlert"] {{ border-radius: 14px; border: 1px solid {BORDA}; }}
code {{ background: #FFFFFF14; color: #C8CCFF; border-radius: 6px; }}
[data-testid="stCaptionContainer"] p {{ color: {TEXTO_FRACO}; }}

/* mapas e iframes herdam cantos arredondados */
iframe {{ border-radius: 16px; }}

/* ============================================================== utilidades */
.lg-gap {{ height: .9rem; }}
.lg-secao-titulo {{
    font-size: 1.12rem; font-weight: 800; color: {TEXTO};
    margin: .2rem 0 .2rem 0;
}}
.lg-secao-texto {{ color: {TEXTO_FRACO}; font-size: .9rem; margin-bottom: .7rem; }}
.lg-texto {{ color: {TEXTO}; }}
.lg-texto-claro {{ color: {TEXTO_SECUNDARIO}; }}
.lg-texto-fraco {{ color: {TEXTO_FRACO}; }}
.lg-superficie {{ background: {SUPERFICIE}; }}
.lg-borda {{ border: 1px solid {BORDA}; }}
.lg-borda-forte {{ border: 1px solid {BORDA_FORTE}; }}
.lg-r-sm {{ border-radius: 10px; }}
.lg-r-md {{ border-radius: 14px; }}
.lg-r-lg {{ border-radius: 18px; }}
.lg-r-xl {{ border-radius: 24px; }}
.lg-marinho {{ color: {TEXTO}; }}
.lg-oceano {{ color: {AZUL_OCEANO}; }}
.lg-turquesa {{ color: {TURQUESA}; }}
.lg-coral {{ color: {VERMELHO}; }}
.lg-transicao {{ transition: all .15s ease; }}

@keyframes lg-flutuar {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-9px); }}
}}
.lg-hero-arte svg {{ animation: lg-flutuar 7s ease-in-out infinite; }}
@media (prefers-reduced-motion: reduce) {{
    .lg-hero-arte svg {{ animation: none; }}
    .lg-transicao, .stButton > button {{ transition: none; }}
}}
</style>
"""


def aplicar_tema(st) -> None:
    """Injeta o CSS da identidade visual. Chamar uma vez por página."""
    st.markdown(CSS, unsafe_allow_html=True)


def layout_plotly(titulo: str | None = None, altura: int = 340) -> dict:
    """Layout padrão dos gráficos, consistente entre todos os painéis."""
    return {
        "title": {"text": titulo, "font": {"size": 15, "color": TEXTO}} if titulo else None,
        "height": altura,
        "margin": {"l": 10, "r": 10, "t": 46 if titulo else 18, "b": 10},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": TEXTO_SECUNDARIO, "size": 12},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": -0.25, "x": 0},
        "hoverlabel": {
            "bgcolor": SUPERFICIE_ALTA,
            "bordercolor": BORDA_FORTE,
            "font": {"color": TEXTO, "size": 12},
        },
        "xaxis": {"gridcolor": GRADE, "linecolor": EIXO, "zerolinecolor": GRADE},
        "yaxis": {"gridcolor": GRADE, "linecolor": EIXO, "zerolinecolor": GRADE},
    }
