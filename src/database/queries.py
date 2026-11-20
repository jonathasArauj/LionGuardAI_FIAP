"""
Consultas analíticas reutilizáveis — fonte única de verdade dos dashboards.

Nenhum indicador é fixo: todos os números vêm de agregações SQL sobre as
tabelas. Os filtros globais (período, estado, município, status, origem e
procedência do dado) são aplicados pela mesma cláusula WHERE em todas as
consultas, o que garante que cards, gráficos e tabelas concordem entre si.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

from src.database.connection import consultar, consultar_escalar
from src.database.schema import StatusOcorrencia, TipoDado


@dataclass(slots=True)
class Filtros:
    """Filtros globais dos dashboards."""

    data_inicio: str | None = None
    data_fim: str | None = None
    estados: list[str] = field(default_factory=list)
    municipios: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    origens: list[str] = field(default_factory=list)
    # Procedência: por padrão o painel mostra tudo, mas sempre identificado.
    tipos_dado: list[str] = field(
        default_factory=lambda: [str(TipoDado.REAL), str(TipoDado.IMPORTADO), str(TipoDado.DEMO)]
    )
    somente_com_coordenadas: bool = False

    def sem_demonstracao(self) -> Filtros:
        """Cópia dos filtros excluindo todos os dados de demonstração."""
        return Filtros(
            data_inicio=self.data_inicio,
            data_fim=self.data_fim,
            estados=list(self.estados),
            municipios=list(self.municipios),
            status=list(self.status),
            origens=list(self.origens),
            tipos_dado=[t for t in self.tipos_dado if t != str(TipoDado.DEMO)],
            somente_com_coordenadas=self.somente_com_coordenadas,
        )

    @property
    def inclui_demonstracao(self) -> bool:
        return str(TipoDado.DEMO) in self.tipos_dado


def construir_where(filtros: Filtros | None, alias: str = "o") -> tuple[str, list]:
    """
    Monta a cláusula WHERE e a lista de parâmetros.

    Devolve sempre uma cláusula iniciada por `WHERE 1 = 1`, o que permite
    concatenar condições adicionais sem tratar o primeiro caso.
    """
    filtros = filtros or Filtros()
    partes = ["WHERE 1 = 1"]
    parametros: list = []
    p = f"{alias}." if alias else ""

    def _in(coluna: str, valores: list[str]) -> None:
        if valores:
            marcadores = ", ".join("?" for _ in valores)
            partes.append(f"AND {p}{coluna} IN ({marcadores})")
            parametros.extend(valores)

    if filtros.data_inicio:
        partes.append(f"AND date({p}data_hora_avistamento) >= date(?)")
        parametros.append(filtros.data_inicio)
    if filtros.data_fim:
        partes.append(f"AND date({p}data_hora_avistamento) <= date(?)")
        parametros.append(filtros.data_fim)

    _in("estado", filtros.estados)
    _in("municipio", filtros.municipios)
    _in("status", filtros.status)
    _in("origem_registro", filtros.origens)
    _in("tipo_dado", filtros.tipos_dado)

    if filtros.somente_com_coordenadas:
        partes.append(f"AND {p}latitude IS NOT NULL AND {p}longitude IS NOT NULL")

    return " ".join(partes), parametros


# ---------------------------------------------------------------------- KPIs
def kpis_gerais(filtros: Filtros | None = None, caminho: str | Path | None = None) -> dict:
    """
    Indicadores do painel executivo (Dashboard 1).

    Definições (seção 5.1 do escopo):
      * total: ocorrências únicas cadastradas que atendem aos filtros;
      * confirmados/pendentes/rejeitados: contagem por status;
      * percentual_validado: registros com decisão final / total elegível;
      * tempo_mediano_revisao_horas: mediana entre cadastro e primeira decisão.
    """
    where, parametros = construir_where(filtros, "o")

    linha = consultar(
        f"""
        SELECT
            COUNT(*)                                                   AS total,
            SUM(CASE WHEN o.status = 'CONFIRMADO'      THEN 1 ELSE 0 END) AS confirmados,
            SUM(CASE WHEN o.status = 'PENDENTE'        THEN 1 ELSE 0 END) AS pendentes,
            SUM(CASE WHEN o.status = 'REJEITADO'       THEN 1 ELSE 0 END) AS rejeitados,
            SUM(CASE WHEN o.status = 'INCONCLUSIVO'    THEN 1 ELSE 0 END) AS inconclusivos,
            SUM(CASE WHEN o.status = 'AGUARDANDO_INFO' THEN 1 ELSE 0 END) AS aguardando_info,
            COUNT(DISTINCT o.municipio)                                AS municipios,
            COUNT(DISTINCT o.estado)                                   AS estados,
            SUM(CASE WHEN o.tipo_dado = 'DEMO' THEN 1 ELSE 0 END)      AS demonstrativos
          FROM ocorrencia o
          {where}
        """,
        tuple(parametros),
        caminho,
    )[0]

    total = int(linha["total"] or 0)
    decididos = (
        int(linha["confirmados"] or 0)
        + int(linha["rejeitados"] or 0)
        + int(linha["inconclusivos"] or 0)
    )

    return {
        "total": total,
        "confirmados": int(linha["confirmados"] or 0),
        "pendentes": int(linha["pendentes"] or 0),
        "rejeitados": int(linha["rejeitados"] or 0),
        "inconclusivos": int(linha["inconclusivos"] or 0),
        "aguardando_info": int(linha["aguardando_info"] or 0),
        "municipios": int(linha["municipios"] or 0),
        "estados": int(linha["estados"] or 0),
        "demonstrativos": int(linha["demonstrativos"] or 0),
        "decididos": decididos,
        "percentual_validado": round(100.0 * decididos / total, 1) if total else None,
        "tempo_mediano_revisao_horas": tempo_mediano_revisao(filtros, caminho),
        "novos_no_periodo": novos_no_periodo(filtros, caminho),
    }


def novos_no_periodo(filtros: Filtros | None = None, caminho: str | Path | None = None) -> int:
    """Registros **cadastrados** dentro da janela de datas do filtro."""
    filtros = filtros or Filtros()
    where, parametros = construir_where(
        Filtros(
            estados=filtros.estados,
            municipios=filtros.municipios,
            status=filtros.status,
            origens=filtros.origens,
            tipos_dado=filtros.tipos_dado,
        ),
        "o",
    )
    sql = [f"SELECT COUNT(*) FROM ocorrencia o {where}"]
    if filtros.data_inicio:
        sql.append("AND date(o.data_hora_cadastro) >= date(?)")
        parametros.append(filtros.data_inicio)
    if filtros.data_fim:
        sql.append("AND date(o.data_hora_cadastro) <= date(?)")
        parametros.append(filtros.data_fim)
    return int(consultar_escalar(" ".join(sql), tuple(parametros), caminho, 0))


def duracoes_revisao_horas(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[float]:
    """Horas entre o cadastro e a primeira decisão final, por ocorrência."""
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT (julianday(o.data_primeira_decisao)
              - julianday(o.data_hora_cadastro)) * 24.0 AS horas
          FROM ocorrencia o
          {where}
           AND o.data_primeira_decisao IS NOT NULL
        """,
        tuple(parametros),
        caminho,
    )
    return [float(linha["horas"]) for linha in linhas if linha["horas"] is not None]


def tempo_mediano_revisao(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> float | None:
    duracoes = duracoes_revisao_horas(filtros, caminho)
    if not duracoes:
        return None
    return round(statistics.median(duracoes), 2)


# ------------------------------------------------------------------- agregações
def contagem_por_status(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.status AS status, COUNT(*) AS total
          FROM ocorrencia o
          {where}
         GROUP BY o.status
         ORDER BY total DESC
        """,
        tuple(parametros),
        caminho,
    )
    return [{"status": linha["status"], "total": int(linha["total"])} for linha in linhas]


def total_por_estado(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT COALESCE(o.estado, 'NÃO INFORMADO') AS estado,
               COUNT(*)                            AS total,
               SUM(CASE WHEN o.status = 'CONFIRMADO' THEN 1 ELSE 0 END) AS confirmados
          FROM ocorrencia o
          {where}
         GROUP BY COALESCE(o.estado, 'NÃO INFORMADO')
         ORDER BY total DESC, estado
        """,
        tuple(parametros),
        caminho,
    )
    return [
        {
            "estado": linha["estado"],
            "total": int(linha["total"]),
            "confirmados": int(linha["confirmados"] or 0),
        }
        for linha in linhas
    ]


def total_por_municipio(
    filtros: Filtros | None = None, limite: int = 10, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT COALESCE(o.municipio, 'NÃO INFORMADO') AS municipio,
               COALESCE(o.estado, '--')               AS estado,
               COUNT(*)                                AS total
          FROM ocorrencia o
          {where}
         GROUP BY COALESCE(o.municipio, 'NÃO INFORMADO'), COALESCE(o.estado, '--')
         ORDER BY total DESC, municipio
         LIMIT ?
        """,
        (*parametros, int(limite)),
        caminho,
    )
    return [
        {
            "municipio": linha["municipio"],
            "estado": linha["estado"],
            "total": int(linha["total"]),
            "rotulo": f"{linha['municipio']} ({linha['estado']})",
        }
        for linha in linhas
    ]


def evolucao_mensal(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT strftime('%Y-%m', o.data_hora_avistamento) AS mes,
               COUNT(*)                                    AS total,
               SUM(CASE WHEN o.status = 'CONFIRMADO' THEN 1 ELSE 0 END) AS confirmados
          FROM ocorrencia o
          {where}
         GROUP BY mes
         ORDER BY mes
        """,
        tuple(parametros),
        caminho,
    )
    return [
        {
            "mes": linha["mes"],
            "total": int(linha["total"]),
            "confirmados": int(linha["confirmados"] or 0),
        }
        for linha in linhas
        if linha["mes"]
    ]


def evolucao_mensal_por_estado(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT strftime('%Y-%m', o.data_hora_avistamento) AS mes,
               COALESCE(o.estado, 'NÃO INFORMADO')         AS estado,
               COUNT(*)                                    AS total
          FROM ocorrencia o
          {where}
         GROUP BY mes, estado
         ORDER BY mes, estado
        """,
        tuple(parametros),
        caminho,
    )
    return [
        {"mes": linha["mes"], "estado": linha["estado"], "total": int(linha["total"])}
        for linha in linhas
        if linha["mes"]
    ]


def distribuicao_por_origem(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.origem_registro AS origem, COUNT(*) AS total
          FROM ocorrencia o
          {where}
         GROUP BY o.origem_registro
         ORDER BY total DESC
        """,
        tuple(parametros),
        caminho,
    )
    return [{"origem": linha["origem"], "total": int(linha["total"])} for linha in linhas]


def distribuicao_por_tipo_dado(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.tipo_dado AS tipo_dado, COUNT(*) AS total
          FROM ocorrencia o
          {where}
         GROUP BY o.tipo_dado
         ORDER BY total DESC
        """,
        tuple(parametros),
        caminho,
    )
    return [{"tipo_dado": linha["tipo_dado"], "total": int(linha["total"])} for linha in linhas]


def distribuicao_por_habitat(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    """
    Distribuição por habitat. `NAO_INFORMADO` é mantido como categoria própria —
    nunca redistribuído entre as demais (seção 5.3 do escopo).
    """
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.habitat AS habitat, COUNT(*) AS total
          FROM ocorrencia o
          {where}
         GROUP BY o.habitat
         ORDER BY total DESC
        """,
        tuple(parametros),
        caminho,
    )
    return [{"habitat": linha["habitat"], "total": int(linha["total"])} for linha in linhas]


def profundidades(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[float]:
    """Profundidades informadas. Valores nulos são descartados, não zerados."""
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.profundidade AS profundidade
          FROM ocorrencia o
          {where}
           AND o.profundidade IS NOT NULL
         ORDER BY o.profundidade
        """,
        tuple(parametros),
        caminho,
    )
    return [float(linha["profundidade"]) for linha in linhas]


def distribuicao_por_hora(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[dict]:
    """Avistamentos por hora do dia, usando o horário informado do avistamento."""
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT CAST(strftime('%H', o.data_hora_avistamento) AS INTEGER) AS hora,
               COUNT(*) AS total
          FROM ocorrencia o
          {where}
         GROUP BY hora
         ORDER BY hora
        """,
        tuple(parametros),
        caminho,
    )
    return [
        {"hora": int(linha["hora"]), "total": int(linha["total"])}
        for linha in linhas
        if linha["hora"] is not None
    ]


def quantidades_observadas(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> list[int]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.quantidade_observada AS q
          FROM ocorrencia o
          {where}
           AND o.quantidade_observada IS NOT NULL
        """,
        tuple(parametros),
        caminho,
    )
    return [int(linha["q"]) for linha in linhas]


# ----------------------------------------------------------------- completude
def estatisticas_completude(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> dict:
    """Percentual de preenchimento dos campos relevantes (qualidade dos dados)."""
    where, parametros = construir_where(filtros, "o")
    linha = consultar(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN o.latitude IS NOT NULL AND o.longitude IS NOT NULL
                     THEN 1 ELSE 0 END)                        AS com_coordenadas,
            SUM(CASE WHEN o.origem_localizacao IN ('GPS_DISPOSITIVO','MAPA_MANUAL')
                      AND o.latitude IS NOT NULL
                     THEN 1 ELSE 0 END)                        AS localizacao_precisa,
            SUM(CASE WHEN o.profundidade IS NOT NULL THEN 1 ELSE 0 END) AS com_profundidade,
            SUM(CASE WHEN o.habitat <> 'NAO_INFORMADO' THEN 1 ELSE 0 END) AS com_habitat,
            SUM(CASE WHEN o.quantidade_observada IS NOT NULL THEN 1 ELSE 0 END) AS com_quantidade,
            SUM(CASE WHEN o.descricao IS NOT NULL AND TRIM(o.descricao) <> ''
                     THEN 1 ELSE 0 END)                        AS com_descricao,
            SUM(CASE WHEN EXISTS (SELECT 1 FROM imagem i WHERE i.ocorrencia_id = o.id)
                     THEN 1 ELSE 0 END)                        AS com_imagem,
            SUM(CASE WHEN o.status = 'PENDENTE' THEN 1 ELSE 0 END) AS pendentes
          FROM ocorrencia o
          {where}
        """,
        tuple(parametros),
        caminho,
    )[0]

    total = int(linha["total"] or 0)

    def _pct(coluna: str) -> float | None:
        if not total:
            return None
        return round(100.0 * int(linha[coluna] or 0) / total, 1)

    return {
        "total": total,
        "com_coordenadas": int(linha["com_coordenadas"] or 0),
        "localizacao_precisa": int(linha["localizacao_precisa"] or 0),
        "com_profundidade": int(linha["com_profundidade"] or 0),
        "com_habitat": int(linha["com_habitat"] or 0),
        "com_quantidade": int(linha["com_quantidade"] or 0),
        "com_descricao": int(linha["com_descricao"] or 0),
        "com_imagem": int(linha["com_imagem"] or 0),
        "pendentes": int(linha["pendentes"] or 0),
        "pct_coordenadas": _pct("com_coordenadas"),
        "pct_localizacao_precisa": _pct("localizacao_precisa"),
        "pct_profundidade": _pct("com_profundidade"),
        "pct_habitat": _pct("com_habitat"),
        "pct_quantidade": _pct("com_quantidade"),
        "pct_descricao": _pct("com_descricao"),
        "pct_imagem": _pct("com_imagem"),
        "pct_pendente": _pct("pendentes"),
    }


# ----------------------------------------------------------------- geográficas
def dados_geograficos(
    filtros: Filtros | None = None,
    publico: bool = True,
    caminho: str | Path | None = None,
) -> list[dict]:
    """
    Pontos para o mapa.

    Com `publico=True` as coordenadas são arredondadas antes de sair do banco
    (visualização aproximada) e a imagem só é exposta se houver autorização.
    """
    from src.config import get_config

    casas = get_config().casas_decimais_publicas
    where, parametros = construir_where(filtros, "o")

    if publico:
        selecao_coord = f"ROUND(o.latitude, {casas}) AS latitude, ROUND(o.longitude, {casas}) AS longitude"
    else:
        selecao_coord = "o.latitude AS latitude, o.longitude AS longitude"

    linhas = consultar(
        f"""
        SELECT o.id                     AS id,
               o.protocolo              AS protocolo,
               {selecao_coord},
               o.precisao_metros        AS precisao_metros,
               o.origem_localizacao     AS origem_localizacao,
               o.estado                 AS estado,
               o.municipio              AS municipio,
               o.data_hora_avistamento  AS data_hora_avistamento,
               o.status                 AS status,
               o.origem_registro        AS origem_registro,
               o.tipo_dado              AS tipo_dado,
               o.quantidade_observada   AS quantidade_observada,
               o.autoriza_publicar_imagem AS autoriza_publicar_imagem,
               (SELECT i.identificador_arquivo FROM imagem i
                 WHERE i.ocorrencia_id = o.id ORDER BY i.id LIMIT 1) AS arquivo_imagem,
               (SELECT p.classe FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS classe_ia,
               (SELECT p.score FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS score_ia
          FROM ocorrencia o
          {where}
           AND o.latitude IS NOT NULL AND o.longitude IS NOT NULL
         ORDER BY o.data_hora_avistamento DESC
        """,
        tuple(parametros),
        caminho,
    )

    pontos: list[dict] = []
    for linha in linhas:
        ponto = dict(linha)
        ponto["autoriza_publicar_imagem"] = bool(ponto["autoriza_publicar_imagem"])
        if publico and not ponto["autoriza_publicar_imagem"]:
            ponto["arquivo_imagem"] = None
        pontos.append(ponto)
    return pontos


# ----------------------------------------------------------------- listagens
def registros_recentes(
    filtros: Filtros | None = None, limite: int = 10, caminho: str | Path | None = None
) -> list[dict]:
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.protocolo, o.data_hora_avistamento, o.data_hora_cadastro,
               o.municipio, o.estado, o.status, o.origem_registro, o.tipo_dado,
               (SELECT p.classe FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS classe_ia,
               (SELECT p.score FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS score_ia
          FROM ocorrencia o
          {where}
         ORDER BY o.data_hora_cadastro DESC
         LIMIT ?
        """,
        (*parametros, int(limite)),
        caminho,
    )
    return [dict(linha) for linha in linhas]


def fila_operacional(
    filtros: Filtros | None = None, limite: int = 200, caminho: str | Path | None = None
) -> list[dict]:
    """Tabela do painel operacional, com dados necessários à revisão."""
    where, parametros = construir_where(filtros, "o")
    linhas = consultar(
        f"""
        SELECT o.id, o.protocolo, o.data_hora_avistamento, o.data_hora_cadastro,
               o.municipio, o.estado, o.status, o.origem_registro, o.tipo_dado,
               o.latitude, o.longitude, o.origem_localizacao, o.precisao_metros,
               o.profundidade, o.habitat, o.quantidade_observada, o.descricao,
               (SELECT i.identificador_arquivo FROM imagem i
                 WHERE i.ocorrencia_id = o.id ORDER BY i.id LIMIT 1) AS arquivo_imagem,
               (SELECT p.classe FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS classe_ia,
               (SELECT p.score FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS score_ia,
               (SELECT COUNT(*) FROM validacao v WHERE v.ocorrencia_id = o.id) AS revisoes
          FROM ocorrencia o
          {where}
         ORDER BY
            CASE o.status
                WHEN 'PENDENTE'        THEN 0
                WHEN 'AGUARDANDO_INFO' THEN 1
                ELSE 2
            END,
            o.data_hora_cadastro ASC
         LIMIT ?
        """,
        (*parametros, int(limite)),
        caminho,
    )
    return [dict(linha) for linha in linhas]


def indicadores_operacionais(
    filtros: Filtros | None = None, caminho: str | Path | None = None
) -> dict:
    where, parametros = construir_where(filtros, "o")
    linha = consultar(
        f"""
        SELECT
            SUM(CASE WHEN o.status = 'PENDENTE' THEN 1 ELSE 0 END)        AS pendentes,
            SUM(CASE WHEN o.status = 'AGUARDANDO_INFO' THEN 1 ELSE 0 END) AS aguardando_info,
            SUM(CASE WHEN o.data_primeira_decisao IS NOT NULL THEN 1 ELSE 0 END) AS revisados,
            SUM(CASE WHEN o.latitude IS NULL OR o.longitude IS NULL
                     THEN 1 ELSE 0 END)                                   AS sem_coordenadas,
            SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM imagem i WHERE i.ocorrencia_id = o.id)
                     THEN 1 ELSE 0 END)                                   AS sem_imagem,
            SUM(CASE WHEN EXISTS (SELECT 1 FROM predicao p
                                   WHERE p.ocorrencia_id = o.id AND p.classe = 'ERRO')
                     THEN 1 ELSE 0 END)                                   AS com_erro_ia
          FROM ocorrencia o
          {where}
        """,
        tuple(parametros),
        caminho,
    )[0]
    dados = {chave: int(linha[chave] or 0) for chave in linha.keys()}
    dados["tempo_mediano_revisao_horas"] = tempo_mediano_revisao(filtros, caminho)
    return dados


def valores_de_filtro(caminho: str | Path | None = None) -> dict:
    """Valores disponíveis para popular os seletores dos dashboards."""
    estados = [
        linha["estado"]
        for linha in consultar(
            "SELECT DISTINCT estado FROM ocorrencia WHERE estado IS NOT NULL ORDER BY estado",
            (),
            caminho,
        )
    ]
    municipios = [
        linha["municipio"]
        for linha in consultar(
            "SELECT DISTINCT municipio FROM ocorrencia "
            "WHERE municipio IS NOT NULL ORDER BY municipio",
            (),
            caminho,
        )
    ]
    periodo = consultar(
        """
        SELECT MIN(date(data_hora_avistamento)) AS inicio,
               MAX(date(data_hora_avistamento)) AS fim
          FROM ocorrencia
        """,
        (),
        caminho,
    )[0]
    return {
        "estados": estados,
        "municipios": municipios,
        "status": [str(s) for s in StatusOcorrencia],
        "data_minima": periodo["inicio"],
        "data_maxima": periodo["fim"],
    }


# -------------------------------------------------------------- IA / predições
def metricas_inferencia(caminho: str | Path | None = None) -> dict:
    """Estatísticas das inferências efetivamente executadas em produção."""
    linha = consultar(
        """
        SELECT COUNT(*) AS total,
               AVG(tempo_inferencia_ms) AS media_ms,
               MIN(tempo_inferencia_ms) AS min_ms,
               MAX(tempo_inferencia_ms) AS max_ms
          FROM predicao
         WHERE classe NOT IN ('SEM_MODELO', 'ERRO')
        """,
        (),
        caminho,
    )[0]
    tempos = [
        float(r["tempo_inferencia_ms"])
        for r in consultar(
            """
            SELECT tempo_inferencia_ms FROM predicao
             WHERE tempo_inferencia_ms IS NOT NULL
               AND classe NOT IN ('SEM_MODELO', 'ERRO')
            """,
            (),
            caminho,
        )
    ]
    return {
        "total_inferencias": int(linha["total"] or 0),
        "tempo_medio_ms": round(float(linha["media_ms"]), 2) if linha["media_ms"] else None,
        "tempo_mediano_ms": round(statistics.median(tempos), 2) if tempos else None,
        "tempo_minimo_ms": round(float(linha["min_ms"]), 2) if linha["min_ms"] else None,
        "tempo_maximo_ms": round(float(linha["max_ms"]), 2) if linha["max_ms"] else None,
    }


def distribuicao_scores(caminho: str | Path | None = None) -> list[dict]:
    linhas = consultar(
        """
        SELECT classe, score
          FROM predicao
         WHERE score IS NOT NULL
         ORDER BY score
        """,
        (),
        caminho,
    )
    return [{"classe": linha["classe"], "score": float(linha["score"])} for linha in linhas]


def inferencias_recentes(limite: int = 50, caminho: str | Path | None = None) -> list[dict]:
    linhas = consultar(
        """
        SELECT o.protocolo, p.modelo, p.versao, p.classe, p.score,
               p.tempo_inferencia_ms, p.criado_em, o.status
          FROM predicao p
          JOIN ocorrencia o ON o.id = p.ocorrencia_id
         ORDER BY p.id DESC
         LIMIT ?
        """,
        (int(limite),),
        caminho,
    )
    return [dict(linha) for linha in linhas]


def concordancia_ia_humano(caminho: str | Path | None = None) -> dict:
    """
    Compara a classe da IA com a decisão humana, apenas em ocorrências já
    decididas. Isto é uma matriz operacional (produção), diferente da matriz de
    confusão do conjunto de teste do treinamento.
    """
    linhas = consultar(
        """
        SELECT ultima.classe AS classe_ia, o.status AS status
          FROM ocorrencia o
          JOIN (
                SELECT p.ocorrencia_id, p.classe
                  FROM predicao p
                  JOIN (SELECT ocorrencia_id, MAX(id) AS max_id
                          FROM predicao GROUP BY ocorrencia_id) ultimos
                    ON ultimos.max_id = p.id
               ) ultima ON ultima.ocorrencia_id = o.id
         WHERE o.status IN ('CONFIRMADO', 'REJEITADO')
           AND ultima.classe IN ('PEIXE_LEAO', 'NAO_PEIXE_LEAO')
        """,
        (),
        caminho,
    )
    matriz = {
        "ia_positiva_humano_confirmou": 0,
        "ia_positiva_humano_rejeitou": 0,
        "ia_negativa_humano_confirmou": 0,
        "ia_negativa_humano_rejeitou": 0,
    }
    for linha in linhas:
        positiva = linha["classe_ia"] == "PEIXE_LEAO"
        confirmou = linha["status"] == "CONFIRMADO"
        if positiva and confirmou:
            matriz["ia_positiva_humano_confirmou"] += 1
        elif positiva and not confirmou:
            matriz["ia_positiva_humano_rejeitou"] += 1
        elif not positiva and confirmou:
            matriz["ia_negativa_humano_confirmou"] += 1
        else:
            matriz["ia_negativa_humano_rejeitou"] += 1
    matriz["total"] = sum(
        v for k, v in matriz.items() if k != "total"
    )
    return matriz


# ----------------------------------------------------------------- exportação
def exportar_ocorrencias(
    filtros: Filtros | None = None,
    incluir_coordenadas_precisas: bool = False,
    caminho: str | Path | None = None,
) -> list[dict]:
    """
    Dados para exportação CSV. Sem autorização, as coordenadas saem
    arredondadas e nenhum dado de contato é incluído.
    """
    from src.config import get_config

    casas = get_config().casas_decimais_publicas
    where, parametros = construir_where(filtros, "o")
    coord = (
        "o.latitude AS latitude, o.longitude AS longitude"
        if incluir_coordenadas_precisas
        else f"ROUND(o.latitude, {casas}) AS latitude, ROUND(o.longitude, {casas}) AS longitude"
    )
    linhas = consultar(
        f"""
        SELECT o.protocolo, o.data_hora_avistamento, o.data_hora_cadastro,
               o.estado, o.municipio, {coord},
               o.origem_localizacao, o.precisao_metros, o.profundidade, o.habitat,
               o.quantidade_observada, o.origem_registro, o.tipo_dado, o.status,
               (SELECT p.classe FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS classe_ia,
               (SELECT p.score FROM predicao p
                 WHERE p.ocorrencia_id = o.id ORDER BY p.id DESC LIMIT 1) AS score_ia
          FROM ocorrencia o
          {where}
         ORDER BY o.data_hora_avistamento DESC
        """,
        tuple(parametros),
        caminho,
    )
    return [dict(linha) for linha in linhas]
