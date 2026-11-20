"""
Página inicial pública — porta de entrada do cidadão.

Princípio de composição: a página é rica em informação, mas **a ação vem
primeiro**. O botão de registrar aparece na primeira tela, antes de qualquer
conteúdo educativo, e volta duas vezes ao longo da rolagem — depois do guia de
identificação (quando a pessoa acabou de comparar o que viu) e no encerramento.
Conteúdo serve à decisão de registrar; não a substitui.

As fotografias são reais, vindas do iNaturalist com licença Creative Commons e
atribuição visível. A ilustração do cabeçalho é desenho do próprio projeto.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.maps import mapa_ocorrencias
from app.components.media import (
    galeria_fotos,
    guia_identificacao,
    links_oficiais,
    obter_fotos,
    secao_videos,
)
from app.components.tables import tabela_ocorrencias
from app.components.ui import (
    aviso_perigo,
    comparacao,
    faq,
    hero,
    linha_kpis,
    lista_marcada,
    passos,
    rodape_institucional,
    secao,
)
from app.styles.markup import escrever_html
from app.styles.theme import LARANJA_ALERTA, TURQUESA, VERMELHO
from src.data.conteudo import carregar_conteudo
from src.database import queries
from src.database.queries import Filtros
from src.database.schema import TipoDado
from src.services.analytics import indicadores_publicos
from src.services.sightings import ServicoAvistamentos

conteudo = carregar_conteudo(RAIZ / "data" / "conteudo_educativo.json")


def _botoes_de_acao(sufixo: str, mostrar_mapa: bool = True) -> None:
    """Par de botões da ação principal. Repetido ao longo da página."""
    if mostrar_mapa:
        coluna_registrar, coluna_mapa = st.columns([2, 1], gap="medium")
    else:
        coluna_registrar, coluna_mapa = st.columns([1, 0.001])

    with coluna_registrar:
        if st.button(
            "📷  Registrar avistamento",
            type="primary",
            use_container_width=True,
            key=f"cta_registrar_{sufixo}",
        ):
            st.switch_page("paginas/registrar.py")

    if mostrar_mapa:
        with coluna_mapa:
            if st.button(
                "🗺️  Ver o mapa",
                use_container_width=True,
                key=f"cta_mapa_{sufixo}",
            ):
                st.switch_page("paginas/mapa.py")


# ============================================================ 1. abertura
hero(
    "Viu um peixe-leão? Registre em um minuto.",
    "Tire uma foto, deixe a inteligência artificial fazer a análise preliminar "
    "e marque o local. Seu registro vira dado estruturado para quem monitora o "
    "litoral — <b>sem cadastro, sem formulário longo</b>.",
    selos=[
        "🔓 Sem login",
        "⏱️ Leva 1 minuto",
        "🤖 Análise por IA",
        "🔒 Local aproximado no mapa público",
    ],
)

_botoes_de_acao("topo")
st.caption(
    "Nenhum dado pessoal é solicitado. A foto tem os metadados removidos antes "
    "de ser salva, e no mapa público a posição aparece arredondada em cerca de 1 km."
)

# Uma fotografia real logo no alto: a ilustração do topo é desenho do projeto,
# e quem precisa reconhecer o animal precisa ver o animal.
_destaques = obter_fotos(limite=3)
if _destaques:
    for _coluna, _foto in zip(st.columns(len(_destaques), gap="medium"), _destaques):
        with _coluna:
            escrever_html(
                st,
                f"""
                <figure class="lg-foto-hero" style="margin:0">
                    <img src="{_foto.url_miniatura}" loading="lazy"
                         alt="Fotografia de {_foto.especie} por {_foto.autor}">
                    <figcaption>
                        © {_foto.autor} ·
                        <a href="{_foto.url_licenca}" target="_blank" rel="noopener">
                            {_foto.licenca_legivel}</a> ·
                        <a href="{_foto.url_observacao}" target="_blank" rel="noopener">
                            iNaturalist</a>
                    </figcaption>
                </figure>
                """,
            )
    st.caption(
        "Fotografias de observações reais publicadas no iNaturalist sob licença "
        "Creative Commons, carregadas direto da fonte, com autoria e licença."
    )

# ======================================================== 2. como funciona
st.divider()
secao(
    "Como funciona",
    "Quatro passos, nenhuma burocracia",
    "Cada etapa só aparece quando a anterior está resolvida — você nunca encara "
    "um formulário inteiro de uma vez no celular.",
)
passos(
    [
        {
            "titulo": "Fotografe",
            "texto": "Pela câmera ou escolhendo da galeria. Fotografe de longe: "
            "nunca se aproxime do animal.",
        },
        {
            "titulo": "A IA analisa",
            "texto": "Uma rede neural dá uma indicação preliminar — possível "
            "peixe-leão, não identificado ou inconclusivo.",
        },
        {
            "titulo": "Marque o local",
            "texto": "Pelo GPS do aparelho ou tocando no mapa. Se o GPS falhar, "
            "o registro continua possível.",
        },
        {
            "titulo": "Confirme",
            "texto": "Você recebe um protocolo e a ocorrência entra na fila de "
            "validação por um avaliador humano.",
        },
    ]
)

# ====================================================== 3. números públicos
indicadores = indicadores_publicos()
st.divider()
secao(
    "Panorama",
    "O que já foi registrado",
    "Somente registros de usuários e importações de fontes documentadas — "
    "dados de demonstração não entram nesta contagem.",
)

if indicadores["total"] == 0:
    escrever_html(st, """
        <div class="lg-vazio">
            <div style="font-size:2.1rem;line-height:1">🌊</div>
            <p style="margin:.5rem 0 .2rem 0;font-weight:700">
                Ainda não há avistamentos registrados por usuários
            </p>
            <p style="margin:0;font-size:.9rem">
                Seja a primeira pessoa a contribuir — os indicadores e o mapa
                passam a se alimentar a partir do primeiro registro.
            </p>
        </div>
        """)
else:
    linha_kpis(
        [
            {
                "rotulo": "Avistamentos registrados",
                "valor": indicadores["total"],
                "nota": "ocorrências únicas",
            },
            {
                "rotulo": "Confirmados por avaliador",
                "valor": indicadores["confirmados"],
                "nota": "revisados e confirmados",
                "cor_borda": VERMELHO,
            },
            {
                "rotulo": "Aguardando validação",
                "valor": indicadores["pendentes"],
                "nota": "na fila de revisão",
                "cor_borda": LARANJA_ALERTA,
            },
            {
                "rotulo": "Municípios alcançados",
                "valor": indicadores["municipios"],
                "nota": f"em {indicadores['estados']} estado(s)",
                "cor_borda": TURQUESA,
            },
        ]
    )
    st.caption(
        "“Confirmado” significa que um avaliador revisou o registro. Registros "
        "pendentes **não** constituem ocorrência cientificamente confirmada."
    )

# ==================================================== 4. a espécie, com fotos
st.divider()
secao(
    "A espécie",
    "Como reconhecer um peixe-leão",
    "Fotografias reais de observações publicadas com licença aberta. Compare "
    "com o que você viu — e, na dúvida, registre assim mesmo.",
)
galeria_fotos(limite=8)

st.markdown("")
guia_identificacao(conteudo)

st.markdown("")
comparacao(
    "✅ Sinais de que é peixe-leão",
    [
        "Nadadeiras peitorais abertas como leque, muito maiores que o corpo",
        "Espinhos dorsais longos, finos e <b>soltos nas pontas</b>",
        "Faixas verticais alternadas, claras e avermelhadas, até na cabeça",
        "Fica parado junto a tocas e estruturas, sem fugir de você",
    ],
    "⚠️ Costuma ser confundido com",
    conteudo.nao_confundir,
)

st.markdown("")
aviso_perigo(
    "<b>Não toque, não persiga e não tente capturar.</b> O peixe-leão tem "
    "espinhos venenosos e a picada é intensamente dolorosa. Fotografe de longe. "
    "Manejo e remoção são atribuição dos órgãos competentes e de profissionais "
    "autorizados. Em caso de acidente, procure atendimento médico."
)

st.markdown("")
_botoes_de_acao("meio")

# ======================================================== 5. por que importa
st.divider()
secao(
    "Por que importa",
    "Um avistamento registrado vale mais que um avistamento comentado",
)

coluna_texto, coluna_destaque = st.columns([1.3, 1], gap="large")
with coluna_texto:
    escrever_html(st, """
O peixe-leão (*Pterois volitans*) é nativo dos oceanos Índico e Pacífico. No
Atlântico ele é **invasor**: tem poucos predadores naturais, reproduz-se com
rapidez e come peixes juvenis — o que pressiona recifes, pesca artesanal e
turismo de mergulho.

O primeiro registro no Brasil é de **2014**; desde **2020** os registros se
tornaram frequentes, avançando pela costa. Em **setembro de 2026**, a Bahia já
contabilizava registros em pelo menos dez municípios. E em **14 de novembro de
2026** a espécie foi registrada pela primeira vez no Espírito Santo, na Ilha
Escalvada, em Guarapari — **por uma equipe de mergulho recreativo**, não por uma
rede oficial de monitoramento.

É esse o ponto. O Plano Emergencial do ICMBio reconhece que métodos padronizados
de monitoramento têm baixa probabilidade de detectar a espécie no início da
invasão — justamente quando detectar vale mais. Quem está na água vê primeiro.
        """
    )
with coluna_destaque:
    st.markdown(
        f"""
        <div class="lg-faixa-escura">
            <span class="lg-sobrenome">O que muda com o registro</span>
            {lista_marcada([
                "Vira <b>dado estruturado</b>: foto, coordenada, data e protocolo",
                "Entra em <b>validação humana</b>, com justificativa registrada",
                "Alimenta <b>mapas e indicadores</b> abertos",
                "Permite ver <b>onde</b> a invasão avança, e com que velocidade",
            ])}
        </div>
        """)
    if st.button(
        "Saber mais sobre a espécie", use_container_width=True, key="home_saber"
    ):
        st.switch_page("paginas/sobre_peixe_leao.py")

# ============================================================== 6. vídeos
st.divider()
secao(
    "Vídeos",
    "Veja antes de ir para a água",
    "Material em vídeo sobre identificação, riscos e o que fazer ao encontrar a "
    "espécie.",
)
secao_videos(conteudo)

# =============================================================== 7. mapa
st.divider()
secao(
    "Mapa",
    "Onde há registros",
    "Posições aproximadas em cerca de 1 km. Um registro pendente é uma "
    "notificação, não uma ocorrência confirmada.",
)

filtros_publicos = Filtros(tipos_dado=[str(TipoDado.REAL), str(TipoDado.IMPORTADO)])
pontos_publicos = queries.dados_geograficos(filtros_publicos, publico=True)

if pontos_publicos:
    mapa_ocorrencias(
        pontos_publicos,
        publico=True,
        agrupar=True,
        altura=430,
        chave="mapa_home",
    )
    coluna_mapa_botao, coluna_mapa_nota = st.columns([1, 2], gap="medium")
    with coluna_mapa_botao:
        if st.button("Abrir o mapa completo", use_container_width=True, key="home_mapa_full"):
            st.switch_page("paginas/mapa.py")
    with coluna_mapa_nota:
        st.caption(
            "No mapa completo você pode trocar a camada de base (batimetria, "
            "satélite), filtrar por período, estado e status, e ver as áreas de "
            "concentração de notificações."
        )
else:
    escrever_html(st, """
        <div class="lg-vazio">
            <div style="font-size:2.1rem;line-height:1">🗺️</div>
            <p style="margin:.5rem 0 .2rem 0;font-weight:700">
                O mapa ainda não tem pontos
            </p>
            <p style="margin:0;font-size:.9rem">
                Os marcadores aparecem assim que o primeiro avistamento for
                registrado.
            </p>
        </div>
        """)

# ================================================= 8. acompanhar protocolo
st.divider()
secao(
    "Acompanhamento",
    "Já registrou? Consulte seu protocolo",
    "Informe o código que você recebeu ao confirmar o avistamento.",
)

coluna_entrada, coluna_botao = st.columns([3, 1], gap="small")
with coluna_entrada:
    protocolo = st.text_input(
        "Protocolo",
        placeholder="LG-2026-XXXXXX",
        key="home_protocolo",
        label_visibility="collapsed",
    )
with coluna_botao:
    consultar = st.button("Consultar", use_container_width=True, key="home_consultar")

if consultar:
    if not protocolo.strip():
        st.warning("Digite o protocolo que você recebeu.")
    else:
        registro = ServicoAvistamentos().consultar_por_protocolo(protocolo)
        if registro is None:
            st.error(
                "Protocolo não encontrado. Confira os caracteres — o código tem o "
                "formato LG-ANO-XXXXXX."
            )
        else:
            tabela_ocorrencias(
                [registro],
                titulo="Situação do seu registro",
                altura=110,
                colunas={
                    "protocolo": "Protocolo",
                    "status": "Status",
                    "data_hora_avistamento": "Avistamento",
                    "municipio": "Município",
                    "estado": "UF",
                    "classe_ia": "Resultado da IA",
                    "score_ia": "Score",
                },
            )
            st.caption(
                "O status muda quando um avaliador revisa a ocorrência. Não há "
                "prazo garantido de revisão neste protótipo acadêmico."
            )

# ================================================================ 9. FAQ
st.divider()
secao("Dúvidas", "Perguntas frequentes")
faq(conteudo.perguntas)

# ============================================================ 10. fontes
st.divider()
secao(
    "Fontes",
    "Onde se informar oficialmente",
    "Esta plataforma é um protótipo acadêmico e não substitui os canais "
    "oficiais. Comunique também o órgão ambiental do seu estado.",
)
links_oficiais(conteudo)

# ========================================================= 11. chamada final
st.divider()
escrever_html(st, """
    <div class="lg-faixa-escura" style="text-align:center">
        <h2 style="margin:.2rem 0 .4rem 0">Viu um peixe-leão hoje?</h2>
        <p style="margin:0 auto;max-width:56ch">
            O registro leva um minuto e não pede cadastro. Quem está na água vê
            primeiro — e é isso que faz diferença na detecção precoce.
        </p>
    </div>
    """)
_botoes_de_acao("rodape", mostrar_mapa=False)

rodape_institucional()
