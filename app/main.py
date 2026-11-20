"""
LionGuard AI — ponto de entrada da aplicação Streamlit.

Executar na raiz do projeto:
    streamlit run app/main.py

Este arquivo funciona como roteador: monta a navegação conforme o perfil
autenticado e delega a execução para a página escolhida. As páginas ficam em
`app/paginas/`.

Observação sobre a estrutura: o diretório foi nomeado `paginas/` em vez de
`pages/` de propósito. O Streamlit detecta automaticamente um diretório
`pages/` ao lado do arquivo de entrada e emite aviso de comportamento
indeterminado quando `st.navigation` também é usado. Como precisamos de
navegação condicionada a permissão, usamos `st.navigation` e evitamos o nome
reservado.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from app.components.auth_ui import caixa_usuario, sessao_atual  # noqa: E402
from app.styles.theme import aplicar_tema  # noqa: E402
from src.database.connection import inicializar_banco  # noqa: E402
from src.security.auth import ServicoAutenticacao  # noqa: E402
from src.security.permissions import Permissao, tem_permissao  # noqa: E402

st.set_page_config(
    page_title="LionGuard AI — Monitoramento do peixe-leão",
    page_icon="🐠",
    layout="wide",
    initial_sidebar_state="collapsed",  # celular primeiro: conteúdo em foco
    menu_items={
        "about": (
            "**LionGuard AI** — protótipo acadêmico (FIAP, Global Solution 2026.2) "
            "para detecção precoce e monitoramento colaborativo do peixe-leão. "
            "Não é um sistema oficial de órgão ambiental."
        )
    },
)


@st.cache_resource(show_spinner=False)
def _preparar_ambiente() -> list[str]:
    """
    Executa uma única vez por processo: cria o esquema (se não existir) e
    garante as contas de acesso restrito.

    O banco **não** é recriado — `CREATE TABLE IF NOT EXISTS` preserva os dados
    entre reinicializações.
    """
    inicializar_banco()
    credenciais = ServicoAutenticacao().garantir_usuarios_iniciais()
    for linha in credenciais:
        # Exibido somente no terminal de quem executa a aplicação.
        print(f"[LionGuard AI] conta criada -> {linha}", flush=True)
    return credenciais


_preparar_ambiente()
aplicar_tema(st)

sessao = sessao_atual()


def _pagina(arquivo: str, titulo: str, icone: str, padrao: bool = False):
    return st.Page(f"paginas/{arquivo}", title=titulo, icon=icone, default=padrao)


paginas_publicas = [
    _pagina("inicio.py", "Início", "🏠", padrao=True),
    _pagina("registrar.py", "Registrar avistamento", "📷"),
    _pagina("mapa.py", "Mapa de avistamentos", "🗺️"),
    _pagina("indicadores.py", "Indicadores públicos", "📊"),
    _pagina("sobre_peixe_leao.py", "Sobre o peixe-leão", "🐠"),
    _pagina("sobre_projeto.py", "Sobre o projeto", "ℹ️"),
]

navegacao: dict[str, list] = {"Área pública": paginas_publicas}

if tem_permissao(sessao, Permissao.VER_DASHBOARD_GERAL):
    paginas_restritas = [
        _pagina("dashboard_geral.py", "Visão geral", "📈"),
        _pagina("dashboard_cientifico.py", "Análise científica", "🔬"),
        _pagina("dashboard_ia.py", "Inteligência artificial", "🤖"),
        _pagina("validacao.py", "Validação de ocorrências", "✅"),
    ]
    if tem_permissao(sessao, Permissao.GERENCIAR_USUARIOS):
        paginas_restritas.append(_pagina("administracao.py", "Administração", "⚙️"))
    navegacao["Monitoramento"] = paginas_restritas
else:
    navegacao["Monitoramento"] = [_pagina("acesso.py", "Acesso de pesquisador", "🔐")]

pagina = st.navigation(navegacao, position="sidebar")

with st.sidebar:
    st.markdown("### 🐠 LionGuard AI")
    st.caption(
        "Detecção precoce e monitoramento colaborativo do peixe-leão "
        "no litoral brasileiro."
    )

caixa_usuario()

pagina.run()
