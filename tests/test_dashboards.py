"""
Testes das consultas analíticas e dos dados dos dashboards.

Cobertura: cálculo dos KPIs a partir do banco (nunca fixos), aplicação
simultânea dos filtros, separação dos dados de demonstração, atualização
após cadastro e após validação, séries temporais sem buracos, tratamento de
valores ausentes, agrupamento espacial e exportação.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.data.demo_seed import GeradorDemonstracao
from src.database import queries
from src.database.models import Ocorrencia
from src.database.queries import Filtros
from src.database.repositories import OcorrenciaRepository
from src.database.schema import (
    Decisao,
    Habitat,
    OrigemLocalizacao,
    OrigemRegistro,
    StatusOcorrencia,
    TipoDado,
)
from src.services import analytics
from src.services.spatial import agrupar_ocorrencias, evolucao_por_cluster
from src.services.validation import ServicoValidacao


def _criar(protocolo: str, **extras) -> Ocorrencia:
    padrao = {
        "protocolo": protocolo,
        "data_hora_avistamento": "2026-06-15T10:00:00",
        "origem_localizacao": OrigemLocalizacao.GPS_DISPOSITIVO,
        "origem_registro": OrigemRegistro.CIDADAO,
        "tipo_dado": TipoDado.REAL,
        "estado": "ES",
        "municipio": "Guarapari",
        "latitude": -20.67,
        "longitude": -40.49,
    }
    padrao.update(extras)
    return OcorrenciaRepository().criar(Ocorrencia(**padrao))


# ---------------------------------------------------------------- base vazia
def test_kpis_em_base_vazia_nao_inventam_numeros(ambiente):
    kpis = queries.kpis_gerais()
    assert kpis["total"] == 0
    assert kpis["confirmados"] == 0
    assert kpis["percentual_validado"] is None  # ausência, não zero
    assert kpis["tempo_mediano_revisao_horas"] is None


def test_completude_em_base_vazia(ambiente):
    completude = queries.estatisticas_completude()
    assert completude["total"] == 0
    assert completude["pct_coordenadas"] is None


def test_graficos_em_base_vazia_ficam_vazios(ambiente):
    painel = analytics.painel_geral()
    assert painel["por_estado"].empty
    assert painel["mensal"].empty
    assert list(painel["por_estado"].columns) == ["Estado", "Registros", "Confirmados"]


def test_agrupamento_com_poucos_pontos_nao_executa(ambiente):
    _criar("LG-2026-C00001")
    resultado = agrupar_ocorrencias(queries.dados_geograficos())
    assert resultado.executado is False
    assert "necessários" in resultado.motivo
    assert resultado.clusters == []


# -------------------------------------------------------------------- KPIs
def test_kpis_contam_por_status(ambiente):
    _criar("LG-2026-K00001", status=StatusOcorrencia.PENDENTE)
    _criar("LG-2026-K00002", status=StatusOcorrencia.CONFIRMADO)
    _criar("LG-2026-K00003", status=StatusOcorrencia.CONFIRMADO)
    _criar("LG-2026-K00004", status=StatusOcorrencia.REJEITADO)
    _criar("LG-2026-K00005", status=StatusOcorrencia.INCONCLUSIVO)

    kpis = queries.kpis_gerais()
    assert kpis["total"] == 5
    assert kpis["pendentes"] == 1
    assert kpis["confirmados"] == 2
    assert kpis["rejeitados"] == 1
    assert kpis["inconclusivos"] == 1
    assert kpis["decididos"] == 4
    assert kpis["percentual_validado"] == 80.0


def test_kpis_contam_municipios_e_estados_distintos(ambiente):
    _criar("LG-2026-M00001", estado="ES", municipio="Guarapari")
    _criar("LG-2026-M00002", estado="ES", municipio="Guarapari")
    _criar("LG-2026-M00003", estado="ES", municipio="Anchieta")
    _criar("LG-2026-M00004", estado="BA", municipio="Ilhéus")

    kpis = queries.kpis_gerais()
    assert kpis["municipios"] == 3
    assert kpis["estados"] == 2


def test_tempo_mediano_de_revisao_usa_mediana(ambiente):
    cadastro = datetime(2026, 6, 1, 8, 0, 0)
    for indice, horas in enumerate((2, 4, 100)):  # mediana = 4, média seria ~35
        _criar(
            f"LG-2026-T0000{indice}",
            status=StatusOcorrencia.CONFIRMADO,
            data_hora_cadastro=cadastro.isoformat(),
            data_primeira_decisao=(cadastro + timedelta(hours=horas)).isoformat(),
        )
    assert queries.tempo_mediano_revisao() == pytest.approx(4.0, abs=0.01)


def test_tempo_de_revisao_ignora_pendentes(ambiente):
    _criar("LG-2026-T10001", status=StatusOcorrencia.PENDENTE)
    assert queries.tempo_mediano_revisao() is None


def test_novos_no_periodo_usa_data_de_cadastro(ambiente):
    """A janela de datas filtra avistamento; 'novos' conta cadastro."""
    _criar(
        "LG-2026-N00001",
        data_hora_avistamento="2026-01-10T10:00:00",
        data_hora_cadastro="2026-06-20T10:00:00",
    )
    filtros = Filtros(data_inicio="2026-06-01", data_fim="2026-06-30")
    assert queries.kpis_gerais(filtros)["total"] == 0  # avistamento fora da janela
    assert queries.novos_no_periodo(filtros) == 1  # cadastro dentro da janela


# ------------------------------------------------------------------ filtros
def test_filtros_se_aplicam_a_todas_as_consultas(ambiente):
    _criar("LG-2026-F10001", estado="ES", status=StatusOcorrencia.CONFIRMADO)
    _criar("LG-2026-F10002", estado="BA", municipio="Ilhéus")
    _criar("LG-2026-F10003", estado="BA", municipio="Salvador")

    filtros = Filtros(estados=["BA"])
    assert queries.kpis_gerais(filtros)["total"] == 2
    assert len(queries.total_por_estado(filtros)) == 1
    assert len(queries.total_por_municipio(filtros)) == 2
    assert len(queries.dados_geograficos(filtros)) == 2
    assert len(queries.registros_recentes(filtros)) == 2
    assert queries.estatisticas_completude(filtros)["total"] == 2


def test_filtro_de_periodo_usa_data_do_avistamento(ambiente):
    _criar("LG-2026-P10001", data_hora_avistamento="2026-01-15T10:00:00")
    _criar("LG-2026-P10002", data_hora_avistamento="2026-07-15T10:00:00")
    _criar("LG-2026-P10003", data_hora_avistamento="2026-11-15T10:00:00")

    assert queries.kpis_gerais(Filtros(data_inicio="2026-06-01"))["total"] == 2
    assert queries.kpis_gerais(Filtros(data_fim="2026-06-01"))["total"] == 1
    assert (
        queries.kpis_gerais(Filtros(data_inicio="2026-06-01", data_fim="2026-08-01"))["total"]
        == 1
    )


def test_filtro_de_status_e_origem_combinados(ambiente):
    _criar(
        "LG-2026-S10001",
        status=StatusOcorrencia.CONFIRMADO,
        origem_registro=OrigemRegistro.MERGULHADOR,
    )
    _criar(
        "LG-2026-S10002",
        status=StatusOcorrencia.CONFIRMADO,
        origem_registro=OrigemRegistro.CIDADAO,
    )
    _criar("LG-2026-S10003", status=StatusOcorrencia.PENDENTE)

    filtros = Filtros(status=["CONFIRMADO"], origens=["MERGULHADOR"])
    assert queries.kpis_gerais(filtros)["total"] == 1


def test_filtro_somente_com_coordenadas(ambiente):
    _criar("LG-2026-G10001")
    _criar("LG-2026-G10002", latitude=None, longitude=None,
           origem_localizacao=OrigemLocalizacao.REGIAO_APROXIMADA)

    assert queries.kpis_gerais(Filtros())["total"] == 2
    assert queries.kpis_gerais(Filtros(somente_com_coordenadas=True))["total"] == 1


def test_valores_de_filtro_vem_do_banco(ambiente):
    _criar("LG-2026-V10001", estado="ES", municipio="Guarapari")
    _criar("LG-2026-V10002", estado="BA", municipio="Ilhéus")

    valores = queries.valores_de_filtro()
    assert valores["estados"] == ["BA", "ES"]
    assert "Guarapari" in valores["municipios"]
    assert valores["data_minima"] is not None


# ------------------------------------------------- dados de demonstração
def test_dados_de_demonstracao_sao_separaveis(ambiente):
    _criar("LG-2026-R10001", tipo_dado=TipoDado.REAL)
    GeradorDemonstracao().gerar(quantidade=15, semente=99)

    com_demo = queries.kpis_gerais(Filtros())
    sem_demo = queries.kpis_gerais(Filtros().sem_demonstracao())

    assert com_demo["total"] == 16
    assert com_demo["demonstrativos"] == 15
    assert sem_demo["total"] == 1
    assert sem_demo["demonstrativos"] == 0


def test_indicadores_publicos_excluem_demonstracao(ambiente):
    _criar("LG-2026-R20001", tipo_dado=TipoDado.REAL)
    GeradorDemonstracao().gerar(quantidade=20, semente=7)

    publicos = analytics.indicadores_publicos()
    assert publicos["total"] == 1


def test_demonstracao_nao_gera_predicao_de_ia(ambiente):
    GeradorDemonstracao().gerar(quantidade=25, semente=3)
    total = queries.consultar_escalar(
        "SELECT COUNT(*) FROM predicao p JOIN ocorrencia o ON o.id = p.ocorrencia_id "
        "WHERE o.tipo_dado = 'DEMO'"
    )
    assert total == 0
    assert queries.metricas_inferencia()["total_inferencias"] == 0


def test_demonstracao_usa_regiao_aproximada(ambiente):
    GeradorDemonstracao().gerar(quantidade=10, semente=3)
    registros = OcorrenciaRepository().listar(tipos_dado=[str(TipoDado.DEMO)])
    assert registros
    assert all(
        registro.origem_localizacao == OrigemLocalizacao.REGIAO_APROXIMADA
        for registro in registros
    )
    assert all(not registro.localizacao_precisa for registro in registros)


def test_demonstracao_e_deterministica(ambiente):
    primeira = GeradorDemonstracao().gerar(quantidade=10, semente=555)
    protocolos_a = [o.protocolo for o in OcorrenciaRepository().listar()]
    estados_a = [o.estado for o in OcorrenciaRepository().listar(ordem="protocolo ASC")]

    OcorrenciaRepository().remover_demonstracao()
    GeradorDemonstracao().gerar(quantidade=10, semente=555)
    estados_b = [o.estado for o in OcorrenciaRepository().listar(ordem="protocolo ASC")]

    assert primeira.criados == 10
    assert len(protocolos_a) == 10
    assert estados_a == estados_b


def test_remover_demonstracao_preserva_registros_reais(ambiente):
    _criar("LG-2026-R30001", tipo_dado=TipoDado.REAL)
    GeradorDemonstracao().gerar(quantidade=12, semente=11)

    removidos = GeradorDemonstracao().remover()

    assert removidos == 12
    assert queries.kpis_gerais()["total"] == 1


# ---------------------------------------------- atualização após operações
def test_kpis_mudam_apos_novo_cadastro(ambiente, registrar_avistamento):
    antes = queries.kpis_gerais()["total"]
    registrar_avistamento(chave="novo-1")
    assert queries.kpis_gerais()["total"] == antes + 1


def test_mapa_mostra_registro_recem_criado(ambiente, registrar_avistamento):
    assert queries.dados_geograficos() == []
    resultado = registrar_avistamento(chave="mapa-1")
    pontos = queries.dados_geograficos()
    assert len(pontos) == 1
    assert pontos[0]["protocolo"] == resultado.protocolo


def test_kpis_mudam_apos_validacao(ambiente, registrar_avistamento, sessao_pesquisador):
    resultado = registrar_avistamento(chave="val-1")
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)

    antes = queries.kpis_gerais()
    assert antes["pendentes"] == 1
    assert antes["confirmados"] == 0

    ServicoValidacao().decidir(
        ocorrencia_id=ocorrencia.id,
        decisao=Decisao.CONFIRMAR,
        justificativa="justificativa suficiente para o teste automatizado",
        sessao=sessao_pesquisador,
    )

    depois = queries.kpis_gerais()
    assert depois["pendentes"] == 0
    assert depois["confirmados"] == 1
    assert depois["percentual_validado"] == 100.0
    assert depois["tempo_mediano_revisao_horas"] is not None


def test_grafico_de_status_reflete_validacao(ambiente, registrar_avistamento, sessao_pesquisador):
    resultado = registrar_avistamento(chave="graf-1")
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    ServicoValidacao().decidir(
        ocorrencia_id=ocorrencia.id,
        decisao=Decisao.REJEITAR,
        justificativa="imagem não permite sustentar a identificação",
        sessao=sessao_pesquisador,
    )
    distribuicao = {item["status"]: item["total"] for item in queries.contagem_por_status()}
    assert distribuicao == {"REJEITADO": 1}


def test_fila_operacional_prioriza_pendentes(ambiente):
    _criar("LG-2026-O10001", status=StatusOcorrencia.CONFIRMADO)
    _criar("LG-2026-O10002", status=StatusOcorrencia.PENDENTE)
    _criar("LG-2026-O10003", status=StatusOcorrencia.AGUARDANDO_INFO)

    fila = queries.fila_operacional()
    assert fila[0]["status"] == "PENDENTE"
    assert fila[1]["status"] == "AGUARDANDO_INFO"
    assert fila[2]["status"] == "CONFIRMADO"


def test_indicadores_operacionais(ambiente, registrar_avistamento):
    registrar_avistamento(chave="op-1")
    _criar("LG-2026-O20001", latitude=None, longitude=None,
           origem_localizacao=OrigemLocalizacao.REGIAO_APROXIMADA)

    indicadores = queries.indicadores_operacionais()
    assert indicadores["pendentes"] == 2
    assert indicadores["sem_coordenadas"] == 1
    assert indicadores["sem_imagem"] == 1  # o criado direto não tem imagem


# ------------------------------------------------------------ séries e dados
def test_serie_mensal_preenche_meses_vazios_no_intervalo(ambiente):
    _criar("LG-2026-Y10001", data_hora_avistamento="2026-01-10T10:00:00")
    _criar("LG-2026-Y10002", data_hora_avistamento="2026-04-10T10:00:00")

    serie = analytics.serie_mensal_completa()
    assert list(serie["Mês"]) == ["2026-01", "2026-02", "2026-03", "2026-04"]
    assert list(serie["Registros"]) == [1, 0, 0, 1]


def test_serie_mensal_nao_extrapola_fora_do_intervalo(ambiente):
    _criar("LG-2026-Y20001", data_hora_avistamento="2026-05-10T10:00:00")
    serie = analytics.serie_mensal_completa()
    assert list(serie["Mês"]) == ["2026-05"]


def test_distribuicao_horaria_cobre_as_24_horas(ambiente):
    _criar("LG-2026-H10001", data_hora_avistamento="2026-06-15T09:30:00")
    _criar("LG-2026-H10002", data_hora_avistamento="2026-06-15T09:45:00")

    distribuicao = analytics.distribuicao_horaria_completa()
    assert len(distribuicao) == 24
    assert distribuicao.loc[distribuicao["Hora"] == "09h", "Registros"].iloc[0] == 2
    assert distribuicao["Registros"].sum() == 2


def test_profundidade_nula_e_descartada_nao_zerada(ambiente):
    _criar("LG-2026-D10001", profundidade=10.0)
    _criar("LG-2026-D10002", profundidade=20.0)
    _criar("LG-2026-D10003", profundidade=None)

    profundidades = queries.profundidades()
    assert profundidades == [10.0, 20.0]

    resumo = analytics.resumo_numerico(profundidades, "m")
    assert resumo["n"] == 2
    assert resumo["media"] == 15.0  # e não 10.0, que seria o efeito de zerar
    assert resumo["minimo"] == 10.0


def test_habitat_nao_informado_e_categoria_propria(ambiente):
    _criar("LG-2026-B10001", habitat=Habitat.RECIFE)
    _criar("LG-2026-B10002", habitat=Habitat.NAO_INFORMADO)
    _criar("LG-2026-B10003", habitat=Habitat.NAO_INFORMADO)

    distribuicao = {item["habitat"]: item["total"] for item in queries.distribuicao_por_habitat()}
    assert distribuicao["NAO_INFORMADO"] == 2
    assert distribuicao["RECIFE"] == 1
    assert sum(distribuicao.values()) == 3


def test_resumo_numerico_de_lista_vazia(ambiente):
    resumo = analytics.resumo_numerico([], "m")
    assert resumo["disponivel"] is False
    assert resumo["n"] == 0


def test_resumo_numerico_calcula_quartis(ambiente):
    resumo = analytics.resumo_numerico([1.0, 2.0, 3.0, 4.0, 5.0], "m")
    assert resumo["mediana"] == 3.0
    assert resumo["quartil_1"] == 2.0
    assert resumo["quartil_3"] == 4.0
    assert resumo["desvio_padrao"] is not None


def test_histograma_classifica_em_faixas(ambiente):
    histograma = analytics.histograma([1.0, 3.0, 6.0, 12.0], largura_classe=5.0)
    assert histograma["disponivel"] is True
    assert histograma["classes"][0] == "0–5"
    assert histograma["contagens"] == [2, 1, 1]
    assert histograma["n"] == 4


def test_histograma_de_lista_vazia(ambiente):
    assert analytics.histograma([])["disponivel"] is False


def test_completude_calcula_percentuais(ambiente, registrar_avistamento):
    registrar_avistamento(chave="comp-1", profundidade=10.0, habitat=Habitat.RECIFE)
    _criar("LG-2026-X10001", profundidade=None, habitat=Habitat.NAO_INFORMADO)

    completude = queries.estatisticas_completude()
    assert completude["total"] == 2
    assert completude["pct_coordenadas"] == 100.0
    assert completude["pct_profundidade"] == 50.0
    assert completude["pct_habitat"] == 50.0
    assert completude["pct_imagem"] == 50.0
    assert completude["pct_localizacao_precisa"] == 100.0


# -------------------------------------------------------------- espacial
def test_dbscan_identifica_agrupamentos(ambiente):
    # 6 pontos próximos no ES + 6 próximos na BA, separados por ~900 km
    for indice in range(6):
        _criar(
            f"LG-2026-E1{indice:04d}",
            latitude=-20.67 + indice * 0.01,
            longitude=-40.49 + indice * 0.01,
            estado="ES",
            municipio="Guarapari",
        )
    for indice in range(6):
        _criar(
            f"LG-2026-E2{indice:04d}",
            latitude=-12.97 + indice * 0.01,
            longitude=-38.50 + indice * 0.01,
            estado="BA",
            municipio="Salvador",
        )

    resultado = agrupar_ocorrencias(queries.dados_geograficos(publico=False), eps_km=30)

    assert resultado.executado is True
    assert resultado.quantidade_clusters == 2
    assert sum(cluster.quantidade for cluster in resultado.clusters) == 12
    assert resultado.ruido == 0
    assert all(cluster.raio_maximo_km < 30 for cluster in resultado.clusters)
    assert "não necessariamente" in resultado.ressalva


def test_dbscan_marca_ponto_isolado_como_ruido(ambiente):
    for indice in range(6):
        _criar(
            f"LG-2026-E3{indice:04d}",
            latitude=-20.67 + indice * 0.005,
            longitude=-40.49,
        )
    _criar("LG-2026-E39999", latitude=-5.79, longitude=-35.21, estado="RN", municipio="Natal")

    resultado = agrupar_ocorrencias(queries.dados_geograficos(publico=False), eps_km=20)
    assert resultado.ruido == 1


def test_evolucao_por_cluster(ambiente):
    for indice in range(6):
        _criar(
            f"LG-2026-E4{indice:04d}",
            latitude=-20.67 + indice * 0.005,
            longitude=-40.49,
            data_hora_avistamento=f"2026-0{(indice % 3) + 1}-10T10:00:00",
        )
    pontos = queries.dados_geograficos(publico=False)
    resultado = agrupar_ocorrencias(pontos, eps_km=20)
    evolucao = evolucao_por_cluster(resultado, pontos)

    assert evolucao
    assert sum(item["total"] for item in evolucao) == 6
    assert all({"area", "mes", "total"} == set(item) for item in evolucao)


# ----------------------------------------------------------- exportação
def test_exportacao_inclui_cabecalho_de_ressalvas(ambiente, sessao_admin, registrar_avistamento):
    registrar_avistamento(chave="exp-1")
    conteudo, nome = analytics.exportar_csv(sessao=sessao_admin)

    assert nome.startswith("lionguard_ocorrencias_")
    assert "viés de observação" in conteudo
    assert "demonstração" in conteudo
    assert "protocolo" in conteudo


def test_exportacao_respeita_filtros(ambiente, sessao_admin):
    _criar("LG-2026-Q10001", estado="ES")
    _criar("LG-2026-Q10002", estado="BA", municipio="Ilhéus")

    conteudo, _ = analytics.exportar_csv(Filtros(estados=["BA"]), sessao=sessao_admin)
    assert "LG-2026-Q10002" in conteudo
    assert "LG-2026-Q10001" not in conteudo


def test_admin_exporta_coordenadas_precisas(ambiente, sessao_admin, registrar_avistamento):
    registrar_avistamento(chave="exp-2")
    conteudo, _ = analytics.exportar_csv(sessao=sessao_admin)
    assert "-20.6712" in conteudo
    assert "precisas" in conteudo


# ------------------------------------------------------------- painel de IA
def test_painel_de_ia_sem_modelo_nao_mostra_metricas(ambiente):
    painel = analytics.painel_ia()
    assert painel["estado_modelo"] == "SEM_MODELO"
    assert painel["metricas_treinamento"]["disponivel"] is False
    assert painel["metricas_producao"]["total_inferencias"] == 0
    assert painel["scores"] == []


def test_metricas_de_modelo_lidas_de_arquivo(ambiente, tmp_path):
    import json

    arquivo = tmp_path / "metricas.json"
    arquivo.write_text(
        json.dumps({"metricas": {"acuracia": 0.91}, "modelo": {"nome": "x"}}), encoding="utf-8"
    )
    metricas = analytics.carregar_metricas_modelo(arquivo)
    assert metricas["disponivel"] is True
    assert metricas["metricas"]["acuracia"] == 0.91


def test_metricas_de_arquivo_corrompido(ambiente, tmp_path):
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text("{quebrado", encoding="utf-8")
    metricas = analytics.carregar_metricas_modelo(arquivo)
    assert metricas["disponivel"] is False
    assert "ilegível" in metricas["motivo"]


def test_concordancia_ia_humano(ambiente, registrar_avistamento, sessao_pesquisador):
    from src.ai.inference import ClassePredicao, ResultadoInferencia
    from src.database.models import Predicao
    from src.database.repositories import PredicaoRepository

    resultado = registrar_avistamento(chave="conc-1", com_inferencia=False)
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    PredicaoRepository().criar(
        Predicao(
            ocorrencia_id=ocorrencia.id,
            modelo="m",
            versao="1",
            classe=ClassePredicao.PEIXE_LEAO,
            score=0.9,
        )
    )
    ServicoValidacao().decidir(
        ocorrencia_id=ocorrencia.id,
        decisao=Decisao.CONFIRMAR,
        justificativa="concordância entre modelo e avaliador neste caso",
        sessao=sessao_pesquisador,
    )

    concordancia = queries.concordancia_ia_humano()
    assert concordancia["total"] == 1
    assert concordancia["ia_positiva_humano_confirmou"] == 1


# ---------------------------------------------------------- painéis completos
def test_painel_geral_monta_todas_as_estruturas(ambiente, registrar_avistamento):
    registrar_avistamento(chave="pg-1")
    painel = analytics.painel_geral()

    for chave in (
        "kpis",
        "por_status",
        "por_estado",
        "por_municipio",
        "mensal",
        "por_origem",
        "por_tipo_dado",
        "recentes",
    ):
        assert chave in painel
    assert painel["kpis"]["total"] == 1
    assert not painel["por_estado"].empty


def test_painel_cientifico_monta_todas_as_estruturas(ambiente, registrar_avistamento):
    registrar_avistamento(chave="pc-1", profundidade=12.0, habitat=Habitat.RECIFE)
    painel = analytics.painel_cientifico()

    assert painel["completude"]["total"] == 1
    assert painel["resumo_profundidade"]["n"] == 1
    assert painel["histograma_profundidade"]["disponivel"] is True
    assert not painel["por_habitat"].empty
    assert len(painel["por_hora"]) == 24
    assert not painel["qualidade"].empty


def test_painel_operacional_monta_todas_as_estruturas(ambiente, registrar_avistamento):
    registrar_avistamento(chave="po-1")
    painel = analytics.painel_operacional()

    assert painel["indicadores"]["pendentes"] == 1
    assert len(painel["fila"]) == 1
    assert painel["quantidade_duplicatas"] == 0


def test_rotulos_cobrem_todos_os_valores_do_dominio():
    """Nenhum valor do banco deve aparecer na tela como código cru."""
    for enumeracao, mapa in (
        (StatusOcorrencia, analytics.ROTULOS_STATUS),
        (Habitat, analytics.ROTULOS_HABITAT),
        (OrigemRegistro, analytics.ROTULOS_ORIGEM),
        (TipoDado, analytics.ROTULOS_TIPO_DADO),
    ):
        for membro in enumeracao:
            assert str(membro) in mapa, f"rótulo ausente para {membro}"
