"""
Camada de análise — converte o resultado das consultas SQL em estruturas
prontas para os gráficos e para exportação.

Nenhum número é calculado aqui a partir de constantes: todos vêm de
`src.database.queries`. Este módulo apenas organiza, formata e, quando faz
sentido estatístico, resume (histogramas, percentuais, séries completas de
meses sem buraco).
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.config import get_config
from src.database import queries
from src.database.queries import Filtros
from src.database.schema import Habitat, StatusOcorrencia, TipoDado
from src.security.auth import Sessao
from src.security.permissions import Permissao, exigir, tem_permissao

ROTULOS_STATUS = {
    "PENDENTE": "Pendente de validação",
    "AGUARDANDO_INFO": "Aguardando informações",
    "CONFIRMADO": "Confirmado",
    "REJEITADO": "Rejeitado",
    "INCONCLUSIVO": "Inconclusivo",
}

ROTULOS_HABITAT = {
    "RECIFE": "Recife",
    "COSTAO_ROCHOSO": "Costão rochoso",
    "AREA_ARENOSA": "Área arenosa",
    "MANGUEZAL": "Manguezal",
    "OUTRO": "Outro ambiente",
    "NAO_INFORMADO": "Não informado",
}

ROTULOS_ORIGEM = {
    "CIDADAO": "Cidadão",
    "PESCADOR": "Pescador",
    "MERGULHADOR": "Mergulhador",
    "PESQUISADOR": "Pesquisador",
    "IMPORTACAO": "Importação de fonte externa",
    "DEMONSTRACAO": "Dado de demonstração",
}

ROTULOS_TIPO_DADO = {
    "REAL": "Registro de usuário",
    "IMPORTADO": "Importado de fonte documentada",
    "DEMO": "Demonstração (não é dado real)",
}

ROTULOS_CLASSE_IA = {
    "PEIXE_LEAO": "Possível peixe-leão",
    "NAO_PEIXE_LEAO": "Não identificado",
    "INCONCLUSIVO": "Inconclusivo",
    "SEM_MODELO": "Sem modelo disponível",
    "ERRO": "Erro na análise",
}

# Cores de status usadas no mapa e nos gráficos (seção 5.2 do escopo).
CORES_STATUS = {
    "PENDENTE": "#F59E0B",
    "AGUARDANDO_INFO": "#D97706",
    "CONFIRMADO": "#DC2626",
    "REJEITADO": "#9CA3AF",
    "INCONCLUSIVO": "#2563EB",
}


def rotular(valor: str | None, mapa: dict[str, str]) -> str:
    if valor is None:
        return "Não informado"
    return mapa.get(str(valor), str(valor).replace("_", " ").capitalize())


# ------------------------------------------------------------------ dashboards
def painel_geral(filtros: Filtros | None = None, caminho=None) -> dict:
    """Todos os dados do Dashboard 1 em uma chamada."""
    kpis = queries.kpis_gerais(filtros, caminho)
    return {
        "kpis": kpis,
        "por_status": _df(
            queries.contagem_por_status(filtros, caminho),
            colunas={"status": "Status", "total": "Registros"},
            rotulos={"status": ROTULOS_STATUS},
        ),
        "por_estado": _df(
            queries.total_por_estado(filtros, caminho),
            colunas={"estado": "Estado", "total": "Registros", "confirmados": "Confirmados"},
        ),
        "por_municipio": _df(
            queries.total_por_municipio(filtros, 10, caminho),
            colunas={"rotulo": "Município", "total": "Registros"},
        ),
        "mensal": serie_mensal_completa(filtros, caminho),
        "por_origem": _df(
            queries.distribuicao_por_origem(filtros, caminho),
            colunas={"origem": "Origem", "total": "Registros"},
            rotulos={"origem": ROTULOS_ORIGEM},
        ),
        "por_tipo_dado": _df(
            queries.distribuicao_por_tipo_dado(filtros, caminho),
            colunas={"tipo_dado": "Procedência", "total": "Registros"},
            rotulos={"tipo_dado": ROTULOS_TIPO_DADO},
        ),
        "recentes": _df(
            queries.registros_recentes(filtros, 10, caminho),
            colunas={
                "protocolo": "Protocolo",
                "data_hora_avistamento": "Avistamento",
                "municipio": "Município",
                "estado": "UF",
                "status": "Status",
                "classe_ia": "IA",
                "score_ia": "Score",
            },
            rotulos={"status": ROTULOS_STATUS, "classe_ia": ROTULOS_CLASSE_IA},
        ),
    }


def _df(registros: list[dict], colunas: dict[str, str], rotulos: dict | None = None):
    """
    Monta um DataFrame com as colunas pedidas, aplicando rótulos legíveis.

    Devolve DataFrame vazio (com as colunas corretas) quando não há dados, para
    que os gráficos exibam estado vazio em vez de erro.
    """
    if not registros:
        return pd.DataFrame({nome: [] for nome in colunas.values()})

    dados: dict[str, list] = {}
    for chave, titulo in colunas.items():
        valores = [registro.get(chave) for registro in registros]
        if rotulos and chave in rotulos:
            valores = [rotular(valor, rotulos[chave]) for valor in valores]
        dados[titulo] = valores
    return pd.DataFrame(dados)


def serie_mensal_completa(filtros: Filtros | None = None, caminho=None):
    """
    Série mensal sem meses faltando.

    Meses sem registro recebem zero **somente** dentro do intervalo observado —
    não há extrapolação para antes do primeiro nem depois do último registro.
    """
    linhas = queries.evolucao_mensal(filtros, caminho)
    if not linhas:
        return pd.DataFrame({"Mês": [], "Registros": [], "Confirmados": []})

    inicio = datetime.strptime(linhas[0]["mes"], "%Y-%m").date().replace(day=1)
    fim = datetime.strptime(linhas[-1]["mes"], "%Y-%m").date().replace(day=1)
    indice = pd.period_range(start=inicio, end=fim, freq="M").strftime("%Y-%m")

    por_mes = {linha["mes"]: linha for linha in linhas}
    return pd.DataFrame(
        {
            "Mês": list(indice),
            "Registros": [por_mes.get(mes, {}).get("total", 0) for mes in indice],
            "Confirmados": [por_mes.get(mes, {}).get("confirmados", 0) for mes in indice],
        }
    )


def painel_cientifico(filtros: Filtros | None = None, caminho=None) -> dict:
    """Dados do Dashboard 3 — análise exploratória."""
    completude = queries.estatisticas_completude(filtros, caminho)
    profundidades_lista = queries.profundidades(filtros, caminho)
    quantidades = queries.quantidades_observadas(filtros, caminho)

    return {
        "completude": completude,
        "resumo_profundidade": resumo_numerico(profundidades_lista, "m"),
        "profundidades": profundidades_lista,
        "histograma_profundidade": histograma(profundidades_lista, largura_classe=5.0),
        "resumo_quantidade": resumo_numerico([float(q) for q in quantidades], "indivíduos"),
        "por_habitat": _df(
            queries.distribuicao_por_habitat(filtros, caminho),
            colunas={"habitat": "Habitat", "total": "Registros"},
            rotulos={"habitat": ROTULOS_HABITAT},
        ),
        "por_hora": distribuicao_horaria_completa(filtros, caminho),
        "mensal": serie_mensal_completa(filtros, caminho),
        "mensal_por_estado": _df(
            queries.evolucao_mensal_por_estado(filtros, caminho),
            colunas={"mes": "Mês", "estado": "Estado", "total": "Registros"},
        ),
        "qualidade": _df(
            [
                {"indicador": "Com coordenadas", "percentual": completude["pct_coordenadas"]},
                {
                    "indicador": "Localização precisa (GPS/mapa)",
                    "percentual": completude["pct_localizacao_precisa"],
                },
                {"indicador": "Com fotografia", "percentual": completude["pct_imagem"]},
                {"indicador": "Com profundidade", "percentual": completude["pct_profundidade"]},
                {"indicador": "Com habitat", "percentual": completude["pct_habitat"]},
                {"indicador": "Com quantidade", "percentual": completude["pct_quantidade"]},
                {"indicador": "Pendentes de validação", "percentual": completude["pct_pendente"]},
            ],
            colunas={"indicador": "Indicador", "percentual": "Percentual"},
        ),
    }


def distribuicao_horaria_completa(filtros: Filtros | None = None, caminho=None):
    """As 24 horas do dia, com zero nas horas sem registro."""
    linhas = {item["hora"]: item["total"] for item in queries.distribuicao_por_hora(filtros, caminho)}
    return pd.DataFrame(
        {
            "Hora": [f"{hora:02d}h" for hora in range(24)],
            "Registros": [linhas.get(hora, 0) for hora in range(24)],
        }
    )


def resumo_numerico(valores: list[float], unidade: str = "") -> dict:
    """
    Estatísticas descritivas de uma lista de valores.

    Valores ausentes foram descartados na consulta SQL — nunca substituídos por
    zero (seção 5.3 do escopo). `n` informa quantos registros sustentam o
    resumo, o que permite ao leitor julgar sua representatividade.
    """
    if not valores:
        return {"n": 0, "unidade": unidade, "disponivel": False}
    ordenados = sorted(valores)
    return {
        "n": len(ordenados),
        "unidade": unidade,
        "disponivel": True,
        "minimo": round(ordenados[0], 2),
        "maximo": round(ordenados[-1], 2),
        "media": round(statistics.fmean(ordenados), 2),
        "mediana": round(statistics.median(ordenados), 2),
        "desvio_padrao": round(statistics.stdev(ordenados), 2) if len(ordenados) > 1 else None,
        "quartil_1": round(_percentil(ordenados, 25), 2),
        "quartil_3": round(_percentil(ordenados, 75), 2),
    }


def _percentil(ordenados: list[float], percentil: float) -> float:
    if not ordenados:
        return 0.0
    if len(ordenados) == 1:
        return ordenados[0]
    posicao = (len(ordenados) - 1) * percentil / 100.0
    inferior = int(posicao)
    superior = min(inferior + 1, len(ordenados) - 1)
    peso = posicao - inferior
    return ordenados[inferior] * (1 - peso) + ordenados[superior] * peso


def histograma(valores: list[float], largura_classe: float = 5.0) -> dict:
    """Histograma com classes de largura fixa, em formato pronto para gráfico."""
    if not valores:
        return {"disponivel": False, "classes": [], "contagens": [], "n": 0}
    maximo = max(valores)
    quantidade_classes = max(1, int(maximo // largura_classe) + 1)
    contagens = [0] * quantidade_classes
    for valor in valores:
        indice = min(int(valor // largura_classe), quantidade_classes - 1)
        contagens[indice] += 1
    classes = [
        f"{int(i * largura_classe)}–{int((i + 1) * largura_classe)}"
        for i in range(quantidade_classes)
    ]
    return {
        "disponivel": True,
        "classes": classes,
        "contagens": contagens,
        "n": len(valores),
        "largura_classe": largura_classe,
    }


def painel_operacional(filtros: Filtros | None = None, caminho=None) -> dict:
    """Dados do Dashboard 5 — fila de revisão."""
    from src.database.repositories import OcorrenciaRepository

    indicadores = queries.indicadores_operacionais(filtros, caminho)
    duplicatas = OcorrenciaRepository(caminho).possiveis_duplicatas()
    return {
        "indicadores": indicadores,
        "fila": queries.fila_operacional(filtros, 300, caminho),
        "possiveis_duplicatas": duplicatas,
        "quantidade_duplicatas": len(duplicatas),
    }


# --------------------------------------------------------------------- IA
def carregar_metricas_modelo(caminho_arquivo: Path | str | None = None) -> dict:
    """
    Lê as métricas geradas pelo script de avaliação.

    Se o arquivo não existir, devolve `{"disponivel": False}` — o dashboard de
    IA exibe o estado "modelo não avaliado" em vez de números inventados
    (seção 5.4 do escopo).
    """
    config = get_config()
    if caminho_arquivo is None:
        caminho_arquivo = config.diretorio_relatorios / "metricas_modelo.json"
    caminho = Path(caminho_arquivo)
    if not caminho.is_file():
        return {
            "disponivel": False,
            "motivo": (
                "Nenhuma avaliação encontrada em reports/metricas_modelo.json. "
                "Execute `python scripts/avaliar_modelo.py` após o treinamento."
            ),
        }
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as erro:
        return {"disponivel": False, "motivo": f"arquivo de métricas ilegível: {erro}"}
    dados["disponivel"] = True
    dados["arquivo"] = str(caminho)
    return dados


def painel_ia(caminho=None) -> dict:
    """Dados do Dashboard 4 — desempenho do modelo e rastreamento."""
    from src.ai.inference import obter_servico_inferencia

    servico = obter_servico_inferencia()
    metricas = carregar_metricas_modelo()
    scores = queries.distribuicao_scores(caminho)

    return {
        "estado_modelo": servico.estado,
        "descricao_modelo": servico.descricao_estado,
        "cartao": servico.cartao,
        "metricas_treinamento": metricas,
        "metricas_producao": queries.metricas_inferencia(caminho),
        "concordancia": queries.concordancia_ia_humano(caminho),
        "scores": scores,
        "histograma_scores": histograma([s["score"] for s in scores], largura_classe=0.1),
        "inferencias": _df(
            queries.inferencias_recentes(50, caminho),
            colunas={
                "protocolo": "Protocolo",
                "versao": "Versão",
                "classe": "Resultado",
                "score": "Score",
                "tempo_inferencia_ms": "Tempo (ms)",
                "criado_em": "Data/hora",
            },
            rotulos={"classe": ROTULOS_CLASSE_IA},
        ),
    }


# -------------------------------------------------------------- exportação CSV
def exportar_csv(
    filtros: Filtros | None = None,
    sessao: Sessao | None = None,
    caminho=None,
) -> tuple[str, str]:
    """
    Gera o CSV dos dados filtrados conforme o perfil do usuário.

    Coordenadas precisas só entram se o perfil tiver a permissão específica;
    caso contrário saem arredondadas. Devolve `(conteudo, nome_arquivo)`.
    """
    exigir(sessao, Permissao.EXPORTAR_DADOS)
    precisas = tem_permissao(sessao, Permissao.EXPORTAR_COORDENADAS_PRECISAS)
    registros = queries.exportar_ocorrencias(filtros, precisas, caminho)

    colunas = [
        "protocolo",
        "data_hora_avistamento",
        "data_hora_cadastro",
        "estado",
        "municipio",
        "latitude",
        "longitude",
        "origem_localizacao",
        "precisao_metros",
        "profundidade",
        "habitat",
        "quantidade_observada",
        "origem_registro",
        "tipo_dado",
        "status",
        "classe_ia",
        "score_ia",
    ]

    buffer = io.StringIO()
    buffer.write(
        "# LionGuard AI — exportação de ocorrências\n"
        f"# gerado em: {datetime.now().replace(microsecond=0).isoformat()}\n"
        f"# coordenadas: {'precisas' if precisas else 'aproximadas (arredondadas)'}\n"
        "# registros com tipo_dado=DEMO são dados de demonstração, não ocorrências reais\n"
        "# dados de ciência cidadã possuem viés de observação; "
        "ausência de registro não indica ausência da espécie\n"
    )
    escritor = csv.DictWriter(buffer, fieldnames=colunas, extrasaction="ignore")
    escritor.writeheader()
    for registro in registros:
        escritor.writerow({coluna: registro.get(coluna) for coluna in colunas})

    nome = f"lionguard_ocorrencias_{date.today().isoformat()}.csv"
    return buffer.getvalue(), nome


def indicadores_publicos(caminho=None) -> dict:
    """
    Números exibidos na página inicial, sem dados de demonstração.

    A home pública mostra apenas registros reais e importados, para não
    anunciar ao cidadão um volume que inclui dados fictícios.
    """
    filtros = Filtros(tipos_dado=[str(TipoDado.REAL), str(TipoDado.IMPORTADO)])
    kpis = queries.kpis_gerais(filtros, caminho)
    return {
        "total": kpis["total"],
        "confirmados": kpis["confirmados"],
        "pendentes": kpis["pendentes"],
        "municipios": kpis["municipios"],
        "estados": kpis["estados"],
        "ultimos": queries.registros_recentes(filtros, 5, caminho),
    }
