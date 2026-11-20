"""
Fluxo de validação humana das ocorrências.

Regras (seção 5.5 do escopo):
  * somente perfis autorizados validam — a permissão é verificada aqui, não
    apenas na interface;
  * toda decisão exige justificativa e fica registrada no histórico
    (`validacao`) e na auditoria (`log_auditoria`);
  * a mudança de status e o registro histórico acontecem na mesma transação;
  * `data_primeira_decisao` é gravada apenas na primeira decisão final, pois é
    a base do indicador de tempo de revisão.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.database.connection import transacao
from src.database.models import Validacao, agora_iso
from src.database.repositories import (
    AuditoriaRepository,
    OcorrenciaRepository,
    ValidacaoRepository,
)
from src.database.schema import Decisao, StatusOcorrencia
from src.security.auth import Sessao
from src.security.permissions import Permissao, exigir
from src.security.sanitize import limpar_texto

JUSTIFICATIVA_MINIMA = 10

# Cada decisão do avaliador leva a exatamente um status.
MAPA_DECISAO_STATUS: dict[Decisao, StatusOcorrencia] = {
    Decisao.CONFIRMAR: StatusOcorrencia.CONFIRMADO,
    Decisao.REJEITAR: StatusOcorrencia.REJEITADO,
    Decisao.INCONCLUSIVO: StatusOcorrencia.INCONCLUSIVO,
    Decisao.SOLICITAR_INFO: StatusOcorrencia.AGUARDANDO_INFO,
}


class ErroValidacao(Exception):
    """Decisão inválida ou dados insuficientes."""


@dataclass(slots=True)
class ResultadoValidacao:
    sucesso: bool
    protocolo: str
    status_anterior: StatusOcorrencia
    status_novo: StatusOcorrencia
    mensagem: str


class ServicoValidacao:
    def __init__(self, caminho_banco: str | Path | None = None) -> None:
        self.caminho = caminho_banco
        self.ocorrencias = OcorrenciaRepository(caminho_banco)
        self.validacoes = ValidacaoRepository(caminho_banco)
        self.auditoria = AuditoriaRepository(caminho_banco)

    def decidir(
        self,
        ocorrencia_id: int,
        decisao: Decisao,
        justificativa: str,
        sessao: Sessao | None,
    ) -> ResultadoValidacao:
        """Aplica a decisão do avaliador sobre uma ocorrência."""
        exigir(sessao, Permissao.VALIDAR_OCORRENCIA)
        assert sessao is not None  # garantido por `exigir`

        justificativa = limpar_texto(justificativa, 1000) or ""
        if len(justificativa) < JUSTIFICATIVA_MINIMA:
            raise ErroValidacao(
                f"Descreva a justificativa da decisão (mínimo {JUSTIFICATIVA_MINIMA} caracteres)."
            )

        if decisao not in MAPA_DECISAO_STATUS:
            raise ErroValidacao(f"Decisão desconhecida: {decisao}")

        ocorrencia = self.ocorrencias.por_id(ocorrencia_id)
        if ocorrencia is None:
            raise ErroValidacao("Ocorrência não encontrada.")

        status_anterior = ocorrencia.status
        status_novo = MAPA_DECISAO_STATUS[decisao]

        if status_anterior == status_novo:
            raise ErroValidacao(
                f"A ocorrência {ocorrencia.protocolo} já está com status {status_novo}."
            )

        with transacao(self.caminho):
            self.validacoes.registrar(
                Validacao(
                    ocorrencia_id=ocorrencia.id,
                    avaliador_id=sessao.usuario_id,
                    decisao=decisao,
                    justificativa=justificativa,
                    status_anterior=status_anterior,
                    status_novo=status_novo,
                    data_validacao=agora_iso(),
                )
            )
            self.ocorrencias.atualizar_status(ocorrencia.id, status_novo)
            self.auditoria.registrar(
                entidade="ocorrencia",
                acao=f"VALIDACAO_{decisao}",
                entidade_id=ocorrencia.protocolo,
                usuario_id=sessao.usuario_id,
                detalhes={
                    "status_anterior": str(status_anterior),
                    "status_novo": str(status_novo),
                },
            )

        atualizada = self.ocorrencias.por_id(ocorrencia_id)
        if atualizada is None or atualizada.status != status_novo:  # pragma: no cover
            raise ErroValidacao("A decisão não pôde ser confirmada no banco de dados.")

        return ResultadoValidacao(
            sucesso=True,
            protocolo=ocorrencia.protocolo,
            status_anterior=status_anterior,
            status_novo=status_novo,
            mensagem=(
                f"Ocorrência {ocorrencia.protocolo} atualizada: "
                f"{status_anterior} → {status_novo}."
            ),
        )

    def historico(self, ocorrencia_id: int, sessao: Sessao | None) -> list[Validacao]:
        exigir(sessao, Permissao.VER_PAINEL_OPERACIONAL)
        return self.validacoes.historico(ocorrencia_id)

    def resumo_decisoes(self) -> dict[str, int]:
        return {str(decisao): self.validacoes.contar_decisoes(decisao) for decisao in Decisao}
