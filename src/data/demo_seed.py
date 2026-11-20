"""
Gerador de dados de demonstração.

Para que servem: permitir demonstrar os dashboards, os filtros e o fluxo de
validação sem depender de haver muitos registros reais na base (seção 11 do
escopo).

Regras que este módulo respeita, sem exceção:
  * todo registro criado aqui recebe `tipo_dado = DEMO` e
    `origem_registro = DEMONSTRACAO`, de modo que qualquer tela possa
    identificá-lo e qualquer filtro possa excluí-lo;
  * `origem_localizacao = REGIAO_APROXIMADA` — nenhum ponto de demonstração se
    apresenta como leitura de GPS;
  * **nenhuma predição de IA é criada** para dados de demonstração. Score
    fabricado seria resultado de modelo inventado, e o painel de IA mostra
    somente inferências reais e as métricas do arquivo de avaliação;
  * nenhuma imagem é associada, porque não há fotografia real por trás;
  * a geração é determinística (semente fixa), o que torna a demonstração
    reproduzível e os testes estáveis.

Os dados **não** representam ocorrências reais da espécie em nenhum município.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.database.connection import transacao
from src.database.models import FonteDados, Ocorrencia, Validacao, agora_iso
from src.database.repositories import (
    AuditoriaRepository,
    FonteDadosRepository,
    OcorrenciaRepository,
    RegistroDuplicado,
    UsuarioRepository,
    ValidacaoRepository,
)
from src.database.schema import (
    Decisao,
    Habitat,
    OrigemLocalizacao,
    OrigemRegistro,
    Perfil,
    StatusOcorrencia,
    TipoDado,
)
from src.services.geolocation import MUNICIPIOS_LITORANEOS

SEMENTE_PADRAO = 20262
PREFIXO_PROTOCOLO_DEMO = "LG-DEMO-"

# Distribuição de status usada na demonstração. Reflete uma operação em que a
# maior parte da fila ainda aguarda revisão — não é estatística de campo.
PESOS_STATUS: tuple[tuple[StatusOcorrencia, float], ...] = (
    (StatusOcorrencia.PENDENTE, 0.42),
    (StatusOcorrencia.CONFIRMADO, 0.26),
    (StatusOcorrencia.REJEITADO, 0.16),
    (StatusOcorrencia.INCONCLUSIVO, 0.10),
    (StatusOcorrencia.AGUARDANDO_INFO, 0.06),
)

PESOS_HABITAT: tuple[tuple[Habitat, float], ...] = (
    (Habitat.RECIFE, 0.34),
    (Habitat.COSTAO_ROCHOSO, 0.26),
    (Habitat.AREA_ARENOSA, 0.14),
    (Habitat.MANGUEZAL, 0.05),
    (Habitat.OUTRO, 0.05),
    (Habitat.NAO_INFORMADO, 0.16),
)

JUSTIFICATIVAS_DEMO = (
    "Registro de demonstração revisado no roteiro de validação do protótipo.",
    "Imagem compatível com a espécie segundo o roteiro de demonstração.",
    "Dados insuficientes para decisão no cenário de demonstração.",
    "Registro de demonstração sem elementos que sustentem a identificação.",
)


@dataclass(slots=True)
class ResultadoSemeadura:
    criados: int
    validacoes: int
    ja_existentes: int
    semente: int
    fonte_id: int | None

    @property
    def mensagem(self) -> str:
        return (
            f"{self.criados} registros de demonstração criados "
            f"({self.validacoes} com histórico de validação). "
            f"Todos rotulados como tipo_dado=DEMO."
        )


def _sortear(rng: random.Random, pesos) -> object:
    valores = [item[0] for item in pesos]
    probabilidades = [item[1] for item in pesos]
    return rng.choices(valores, weights=probabilidades, k=1)[0]


class GeradorDemonstracao:
    def __init__(self, caminho_banco: str | Path | None = None) -> None:
        self.caminho = caminho_banco
        self.ocorrencias = OcorrenciaRepository(caminho_banco)
        self.validacoes = ValidacaoRepository(caminho_banco)
        self.usuarios = UsuarioRepository(caminho_banco)
        self.fontes = FonteDadosRepository(caminho_banco)
        self.auditoria = AuditoriaRepository(caminho_banco)

    def gerar(
        self,
        quantidade: int = 120,
        semente: int = SEMENTE_PADRAO,
        dias_passados: int = 540,
    ) -> ResultadoSemeadura:
        """Cria `quantidade` registros de demonstração de forma determinística."""
        rng = random.Random(semente)
        agora = datetime.now().replace(microsecond=0)

        fonte = self.fontes.criar(
            FonteDados(
                nome="Dados de demonstração LionGuard AI",
                url=None,
                tipo_fonte="DEMONSTRACAO",
                licenca="não aplicável",
                observacoes=(
                    "Registros gerados pelo próprio sistema para demonstrar dashboards. "
                    f"Semente {semente}. Não representam ocorrências reais."
                ),
            )
        )

        # Municípios com peso maior onde a espécie já teve registros divulgados
        # no Brasil (Nordeste e Espírito Santo) — isso molda a demonstração para
        # um cenário plausível, sem afirmar ocorrência em município algum.
        candidatos = list(MUNICIPIOS_LITORANEOS)
        pesos_municipio = [
            3.0 if uf in ("PE", "RN", "PB", "CE", "AL", "BA", "ES") else 1.0
            for _, uf, _, _ in candidatos
        ]

        criados = 0
        existentes = 0
        validacoes_criadas = 0
        avaliador = self._obter_avaliador()

        for indice in range(quantidade):
            municipio, uf, lat_base, lon_base = rng.choices(
                candidatos, weights=pesos_municipio, k=1
            )[0]
            # Dispersão de até ~0,25° (≈ 25 km) em torno do ponto de referência.
            latitude = round(lat_base + rng.uniform(-0.25, 0.25), 5)
            longitude = round(lon_base + rng.uniform(-0.25, 0.25), 5)

            dias_atras = rng.randint(0, dias_passados)
            hora = int(min(23, max(5, rng.gauss(11.5, 3.2))))
            data_avistamento = (agora - timedelta(days=dias_atras)).replace(
                hour=hora, minute=rng.randrange(0, 60), second=0
            )
            data_cadastro = data_avistamento + timedelta(
                hours=rng.randint(1, 72), minutes=rng.randrange(0, 60)
            )
            if data_cadastro > agora:
                data_cadastro = agora

            status = _sortear(rng, PESOS_STATUS)
            habitat = _sortear(rng, PESOS_HABITAT)

            tem_profundidade = rng.random() < 0.62
            profundidade = round(abs(rng.gauss(14.0, 9.0)) + 1.0, 1) if tem_profundidade else None
            quantidade_observada = rng.choice([1, 1, 1, 2, 2, 3, 4]) if rng.random() < 0.7 else None

            data_decisao = None
            if status in StatusOcorrencia.finais():
                data_decisao = (
                    data_cadastro + timedelta(hours=rng.randint(2, 240))
                ).replace(microsecond=0)
                if data_decisao > agora:
                    data_decisao = agora

            ocorrencia = Ocorrencia(
                protocolo=f"{PREFIXO_PROTOCOLO_DEMO}{indice + 1:04d}",
                chave_idempotencia=f"demo-{semente}-{indice}",
                data_hora_avistamento=data_avistamento.isoformat(),
                data_hora_cadastro=data_cadastro.isoformat(),
                estado=uf,
                municipio=municipio,
                latitude=latitude,
                longitude=longitude,
                precisao_metros=None,
                origem_localizacao=OrigemLocalizacao.REGIAO_APROXIMADA,
                profundidade=profundidade,
                habitat=habitat,
                quantidade_observada=quantidade_observada,
                descricao="Registro de demonstração — não corresponde a avistamento real.",
                origem_registro=OrigemRegistro.DEMONSTRACAO,
                tipo_dado=TipoDado.DEMO,
                status=status,
                fonte_dados_id=fonte.id,
                autoriza_publicar_imagem=False,
                data_primeira_decisao=data_decisao.isoformat() if data_decisao else None,
            )

            try:
                with transacao(self.caminho):
                    self.ocorrencias.criar(ocorrencia)
                    if avaliador is not None and status in StatusOcorrencia.finais():
                        decisao = {
                            StatusOcorrencia.CONFIRMADO: Decisao.CONFIRMAR,
                            StatusOcorrencia.REJEITADO: Decisao.REJEITAR,
                            StatusOcorrencia.INCONCLUSIVO: Decisao.INCONCLUSIVO,
                        }[status]
                        self.validacoes.registrar(
                            Validacao(
                                ocorrencia_id=ocorrencia.id,
                                avaliador_id=avaliador,
                                decisao=decisao,
                                justificativa=rng.choice(JUSTIFICATIVAS_DEMO),
                                status_anterior=StatusOcorrencia.PENDENTE,
                                status_novo=status,
                                data_validacao=(data_decisao or data_cadastro).isoformat(),
                            )
                        )
                        validacoes_criadas += 1
                criados += 1
            except RegistroDuplicado:
                existentes += 1

        self.auditoria.registrar(
            entidade="ocorrencia",
            acao="SEMEADURA_DEMONSTRACAO",
            entidade_id=None,
            detalhes={"criados": criados, "semente": semente, "existentes": existentes},
        )

        return ResultadoSemeadura(
            criados=criados,
            validacoes=validacoes_criadas,
            ja_existentes=existentes,
            semente=semente,
            fonte_id=fonte.id,
        )

    def _obter_avaliador(self) -> int | None:
        """Usa um avaliador real da base para atribuir o histórico de demonstração."""
        for usuario in self.usuarios.listar():
            if usuario.perfil in (Perfil.ADMINISTRADOR, Perfil.PESQUISADOR):
                return usuario.id
        return None

    def remover(self) -> int:
        """Remove todos os dados de demonstração (cascata apaga validações)."""
        removidos = self.ocorrencias.remover_demonstracao()
        self.auditoria.registrar(
            entidade="ocorrencia",
            acao="REMOCAO_DEMONSTRACAO",
            detalhes={"removidos": removidos, "em": agora_iso()},
        )
        return removidos
