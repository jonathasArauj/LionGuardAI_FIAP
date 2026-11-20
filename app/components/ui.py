"""
Componentes visuais reutilizáveis.

Todo componente aqui é funcional: não há controle decorativo sem efeito
(regra 1 da seção 20 do escopo). Componentes que dependem de dados tratam
explicitamente o caso "sem dados", exibindo uma explicação em vez de um
gráfico vazio.
"""

from __future__ import annotations

import streamlit as st

from app.styles.markup import escrever_html
from app.styles.ilustracoes import (
    icone_svg,
    logo_svg,
    padrao_oceano_svg,
    peixe_leao_svg,
)
from app.styles.theme import (
    AZUL_OCEANO,
    estilo_classe_ia,
    estilo_status,
)


def hero(
    titulo: str,
    subtitulo: str | None = None,
    marca: str = "LionGuard AI",
    selos: list[str] | None = None,
    com_ilustracao: bool = True,
) -> None:
    """
    Cabeçalho principal da área pública.

    Traz a ilustração do peixe-leão desenhada pelo projeto, os selos de
    confiança e a chamada. A ilustração é decorativa e some em telas estreitas
    para não empurrar o botão de registro para fora da primeira tela — a ação
    vem antes da imagem.
    """
    selos_html = ""
    if selos:
        itens = "".join(f'<span class="lg-selo">{selo}</span>' for selo in selos)
        selos_html = f'<div class="lg-hero-selos">{itens}</div>'

    arte = (
        f'<div class="lg-hero-arte">{peixe_leao_svg(360, id_unico="hero")}</div>'
        if com_ilustracao
        else ""
    )

    escrever_html(st, f"""
        <div class="lg-hero">
            {padrao_oceano_svg("hero")}
            <div class="lg-hero-grade">
                <div>
                    <div class="lg-marca">{logo_svg(26)} {marca}</div>
                    <h1>{titulo}</h1>
                    {f"<p>{subtitulo}</p>" if subtitulo else ""}
                    {selos_html}
                </div>
                {arte}
            </div>
        </div>
        """)


def cabecalho(titulo: str, subtitulo: str | None = None, marca: str = "LionGuard AI") -> None:
    """
    Cabeçalho compacto, sem ilustração.

    Usado nas páginas internas e nos painéis, onde o conteúdo precisa de toda a
    altura disponível.
    """
    escrever_html(st, f"""
        <div class="lg-hero">
            {padrao_oceano_svg("int")}
            <div class="lg-marca">{logo_svg(24)} {marca}</div>
            <h1>{titulo}</h1>
            {f"<p>{subtitulo}</p>" if subtitulo else ""}
        </div>
        """)


def secao(
    sobrenome: str, titulo: str, texto: str | None = None, ancora: str | None = None
) -> None:
    """Cabeçalho de seção com sobretítulo, título e linha de apoio."""
    escrever_html(st, f"""
        <div {f'id="{ancora}"' if ancora else ""} style="margin:.4rem 0 .7rem 0">
            <span class="lg-sobrenome">{sobrenome}</span>
            <h2 class="lg-secao-titulo">{titulo}</h2>
            {f'<p class="lg-secao-texto">{texto}</p>' if texto else ""}
        </div>
        """)


def cartoes_recurso(itens: list[dict], colunas: int = 3) -> None:
    """
    Grade de cards com ícone, título e texto.

    Cada item aceita `icone` (nome de `ilustracoes.icone_svg`), `titulo` e
    `texto`.
    """
    for inicio in range(0, len(itens), colunas):
        bloco = itens[inicio : inicio + colunas]
        colunas_st = st.columns(len(bloco), gap="medium")
        for coluna, item in zip(colunas_st, bloco):
            with coluna:
                escrever_html(st, f"""
                    <div class="lg-card">
                        <div class="lg-card-icone">{icone_svg(item.get("icone", "lupa"))}</div>
                        <h4>{item["titulo"]}</h4>
                        <p>{item["texto"]}</p>
                    </div>
                    """)


def passos(itens: list[dict]) -> None:
    """Etapas numeradas do fluxo, em grade responsiva."""
    cartoes = "".join(
        f"""
        <div class="lg-passo">
            <h4>{item["titulo"]}</h4>
            <p>{item["texto"]}</p>
        </div>
        """
        for item in itens
    )
    st.markdown(f'<div class="lg-passos">{cartoes}</div>', unsafe_allow_html=True)


def stepper(etapas: list[str], atual: int) -> None:
    """
    Indicador de progresso do registro.

    `atual` é o índice da etapa em andamento (base 0). Etapas anteriores
    aparecem como concluídas, com marca de verificação — informação que não
    depende só de cor.
    """
    partes: list[str] = []
    for indice, nome in enumerate(etapas):
        if indice < atual:
            classe, bolha = "lg-feito", "✓"
        elif indice == atual:
            classe, bolha = "lg-ativo", str(indice + 1)
        else:
            classe, bolha = "", str(indice + 1)
        partes.append(
            f'<div class="lg-stepper-item {classe}">'
            f'<span class="lg-stepper-bolha">{bolha}</span>{nome}</div>'
        )
        if indice < len(etapas) - 1:
            partes.append('<div class="lg-stepper-traco"></div>')
    st.markdown(f'<div class="lg-stepper">{"".join(partes)}</div>', unsafe_allow_html=True)


def faixa_html(conteudo: str, escura: bool = False) -> None:
    """Bloco de destaque com conteúdo em HTML (sem widgets dentro)."""
    classe = "lg-faixa-escura" if escura else "lg-faixa"
    st.markdown(f'<div class="{classe}">{conteudo}</div>', unsafe_allow_html=True)


def lista_marcada(itens: list[str]) -> str:
    """HTML de uma lista com marcadores próprios."""
    elementos = "".join(f"<li>{item}</li>" for item in itens)
    return f'<ul class="lg-lista-marcada">{elementos}</ul>'


def comparacao(
    titulo_positivo: str,
    itens_positivos: list[str],
    titulo_negativo: str,
    itens_negativos: list[str],
) -> None:
    """Bloco lado a lado: o que indica a espécie e o que costuma ser confundido."""
    escrever_html(st, f"""
        <div class="lg-comparacao">
            <div class="lg-sinal-positivo">
                <h4>{titulo_positivo}</h4>
                {lista_marcada(itens_positivos)}
            </div>
            <div class="lg-sinal-negativo">
                <h4>{titulo_negativo}</h4>
                {lista_marcada(itens_negativos)}
            </div>
        </div>
        """)


def faq(perguntas: list) -> None:
    """
    Perguntas frequentes, cada uma em um bloco recolhível.

    Aceita objetos com `.pergunta`/`.resposta` ou dicionários equivalentes.
    """
    for item in perguntas:
        pergunta = getattr(item, "pergunta", None) or item.get("pergunta", "")
        resposta = getattr(item, "resposta", None) or item.get("resposta", "")
        with st.expander(pergunta):
            st.markdown(resposta)


def aviso_perigo(texto: str) -> None:
    """Aviso de segurança física, visualmente distinto dos demais."""
    st.markdown(f'<div class="lg-aviso-perigo">⚠️ {texto}</div>', unsafe_allow_html=True)


def titulo_secao(titulo: str, descricao: str | None = None) -> None:
    st.markdown(f"### {titulo}")
    if descricao:
        st.caption(descricao)


def kpi(
    rotulo: str,
    valor,
    nota: str | None = None,
    cor_borda: str = AZUL_OCEANO,
    formato: str = "{:,}",
) -> None:
    """
    Card de indicador.

    Valor `None` é exibido como "—" com uma nota explicativa: ausência de dado
    nunca aparece como zero.
    """
    if valor is None:
        texto = "—"
        nota = nota or "sem dados suficientes"
    elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
        texto = formato.format(valor).replace(",", ".")
    else:
        texto = str(valor)

    escrever_html(st, f"""
        <div class="lg-kpi" style="border-left-color:{cor_borda}">
            <div class="lg-kpi-rotulo">{rotulo}</div>
            <div class="lg-kpi-valor">{texto}</div>
            {f'<div class="lg-kpi-nota">{nota}</div>' if nota else ""}
        </div>
        """)


def linha_kpis(itens: list[dict], colunas_por_linha: int = 4) -> None:
    """
    Distribui cards de indicador em linhas.

    Cada item aceita: `rotulo`, `valor`, `nota`, `cor_borda`, `formato`.
    """
    for inicio in range(0, len(itens), colunas_por_linha):
        bloco = itens[inicio : inicio + colunas_por_linha]
        colunas = st.columns(len(bloco))
        for coluna, item in zip(colunas, bloco):
            with coluna:
                kpi(
                    rotulo=item["rotulo"],
                    valor=item.get("valor"),
                    nota=item.get("nota"),
                    cor_borda=item.get("cor_borda", AZUL_OCEANO),
                    formato=item.get("formato", "{:,}"),
                )


def etiqueta_status(status: str | None) -> str:
    """HTML de uma etiqueta de status (cor + ícone + texto)."""
    estilo = estilo_status(status)
    return (
        f'<span class="lg-etiqueta" style="color:{estilo["cor"]};'
        f'border-color:{estilo["cor"]};background:{estilo["cor"]}14">'
        f'{estilo["icone"]} {estilo["rotulo"]}</span>'
    )


def mostrar_status(status: str | None) -> None:
    st.markdown(etiqueta_status(status), unsafe_allow_html=True)


def etiqueta_classe_ia(classe: str | None, score: float | None = None) -> str:
    estilo = estilo_classe_ia(classe)
    sufixo = f" · {score * 100:.1f}%" if score is not None else ""
    return (
        f'<span class="lg-etiqueta" style="color:{estilo["cor"]};'
        f'border-color:{estilo["cor"]};background:{estilo["cor"]}14">'
        f'{estilo["icone"]} {estilo["rotulo"]}{sufixo}</span>'
    )


def estado_vazio(mensagem: str, sugestao: str | None = None, icone: str = "🌊") -> None:
    """
    Estado vazio informativo.

    Usado sempre que uma consulta não retorna dados: explica o motivo em vez de
    desenhar um gráfico sem conteúdo.
    """
    escrever_html(st, f"""
        <div class="lg-vazio">
            <div style="font-size:2rem;line-height:1">{icone}</div>
            <p style="margin:.5rem 0 0 0;font-weight:600">{mensagem}</p>
            {f'<p style="margin:.3rem 0 0 0;font-size:.88rem">{sugestao}</p>' if sugestao else ""}
        </div>
        """)


def aviso(texto: str) -> None:
    st.markdown(f'<div class="lg-aviso">⚠️ {texto}</div>', unsafe_allow_html=True)


def aviso_privacidade(texto: str) -> None:
    st.markdown(f'<div class="lg-aviso-privacidade">🔒 {texto}</div>', unsafe_allow_html=True)


def banner_demonstracao(quantidade: int | None = None, visivel: bool = True) -> None:
    """
    Identificação obrigatória de dados de demonstração (seção 11 do escopo).

    Aparece sempre que a visualização corrente pode conter registros DEMO.
    """
    if not visivel:
        return
    detalhe = f" ({quantidade} registros)" if quantidade else ""
    escrever_html(st, f"""
        <div class="lg-aviso-demo">
            🧪 Esta visualização inclui <b>dados de demonstração</b>{detalhe},
            gerados para testar os painéis. Eles <b>não</b> são avistamentos reais
            e não indicam ocorrência da espécie em nenhum município.
            Use o filtro "Procedência do dado" para removê-los.
        </div>
        """)


def ressalva_cientifica(texto: str | None = None) -> None:
    """Ressalva de viés de observação, obrigatória nos painéis analíticos."""
    padrao = (
        "Dados de ciência cidadã possuem viés de observação: as áreas com mais "
        "registros são as com mais observadores e conectividade, não "
        "necessariamente as com mais peixes-leão. Ausência de registros não "
        "significa ausência da espécie. As relações mostradas são associações, "
        "não causalidade comprovada."
    )
    with st.expander("Ressalva metodológica sobre a leitura destes dados", expanded=False):
        st.markdown(texto or padrao)


def rodape_institucional() -> None:
    """Esclarecimento institucional exigido pela seção 3.2 do escopo."""
    st.divider()
    st.caption(
        "**LionGuard AI** — protótipo acadêmico desenvolvido para a Global Solution "
        "2026.2 da FIAP (desafio CitizenTech). Não é um sistema oficial do ICMBio "
        "nem de qualquer órgão ambiental, e não possui homologação ou parceria "
        "institucional. Utiliza documentos públicos como fundamentação. "
        "As identificações automáticas são preliminares e dependem de validação humana."
    )


def orientacao_seguranca() -> None:
    """
    Orientação de segurança ambiental (seção 10 do escopo).

    A plataforma nunca instrui captura ou manuseio do animal.
    """
    st.info(
        "**Registre com segurança.** O peixe-leão possui espinhos venenosos cuja "
        "picada é muito dolorosa. Mantenha distância, não toque, não tente capturar "
        "nem manipular o animal, e fotografe de longe. Ações de manejo e remoção "
        "cabem exclusivamente aos órgãos competentes e a profissionais autorizados. "
        "Em caso de acidente, procure atendimento médico."
    )


def carregando(mensagem: str = "Processando..."):
    """Indicador de carregamento padronizado (usar como gerenciador de contexto)."""
    return st.spinner(mensagem)
