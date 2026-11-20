"""
Tela de acesso dos especialistas.

A plataforma funciona em dois níveis, e esta página torna isso explícito:
qualquer pessoa registra um avistamento e acompanha o panorama sem se
identificar; pesquisadores e administradores entram para ver o que a visão
pública **não** mostra — coordenada precisa, fila de validação, desempenho do
modelo e trilha de auditoria.

Os cartões de perfil são gerados a partir da matriz de permissões
(`src/security/permissions.py`), e não escritos à mão: a tela não pode
prometer um acesso que o controle não conceda.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.auth_ui import cartoes_de_perfil, formulario_login, sessao_atual
from app.components.media import obter_fotos
from app.components.ui import hero, rodape_institucional, secao
from app.styles.markup import escrever_html
from src.database.schema import Perfil

sessao = sessao_atual()

hero(
    "Área de monitoramento",
    "Painéis analíticos, coordenadas precisas e validação de ocorrências. "
    "O registro de avistamentos continua público — o login existe para o "
    "trabalho de quem analisa.",
    selos=["Acesso por perfil", "Sessão expira sozinha", "Toda ação auditada"],
)

coluna_login, coluna_foto = st.columns([1.15, 1], gap="large")

with coluna_login:
    if sessao is None:
        formulario_login("Entrar na área de monitoramento")
    else:
        st.success(
            f"Você já está autenticado como **{sessao.nome or sessao.identificador}** "
            f"({sessao.perfil}). Use o menu lateral para abrir os painéis."
        )

with coluna_foto:
    fotos = obter_fotos(limite=1)
    if fotos:
        foto = fotos[0]
        escrever_html(
            st,
            f"""
            <figure class="lg-foto-hero" style="margin:0">
                <img src="{foto.url_miniatura}" loading="lazy"
                     alt="Fotografia de {foto.especie}">
                <figcaption>
                    {foto.especie} · © {foto.autor} ·
                    <a href="{foto.url_licenca}" target="_blank" rel="noopener">
                        {foto.licenca_legivel}</a> ·
                    <a href="{foto.url_observacao}" target="_blank" rel="noopener">
                        iNaturalist</a>
                </figcaption>
            </figure>
            """,
        )
    else:
        st.info(
            "A fotografia desta seção vem do iNaturalist, com licença aberta, e "
            "precisa de conexão para carregar."
        )

st.markdown("")
secao(
    "Perfis de acesso",
    "O que cada um enxerga",
    "A lista de cada cartão é gerada a partir da matriz de permissões do "
    "sistema. O perfil não decide só o que aparece na tela: a mesma matriz é "
    "verificada dentro dos serviços, antes de qualquer leitura ou gravação.",
)
cartoes_de_perfil(perfil_ativo=sessao.perfil if sessao else str(Perfil.CIDADAO))

st.markdown("")
coluna_credenciais, coluna_sessao = st.columns(2, gap="large")

with coluna_credenciais:
    escrever_html(
        st,
        """
        <div class="lg-card">
            <div class="lg-card-titulo">🔑 De onde vêm as credenciais</div>
            <p style="font-size:.9rem;margin:0">
                As contas iniciais são criadas na primeira execução. As senhas
                vêm de variáveis de ambiente
                (<code>LIONGUARD_ADMIN_PASS</code>,
                <code>LIONGUARD_PESQ_PASS</code>). Sem essas variáveis, uma
                senha aleatória é gerada e impressa no terminal de quem
                executou a aplicação. <b>Nenhuma credencial está escrita no
                código</b>, e a senha é guardada como hash scrypt com sal.
            </p>
        </div>
        """,
    )

with coluna_sessao:
    escrever_html(
        st,
        """
        <div class="lg-card">
            <div class="lg-card-titulo">🛡️ Como a sessão é tratada</div>
            <p style="font-size:.9rem;margin:0">
                A sessão tem prazo de validade e expira sozinha. Tentativas de
                login — as que falham também — entram na trilha de auditoria,
                junto das validações de ocorrência. Erro de login devolve
                sempre a mesma mensagem, que não revela se o usuário existe.
            </p>
        </div>
        """,
    )

rodape_institucional()
