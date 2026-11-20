"""
Autenticação de pesquisadores e administradores.

O registro público de avistamentos **não** exige login (seção 10 do escopo);
a autenticação protege apenas os painéis restritos.

Hash de senha: `hashlib.scrypt` (biblioteca padrão), com sal aleatório de 16
bytes por usuário e parâmetros de custo explícitos. Comparação em tempo
constante com `hmac.compare_digest`. Senhas em texto puro nunca são gravadas
nem registradas em log.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.config import get_config
from src.database.models import Usuario
from src.database.repositories import (
    AuditoriaRepository,
    RegistroDuplicado,
    UsuarioRepository,
)
from src.database.schema import Perfil

# Parâmetros de custo do scrypt. n=2**14 equilibra segurança e tempo de
# resposta aceitável em uma POC executada em notebook.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_TAMANHO_HASH = 32
_TAMANHO_SAL = 16

SENHA_MINIMA = 8


class ErroAutenticacao(Exception):
    """Credenciais inválidas ou usuário inativo."""


class SenhaFraca(Exception):
    """Senha não atende à política mínima."""


def gerar_hash_senha(senha: str) -> str:
    """Devolve a senha derivada no formato `scrypt$n$r$p$sal$hash` (hex)."""
    if senha is None or len(senha) < SENHA_MINIMA:
        raise SenhaFraca(f"a senha deve ter ao menos {SENHA_MINIMA} caracteres")
    sal = os.urandom(_TAMANHO_SAL)
    derivada = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=sal,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_TAMANHO_HASH,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${sal.hex()}${derivada.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    """Confere a senha contra o hash armazenado, sem vazar tempo."""
    try:
        algoritmo, n, r, p, sal_hex, hash_hex = armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        derivada = hashlib.scrypt(
            (senha or "").encode("utf-8"),
            salt=bytes.fromhex(sal_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(hash_hex)),
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(derivada.hex(), hash_hex)


@dataclass(slots=True)
class Sessao:
    """Sessão autenticada, guardada no `st.session_state` do Streamlit."""

    usuario_id: int
    identificador: str
    perfil: Perfil
    nome: str | None
    token: str
    expira_em: str

    @property
    def expirada(self) -> bool:
        try:
            return datetime.fromisoformat(self.expira_em) < datetime.now()
        except ValueError:  # pragma: no cover
            return True

    @property
    def valida(self) -> bool:
        return not self.expirada


class ServicoAutenticacao:
    def __init__(self, caminho: str | Path | None = None) -> None:
        self.caminho = caminho
        self.usuarios = UsuarioRepository(caminho)
        self.auditoria = AuditoriaRepository(caminho)

    # ------------------------------------------------------------------ contas
    def criar_usuario(
        self,
        identificador: str,
        senha: str,
        perfil: Perfil,
        nome: str | None = None,
        criado_por: int | None = None,
    ) -> Usuario:
        identificador = (identificador or "").strip().lower()
        if not identificador:
            raise ValueError("identificador obrigatório")
        usuario = Usuario(
            identificador=identificador,
            nome=nome,
            senha_hash=gerar_hash_senha(senha),
            perfil=perfil,
        )
        criado = self.usuarios.criar(usuario)
        self.auditoria.registrar(
            entidade="usuario",
            acao="CRIACAO",
            entidade_id=str(criado.id),
            usuario_id=criado_por,
            detalhes={"perfil": str(perfil), "identificador": identificador},
        )
        return criado

    def autenticar(self, identificador: str, senha: str) -> Sessao:
        usuario = self.usuarios.por_identificador(identificador or "")
        # Mesmo com usuário inexistente, executa uma derivação para não
        # revelar por tempo de resposta se o identificador existe.
        referencia = usuario.senha_hash if usuario else gerar_hash_senha("placeholder-invalido")
        senha_ok = verificar_senha(senha, referencia)

        if not usuario or not senha_ok or not usuario.ativo:
            self.auditoria.registrar(
                entidade="usuario",
                acao="LOGIN_FALHA",
                entidade_id=(identificador or "").strip().lower() or None,
                detalhes={"motivo": "credencial_invalida_ou_inativo"},
            )
            raise ErroAutenticacao("credenciais inválidas")

        self.usuarios.registrar_acesso(usuario.id)
        self.auditoria.registrar(
            entidade="usuario", acao="LOGIN_SUCESSO", entidade_id=str(usuario.id),
            usuario_id=usuario.id,
        )
        horas = get_config().sessao_duracao_horas
        return Sessao(
            usuario_id=usuario.id,
            identificador=usuario.identificador,
            perfil=usuario.perfil,
            nome=usuario.nome,
            token=secrets.token_urlsafe(32),
            expira_em=(datetime.now() + timedelta(hours=horas)).replace(microsecond=0).isoformat(),
        )

    def encerrar(self, sessao: Sessao | None) -> None:
        if sessao:
            self.auditoria.registrar(
                entidade="usuario", acao="LOGOUT", entidade_id=str(sessao.usuario_id),
                usuario_id=sessao.usuario_id,
            )

    # ----------------------------------------------------- contas iniciais
    def garantir_usuarios_iniciais(self) -> list[str]:
        """
        Cria contas de demonstração se a base estiver sem usuários.

        As senhas vêm de variáveis de ambiente. Se não houver variável
        definida, uma senha aleatória é gerada e **devolvida uma única vez**
        para ser exibida no terminal — nada fica fixo no código.
        """
        criados: list[str] = []
        contas = (
            ("LIONGUARD_ADMIN_USER", "LIONGUARD_ADMIN_PASS", Perfil.ADMINISTRADOR, "admin"),
            ("LIONGUARD_PESQ_USER", "LIONGUARD_PESQ_PASS", Perfil.PESQUISADOR, "pesquisador"),
        )
        for var_usuario, var_senha, perfil, padrao_usuario in contas:
            identificador = os.getenv(var_usuario, padrao_usuario).strip().lower()
            if self.usuarios.por_identificador(identificador):
                continue
            senha = os.getenv(var_senha) or secrets.token_urlsafe(12)
            try:
                self.criar_usuario(identificador, senha, perfil, nome=padrao_usuario.title())
            except (RegistroDuplicado, SenhaFraca):
                continue
            origem = "variável de ambiente" if os.getenv(var_senha) else "gerada"
            criados.append(f"{identificador} / {senha}  ({perfil}, senha {origem})")
        return criados
