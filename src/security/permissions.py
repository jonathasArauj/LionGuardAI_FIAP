"""
Controle de acesso por perfil.

Três perfis (seção 10): CIDADAO (anônimo, público), PESQUISADOR e
ADMINISTRADOR. As permissões são declaradas em um mapa explícito — nenhuma
tela decide sozinha o que o usuário pode fazer.
"""

from __future__ import annotations

from enum import StrEnum

from src.database.schema import Perfil
from src.security.auth import Sessao


class Permissao(StrEnum):
    REGISTRAR_AVISTAMENTO = "REGISTRAR_AVISTAMENTO"
    VER_MAPA_PUBLICO = "VER_MAPA_PUBLICO"
    VER_INDICADORES_PUBLICOS = "VER_INDICADORES_PUBLICOS"
    VER_DASHBOARD_GERAL = "VER_DASHBOARD_GERAL"
    VER_DASHBOARD_CIENTIFICO = "VER_DASHBOARD_CIENTIFICO"
    VER_DASHBOARD_IA = "VER_DASHBOARD_IA"
    VER_PAINEL_OPERACIONAL = "VER_PAINEL_OPERACIONAL"
    VALIDAR_OCORRENCIA = "VALIDAR_OCORRENCIA"
    VER_COORDENADAS_PRECISAS = "VER_COORDENADAS_PRECISAS"
    EXPORTAR_DADOS = "EXPORTAR_DADOS"
    EXPORTAR_COORDENADAS_PRECISAS = "EXPORTAR_COORDENADAS_PRECISAS"
    GERENCIAR_USUARIOS = "GERENCIAR_USUARIOS"
    VER_AUDITORIA = "VER_AUDITORIA"
    GERENCIAR_DADOS_DEMO = "GERENCIAR_DADOS_DEMO"


PERMISSOES_PUBLICAS: frozenset[Permissao] = frozenset(
    {
        Permissao.REGISTRAR_AVISTAMENTO,
        Permissao.VER_MAPA_PUBLICO,
        Permissao.VER_INDICADORES_PUBLICOS,
    }
)

PERMISSOES_POR_PERFIL: dict[Perfil, frozenset[Permissao]] = {
    Perfil.CIDADAO: PERMISSOES_PUBLICAS,
    Perfil.PESQUISADOR: PERMISSOES_PUBLICAS
    | frozenset(
        {
            Permissao.VER_DASHBOARD_GERAL,
            Permissao.VER_DASHBOARD_CIENTIFICO,
            Permissao.VER_DASHBOARD_IA,
            Permissao.VER_PAINEL_OPERACIONAL,
            Permissao.VALIDAR_OCORRENCIA,
            Permissao.VER_COORDENADAS_PRECISAS,
            Permissao.EXPORTAR_DADOS,
        }
    ),
    Perfil.ADMINISTRADOR: PERMISSOES_PUBLICAS
    | frozenset(
        {
            Permissao.VER_DASHBOARD_GERAL,
            Permissao.VER_DASHBOARD_CIENTIFICO,
            Permissao.VER_DASHBOARD_IA,
            Permissao.VER_PAINEL_OPERACIONAL,
            Permissao.VALIDAR_OCORRENCIA,
            Permissao.VER_COORDENADAS_PRECISAS,
            Permissao.EXPORTAR_DADOS,
            Permissao.EXPORTAR_COORDENADAS_PRECISAS,
            Permissao.GERENCIAR_USUARIOS,
            Permissao.VER_AUDITORIA,
            Permissao.GERENCIAR_DADOS_DEMO,
        }
    ),
}


class AcessoNegado(Exception):
    """A sessão atual não possui a permissão solicitada."""


def permissoes_da_sessao(sessao: Sessao | None) -> frozenset[Permissao]:
    """Visitante anônimo (sessão ausente ou expirada) recebe o conjunto público."""
    if sessao is None or not sessao.valida:
        return PERMISSOES_PUBLICAS
    return PERMISSOES_POR_PERFIL.get(sessao.perfil, PERMISSOES_PUBLICAS)


def tem_permissao(sessao: Sessao | None, permissao: Permissao) -> bool:
    return permissao in permissoes_da_sessao(sessao)


def exigir(sessao: Sessao | None, permissao: Permissao) -> None:
    """Levanta `AcessoNegado` quando a permissão não está concedida."""
    if not tem_permissao(sessao, permissao):
        raise AcessoNegado(f"permissão necessária: {permissao}")
