"""
Interface de autenticação e proteção das páginas restritas.

A verificação de permissão acontece em duas camadas: aqui, para dar ao usuário
uma mensagem clara, e dentro dos serviços (`src.security.permissions`), que é a
camada que realmente impede a ação. Esconder um botão não é controle de acesso.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from app.styles.markup import escrever_html
from src.database.schema import Perfil
from src.security.auth import ErroAutenticacao, ServicoAutenticacao, Sessao
from src.security.permissions import (
    PERMISSOES_POR_PERFIL,
    PERMISSOES_PUBLICAS,
    Permissao,
    permissoes_da_sessao,
    tem_permissao,
)

CHAVE_SESSAO = "lg_sessao"

# Como cada perfil se apresenta na interface. O conteúdo de cada cartão é
# derivado da matriz de permissões, não escrito à mão: se a matriz mudar, o
# texto muda junto.
APRESENTACAO_PERFIL: dict[str, dict[str, str]] = {
    str(Perfil.CIDADAO): {
        "titulo": "Visitante",
        "chip": "lg-chip-publico",
        "rotulo": "Sem login",
        "icone": "🌊",
        "resumo": "Qualquer pessoa, sem cadastro e sem login.",
    },
    str(Perfil.PESQUISADOR): {
        "titulo": "Pesquisador",
        "chip": "lg-chip-pesquisador",
        "rotulo": "Login",
        "icone": "🔬",
        "resumo": "Quem analisa e valida as ocorrências.",
    },
    str(Perfil.ADMINISTRADOR): {
        "titulo": "Administrador",
        "chip": "lg-chip-admin",
        "rotulo": "Login",
        "icone": "⚙️",
        "resumo": "Quem cuida de contas, auditoria e integridade da base.",
    },
}

# Descrição legível de cada permissão, para o usuário saber o que ganha ao
# entrar — em vez de ver o nome técnico da constante.
DESCRICAO_PERMISSAO: dict[str, str] = {
    str(Permissao.REGISTRAR_AVISTAMENTO): "Registrar avistamentos",
    str(Permissao.VER_MAPA_PUBLICO): "Mapa com posição aproximada (~1 km)",
    str(Permissao.VER_INDICADORES_PUBLICOS): "Indicadores públicos",
    str(Permissao.VER_DASHBOARD_GERAL): "Painel de visão geral com filtros",
    str(Permissao.VER_DASHBOARD_CIENTIFICO): "Análise científica e exportação",
    str(Permissao.VER_DASHBOARD_IA): "Desempenho do modelo de IA",
    str(Permissao.VER_PAINEL_OPERACIONAL): "Fila operacional de revisão",
    str(Permissao.VALIDAR_OCORRENCIA): "Validar ocorrências",
    str(Permissao.VER_COORDENADAS_PRECISAS): "Coordenadas precisas no mapa",
    str(Permissao.EXPORTAR_DADOS): "Exportar dados em CSV",
    str(Permissao.EXPORTAR_COORDENADAS_PRECISAS): "Exportar coordenadas precisas",
    str(Permissao.GERENCIAR_USUARIOS): "Gerenciar contas de acesso",
    str(Permissao.VER_AUDITORIA): "Trilha de auditoria",
    str(Permissao.GERENCIAR_DADOS_DEMO): "Gerenciar dados de demonstração",
}

ORDEM_PERMISSOES = list(DESCRICAO_PERMISSAO)


def sessao_atual() -> Sessao | None:
    """Sessão válida guardada no estado do Streamlit, ou `None`."""
    sessao = st.session_state.get(CHAVE_SESSAO)
    if sessao is None:
        return None
    if not isinstance(sessao, Sessao) or not sessao.valida:
        st.session_state.pop(CHAVE_SESSAO, None)
        return None
    return sessao


def esta_autenticado() -> bool:
    return sessao_atual() is not None


def chip_perfil(perfil: str | None) -> str:
    """Etiqueta do perfil, com ícone e texto — nunca apenas cor."""
    dados = APRESENTACAO_PERFIL.get(
        str(perfil or Perfil.CIDADAO), APRESENTACAO_PERFIL[str(Perfil.CIDADAO)]
    )
    return (
        f'<span class="lg-perfil-chip {dados["chip"]}">'
        f'{dados["icone"]} {_html.escape(dados["titulo"])}</span>'
    )


def _permissoes_legiveis(perfil: str) -> list[str]:
    concedidas = PERMISSOES_POR_PERFIL.get(
        Perfil(perfil), frozenset(PERMISSOES_PUBLICAS)
    )
    nomes = {str(item) for item in concedidas}
    return [DESCRICAO_PERMISSAO[chave] for chave in ORDEM_PERMISSOES if chave in nomes]


def cartoes_de_perfil(perfil_ativo: str | None = None) -> None:
    """
    Os três perfis lado a lado, com o que cada um enxerga.

    A lista de cada cartão sai da matriz de permissões: a tela não pode
    prometer algo que o controle de acesso não conceda.
    """
    cartoes: list[str] = []
    for perfil, dados in APRESENTACAO_PERFIL.items():
        itens = "".join(
            f"<li>{_html.escape(texto)}</li>" for texto in _permissoes_legiveis(perfil)
        )
        ativo = " lg-ativo" if perfil_ativo and str(perfil_ativo) == perfil else ""
        cartoes.append(
            f'<div class="lg-perfil{ativo}">'
            f'<span class="lg-perfil-chip {dados["chip"]}">{dados["rotulo"]}</span>'
            f'<h4>{dados["icone"]} {_html.escape(dados["titulo"])}</h4>'
            f'<p style="font-size:.86rem;margin:0 0 .5rem 0">'
            f'{_html.escape(dados["resumo"])}</p>'
            f'<ul class="lg-lista-marcada">{itens}</ul>'
            f"</div>"
        )
    escrever_html(st, f'<div class="lg-perfis">{"".join(cartoes)}</div>')


def faixa_especialista(sessao: Sessao, pagina: str, descricao: str) -> None:
    """
    Cabeçalho das páginas restritas: quem está vendo, com que perfil e o que
    esta página mostra além da visão pública.
    """
    escrever_html(
        st,
        f"""
        <div class="lg-faixa-escura" style="display:flex;gap:1rem;
             align-items:center;justify-content:space-between;flex-wrap:wrap">
            <div style="min-width:260px;flex:1">
                <span class="lg-sobrenome">Área de monitoramento</span>
                <h2 style="margin:.2rem 0 .3rem 0;font-size:1.45rem">
                    {_html.escape(pagina)}</h2>
                <p style="margin:0;font-size:.9rem">{descricao}</p>
            </div>
            <div style="text-align:right">
                {chip_perfil(sessao.perfil)}
                <div style="font-size:.86rem;margin-top:.35rem">
                    <b>{_html.escape(sessao.nome or sessao.identificador)}</b>
                </div>
                <div style="font-size:.74rem">
                    sessão até {_html.escape(str(sessao.expira_em)[11:16])}
                </div>
            </div>
        </div>
        """,
    )


def formulario_login(titulo: str = "Acesso restrito") -> Sessao | None:
    """Formulário de login para pesquisadores e administradores."""
    escrever_html(
        st,
        f"""
        <div class="lg-card">
            <div class="lg-card-titulo">🔐 {_html.escape(titulo)}</div>
            <p style="font-size:.88rem;margin:0">
                O registro de avistamentos é <b>público e não exige login</b>.
                A autenticação protege apenas os painéis de monitoramento e a
                fila de validação.
            </p>
        </div>
        """,
    )

    with st.form("form_login", clear_on_submit=False):
        identificador = st.text_input("Usuário", key="login_usuario")
        senha = st.text_input("Senha", type="password", key="login_senha")
        enviado = st.form_submit_button(
            "Entrar", type="primary", use_container_width=True
        )

    if not enviado:
        return None

    try:
        sessao = ServicoAutenticacao().autenticar(identificador, senha)
    except ErroAutenticacao:
        # Mensagem genérica de propósito: não revela se o usuário existe.
        st.error("Usuário ou senha inválidos.")
        return None

    st.session_state[CHAVE_SESSAO] = sessao
    st.success(f"Bem-vindo, {sessao.nome or sessao.identificador}.")
    st.rerun()
    return sessao


def encerrar_sessao() -> None:
    sessao = sessao_atual()
    if sessao:
        ServicoAutenticacao().encerrar(sessao)
    st.session_state.pop(CHAVE_SESSAO, None)


def caixa_usuario() -> None:
    """Bloco de identificação do usuário na barra lateral."""
    sessao = sessao_atual()
    with st.sidebar:
        st.divider()
        if sessao is None:
            escrever_html(
                st,
                f"""
                <div style="display:flex;flex-direction:column;gap:.4rem">
                    {chip_perfil(None)}
                    <span style="font-size:.8rem">
                        Navegando na área pública. Registrar avistamento,
                        mapa e indicadores não exigem login.
                    </span>
                </div>
                """,
            )
            return

        escrever_html(
            st,
            f"""
            <div style="display:flex;flex-direction:column;gap:.35rem">
                {chip_perfil(sessao.perfil)}
                <b style="font-size:.95rem">
                    {_html.escape(sessao.nome or sessao.identificador)}
                </b>
                <span style="font-size:.76rem">
                    Sessão válida até {_html.escape(str(sessao.expira_em)[11:16])}
                </span>
            </div>
            """,
        )
        if st.button("Sair", key="btn_sair", use_container_width=True):
            encerrar_sessao()
            st.rerun()


def proteger(permissao: Permissao, titulo_pagina: str = "Área restrita") -> Sessao:
    """
    Garante que a página só continue se a sessão tiver a permissão.

    Sem sessão, mostra o login. Com sessão sem permissão, explica o que falta.
    Interrompe a execução da página nos dois casos.
    """
    sessao = sessao_atual()

    if sessao is None:
        formulario_login(titulo_pagina)
        st.stop()

    if not tem_permissao(sessao, permissao):
        st.error(
            f"Seu perfil (**{sessao.perfil}**) não tem permissão para acessar "
            f"esta página (requer `{permissao}`)."
        )
        with st.expander("O que o seu perfil pode fazer"):
            nomes = {str(item) for item in permissoes_da_sessao(sessao)}
            for chave in ORDEM_PERMISSOES:
                if chave in nomes:
                    st.write(f"- {DESCRICAO_PERMISSAO[chave]}")
        st.stop()

    return sessao
