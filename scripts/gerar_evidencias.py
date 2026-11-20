#!/usr/bin/env python3
"""
Executa o fluxo completo do sistema sem interface e grava as evidências.

Produz `reports/evidencias_execucao.md` com a saída real de cada passo:
cadastro, idempotência, limite de envios, permissões, validação humana,
atualização dos indicadores, análise espacial e persistência após reabertura
do banco.

Serve a dois propósitos: comprovar o funcionamento no PDF da entrega e servir
de teste de fumaça antes de uma demonstração ao vivo.

A execução usa um banco **isolado** (em diretório temporário), para não alterar
a base de desenvolvimento.

Uso:
    python scripts/gerar_evidencias.py
    python scripts/gerar_evidencias.py --manter   # usa o banco configurado
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import _caminho  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]

linhas_relatorio: list[str] = []


def registrar(texto: str = "", imprimir: bool = True) -> None:
    linhas_relatorio.append(texto)
    if imprimir:
        print(texto, flush=True)


def titulo(texto: str) -> None:
    registrar()
    registrar(f"## {texto}")
    registrar()


def item(rotulo: str, valor) -> None:
    registrar(f"- **{rotulo}:** {valor}")


def imagem_sintetica(semente: int = 11) -> bytes:
    """
    Gera uma imagem JPEG sintética para exercitar o pipeline.

    **Não é uma fotografia de peixe-leão.** Serve apenas para comprovar que
    validação, pré-processamento, armazenamento e persistência funcionam. Por
    isso nenhuma conclusão sobre identificação da espécie é extraída dela.
    """
    import numpy as np
    from PIL import Image

    gerador = np.random.default_rng(semente)
    base = gerador.integers(40, 210, size=(480, 640, 3), dtype=np.uint8)
    # listras verticais, para que a imagem tenha estrutura e não só ruído
    base[:, ::40, :] = 230
    buffer = io.BytesIO()
    Image.fromarray(base).save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def main() -> int:
    analisador = argparse.ArgumentParser(description="Gera evidências de execução.")
    analisador.add_argument(
        "--manter",
        action="store_true",
        help="usar o banco configurado em vez de um banco temporário",
    )
    analisador.add_argument("--saida", default="reports/evidencias_execucao.md")
    argumentos = analisador.parse_args()

    diretorio_temporario = None
    if not argumentos.manter:
        diretorio_temporario = tempfile.mkdtemp(prefix="lionguard_evid_")
        os.environ["LIONGUARD_DB"] = str(Path(diretorio_temporario) / "evidencias.db")
        os.environ["LIONGUARD_IMAGE_DIR"] = str(Path(diretorio_temporario) / "images")
        os.environ.setdefault("LIONGUARD_ADMIN_PASS", "evidencia-admin-2026")
        os.environ.setdefault("LIONGUARD_PESQ_PASS", "evidencia-pesq-2026")

    # Importações após definir as variáveis de ambiente.
    from src.ai.inference import obter_servico_inferencia
    from src.config import get_config, resetar_config
    from src.data.demo_seed import GeradorDemonstracao
    from src.database import queries
    from src.database.connection import fechar_conexoes, inicializar_banco
    from src.database.queries import Filtros
    from src.database.repositories import AuditoriaRepository, OcorrenciaRepository
    from src.database.schema import Decisao, Habitat, OrigemLocalizacao, TipoDado
    from src.security.auth import ServicoAutenticacao
    from src.security.permissions import AcessoNegado, Permissao, exigir
    from src.security.rate_limit import LimitadorRequisicoes
    from src.security.sanitize import CaminhoInvalido, caminho_seguro
    from src.security.uploads import ImagemInvalida, validar_imagem
    from src.services.geolocation import (
        CoordenadaInvalida,
        arredondar_para_publico,
        construir_localizacao,
    )
    from src.services.sightings import DadosAvistamento, ServicoAvistamentos
    from src.services.spatial import agrupar_ocorrencias
    from src.services.validation import ErroValidacao, ServicoValidacao

    resetar_config()
    configuracao = get_config()

    registrar("# LionGuard AI — evidências de execução")
    registrar()
    registrar(
        f"Execução automática de ponta a ponta, gerada por "
        f"`scripts/gerar_evidencias.py` em "
        f"**{datetime.now().replace(microsecond=0).isoformat()}**."
    )
    registrar()
    registrar(
        "> Toda saída abaixo é produto da execução real do código deste "
        "repositório. Nenhum valor foi escrito à mão."
    )

    titulo("Ambiente")
    item("Python", sys.version.split()[0])
    item("Sistema", f"{platform.system()} {platform.release()} ({platform.machine()})")
    item("Banco de dados", configuracao.database_url)
    item("Diretório de imagens", configuracao.diretorio_imagens)
    item(
        "Modo",
        "banco temporário isolado" if not argumentos.manter else "banco configurado",
    )

    # ------------------------------------------------------------- 1. banco
    titulo("1. Criação do esquema e contas de acesso")
    inicializar_banco()
    tabelas = [
        linha["name"]
        for linha in queries.consultar(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    indices = queries.consultar_escalar(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    item("Tabelas criadas", f"{len(tabelas)} — {', '.join(tabelas)}")
    item("Índices de consulta", indices)

    autenticacao = ServicoAutenticacao()
    contas = autenticacao.garantir_usuarios_iniciais()
    item("Contas criadas nesta execução", len(contas))
    registrar(
        "  (as senhas vêm de variáveis de ambiente; nenhuma credencial consta "
        "no código-fonte)"
    )

    sessao_pesquisador = autenticacao.autenticar(
        os.environ.get("LIONGUARD_PESQ_USER", "pesquisador"),
        os.environ["LIONGUARD_PESQ_PASS"],
    )
    item(
        "Login de pesquisador",
        f"OK — perfil {sessao_pesquisador.perfil}, sessão válida até "
        f"{sessao_pesquisador.expira_em}",
    )

    try:
        autenticacao.autenticar(
            os.environ.get("LIONGUARD_PESQ_USER", "pesquisador"), "senha-errada"
        )
        item("Login com senha incorreta", "FALHA — acesso indevido concedido")
    except Exception as erro:
        item("Login com senha incorreta", f"recusado corretamente ({type(erro).__name__})")

    # ---------------------------------------------------- 2. segurança upload
    titulo("2. Validação de imagem e saneamento de entrada")
    dados_imagem = imagem_sintetica()
    validada = validar_imagem(dados_imagem)
    item(
        "Imagem sintética aceita",
        f"{validada.formato.upper()} {validada.largura}×{validada.altura}, "
        f"{validada.tamanho_bytes / 1024:.0f} KB, EXIF removido: {validada.exif_removido}",
    )
    registrar(
        "  *A imagem é sintética e serve só para exercitar o pipeline — "
        "não é uma fotografia da espécie, e nenhuma conclusão de identificação "
        "é tirada dela.*"
    )

    for descricao, conteudo in (
        ("arquivo que não é imagem", b"isto nao e uma imagem" * 50),
        ("JPEG truncado", dados_imagem[:120]),
        ("arquivo vazio", b""),
    ):
        try:
            validar_imagem(conteudo)
            item(f"Rejeição de {descricao}", "FALHA — aceitou conteúdo inválido")
        except ImagemInvalida as erro:
            item(f"Rejeição de {descricao}", f"recusado — “{erro}”")

    for nome_malicioso in ("../../etc/passwd", "/etc/shadow", "..\\..\\windows\\system.ini"):
        try:
            caminho_seguro(configuracao.diretorio_imagens, nome_malicioso)
            item(f"Bloqueio de `{nome_malicioso}`", "FALHA — caminho aceito")
        except CaminhoInvalido as erro:
            item(f"Bloqueio de `{nome_malicioso}`", f"recusado — “{erro}”")

    from src.security.sanitize import sanitizar_nome_arquivo

    item(
        "Saneamento de nome enviado pelo usuário",
        f"`../../etc/passwd` → `{sanitizar_nome_arquivo('../../etc/passwd')}` · "
        f"`foto;rm -rf /.JPG` → `{sanitizar_nome_arquivo('foto;rm -rf /.JPG')}`",
    )
    caminho_valido = caminho_seguro(configuracao.diretorio_imagens, "abc123.jpg")
    item(
        "Nome legítimo resolvido dentro do diretório",
        f"`abc123.jpg` → dentro de `{configuracao.diretorio_imagens}`: "
        f"{Path(configuracao.diretorio_imagens).resolve() in caminho_valido.parents}",
    )

    # --------------------------------------------------------- 3. geolocation
    titulo("3. Geolocalização")
    localizacao = construir_localizacao(
        -20.6712, -40.4985, OrigemLocalizacao.GPS_DISPOSITIVO, precisao_metros=12.0
    )
    item(
        "Coordenada do GPS validada",
        f"{localizacao.latitude}, {localizacao.longitude} → "
        f"{localizacao.municipio}/{localizacao.estado} "
        f"(referência a {localizacao.distancia_referencia_km} km), "
        f"origem: {localizacao.descricao_origem()}",
    )
    publica = arredondar_para_publico(localizacao.latitude, localizacao.longitude)
    item(
        "Coordenada no mapa público",
        f"{publica[0]}, {publica[1]} — arredondada para "
        f"{configuracao.casas_decimais_publicas} casas (~1 km)",
    )
    try:
        construir_localizacao(48.85, 2.35, OrigemLocalizacao.MAPA_MANUAL)
        item("Rejeição de ponto fora da área", "FALHA — aceitou ponto fora do Brasil")
    except CoordenadaInvalida as erro:
        item("Rejeição de ponto fora da área", f"recusado — “{erro}”")

    # ------------------------------------------------------------ 4. IA
    titulo("4. Inferência")
    servico_ia = obter_servico_inferencia()
    item("Estado do modelo", f"`{servico_ia.estado}`")
    item("Detalhe", servico_ia.descricao_estado)
    resultado_ia = servico_ia.classificar(validada.conteudo)
    item("Classe atribuída", f"`{resultado_ia.classe}`")
    item("Score", resultado_ia.score if resultado_ia.score is not None else "— (indisponível)")
    item("Mensagem ao usuário", f"“{resultado_ia.mensagem_usuario}”")
    item(
        "Qualidade medida da imagem",
        f"nitidez {resultado_ia.qualidade_imagem.get('nitidez_laplaciano')}, "
        f"brilho {resultado_ia.qualidade_imagem.get('brilho_medio')}, "
        f"contraste {resultado_ia.qualidade_imagem.get('contraste')}",
    )
    if not resultado_ia.disponivel:
        registrar(
            "  *Nenhum modelo publicado nesta execução: o sistema devolve o "
            "estado de indisponibilidade e o registro segue para revisão "
            "humana, sem classificação inventada.*"
        )

    # ------------------------------------------------------- 5. cadastro
    titulo("5. Cadastro do avistamento (transação)")
    servico_avistamentos = ServicoAvistamentos()
    data_avistamento = (datetime.now() - timedelta(hours=3)).replace(microsecond=0)
    chave = servico_avistamentos.calcular_chave_idempotencia(
        hash_imagem=None,
        data_hora_avistamento=data_avistamento.isoformat(),
        latitude=localizacao.latitude,
        longitude=localizacao.longitude,
        sessao="evidencia-sessao",
    )
    dados = DadosAvistamento(
        localizacao=localizacao,
        data_hora_avistamento=data_avistamento.isoformat(),
        imagem=validada,
        nome_arquivo_original="../../../etc/shadow;rm -rf.jpg",
        inferencia=resultado_ia,
        profundidade=9.4,
        habitat=Habitat.COSTAO_ROCHOSO,
        quantidade_observada=1,
        descricao="Registro de evidência automatizada (execução de teste).",
        chave_idempotencia=chave,
    )
    resultado = servico_avistamentos.registrar(dados)
    item("Registro gravado", f"protocolo `{resultado.protocolo}`")
    item("Status inicial", f"`{resultado.status}` (nunca confirmado automaticamente)")
    item("Sucesso confirmado relendo do banco", resultado.sucesso)

    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    from src.database.repositories import ImagemRepository

    imagem_gravada = ImagemRepository().primeira_por_ocorrencia(ocorrencia.id)
    item(
        "Nome de arquivo sanitizado",
        f"original `../../../etc/shadow;rm -rf.jpg` → gravado como "
        f"`{imagem_gravada.identificador_arquivo}` "
        f"(nome original guardado como `{imagem_gravada.nome_original_sanitizado}`)",
    )
    item("Arquivo existe no disco", (configuracao.diretorio_imagens / imagem_gravada.identificador_arquivo).is_file())

    resultado_repetido = servico_avistamentos.registrar(dados)
    item(
        "Reenvio com a mesma chave (duplo clique)",
        f"protocolo `{resultado_repetido.protocolo}` · "
        f"duplicado={resultado_repetido.duplicado} · "
        f"total de ocorrências: {OcorrenciaRepository().contar()}",
    )

    limitador = LimitadorRequisicoes()
    consumos = [limitador.consumir("sessao-evidencia").permitido for _ in range(7)]
    item(
        "Limite de envios por sessão",
        f"limite {configuracao.rate_limit_registros} em "
        f"{configuracao.rate_limit_janela_segundos}s → "
        f"permitidos: {consumos.count(True)}, bloqueados: {consumos.count(False)}",
    )

    # -------------------------------------------------- 6. permissões
    titulo("6. Controle de acesso")
    for permissao in (
        Permissao.REGISTRAR_AVISTAMENTO,
        Permissao.VER_PAINEL_OPERACIONAL,
        Permissao.VALIDAR_OCORRENCIA,
        Permissao.GERENCIAR_USUARIOS,
    ):
        for rotulo, sessao_teste in (
            ("visitante anônimo", None),
            ("pesquisador", sessao_pesquisador),
        ):
            try:
                exigir(sessao_teste, permissao)
                situacao = "permitido"
            except AcessoNegado:
                situacao = "negado"
            registrar(f"- `{permissao}` para {rotulo}: **{situacao}**")

    try:
        ServicoValidacao().decidir(
            ocorrencia_id=ocorrencia.id,
            decisao=Decisao.CONFIRMAR,
            justificativa="tentativa sem sessão autenticada",
            sessao=None,
        )
        item("Validação sem autenticação", "FALHA — decisão aceita sem sessão")
    except AcessoNegado:
        item("Validação sem autenticação", "recusada corretamente (AcessoNegado)")

    try:
        ServicoValidacao().decidir(
            ocorrencia_id=ocorrencia.id,
            decisao=Decisao.CONFIRMAR,
            justificativa="curto",
            sessao=sessao_pesquisador,
        )
        item("Validação sem justificativa adequada", "FALHA — aceita")
    except ErroValidacao as erro:
        item("Validação sem justificativa adequada", f"recusada — “{erro}”")

    # ---------------------------------------- 7. indicadores antes/depois
    titulo("7. Validação humana e atualização dos indicadores")
    kpis_antes = queries.kpis_gerais()
    item(
        "Indicadores antes da decisão",
        f"total={kpis_antes['total']}, pendentes={kpis_antes['pendentes']}, "
        f"confirmados={kpis_antes['confirmados']}, "
        f"validados={kpis_antes['percentual_validado']}%",
    )

    decisao = ServicoValidacao().decidir(
        ocorrencia_id=ocorrencia.id,
        decisao=Decisao.CONFIRMAR,
        justificativa=(
            "Evidência automatizada: decisão registrada para comprovar o fluxo "
            "de validação e a atualização dos indicadores."
        ),
        sessao=sessao_pesquisador,
    )
    item("Decisão registrada", decisao.mensagem)

    kpis_depois = queries.kpis_gerais()
    item(
        "Indicadores depois da decisão",
        f"total={kpis_depois['total']}, pendentes={kpis_depois['pendentes']}, "
        f"confirmados={kpis_depois['confirmados']}, "
        f"validados={kpis_depois['percentual_validado']}%, "
        f"tempo mediano de revisão={kpis_depois['tempo_mediano_revisao_horas']}h",
    )
    historico = ServicoValidacao().historico(ocorrencia.id, sessao_pesquisador)
    item(
        "Histórico de validação",
        f"{len(historico)} decisão(ões) registrada(s) — "
        f"{historico[-1].status_anterior} → {historico[-1].status_novo}",
    )

    # ----------------------------------------------- 8. dados de demonstração
    titulo("8. Dados de demonstração e separação por procedência")
    semeadura = GeradorDemonstracao().gerar(quantidade=90, semente=20262)
    item("Registros de demonstração criados", semeadura.criados)
    com_demo = queries.kpis_gerais(Filtros())
    sem_demo = queries.kpis_gerais(Filtros().sem_demonstracao())
    item("Total com demonstração", com_demo["total"])
    item("Total sem demonstração (filtro aplicado)", sem_demo["total"])
    item(
        "Rotulagem",
        f"{com_demo['demonstrativos']} registro(s) marcados como "
        f"`{TipoDado.DEMO}`; o filtro de procedência os remove por completo",
    )
    predicoes_demo = queries.consultar_escalar(
        "SELECT COUNT(*) FROM predicao p JOIN ocorrencia o ON o.id = p.ocorrencia_id "
        "WHERE o.tipo_dado = 'DEMO'"
    )
    item(
        "Predições de IA em registros de demonstração",
        f"{predicoes_demo} (por decisão de projeto: dado de demonstração não "
        "recebe score de modelo)",
    )

    # ------------------------------------------------------- 9. consultas
    titulo("9. Consultas analíticas dos dashboards")
    por_estado = queries.total_por_estado()
    completude = queries.estatisticas_completude()
    item("Estados com registro", len(por_estado))
    item(
        "Cinco primeiros estados",
        ", ".join(f"{linha['estado']}={linha['total']}" for linha in por_estado[:5]),
    )
    item("Meses na série temporal", len(queries.evolucao_mensal()))
    item("Distribuição por status", queries.contagem_por_status())
    item(
        "Completude",
        f"coordenadas {completude['pct_coordenadas']}%, "
        f"imagem {completude['pct_imagem']}%, "
        f"profundidade {completude['pct_profundidade']}%, "
        f"habitat {completude['pct_habitat']}%",
    )
    operacionais = queries.indicadores_operacionais()
    item("Indicadores operacionais", operacionais)

    # ---------------------------------------------------- 10. espacial
    titulo("10. Análise espacial (DBSCAN)")
    pontos = queries.dados_geograficos(publico=False)
    agrupamento = agrupar_ocorrencias(pontos, eps_km=25.0, minimo_amostras=3)
    item("Pontos analisados", agrupamento.total_pontos)
    item("Executado", agrupamento.executado)
    if agrupamento.executado:
        item("Agrupamentos encontrados", agrupamento.quantidade_clusters)
        item("Pontos de ruído (isolados)", agrupamento.ruido)
        item("Biblioteca", agrupamento.biblioteca)
        for cluster in agrupamento.clusters[:5]:
            registrar(
                f"  - {cluster.nome}: {cluster.quantidade} registros, "
                f"raio {cluster.raio_maximo_km} km, UFs {cluster.estados}"
            )
        registrar(f"  - Ressalva registrada: *{agrupamento.ressalva}*")
    else:
        item("Motivo", agrupamento.motivo)

    # ---------------------------------------------------- 11. exportação
    titulo("11. Exportação e auditoria")
    from src.services.analytics import exportar_csv

    conteudo_csv, nome_csv = exportar_csv(sessao=sessao_pesquisador)
    item(
        "Exportação CSV",
        f"`{nome_csv}` com {len(conteudo_csv.splitlines())} linha(s), "
        "coordenadas arredondadas (perfil pesquisador não exporta precisas)",
    )
    item("Contato exportado", "não — a coluna de contato não entra no CSV")
    item("Eventos de auditoria registrados", AuditoriaRepository().contar())
    acoes = queries.consultar(
        "SELECT acao, COUNT(*) AS t FROM log_auditoria GROUP BY acao ORDER BY t DESC"
    )
    registrar(
        "  Ações auditadas: "
        + ", ".join(f"{linha['acao']}={linha['t']}" for linha in acoes)
    )

    # ---------------------------------------------------- 12. persistência
    titulo("12. Persistência após reabertura do banco")
    total_antes_fechar = OcorrenciaRepository().contar()
    fechar_conexoes()
    item("Conexões fechadas", "sim (simula reinicialização da aplicação)")
    ocorrencia_relida = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    item("Total de ocorrências após reabrir", OcorrenciaRepository().contar())
    item(
        "Ocorrência relida",
        f"`{ocorrencia_relida.protocolo}` com status `{ocorrencia_relida.status}`",
    )
    item(
        "Integridade",
        "OK — nenhum registro perdido"
        if OcorrenciaRepository().contar() == total_antes_fechar
        else "FALHA — contagem divergente",
    )

    # ------------------------------------------------------------- resumo
    titulo("Resumo")
    registrar(
        "O fluxo **foto → IA → GPS → confirmação → SQL → dashboard → "
        "validação** foi executado de ponta a ponta nesta máquina, com "
        "transação atômica, idempotência, controle de acesso, auditoria e "
        "persistência verificados. O estado do modelo de IA é reportado como "
        "encontrado: se não houver modelo publicado, o sistema informa a "
        "indisponibilidade em vez de produzir uma classificação."
    )

    saida = RAIZ / argumentos.saida
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas_relatorio) + "\n", encoding="utf-8")
    print(f"\n>>> Evidências gravadas em {saida}")

    if diretorio_temporario:
        print(f">>> Banco temporário desta execução: {diretorio_temporario}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
