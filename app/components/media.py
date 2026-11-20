"""
Mídia da área pública: galeria de fotografias e vídeos.

**Fotografias** vêm do iNaturalist em tempo de execução, apenas com licença
Creative Commons, e são exibidas sempre com autoria, licença e link para a
observação original — a atribuição é condição da licença. Sem internet, a
galeria dá lugar à ilustração própria do projeto, com explicação; nunca a uma
imagem improvisada.

**Vídeos** vêm de `data/conteudo_educativo.json`. A lista começa vazia de
propósito: o sistema não inventa endereços. A interface mostra como adicioná-los
— inclusive o vídeo demonstrativo que o grupo grava para a entrega.
"""

from __future__ import annotations

import html

import streamlit as st

from app.components.ui import estado_vazio
from app.styles.markup import escrever_html
from app.styles.ilustracoes import icone_svg, peixe_leao_svg
from src.data.conteudo import ConteudoEducativo, Video
from src.data.galeria import Foto, GaleriaIndisponivel, buscar_fotos, resumo_creditos


@st.cache_data(ttl=3600, show_spinner=False)
def _fotos_em_cache(limite: int, apenas_brasil: bool) -> list[dict]:
    """
    Busca as fotos uma vez por hora.

    O cache guarda dicionários simples porque o Streamlit precisa serializar o
    valor; a reconstrução em `Foto` acontece na leitura.
    """
    try:
        fotos = buscar_fotos(limite=limite, apenas_brasil=apenas_brasil)
    except GaleriaIndisponivel:
        return []
    return [
        {
            "url": foto.url,
            "url_miniatura": foto.url_miniatura,
            "autor": foto.autor,
            "licenca": foto.licenca,
            "url_licenca": foto.url_licenca,
            "especie": foto.especie,
            "url_observacao": foto.url_observacao,
            "local": foto.local,
            "observacao_id": foto.observacao_id,
        }
        for foto in fotos
    ]


def obter_fotos(limite: int = 8, apenas_brasil: bool = False) -> list[Foto]:
    return [Foto(**registro) for registro in _fotos_em_cache(limite, apenas_brasil)]


def galeria_fotos(
    limite: int = 8,
    apenas_brasil: bool = False,
    mostrar_creditos: bool = True,
) -> list[Foto]:
    """
    Grade de fotografias reais da espécie, com atribuição em cada imagem.

    Devolve as fotos exibidas, para quem chamar poder reaproveitá-las.
    """
    with st.spinner("Carregando fotografias licenciadas..."):
        fotos = obter_fotos(limite=limite, apenas_brasil=apenas_brasil)

    if not fotos:
        coluna_arte, coluna_texto = st.columns([1, 1.4], gap="medium")
        with coluna_arte:
            st.markdown(
                f'<div style="display:flex;justify-content:center">'
                f'{peixe_leao_svg(300, id_unico="semfoto")}</div>',
                unsafe_allow_html=True,
            )
        with coluna_texto:
            estado_vazio(
                "Não foi possível carregar as fotografias agora.",
                "A galeria busca imagens licenciadas do iNaturalist em tempo real "
                "e precisa de conexão. A ilustração ao lado é desenho do próprio "
                "projeto — não é fotografia da espécie.",
                "📷",
            )
        return []

    cartoes = []
    for foto in fotos:
        local = f" · {html.escape(foto.local)}" if foto.local else ""
        cartoes.append(
            f"""
            <figure class="lg-foto" style="margin:0">
                <img src="{html.escape(foto.url_miniatura)}" loading="lazy"
                     alt="Fotografia de {html.escape(foto.especie)}
                          por {html.escape(foto.autor)}">
                <figcaption class="lg-foto-credito">
                    <b>{html.escape(foto.especie)}</b>{local}<br>
                    © {html.escape(foto.autor)} ·
                    <a href="{html.escape(foto.url_licenca)}" target="_blank"
                       rel="noopener">{html.escape(foto.licenca_legivel)}</a> ·
                    <a href="{html.escape(foto.url_observacao)}" target="_blank"
                       rel="noopener">iNaturalist</a>
                </figcaption>
            </figure>
            """
        )
    st.markdown(f'<div class="lg-galeria">{"".join(cartoes)}</div>', unsafe_allow_html=True)

    if mostrar_creditos:
        st.caption(
            f"{resumo_creditos(fotos)} As imagens são carregadas direto da fonte, "
            "não redistribuídas por este projeto."
        )
    return fotos


def secao_videos(conteudo: ConteudoEducativo, colunas: int = 2) -> None:
    """
    Vídeos educativos cadastrados em `data/conteudo_educativo.json`.

    Quando não há nenhum, a seção explica como incluir em vez de mostrar um
    espaço vazio — e lembra que o vídeo da entrega é o primeiro candidato.
    """
    videos: list[Video] = conteudo.videos_validos

    if not videos:
        escrever_html(st, """
            <div class="lg-vazio">
                <div style="font-size:2rem;line-height:1">🎬</div>
                <p style="margin:.5rem 0 .2rem 0;font-weight:700">
                    Nenhum vídeo cadastrado ainda
                </p>
                <p style="margin:0;font-size:.88rem">
                    Esta seção é alimentada por <code>data/conteudo_educativo.json</code>.
                    Acrescente objetos na lista <code>videos</code> com
                    <code>titulo</code>, <code>url</code>, <code>descricao</code> e
                    <code>fonte</code>, e eles aparecem aqui.
                </p>
            </div>
            """)
        with st.expander("Como adicionar um vídeo"):
            st.markdown(
                "O arquivo não vem com vídeos preenchidos porque o sistema não "
                "inventa endereços. Para criar o arquivo já no formato correto:"
            )
            st.code(
                "python -c \"from src.data.conteudo import gravar_modelo; "
                'print(gravar_modelo())"',
                language="bash",
            )
            st.markdown("Depois é só editar a lista `videos`:")
            st.code(
                """{
  "videos": [
    {
      "titulo": "LionGuard AI — demonstração do sistema",
      "url": "https://youtu.be/SEU_VIDEO",
      "descricao": "Registro de um avistamento, validação e painéis.",
      "fonte": "Equipe do projeto"
    }
  ]
}""",
                language="json",
            )
        return

    for inicio in range(0, len(videos), colunas):
        bloco = videos[inicio : inicio + colunas]
        colunas_st = st.columns(len(bloco), gap="medium")
        for coluna, video in zip(colunas_st, bloco):
            with coluna:
                st.markdown(f"**{video.titulo}**")
                try:
                    st.video(video.url)
                except Exception:
                    st.warning(
                        "Não foi possível carregar este vídeo. "
                        f"Abra direto na fonte: {video.url}"
                    )
                legenda = " · ".join(
                    parte for parte in (video.descricao, video.fonte) if parte
                )
                if legenda:
                    st.caption(legenda)


def links_oficiais(conteudo: ConteudoEducativo, colunas: int = 2) -> None:
    """Cards com as fontes institucionais e bases de dados do projeto."""
    links = conteudo.links_oficiais
    if not links:
        return

    for inicio in range(0, len(links), colunas):
        bloco = links[inicio : inicio + colunas]
        colunas_st = st.columns(len(bloco), gap="medium")
        for coluna, link in zip(colunas_st, bloco):
            with coluna:
                escrever_html(st, f"""
                    <div class="lg-card">
                        <div style="display:flex;align-items:center;gap:.55rem">
                            <div class="lg-card-icone"
                                 style="width:36px;height:36px;border-radius:10px">
                                {icone_svg("lupa", 20)}
                            </div>
                            <span style="font-size:.74rem;font-weight:800;
                                         letter-spacing:.09em;text-transform:uppercase;
                                         color:#6B8795">
                                {html.escape(link.organizacao or "Fonte")}
                            </span>
                        </div>
                        <h4 style="margin:.6rem 0 .3rem 0">
                            <a href="{html.escape(link.url)}" target="_blank"
                               rel="noopener">{html.escape(link.titulo)}</a>
                        </h4>
                        <p>{html.escape(link.descricao)}</p>
                    </div>
                    """)


def guia_identificacao(conteudo: ConteudoEducativo) -> None:
    """Características de identificação, em cards com ícone."""
    from app.components.ui import cartoes_recurso

    if not conteudo.identificacao:
        return
    cartoes_recurso(
        [
            {
                "icone": item.icone,
                "titulo": item.caracteristica,
                "texto": item.descricao,
            }
            for item in conteudo.identificacao
        ],
        colunas=3,
    )
