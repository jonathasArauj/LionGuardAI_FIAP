"""
Limitação de requisições por chave (proteção contra abuso — seção 10).

A contagem é persistida em tabela, e não em memória: o Streamlit recria o
estado da sessão com facilidade, e um limite guardado só em memória seria
contornado ao recarregar a página.

A chave é derivada de um identificador de sessão do navegador — não é um
endereço IP nem dado pessoal.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import get_config
from src.database.repositories import EventoRequisicaoRepository


@dataclass(slots=True)
class ResultadoLimite:
    permitido: bool
    usados: int
    limite: int
    janela_segundos: int

    @property
    def restantes(self) -> int:
        return max(0, self.limite - self.usados)

    def mensagem(self) -> str:
        minutos = max(1, self.janela_segundos // 60)
        return (
            f"Limite de {self.limite} registros a cada {minutos} minutos atingido. "
            "Aguarde alguns minutos antes de enviar outro avistamento."
        )


class LimitadorRequisicoes:
    def __init__(self, caminho: str | Path | None = None) -> None:
        self.eventos = EventoRequisicaoRepository(caminho)

    def verificar(
        self,
        chave: str,
        acao: str = "REGISTRO",
        limite: int | None = None,
        janela_segundos: int | None = None,
    ) -> ResultadoLimite:
        """Consulta o limite **sem** consumir uma unidade."""
        config = get_config()
        limite = limite if limite is not None else config.rate_limit_registros
        janela = (
            janela_segundos
            if janela_segundos is not None
            else config.rate_limit_janela_segundos
        )
        usados = self.eventos.contar_na_janela(chave, acao, janela)
        return ResultadoLimite(
            permitido=usados < limite,
            usados=usados,
            limite=limite,
            janela_segundos=janela,
        )

    def registrar(self, chave: str, acao: str = "REGISTRO") -> None:
        """Consome uma unidade do limite (chamar só quando a ação ocorreu)."""
        self.eventos.registrar(chave, acao)

    def consumir(
        self,
        chave: str,
        acao: str = "REGISTRO",
        limite: int | None = None,
        janela_segundos: int | None = None,
    ) -> ResultadoLimite:
        """Verifica e, se permitido, consome uma unidade — operação combinada."""
        resultado = self.verificar(chave, acao, limite, janela_segundos)
        if resultado.permitido:
            self.registrar(chave, acao)
            resultado = ResultadoLimite(
                permitido=True,
                usados=resultado.usados + 1,
                limite=resultado.limite,
                janela_segundos=resultado.janela_segundos,
            )
        return resultado
