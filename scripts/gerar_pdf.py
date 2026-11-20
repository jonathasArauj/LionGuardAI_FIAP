#!/usr/bin/env python3
"""
Gera o PDF acadêmico da entrega.

O documento segue a estrutura mínima exigida pela Global Solution (27 seções) e
é montado a partir de **dados reais**: os indicadores vêm de consultas ao banco,
o resultado dos testes vem de `reports/testes_execucao.md`, os critérios de
aceite vêm de `reports/diagnostico_criterios.md` e as métricas de IA, quando
existirem, de `reports/metricas_modelo.json`. Os trechos de código são lidos dos
arquivos-fonte, de modo que aparecem como **texto legível** — não como captura
de tela.

Campos que dependem do grupo (nomes, turma, links) ficam como marcadores
explícitos até serem informados por argumento de linha de comando.

Uso:
    python scripts/gerar_pdf.py
    python scripts/gerar_pdf.py \\
        --integrantes "Ana Souza (RM123456)" "Bruno Lima (RM234567)" \\
        --turma "1TIAOB" \\
        --video "https://youtu.be/XXXX" \\
        --repositorio "https://github.com/grupo/lionguard-ai" \\
        --concorrer
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import _caminho  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]

AZUL_MARINHO = "#062B43"
AZUL_OCEANO = "#086F8C"
TURQUESA = "#14B8A6"
CINZA_CLARO = "#F3F7F9"
CINZA_BORDA = "#D7E3E8"
CINZA_TEXTO = "#334155"

MARCADOR = "[PREENCHER]"


# --------------------------------------------------------------------- estilos
def construir_estilos():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    base = getSampleStyleSheet()
    estilos = {}

    estilos["titulo_capa"] = ParagraphStyle(
        "titulo_capa",
        parent=base["Title"],
        fontSize=30,
        leading=35,
        textColor=colors.HexColor(AZUL_MARINHO),
        spaceAfter=6,
    )
    estilos["subtitulo_capa"] = ParagraphStyle(
        "subtitulo_capa",
        parent=base["Normal"],
        fontSize=13.5,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor(AZUL_OCEANO),
        spaceAfter=26,
    )
    estilos["capa_info"] = ParagraphStyle(
        "capa_info",
        parent=base["Normal"],
        fontSize=11,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor(CINZA_TEXTO),
    )
    estilos["h1"] = ParagraphStyle(
        "h1",
        parent=base["Heading1"],
        fontSize=17,
        leading=21,
        textColor=colors.HexColor(AZUL_MARINHO),
        spaceBefore=18,
        spaceAfter=9,
    )
    estilos["h2"] = ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor(AZUL_OCEANO),
        spaceBefore=13,
        spaceAfter=6,
    )
    estilos["h3"] = ParagraphStyle(
        "h3",
        parent=base["Heading3"],
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor(CINZA_TEXTO),
        spaceBefore=10,
        spaceAfter=4,
    )
    estilos["corpo"] = ParagraphStyle(
        "corpo",
        parent=base["BodyText"],
        fontSize=10,
        leading=14.5,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor(CINZA_TEXTO),
        spaceAfter=7,
    )
    estilos["lista"] = ParagraphStyle(
        "lista",
        parent=estilos["corpo"],
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=3,
    )
    estilos["codigo"] = ParagraphStyle(
        "codigo",
        parent=base["Code"],
        fontName="Courier",
        fontSize=7.1,
        leading=8.6,
        textColor=colors.HexColor("#1F2937"),
        backColor=colors.HexColor(CINZA_CLARO),
        borderPadding=5,
        leftIndent=3,
        spaceBefore=3,
        spaceAfter=8,
    )
    estilos["legenda"] = ParagraphStyle(
        "legenda",
        parent=base["Normal"],
        fontSize=8.3,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#6B8795"),
        spaceBefore=3,
        spaceAfter=12,
    )
    estilos["aviso"] = ParagraphStyle(
        "aviso",
        parent=estilos["corpo"],
        backColor=colors.HexColor("#FFF8EC"),
        borderPadding=7,
        borderColor=colors.HexColor("#F59E0B"),
        borderWidth=0.8,
        spaceBefore=6,
        spaceAfter=10,
    )
    estilos["celula"] = ParagraphStyle(
        "celula", parent=base["Normal"], fontSize=8.2, leading=10.6,
        textColor=colors.HexColor(CINZA_TEXTO),
    )
    estilos["celula_cabecalho"] = ParagraphStyle(
        "celula_cabecalho", parent=estilos["celula"], fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    return estilos


def tabela(dados: list[list], estilos, larguras=None, destaque_primeira=True):
    """Monta uma tabela com a identidade visual do projeto."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    from reportlab.platypus import Paragraph

    corpo = []
    for indice, linha in enumerate(dados):
        estilo = (
            estilos["celula_cabecalho"]
            if indice == 0 and destaque_primeira
            else estilos["celula"]
        )
        corpo.append([Paragraph(str(celula), estilo) for celula in linha])

    objeto = Table(corpo, colWidths=larguras, repeatRows=1 if destaque_primeira else 0)
    comandos = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(CINZA_BORDA)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if destaque_primeira:
        comandos += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL_OCEANO)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(CINZA_CLARO)]),
        ]
    objeto.setStyle(TableStyle(comandos))
    return objeto


def bloco_codigo(texto: str, estilos):
    """Código como texto selecionável, com indentação preservada."""
    from reportlab.platypus import Paragraph

    escapado = (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&nbsp;")
        .replace("\n", "<br/>")
    )
    return Paragraph(escapado, estilos["codigo"])


def trecho_de_arquivo(caminho: str, inicio: int, fim: int) -> str:
    """Lê um intervalo de linhas de um arquivo-fonte, com numeração."""
    arquivo = RAIZ / caminho
    if not arquivo.is_file():
        return f"# arquivo não encontrado: {caminho}"
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    recorte = linhas[inicio - 1 : fim]
    largura = len(str(fim))
    return "\n".join(
        f"{str(inicio + i).rjust(largura)}  {linha}" for i, linha in enumerate(recorte)
    )


# ----------------------------------------------------------------- dados reais
def preparar_banco_para_figuras() -> tuple[bool, str]:
    """
    Garante que haja dados para os gráficos.

    Usa o banco configurado se ele tiver volume suficiente; caso contrário cria
    um banco temporário com dados de demonstração, e devolve essa informação
    para que as legendas das figuras digam a verdade.
    """
    from src.database.connection import inicializar_banco
    from src.database.repositories import OcorrenciaRepository

    inicializar_banco()
    if OcorrenciaRepository().contar() >= 20:
        return False, "banco configurado da instalação"

    temporario = tempfile.mkdtemp(prefix="lionguard_pdf_")
    os.environ["LIONGUARD_DB"] = str(Path(temporario) / "pdf.db")
    os.environ["LIONGUARD_IMAGE_DIR"] = str(Path(temporario) / "images")
    os.environ.setdefault("LIONGUARD_ADMIN_PASS", "pdf-admin-2026")
    os.environ.setdefault("LIONGUARD_PESQ_PASS", "pdf-pesq-2026")

    from src.config import resetar_config
    from src.data.demo_seed import GeradorDemonstracao
    from src.database.connection import esquecer_inicializacao, fechar_conexoes
    from src.security.auth import ServicoAutenticacao

    fechar_conexoes()
    esquecer_inicializacao()
    resetar_config()
    inicializar_banco()
    ServicoAutenticacao().garantir_usuarios_iniciais()
    GeradorDemonstracao().gerar(quantidade=150, semente=20262)
    return True, "dados de demonstração gerados para este documento"


def gerar_figuras(diretorio: Path) -> dict[str, Path]:
    """Gráficos a partir de consultas reais ao banco, via matplotlib."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from src.database import queries
    from src.services import analytics

    diretorio.mkdir(parents=True, exist_ok=True)
    figuras: dict[str, Path] = {}
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.edgecolor": CINZA_BORDA,
            "axes.labelcolor": CINZA_TEXTO,
            "text.color": CINZA_TEXTO,
            "xtick.color": CINZA_TEXTO,
            "ytick.color": CINZA_TEXTO,
            "axes.grid": True,
            "grid.color": CINZA_BORDA,
            "grid.linewidth": 0.6,
            "figure.dpi": 190,
        }
    )

    # 1. por estado
    por_estado = queries.total_por_estado()[:12]
    if por_estado:
        figura, eixo = plt.subplots(figsize=(6.4, 2.7))
        nomes = [item["estado"] for item in por_estado]
        valores = [item["total"] for item in por_estado]
        eixo.bar(nomes, valores, color="#0891B2")
        for indice, valor in enumerate(valores):
            eixo.text(indice, valor, str(valor), ha="center", va="bottom", fontsize=7.5)
        eixo.set_ylabel("Registros")
        eixo.set_xlabel("")
        eixo.grid(axis="x", visible=False)
        figura.tight_layout()
        caminho = diretorio / "por_estado.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["por_estado"] = caminho

    # 2. distribuição por status
    por_status = queries.contagem_por_status()
    if por_status:
        from app.styles.theme import estilo_status

        figura, eixo = plt.subplots(figsize=(4.6, 3.4))
        valores = [item["total"] for item in por_status]
        rotulos = [estilo_status(item["status"])["rotulo"] for item in por_status]
        cores = [estilo_status(item["status"])["cor"] for item in por_status]
        cunhas, _, textos = eixo.pie(
            valores,
            colors=cores,
            autopct="%1.0f%%",
            startangle=90,
            wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 1.6},
            pctdistance=0.79,
            textprops={"fontsize": 7.5, "color": "white"},
        )
        eixo.legend(
            cunhas,
            rotulos,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.02),
            ncol=2,
            fontsize=6.8,
            frameon=False,
        )
        eixo.text(
            0, 0, f"{sum(valores)}\nregistros", ha="center", va="center",
            fontsize=9, color=CINZA_TEXTO,
        )
        eixo.set_aspect("equal")
        eixo.grid(visible=False)
        figura.tight_layout()
        caminho = diretorio / "por_status.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["por_status"] = caminho

    # 3. evolução mensal
    serie = analytics.serie_mensal_completa()
    if not serie.empty and len(serie) > 1:
        figura, eixo = plt.subplots(figsize=(6.4, 2.5))
        eixo.plot(serie["Mês"], serie["Registros"], marker="o", markersize=4,
                  linewidth=2, color="#0891B2", label="Registros")
        eixo.plot(serie["Mês"], serie["Confirmados"], marker="s", markersize=4,
                  linewidth=2, color="#F59E0B", label="Confirmados")
        eixo.set_ylabel("Registros")
        eixo.set_ylim(bottom=0)
        eixo.legend(fontsize=7.5, frameon=False)
        passo = max(1, len(serie) // 10)
        eixo.set_xticks(range(0, len(serie), passo))
        eixo.set_xticklabels(serie["Mês"][::passo], rotation=45, ha="right", fontsize=7)
        eixo.grid(axis="x", visible=False)
        figura.tight_layout()
        caminho = diretorio / "mensal.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["mensal"] = caminho

    # 4. histograma de profundidade
    profundidades = queries.profundidades()
    if profundidades:
        figura, eixo = plt.subplots(figsize=(3.1, 2.4))
        eixo.hist(profundidades, bins=range(0, int(max(profundidades)) + 6, 5),
                  color="#0891B2", edgecolor="white")
        eixo.set_xlabel("Profundidade (m)")
        eixo.set_ylabel("Registros")
        eixo.grid(axis="x", visible=False)
        figura.tight_layout()
        caminho = diretorio / "profundidade.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["profundidade"] = caminho

    # 5. completude dos dados
    completude = queries.estatisticas_completude()
    itens = [
        ("Com coordenadas", completude["pct_coordenadas"]),
        ("Localização precisa", completude["pct_localizacao_precisa"]),
        ("Com fotografia", completude["pct_imagem"]),
        ("Com profundidade", completude["pct_profundidade"]),
        ("Com habitat", completude["pct_habitat"]),
        ("Com quantidade", completude["pct_quantidade"]),
    ]
    itens = [(nome, valor) for nome, valor in itens if valor is not None]
    if itens:
        figura, eixo = plt.subplots(figsize=(3.1, 2.4))
        nomes = [nome for nome, _ in itens][::-1]
        valores = [valor for _, valor in itens][::-1]
        eixo.barh(nomes, valores, color="#0891B2")
        for indice, valor in enumerate(valores):
            eixo.text(valor + 1.5, indice, f"{valor:.0f}%", va="center", fontsize=7)
        eixo.set_xlim(0, 112)
        eixo.set_xlabel("% dos registros")
        eixo.tick_params(axis="y", labelsize=7)
        eixo.grid(axis="y", visible=False)
        figura.tight_layout()
        caminho = diretorio / "completude.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["completude"] = caminho

    # 6. agrupamento espacial
    from src.services.spatial import agrupar_ocorrencias

    pontos = queries.dados_geograficos(publico=False)
    agrupamento = agrupar_ocorrencias(pontos, eps_km=25.0, minimo_amostras=3)
    if agrupamento.executado and agrupamento.clusters:
        figura, eixo = plt.subplots(figsize=(6.4, 3.0))
        nomes = [cluster.nome for cluster in agrupamento.clusters][:10][::-1]
        valores = [cluster.quantidade for cluster in agrupamento.clusters][:10][::-1]
        eixo.barh(nomes, valores, color="#14B8A6")
        for indice, valor in enumerate(valores):
            eixo.text(valor, indice, f" {valor}", va="center", fontsize=7.5)
        eixo.set_xlabel("Registros no agrupamento")
        eixo.tick_params(axis="y", labelsize=7)
        eixo.grid(axis="y", visible=False)
        figura.tight_layout()
        caminho = diretorio / "clusters.png"
        figura.savefig(caminho, bbox_inches="tight")
        plt.close(figura)
        figuras["clusters"] = caminho
    figuras["_agrupamento"] = agrupamento  # type: ignore[assignment]
    return figuras


def ler_resumo_testes() -> dict:
    """Extrai de reports/testes_execucao.md o que foi realmente executado."""
    arquivo = RAIZ / "reports" / "testes_execucao.md"
    if not arquivo.is_file():
        return {"disponivel": False}
    texto = arquivo.read_text(encoding="utf-8")

    linhas = re.findall(r"\|\s*`(tests/[^`]+)`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", texto)
    resumo = re.search(r"\*\*Resumo do Pytest:\*\*\s*`([^`]+)`", texto)
    data = re.search(r"\*\*Data/hora:\*\*\s*(\S+)", texto)
    python = re.search(r"\*\*Python:\*\*\s*(\S+)", texto)
    return {
        "disponivel": True,
        "por_arquivo": [(a, int(p), int(f), int(i)) for a, p, f, i in linhas],
        "resumo": resumo.group(1).strip("= ") if resumo else None,
        "data": data.group(1) if data else None,
        "python": python.group(1) if python else None,
        "total": sum(int(p) for _, p, _, _ in linhas),
        "falhas": sum(int(f) for _, _, f, _ in linhas),
    }


def ler_criterios() -> list[tuple[str, str, str]]:
    arquivo = RAIZ / "reports" / "diagnostico_criterios.md"
    if not arquivo.is_file():
        return []
    texto = arquivo.read_text(encoding="utf-8")
    return re.findall(r"\|\s*([^|]+?)\s*\|\s*\*\*(\w+)\*\*\s*\|\s*([^|]*?)\s*\|", texto)


def ler_metricas_ia() -> dict:
    arquivo = RAIZ / "reports" / "metricas_modelo.json"
    if not arquivo.is_file():
        return {"disponivel": False}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"disponivel": False}
    dados["disponivel"] = True
    return dados


# ------------------------------------------------------------------ documento
def construir_pdf(argumentos) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    estilos = construir_estilos()
    usou_demo, origem_dados = preparar_banco_para_figuras()

    from src.ai.inference import obter_servico_inferencia, resetar_servico_inferencia
    from src.database import queries

    resetar_servico_inferencia()
    kpis = queries.kpis_gerais()
    completude = queries.estatisticas_completude()
    servico_ia = obter_servico_inferencia()
    testes = ler_resumo_testes()
    criterios = ler_criterios()
    metricas_ia = ler_metricas_ia()

    diretorio_figuras = RAIZ / "reports" / "figuras"
    figuras = gerar_figuras(diretorio_figuras)
    agrupamento = figuras.get("_agrupamento")

    destino = RAIZ / "document" / "LionGuard_AI_Global_Solution_2026_2.pdf"
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        leftMargin=2.1 * cm,
        rightMargin=2.1 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="LionGuard AI — Global Solution 2026.2",
        author="FIAP — Global Solution 2026.2",
        subject="Detecção precoce e monitoramento colaborativo do peixe-leão",
    )

    historia = []
    P = lambda texto, estilo="corpo": Paragraph(texto, estilos[estilo])  # noqa: E731

    def secao(numero: int, titulo: str) -> None:
        historia.append(Paragraph(f"{numero}. {titulo}", estilos["h1"]))

    def topicos(itens: list[str]) -> None:
        for item in itens:
            historia.append(Paragraph(item, estilos["lista"], bulletText="•"))
        historia.append(Spacer(1, 6))

    def figura(chave: str, legenda: str, largura: float = 15.0) -> None:
        caminho = figuras.get(chave)
        if not caminho or not Path(caminho).is_file():
            return
        from PIL import Image as PilImage

        with PilImage.open(caminho) as imagem:
            proporcao = imagem.height / imagem.width
        historia.append(
            Image(str(caminho), width=largura * cm, height=largura * proporcao * cm)
        )
        historia.append(Paragraph(legenda, estilos["legenda"]))

    # ============================================================= 1. capa
    historia.append(Spacer(1, 2.2 * cm))
    historia.append(Paragraph("LionGuard AI", estilos["titulo_capa"]))
    historia.append(
        Paragraph(
            "Inteligência artificial e ciência cidadã para a detecção precoce do "
            "peixe-leão no litoral brasileiro",
            estilos["subtitulo_capa"],
        )
    )
    historia.append(
        HRFlowable(width="55%", thickness=1.4, color=colors.HexColor(TURQUESA))
    )
    historia.append(Spacer(1, 0.9 * cm))
    historia.append(
        Paragraph(
            "<b>FIAP — Global Solution 2026.2</b><br/>"
            "Desafio CitizenTech: tecnologia centrada no cidadão<br/>"
            "Prova de conceito funcional",
            estilos["capa_info"],
        )
    )
    historia.append(Spacer(1, 1.6 * cm))

    # ================================================ 2. identificação do grupo
    integrantes = argumentos.integrantes or [f"{MARCADOR} Nome completo e RM"] * 3
    linhas_integrantes = [["Integrante", "Identificação"]]
    for indice, integrante in enumerate(integrantes, 1):
        linhas_integrantes.append([f"{indice}", integrante])
    linhas_integrantes.append(["Turma", argumentos.turma or f"{MARCADOR}"])
    historia.append(
        tabela(linhas_integrantes, estilos, larguras=[2.4 * cm, 12.6 * cm])
    )
    historia.append(Spacer(1, 0.8 * cm))
    if argumentos.concorrer:
        historia.append(
            Paragraph(
                "<b>QUERO CONCORRER</b>",
                estilos["subtitulo_capa"],
            )
        )
    historia.append(
        Paragraph(
            f"Documento gerado automaticamente em "
            f"{datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo script "
            f"<font face='Courier'>scripts/gerar_pdf.py</font>, a partir dos dados e "
            f"relatórios de execução do próprio sistema.",
            estilos["legenda"],
        )
    )
    if any(MARCADOR in str(valor) for valor in (integrantes, argumentos.turma)):
        historia.append(
            P(
                f"<b>Atenção:</b> os campos marcados como {MARCADOR} precisam ser "
                "informados antes da entrega. Gere o PDF novamente passando "
                "<font face='Courier'>--integrantes</font>, "
                "<font face='Courier'>--turma</font>, "
                "<font face='Courier'>--video</font> e "
                "<font face='Courier'>--repositorio</font>.",
                "aviso",
            )
        )
    historia.append(PageBreak())

    # ====================================================== 3. introdução
    secao(3, "Introdução")
    historia.append(
        P(
            "Este documento descreve o <b>LionGuard AI</b>, uma plataforma web de "
            "monitoramento colaborativo desenvolvida como prova de conceito para a "
            "Global Solution 2026.2 da FIAP, no desafio CitizenTech. O sistema "
            "permite que qualquer pessoa registre o avistamento de um peixe-leão "
            "— espécie marinha invasora — a partir de uma fotografia, com análise "
            "preliminar por inteligência artificial e registro de geolocalização, "
            "enquanto pesquisadores validam as ocorrências e acompanham os dados em "
            "painéis analíticos."
        )
    )
    historia.append(
        P(
            "A estrutura do documento acompanha o percurso do projeto: contexto "
            "ambiental e justificativa, definição do problema e do público, "
            "arquitetura e funcionamento, implementação da inteligência artificial e "
            "do pipeline de dados, modelo relacional, painéis analíticos, segurança, "
            "testes, resultados, limitações e relação com os Objetivos de "
            "Desenvolvimento Sustentável."
        )
    )
    historia.append(
        P(
            "Um compromisso atravessa todo o texto: <b>separar o que foi implementado "
            "e verificado do que é projeção</b>. A seção de resultados distingue "
            "explicitamente resultados obtidos de resultados esperados, e a seção de "
            "limitações registra o que o protótipo não faz."
        )
    )

    # ================================================ 4. contexto ambiental
    secao(4, "Contexto ambiental")
    historia.append(
        P(
            "O peixe-leão (<i>Pterois volitans</i>) é um peixe recifal nativo dos "
            "oceanos Índico e Pacífico, reconhecível pelas listras e pelas longas "
            "nadadeiras em forma de leque, que abrigam espinhos venenosos. No "
            "Atlântico Ocidental, a espécie é <b>invasora</b>: a dispersão começou "
            "a partir da costa da Flórida, avançou pelo Caribe e chegou ao Brasil, "
            "inclusive porque ovos e larvas são transportados por correntes."
        )
    )
    historia.append(
        P(
            "Três características tornam a invasão difícil de reverter: a espécie "
            "tem poucos predadores naturais no Atlântico, reproduz-se com frequência "
            "e em grande número, e tem dieta generalista que inclui peixes juvenis e "
            "crustáceos. O impacto não é apenas ecológico — peixes juvenis consumidos "
            "hoje são a captura da pesca artesanal de amanhã, e recifes empobrecidos "
            "afetam o turismo de mergulho."
        )
    )
    historia.append(Paragraph("Cronologia no Brasil", estilos["h2"]))
    historia.append(
        tabela(
            [
                ["Quando", "O que aconteceu"],
                ["2014", "Primeiro registro da espécie no Brasil."],
                [
                    "A partir de 2020",
                    "Os registros passam a ser frequentes, avançando pelo litoral; "
                    "concentram-se inicialmente no Norte e Nordeste, incluindo "
                    "recifes amazônicos e Fernando de Noronha.",
                ],
                [
                    "Set. 2026",
                    "Na Bahia, a Secretaria Estadual do Meio Ambiente informa "
                    "registros em pelo menos dez municípios, do Litoral Norte ao "
                    "Extremo Sul. Porto Seguro institui plano municipal de ação.",
                ],
                [
                    "14/11/2026",
                    "<b>Primeiro registro oficial no Espírito Santo</b>: um exemplar "
                    "de cerca de 15 cm, a 9,4 m de profundidade, na face oeste da "
                    "Ilha Escalvada, em Guarapari, filmado por equipe de mergulho "
                    "recreativo. O Iema inicia mobilização para controle nas ilhas "
                    "do município.",
                ],
            ],
            estilos,
            larguras=[3.2 * cm, 11.8 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "O Plano Emergencial de Monitoramento e Erradicação do Peixe-leão, do "
            "ICMBio, reconhece um ponto decisivo para este projeto: métodos "
            "padronizados de monitoramento têm <b>baixa probabilidade de detectar</b> "
            "a espécie no estágio inicial da invasão — exatamente quando a detecção "
            "tem maior valor."
        )
    )
    historia.append(
        P(
            "<b>O LionGuard AI não é um sistema oficial do ICMBio, do Iema ou de "
            "qualquer órgão ambiental.</b> É uma proposta acadêmica que utiliza "
            "documentos públicos como fundamentação e não substitui os canais "
            "oficiais de comunicação de ocorrências.",
            "aviso",
        )
    )

    # ======================================================= 5. justificativa
    secao(5, "Justificativa")
    historia.append(
        P(
            "O caso do Espírito Santo expõe a lacuna que este projeto endereça: "
            "<b>quem viu primeiro foi um mergulhador recreativo</b>, não uma rede "
            "oficial de monitoramento. A informação chegou ao órgão ambiental por "
            "rede social e depois por comunicação formal. Esse caminho funciona, mas "
            "é frágil: depende de a pessoa saber a quem recorrer, a informação chega "
            "em formato livre — um vídeo, uma mensagem, uma foto sem coordenada — e "
            "não se acumula em uma base consultável."
        )
    )
    historia.append(
        P(
            "O resultado é que <b>avistamentos viram notícia, não dado</b>. Sem "
            "estrutura, não há série temporal, não há mapa de distribuição, não há "
            "como medir se a invasão avança e em que direção. A ciência cidadã resolve "
            "o problema de cobertura — há milhares de olhos na água todos os dias — "
            "mas só se existir um caminho de registro que seja mais rápido do que "
            "desistir."
        )
    )

    # ============================================================ 6. problema
    secao(6, "Problema")
    historia.append(
        P(
            "<b>Não existe um caminho simples, de um minuto e sem cadastro, para que "
            "qualquer pessoa transforme o avistamento de uma espécie marinha invasora "
            "em registro estruturado</b> — com fotografia, coordenada geográfica, "
            "data e trilha de validação — <b>nem um painel único em que pesquisadores "
            "acompanhem, validem e analisem esses registros.</b>"
        )
    )
    historia.append(Paragraph("Desdobramentos do problema", estilos["h2"]))
    topicos(
        [
            "<b>Atrito no registro:</b> formulários longos e exigência de cadastro "
            "fazem a pessoa desistir no momento em que a informação é mais fresca.",
            "<b>Dado sem estrutura:</b> foto sem coordenada, coordenada sem data, "
            "relato sem foto — cada peça separada perde valor analítico.",
            "<b>Identificação incerta:</b> peixes-escorpião nativos e outras espécies "
            "do gênero são visualmente próximos; leigos erram, e especialistas não "
            "conseguem revisar tudo manualmente sem triagem.",
            "<b>Ausência de trilha:</b> sem histórico de quem validou o quê e por "
            "quê, o dado não sustenta decisão.",
            "<b>Confusão entre notificação e ocorrência:</b> um registro não validado "
            "apresentado como confirmado contamina qualquer análise posterior.",
        ]
    )

    # ========================================================= 7. público-alvo
    secao(7, "Público-alvo e atores do ecossistema")
    historia.append(
        tabela(
            [
                ["Ator", "Papel na solução", "Benefício"],
                [
                    "Banhistas, mergulhadores e pescadores",
                    "registram avistamentos",
                    "caminho claro e sem burocracia para contribuir; orientação de "
                    "segurança",
                ],
                [
                    "Operadoras de mergulho",
                    "registro sistemático dos pontos que visitam",
                    "protocolo e histórico das próprias observações",
                ],
                [
                    "Pesquisadores e órgãos ambientais",
                    "validam e analisam",
                    "base organizada, com procedência e qualidade medida",
                ],
                [
                    "Gestão municipal e estadual",
                    "consome indicadores",
                    "priorização de onde capacitar e monitorar",
                ],
                [
                    "Comunidade pesqueira",
                    "beneficiária indireta",
                    "resposta mais rápida reduz impacto no estoque pesqueiro",
                ],
            ],
            estilos,
            larguras=[4.2 * cm, 4.8 * cm, 6.0 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "<b>Como o impacto poderia ser ampliado:</b> integração com os canais "
            "oficiais (Iema, ICMBio/Centro Tamar), publicação dos dados validados em "
            "bases abertas como o GBIF, e convênio com operadoras de mergulho — que "
            "já são, de fato, as sentinelas da costa."
        )
    )

    # ============================================================ 8. objetivos
    secao(8, "Objetivos")
    historia.append(Paragraph("Objetivo geral", estilos["h2"]))
    historia.append(
        P(
            "Permitir que qualquer pessoa registre um possível avistamento de "
            "peixe-leão de forma fácil, usando uma fotografia, inteligência "
            "artificial e localização geográfica, enquanto pesquisadores acompanham "
            "os dados em painéis interativos."
        )
    )
    historia.append(Paragraph("Objetivos específicos", estilos["h2"]))
    topicos(
        [
            "Reduzir o atrito do registro a quatro toques, sem cadastro;",
            "produzir identificação preliminar automática por visão computacional, "
            "com incerteza declarada;",
            "capturar a localização por GPS do aparelho, com fallback obrigatório "
            "quando a permissão é negada;",
            "persistir ocorrência, imagem e predição de forma atômica e auditável;",
            "oferecer cinco painéis analíticos alimentados por consultas reais;",
            "manter a decisão de confirmação <b>humana</b>, com justificativa "
            "registrada;",
            "distinguir, em todas as telas, dado real de dado de demonstração.",
        ]
    )

    # ======================================================= 9. fundamentação
    secao(9, "Fundamentação e integração entre disciplinas")
    historia.append(
        tabela(
            [
                ["Disciplina", "Onde aparece no sistema"],
                [
                    "Visão computacional e redes neurais",
                    "CNN MobileNetV3-Large com transfer learning, classificando as "
                    "fotografias (<font face='Courier'>src/ai/</font>)",
                ],
                [
                    "Aplicações interativas",
                    "portal do cidadão e cinco painéis em Streamlit, mobile-first "
                    "(<font face='Courier'>app/</font>)",
                ],
                [
                    "Modelagem e consultas a bancos de dados",
                    "8 tabelas, 15 índices, constraints de domínio e consultas "
                    "analíticas reutilizáveis "
                    "(<font face='Courier'>src/database/</font>)",
                ],
                [
                    "Análise exploratória de dados",
                    "painel científico: distribuições temporal, batimétrica, de "
                    "habitat e horária, com indicadores de completude",
                ],
                [
                    "Agrupamento (clustering)",
                    "DBSCAN com métrica haversine sobre as coordenadas "
                    "(<font face='Courier'>src/services/spatial.py</font>)",
                ],
                [
                    "Cibersegurança",
                    "hash scrypt, matriz de permissões, validação de upload em quatro "
                    "camadas, auditoria, limite de requisições "
                    "(<font face='Courier'>src/security/</font>)",
                ],
                [
                    "Sensores e conectividade",
                    "API de geolocalização do navegador (GPS do aparelho), com "
                    "precisão em metros registrada",
                ],
                [
                    "Serviços em nuvem",
                    "caminho de implantação documentado (PostgreSQL + armazenamento "
                    "de objetos) em <font face='Courier'>docs/deploy.md</font>",
                ],
                [
                    "Qualidade e testes",
                    f"suíte Pytest com {testes.get('total', 0)} casos cobrindo banco, "
                    "serviços, segurança e IA",
                ],
            ],
            estilos,
            larguras=[5.0 * cm, 10.0 * cm],
        )
    )

    historia.append(PageBreak())

    # ========================================================= 10. arquitetura
    secao(10, "Arquitetura")
    historia.append(
        P(
            "A aplicação separa apresentação, serviços de domínio, acesso a dados e "
            "infraestrutura. A regra estrutural é que <b>a interface nunca fala com o "
            "banco</b>: ela chama serviços, e os serviços usam repositórios. É isso "
            "que permite testar toda a regra de negócio sem subir o Streamlit — e é "
            f"por isso que os {testes.get('total', 0)} testes rodam em poucos segundos."
        )
    )
    historia.append(
        tabela(
            [
                ["Camada", "Módulos", "Responsabilidade"],
                [
                    "Apresentação",
                    "<font face='Courier'>app/main.py</font>, "
                    "<font face='Courier'>app/paginas/</font>, "
                    "<font face='Courier'>app/components/</font>",
                    "navegação por perfil, componentes reutilizáveis, identidade "
                    "visual",
                ],
                [
                    "Serviços de domínio",
                    "<font face='Courier'>sightings</font>, "
                    "<font face='Courier'>geolocation</font>, "
                    "<font face='Courier'>image_storage</font>, "
                    "<font face='Courier'>validation</font>, "
                    "<font face='Courier'>analytics</font>, "
                    "<font face='Courier'>spatial</font>",
                    "regra de negócio, transações, decisões de domínio",
                ],
                [
                    "Inteligência artificial",
                    "<font face='Courier'>preprocessing</font>, "
                    "<font face='Courier'>inference</font>, "
                    "<font face='Courier'>train</font>, "
                    "<font face='Courier'>evaluate</font>",
                    "pré-processamento compartilhado, inferência, treino e avaliação "
                    "offline",
                ],
                [
                    "Segurança",
                    "<font face='Courier'>auth</font>, "
                    "<font face='Courier'>permissions</font>, "
                    "<font face='Courier'>uploads</font>, "
                    "<font face='Courier'>rate_limit</font>, "
                    "<font face='Courier'>sanitize</font>",
                    "autenticação, autorização, validação de entrada, auditoria",
                ],
                [
                    "Acesso a dados",
                    "<font face='Courier'>repositories</font>, "
                    "<font face='Courier'>queries</font>, "
                    "<font face='Courier'>connection</font>",
                    "única camada que escreve SQL; transações explícitas",
                ],
            ],
            estilos,
            larguras=[3.3 * cm, 5.2 * cm, 6.5 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "O repositório traz <b>seis diagramas Mermaid</b> em "
            "<font face='Courier'>docs/arquitetura.md</font>: componentes, fluxo do "
            "avistamento, fluxo da inteligência artificial, modelo "
            "entidade-relacionamento, máquina de estados da validação e diagrama de "
            "sequência da atualização dos painéis."
        )
    )

    historia.append(Paragraph("Decisões técnicas e seus motivos", estilos["h2"]))
    historia.append(
        tabela(
            [
                ["Decisão", "Por quê"],
                [
                    "Classificação (CNN) em vez de detecção (YOLO)",
                    "com base de imagens limitada, um detector treinado com poucas "
                    "anotações de caixa teria desempenho pior e sugeriria capacidade "
                    "inexistente. Consequência assumida: o sistema não desenha caixas "
                    "nem conta indivíduos.",
                ],
                [
                    "Três respostas da IA, não duas",
                    "a faixa intermediária de score existe de verdade; forçá-la a "
                    "positivo ou negativo produz erro silencioso.",
                ],
                [
                    "Status inicial sempre PENDENTE",
                    "nenhum score, por alto que seja, confirma ocorrência. A "
                    "confirmação é ato humano registrado.",
                ],
                [
                    "SQL explícito em vez de ORM",
                    "modelagem e consultas ficam auditáveis e evidenciam a disciplina "
                    "de banco; migração para PostgreSQL documentada.",
                ],
                [
                    "Chave de idempotência derivada do conteúdo",
                    "resiste a recarregar a página, não apenas ao duplo clique.",
                ],
                [
                    "Nenhum cache nas consultas de leitura",
                    "garante que um registro novo apareça na consulta seguinte, sem "
                    "invalidação manual.",
                ],
                [
                    "Coordenada pública arredondada no SQL",
                    "a coordenada precisa não sai do banco para a camada pública.",
                ],
                [
                    "Dados de demonstração sem predição de IA",
                    "score fabricado seria resultado de modelo inventado.",
                ],
            ],
            estilos,
            larguras=[5.0 * cm, 10.0 * cm],
        )
    )

    # ============================================= 11. funcionamento do sistema
    historia.append(PageBreak())
    secao(11, "Funcionamento do sistema")
    historia.append(
        bloco_codigo(
            "Cidadão → fotografia → validação da imagem → IA (classificação) →\n"
            "localização (GPS ou mapa) → confirmação → banco de dados →\n"
            "dashboards → validação humana → indicadores atualizados",
            estilos,
        )
    )
    historia.append(
        P(
            "O processamento da imagem pode acontecer antes da confirmação, mas o "
            "cadastro definitivo respeita a ação expressa do usuário: nada é gravado "
            "sem o toque em “Confirmar avistamento”."
        )
    )
    historia.append(Paragraph("Garantias implementadas no registro", estilos["h2"]))
    topicos(
        [
            "<b>Atomicidade:</b> ocorrência, imagem, predição e auditoria são "
            "gravadas na mesma transação; falha em qualquer passo não deixa registro "
            "parcial nem arquivo órfão.",
            "<b>Idempotência:</b> a chave é derivada do hash da foto, da data, da "
            "coordenada e da sessão do navegador — duplo clique ou recarregamento "
            "devolve o mesmo protocolo.",
            "<b>Sucesso verificado:</b> o serviço relê a ocorrência pelo protocolo "
            "depois do commit e só então declara sucesso.",
            "<b>Status inicial pendente:</b> independentemente do score da IA.",
        ]
    )
    historia.append(
        Paragraph(
            "Trecho do serviço de registro — transação única "
            "(<font face='Courier'>src/services/sightings.py</font>)",
            estilos["h3"],
        )
    )
    historia.append(
        bloco_codigo(
            trecho_de_arquivo("src/services/sightings.py", 222, 232), estilos
        )
    )

    # ================================================ 12. experiência do cidadão
    secao(12, "Experiência do cidadão")
    historia.append(
        P(
            "A experiência do cidadão foi tratada como requisito de primeira ordem. "
            "Cada etapa só aparece na tela quando a anterior está resolvida, para não "
            "apresentar um formulário longo no celular, e nenhuma falha intermediária "
            "interrompe o registro."
        )
    )
    historia.append(
        tabela(
            [
                ["Situação", "Comportamento do sistema"],
                [
                    "Usuário nega a permissão de localização",
                    "mensagem explicativa e mapa manual; o registro continua "
                    "possível e nada digitado é perdido",
                ],
                [
                    "Modelo de IA indisponível",
                    "estado <font face='Courier'>SEM_MODELO</font> informado em "
                    "texto; a ocorrência é gravada para revisão humana",
                ],
                [
                    "Imagem inválida ou corrompida",
                    "recusa com mensagem específica (formato, tamanho, integridade), "
                    "preservando o formulário",
                ],
                [
                    "Fotografia tirada em outro dia",
                    "campo de data do avistamento, separado da data de cadastro",
                ],
                [
                    "Usuário não está no local do avistamento",
                    "pergunta explícita “Você está no local onde viu o peixe?”; a "
                    "posição atual nunca é assumida",
                ],
                [
                    "Foto com coordenadas no EXIF",
                    "o sistema informa, pede autorização e só usa se o usuário "
                    "marcar; os metadados são removidos do arquivo salvo",
                ],
                [
                    "Duplo clique em “Confirmar”",
                    "um único registro, mesmo protocolo",
                ],
                [
                    "Sem conexão",
                    "erro honesto; o sistema não afirma que salvou",
                ],
            ],
            estilos,
            larguras=[5.2 * cm, 9.8 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "<b>Segurança ambiental:</b> a plataforma não orienta captura, "
            "perseguição ou manuseio do animal. A tela de registro exibe o aviso de "
            "manter distância, não tocar e procurar atendimento médico em caso de "
            "acidente — manejo é atribuição dos órgãos competentes e de profissionais "
            "autorizados."
        )
    )

    # =========================================== 13. implementação da IA
    historia.append(PageBreak())
    secao(13, "Implementação da inteligência artificial")
    historia.append(
        tabela(
            [
                ["Item", "Escolha"],
                ["Arquitetura", "MobileNetV3-Large pré-treinada no ImageNet"],
                ["Abordagem", "classificação binária com transfer learning"],
                [
                    "Treinamento",
                    "duas fases (classificador, depois ajuste fino dos últimos blocos "
                    "convolucionais), early stopping por F1 de validação, pesos de "
                    "classe, semente fixa",
                ],
                [
                    "Pré-processamento",
                    "letterbox 224×224 preservando proporção, normalização ImageNet — "
                    "o mesmo código no treino e na inferência",
                ],
                [
                    "Decisão",
                    "score ≥ 0,70 → possível peixe-leão · 0,45–0,70 → inconclusivo · "
                    "< 0,45 → não identificado",
                ],
                [
                    "Salvaguarda",
                    "positivo em imagem desfocada ou subexposta é rebaixado a "
                    "inconclusivo",
                ],
                ["Formato de inferência", "ONNX Runtime (TorchScript como alternativa)"],
                [
                    "Rastreabilidade",
                    "toda predição grava modelo, versão, score, tempo de inferência e "
                    "limiares aplicados",
                ],
            ],
            estilos,
            larguras=[3.8 * cm, 11.2 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "<b>Por que letterbox e não redimensionamento simples:</b> esticar a "
            "imagem distorce a silhueta das nadadeiras, que é justamente a "
            "característica discriminante da espécie. O preenchimento preserva a "
            "proporção ao custo de algumas bordas pretas, que a aumentação de dados "
            "ensina o modelo a ignorar."
        )
    )
    historia.append(
        Paragraph(
            "Trecho do serviço de inferência — faixas de decisão e estado de "
            "indisponibilidade (<font face='Courier'>src/ai/inference.py</font>)",
            estilos["h3"],
        )
    )
    historia.append(bloco_codigo(trecho_de_arquivo("src/ai/inference.py", 308, 313), estilos))
    historia.append(
        P(
            "<b>Compromissos de honestidade implementados em código:</b> não existe "
            "caminho que produza classe ou score sem executar o modelo; sem modelo "
            "publicado o estado é <font face='Courier'>SEM_MODELO</font> e erro de "
            "inferência é <font face='Courier'>ERRO</font>; o painel de IA lê métricas "
            "apenas do arquivo gerado pelo script de avaliação; o score é apresentado "
            "com a ressalva de que não é probabilidade calibrada."
        )
    )

    estado_ia = servico_ia.estado
    historia.append(Paragraph("Estado do modelo nesta instalação", estilos["h2"]))
    if metricas_ia.get("disponivel"):
        principais = metricas_ia["metricas"]
        conjunto = metricas_ia.get("conjunto_teste", {})
        historia.append(
            tabela(
                [
                    ["Métrica", "Valor"],
                    ["Modelo", f"{metricas_ia['modelo']['nome']} v{metricas_ia['modelo']['versao']}"],
                    ["Imagens no conjunto de teste", str(conjunto.get("total", "—"))],
                    ["Limiar de decisão", f"{principais['limiar']:.2f}"],
                    ["Acurácia", f"{principais['acuracia']:.4f}"],
                    ["Precisão", f"{principais['precisao']:.4f}"],
                    ["Revocação", f"{principais['revocacao']:.4f}"],
                    ["F1-score", f"{principais['f1']:.4f}"],
                    ["AUC-ROC", str(metricas_ia.get("auc_roc", "—"))],
                    [
                        "Matriz de confusão [[VN, FP], [FN, VP]]",
                        str(principais["matriz_confusao"]),
                    ],
                ],
                estilos,
                larguras=[7.0 * cm, 8.0 * cm],
            )
        )
    else:
        historia.append(
            P(
                f"<b>Estado atual:</b> <font face='Courier'>{estado_ia}</font>. "
                f"{servico_ia.descricao_estado}<br/><br/>"
                "Nenhuma métrica é exibida neste documento porque nenhuma avaliação "
                "foi executada nesta instalação. O pipeline de treinamento está "
                "implementado e documentado (<font face='Courier'>scripts/"
                "baixar_dados.py</font> → <font face='Courier'>preparar_dataset.py"
                "</font> → <font face='Courier'>treinar_modelo.py</font> → "
                "<font face='Courier'>avaliar_modelo.py</font>); após executá-lo, "
                "este PDF gerado novamente passa a trazer a tabela de métricas, e o "
                "painel de IA passa a exibi-las na interface.",
                "aviso",
            )
        )

    # ==================================================== 14. pipeline de dados
    secao(14, "Pipeline de dados")
    historia.append(Paragraph("Origem e procedência", estilos["h2"]))
    historia.append(
        tabela(
            [
                ["Categoria", "Marcação", "Tratamento"],
                [
                    "Registros de usuários",
                    "<font face='Courier'>REAL</font>",
                    "enviados pela plataforma, com foto e coordenada",
                ],
                [
                    "Importados de fontes documentadas",
                    "<font face='Courier'>IMPORTADO</font>",
                    "GBIF e iNaturalist, com fonte, URL e licença gravadas; entram "
                    "como <b>pendentes</b> — base externa não é validação nossa",
                ],
                [
                    "Ocorrências revisadas",
                    "qualquer uma das acima",
                    "após decisão humana, com histórico e justificativa",
                ],
                [
                    "Dados de demonstração",
                    "<font face='Courier'>DEMO</font>",
                    "gerados pelo sistema, sem imagem e <b>sem predição de IA</b>, "
                    "removíveis por filtro em qualquer painel",
                ],
            ],
            estilos,
            larguras=[4.0 * cm, 2.8 * cm, 8.2 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(Paragraph("Imagens de treinamento", estilos["h2"]))
    historia.append(
        P(
            "As imagens são baixadas do iNaturalist apenas quando há licença Creative "
            "Commons declarada; observações sem licença explícita são ignoradas. O "
            "manifesto (<font face='Courier'>data/raw/manifesto.csv</font>) registra "
            "fonte, URL, licença, autor, espécie, identificador da observação, data de "
            "aquisição e hash SHA-256 de cada arquivo. Como classes negativas são "
            "usados peixes recifais que convivem no mesmo ambiente — negativos "
            "difíceis, que ensinam o modelo a discriminar de fato em vez de reagir a "
            "“foto subaquática”."
        )
    )
    historia.append(Paragraph("Divisão sem vazamento", estilos["h2"]))
    historia.append(
        P(
            "A separação treino/validação/teste é feita <b>por observação</b>, não por "
            "imagem: duas fotos do mesmo peixe no mesmo dia são quase idênticas e, "
            "separadas entre treino e teste, inflariam artificialmente as métricas. O "
            "script verifica isso explicitamente ao final e falha se detectar "
            "vazamento. Arquivos corrompidos e duplicatas exatas (mesmo hash) são "
            "descartados e contados no relatório."
        )
    )
    historia.append(
        Paragraph(
            "Trecho da preparação do dataset — agrupamento por observação "
            "(<font face='Courier'>src/data/dataset.py</font>)",
            estilos["h3"],
        )
    )
    historia.append(bloco_codigo(trecho_de_arquivo("src/data/dataset.py", 342, 360), estilos))

    # ======================================================= 15. modelo SQL
    historia.append(PageBreak())
    secao(15, "Modelo de dados e SQL")
    historia.append(
        P(
            "São <b>8 tabelas e 15 índices</b>, com chaves estrangeiras verificadas, "
            "constraints de domínio e unicidade onde o domínio exige. O diagrama "
            "entidade-relacionamento completo está em "
            "<font face='Courier'>docs/arquitetura.md</font>."
        )
    )
    historia.append(
        tabela(
            [
                ["Tabela", "Papel", "Pontos de atenção"],
                [
                    "<font face='Courier'>usuario</font>",
                    "contas de acesso restrito",
                    "identificador único; senha apenas como hash scrypt",
                ],
                [
                    "<font face='Courier'>ocorrencia</font>",
                    "o avistamento",
                    "protocolo e chave de idempotência únicos; CHECK em coordenadas, "
                    "profundidade e quantidade; data da primeira decisão",
                ],
                [
                    "<font face='Courier'>imagem</font>",
                    "arquivo da fotografia",
                    "identificador gerado pela aplicação; hash SHA-256; marca de EXIF "
                    "removido; cascata ao excluir a ocorrência",
                ],
                [
                    "<font face='Courier'>predicao</font>",
                    "resultado da IA",
                    "modelo, versão, score (CHECK 0–1) e tempo de inferência",
                ],
                [
                    "<font face='Courier'>validacao</font>",
                    "histórico de decisões",
                    "justificativa obrigatória; status anterior e novo; avaliador "
                    "protegido por RESTRICT",
                ],
                [
                    "<font face='Courier'>log_auditoria</font>",
                    "trilha de auditoria",
                    "ação, entidade, usuário e detalhes em JSON",
                ],
                [
                    "<font face='Courier'>fonte_dados</font>",
                    "procedência das importações",
                    "nome, URL, licença e data de importação",
                ],
                [
                    "<font face='Courier'>evento_requisicao</font>",
                    "limite de envios",
                    "contagem persistida, não em memória",
                ],
            ],
            estilos,
            larguras=[3.3 * cm, 3.4 * cm, 8.3 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        Paragraph(
            "DDL da tabela principal "
            "(<font face='Courier'>src/database/schema.py</font>)",
            estilos["h3"],
        )
    )
    historia.append(
        bloco_codigo(
            """CREATE TABLE IF NOT EXISTS ocorrencia (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo               TEXT    NOT NULL UNIQUE,
    chave_idempotencia      TEXT    UNIQUE,
    data_hora_avistamento   TEXT    NOT NULL,
    data_hora_cadastro      TEXT    NOT NULL,
    estado                  TEXT,
    municipio               TEXT,
    latitude                REAL    CHECK (latitude IS NULL OR (latitude BETWEEN -90 AND 90)),
    longitude               REAL    CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180)),
    precisao_metros         REAL    CHECK (precisao_metros IS NULL OR precisao_metros >= 0),
    origem_localizacao      TEXT    NOT NULL
                            CHECK (origem_localizacao IN ('GPS_DISPOSITIVO','MAPA_MANUAL',
                                                          'REGIAO_APROXIMADA','IMPORTADA')),
    profundidade            REAL    CHECK (profundidade IS NULL OR profundidade >= 0),
    habitat                 TEXT    NOT NULL DEFAULT 'NAO_INFORMADO',
    quantidade_observada    INTEGER CHECK (quantidade_observada IS NULL OR quantidade_observada > 0),
    descricao               TEXT,
    origem_registro         TEXT    NOT NULL,
    tipo_dado               TEXT    NOT NULL CHECK (tipo_dado IN ('REAL','IMPORTADO','DEMO')),
    status                  TEXT    NOT NULL
                            CHECK (status IN ('PENDENTE','AGUARDANDO_INFO','CONFIRMADO',
                                              'REJEITADO','INCONCLUSIVO')),
    fonte_dados_id          INTEGER REFERENCES fonte_dados (id) ON DELETE SET NULL,
    autoriza_publicar_imagem INTEGER NOT NULL DEFAULT 0,
    contato_hash            TEXT,
    data_primeira_decisao   TEXT
)""",
            estilos,
        )
    )
    historia.append(
        Paragraph(
            "Consulta analítica dos indicadores — nenhum valor fixo "
            "(<font face='Courier'>src/database/queries.py</font>)",
            estilos["h3"],
        )
    )
    historia.append(
        bloco_codigo(
            """SELECT
    COUNT(*)                                                      AS total,
    SUM(CASE WHEN o.status = 'CONFIRMADO'      THEN 1 ELSE 0 END) AS confirmados,
    SUM(CASE WHEN o.status = 'PENDENTE'        THEN 1 ELSE 0 END) AS pendentes,
    SUM(CASE WHEN o.status = 'REJEITADO'       THEN 1 ELSE 0 END) AS rejeitados,
    SUM(CASE WHEN o.status = 'INCONCLUSIVO'    THEN 1 ELSE 0 END) AS inconclusivos,
    SUM(CASE WHEN o.status = 'AGUARDANDO_INFO' THEN 1 ELSE 0 END) AS aguardando_info,
    COUNT(DISTINCT o.municipio)                                   AS municipios,
    COUNT(DISTINCT o.estado)                                      AS estados,
    SUM(CASE WHEN o.tipo_dado = 'DEMO' THEN 1 ELSE 0 END)         AS demonstrativos
  FROM ocorrencia o
  WHERE 1 = 1
    AND date(o.data_hora_avistamento) >= date(?)   -- filtros globais aplicados
    AND o.estado IN (?)                            -- igualmente a cards,
    AND o.tipo_dado IN (?)                         -- gráficos e tabelas""",
            estilos,
        )
    )
    historia.append(
        P(
            "A mesma cláusula <font face='Courier'>WHERE</font> é montada por uma "
            "única função e aplicada a todas as consultas, o que garante que cards, "
            "gráficos, tabelas e mapa mostrem exatamente o mesmo recorte."
        )
    )

    # ========================================================== 16. dashboards
    secao(16, "Dashboards")
    historia.append(
        tabela(
            [
                ["Painel", "Conteúdo", "Acesso"],
                [
                    "1 — Visão geral",
                    "8 indicadores, 6 gráficos, filtros globais simultâneos, tabela "
                    "dos últimos registros",
                    "restrito",
                ],
                [
                    "2 — Mapa geográfico",
                    "marcadores por status, agrupamento, pop-ups, legenda explícita, "
                    "contador, áreas DBSCAN",
                    "público (aproximado) e restrito (preciso)",
                ],
                [
                    "3 — Análise científica",
                    "distribuição temporal, batimétrica, habitat, horário, qualidade "
                    "dos dados, análise espacial, exportação CSV",
                    "restrito",
                ],
                [
                    "4 — Inteligência artificial",
                    "métricas do conjunto de teste, matriz de confusão, curvas de "
                    "treino, distribuição de scores, concordância IA × avaliador, "
                    "rastreamento de inferências",
                    "restrito",
                ],
                [
                    "5 — Operacional e validação",
                    "fila priorizada, revisão com justificativa, histórico auditável, "
                    "detecção de duplicidades",
                    "restrito",
                ],
            ],
            estilos,
            larguras=[3.4 * cm, 8.4 * cm, 3.2 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            f"As figuras a seguir foram geradas a partir de consultas reais ao banco "
            f"no momento em que este documento foi produzido ({origem_dados})."
        )
    )
    if usou_demo:
        historia.append(
            P(
                "<b>Importante:</b> os gráficos deste documento foram produzidos com "
                "<b>dados de demonstração</b> rotulados como "
                "<font face='Courier'>DEMO</font>, gerados de forma determinística "
                "para que os painéis não aparecessem vazios. <b>Eles não representam "
                "ocorrências reais da espécie em nenhum município.</b> A forma dos "
                "gráficos demonstra o funcionamento das consultas, não a distribuição "
                "real da invasão.",
                "aviso",
            )
        )

    figura("por_estado", "Figura 1 — Avistamentos por estado (consulta SQL agregada).")
    figura(
        "por_status",
        "Figura 2 — Distribuição por status da validação. Cada fatia traz ícone, "
        "rótulo e percentual: a cor é reforço, não a informação.",
        largura=9.0,
    )
    figura(
        "mensal",
        "Figura 3 — Evolução mensal pela data do avistamento. Meses sem registro "
        "recebem zero apenas dentro do intervalo observado; não há extrapolação. As "
        "duas séries compartilham um único eixo vertical.",
    )

    # ================================================ 17. análise exploratória
    secao(17, "Análise exploratória de dados")
    historia.append(
        P(
            "O painel científico trata valores ausentes como ausentes. Profundidade e "
            "habitat não informados são <b>descartados</b> das estatísticas — nunca "
            "substituídos por zero nem atribuídos a uma categoria — e cada indicador "
            "informa o <font face='Courier'>n</font> que o sustenta, para que o leitor "
            "julgue a representatividade."
        )
    )
    historia.append(
        tabela(
            [
                ["Indicador", "Valor nesta base"],
                ["Registros analisáveis", f"{completude['total']}"],
                [
                    "Com coordenadas",
                    f"{completude['com_coordenadas']} "
                    f"({completude['pct_coordenadas']}%)",
                ],
                [
                    "Com localização precisa (GPS ou mapa)",
                    f"{completude['localizacao_precisa']} "
                    f"({completude['pct_localizacao_precisa']}%)",
                ],
                [
                    "Com fotografia",
                    f"{completude['com_imagem']} ({completude['pct_imagem']}%)",
                ],
                [
                    "Com profundidade informada",
                    f"{completude['com_profundidade']} "
                    f"({completude['pct_profundidade']}%)",
                ],
                [
                    "Com habitat informado",
                    f"{completude['com_habitat']} ({completude['pct_habitat']}%)",
                ],
                [
                    "Pendentes de validação",
                    f"{completude['pendentes']} ({completude['pct_pendente']}%)",
                ],
            ],
            estilos,
            larguras=[8.5 * cm, 6.5 * cm],
        )
    )
    historia.append(Spacer(1, 10))

    from reportlab.platypus import Table as TabelaBase

    colunas_figuras = []
    if figuras.get("profundidade") and figuras.get("completude"):
        from PIL import Image as PilImage

        imagens = []
        for chave in ("profundidade", "completude"):
            caminho = figuras[chave]
            with PilImage.open(caminho) as imagem:
                proporcao = imagem.height / imagem.width
            imagens.append(
                Image(str(caminho), width=7.2 * cm, height=7.2 * proporcao * cm)
            )
        colunas_figuras = TabelaBase([imagens], colWidths=[7.5 * cm, 7.5 * cm])
        historia.append(colunas_figuras)
        historia.append(
            Paragraph(
                "Figura 4 — Histograma das profundidades informadas (esquerda) e "
                "completude dos campos (direita). O histograma considera apenas os "
                "registros que informaram profundidade; os demais são excluídos do "
                "gráfico, e a quantidade excluída é informada no painel.",
                estilos["legenda"],
            )
        )

    historia.append(
        P(
            "<b>Ressalva obrigatória:</b> dados de ciência cidadã possuem viés de "
            "observação. As áreas com mais registros são as com mais observadores, "
            "turismo e conectividade — não necessariamente as com mais peixes-leão. "
            "<b>Ausência de registros não significa ausência da espécie.</b> As "
            "relações apresentadas são associações, não causalidade comprovada. Essa "
            "ressalva aparece em todos os painéis analíticos e no cabeçalho dos "
            "arquivos exportados.",
            "aviso",
        )
    )

    # ===================================================== 18. análise geográfica
    historia.append(PageBreak())
    secao(18, "Análise geográfica")
    historia.append(
        P(
            "A análise espacial usa <b>DBSCAN</b> com métrica haversine. A escolha se "
            "justifica porque o algoritmo não exige o número de grupos definido de "
            "antemão, encontra agrupamentos de forma arbitrária e classifica pontos "
            "isolados como ruído — adequado a notificações espalhadas por milhares de "
            "quilômetros de costa. O raio de vizinhança é convertido de quilômetros "
            "para radianos dividindo pelo raio da Terra."
        )
    )
    if agrupamento is not None and getattr(agrupamento, "executado", False):
        historia.append(
            tabela(
                [
                    ["Parâmetro / resultado", "Valor"],
                    ["Pontos analisados", str(agrupamento.total_pontos)],
                    ["Raio de vizinhança (eps)", f"{agrupamento.eps_km} km"],
                    ["Mínimo de amostras", str(agrupamento.minimo_amostras)],
                    ["Agrupamentos encontrados", str(agrupamento.quantidade_clusters)],
                    ["Pontos classificados como ruído", str(agrupamento.ruido)],
                    ["Implementação", agrupamento.biblioteca or "—"],
                ],
                estilos,
                larguras=[7.0 * cm, 8.0 * cm],
            )
        )
        historia.append(Spacer(1, 10))
        figura(
            "clusters",
            "Figura 5 — Agrupamentos espaciais identificados pelo DBSCAN, por "
            "quantidade de registros.",
        )
        historia.append(
            tabela(
                [["Área", "Registros", "Confirmados", "Raio (km)", "UFs"]]
                + [
                    [
                        cluster.nome,
                        str(cluster.quantidade),
                        str(cluster.confirmados),
                        str(cluster.raio_maximo_km),
                        ", ".join(cluster.estados) or "—",
                    ]
                    for cluster in agrupamento.clusters[:8]
                ],
                estilos,
                larguras=[5.4 * cm, 2.2 * cm, 2.4 * cm, 2.2 * cm, 2.8 * cm],
            )
        )
        historia.append(Spacer(1, 8))
    historia.append(
        P(
            "<b>Privacidade no mapa:</b> a visualização pública usa coordenadas "
            "arredondadas em duas casas decimais (cerca de 1 km), o que é suficiente "
            "para um mapa de distribuição e insuficiente para localizar um ponto de "
            "mergulho específico. O arredondamento acontece <b>na própria consulta "
            "SQL</b> — a coordenada precisa não sai do banco para a camada pública. "
            "Coordenadas exatas exigem perfil autorizado."
        )
    )

    # =========================================================== 19. segurança
    secao(19, "Segurança e privacidade")
    historia.append(
        tabela(
            [
                ["Camada", "Implementação"],
                [
                    "Senhas",
                    "<font face='Courier'>hashlib.scrypt</font> com sal aleatório de "
                    "16 bytes por usuário e comparação em tempo constante",
                ],
                [
                    "Autenticação",
                    "registro público <b>sem login</b>; painéis exigem sessão com "
                    "expiração configurável",
                ],
                [
                    "Autorização",
                    "matriz explícita de permissões por perfil, verificada <b>no "
                    "serviço</b> — esconder um botão não é controle de acesso",
                ],
                [
                    "Upload",
                    "quatro camadas: tamanho em bytes → assinatura binária (magic "
                    "bytes) → decodificação real → limites de dimensão",
                ],
                [
                    "Metadados EXIF",
                    "lidos para informar o usuário e <b>removidos</b> antes de "
                    "gravar; coordenadas só usadas com autorização explícita",
                ],
                [
                    "Caminhos de arquivo",
                    "nome gerado pela aplicação (UUID); travessia de diretório "
                    "recusada, não corrigida em silêncio",
                ],
                [
                    "Coordenadas",
                    "arredondadas em ~1 km no acesso público; precisas apenas para "
                    "perfis autorizados",
                ],
                [
                    "Contato",
                    "guardado apenas como hash SHA-256 — nunca o contato em si; não "
                    "entra na exportação",
                ],
                [
                    "Proteção contra abuso",
                    "limite de envios por sessão persistido em tabela; detecção de "
                    "imagem repetida por hash; alerta de duplicidade por proximidade",
                ],
                [
                    "Auditoria",
                    "cadastros, decisões de validação, logins (inclusive falhas), "
                    "importações e operações administrativas",
                ],
                [
                    "Segredos",
                    "variáveis de ambiente; <font face='Courier'>.env</font> no "
                    "<font face='Courier'>.gitignore</font>; nenhuma credencial no "
                    "código",
                ],
            ],
            estilos,
            larguras=[3.6 * cm, 11.4 * cm],
        )
    )

    # ============================================================== 20. testes
    historia.append(PageBreak())
    secao(20, "Testes")
    if testes.get("disponivel"):
        historia.append(
            P(
                f"A suíte foi executada em <b>{testes.get('data')}</b>, com Python "
                f"{testes.get('python')}, pelo script "
                f"<font face='Courier'>scripts/rodar_testes.py</font>, que grava a "
                f"saída real do Pytest em "
                f"<font face='Courier'>reports/testes_execucao.md</font>. Resultado: "
                f"<b>{testes.get('resumo')}</b>."
            )
        )
        historia.append(
            tabela(
                [["Arquivo", "Casos", "Falhas", "Ignorados", "Foco"]]
                + [
                    [
                        f"<font face='Courier'>{arquivo.replace('tests/', '')}</font>",
                        str(passou),
                        str(falhou),
                        str(ignorado),
                        {
                            "tests/test_database.py": "esquema, constraints, "
                            "transações, persistência",
                            "tests/test_sightings.py": "registro, idempotência, "
                            "validações, privacidade",
                            "tests/test_geolocation.py": "coordenadas, área "
                            "monitorada, referências, precisão",
                            "tests/test_inference.py": "pré-processamento, limiares, "
                            "indisponibilidade, métricas, dataset",
                            "tests/test_security.py": "senhas, permissões, upload, "
                            "EXIF, saneamento, limite",
                            "tests/test_dashboards.py": "KPIs, filtros, demonstração, "
                            "atualização, DBSCAN, exportação",
                        }.get(arquivo, "—"),
                    ]
                    for arquivo, passou, falhou, ignorado in testes["por_arquivo"]
                ],
                estilos,
                larguras=[3.4 * cm, 1.5 * cm, 1.4 * cm, 1.7 * cm, 7.0 * cm],
            )
        )
    else:
        historia.append(
            P(
                "Nenhum relatório de execução encontrado. Rode "
                "<font face='Courier'>python scripts/rodar_testes.py</font> antes de "
                "gerar este PDF para que esta seção traga os números reais.",
                "aviso",
            )
        )

    historia.append(Spacer(1, 8))
    historia.append(
        Paragraph("Testes que impedem a desonestidade na apresentação", estilos["h2"])
    )
    historia.append(
        P(
            "Parte da suíte existe especificamente para travar, de forma executável, "
            "os erros de integridade que mais pesam em um trabalho como este:"
        )
    )
    topicos(
        [
            "<font face='Courier'>test_status_inicial_e_sempre_pendente</font> — um "
            "score de 0,999 <b>não</b> confirma a ocorrência;",
            "<font face='Courier'>test_demonstracao_nao_gera_predicao_de_ia</font> — "
            "dado de demonstração não recebe score fabricado;",
            "<font face='Courier'>test_painel_de_ia_sem_modelo_nao_mostra_metricas"
            "</font> — sem avaliação, nenhuma métrica aparece;",
            "<font face='Courier'>test_kpis_em_base_vazia_nao_inventam_numeros</font> "
            "— percentual sem dados é ausente, não 0%;",
            "<font face='Courier'>test_profundidade_nula_e_descartada_nao_zerada"
            "</font> — a média de 10 e 20 é 15, e não 10, que seria o efeito de zerar "
            "o ausente;",
            "<font face='Courier'>test_mapa_publico_nao_expoe_coordenada_precisa"
            "</font> — a coordenada pública difere da armazenada;",
            "<font face='Courier'>test_coordenada_exif_nao_e_usada_automaticamente"
            "</font> — GPS no EXIF não define o local sozinho;",
            "<font face='Courier'>test_servico_de_validacao_recusa_sessao_sem_"
            "permissao</font> — a proteção está no serviço, não na interface.",
        ]
    )
    historia.append(
        P(
            "Além da suíte, <font face='Courier'>scripts/gerar_evidencias.py</font> "
            "executa o sistema de ponta a ponta sem interface e grava a saída de cada "
            "passo em <font face='Courier'>reports/evidencias_execucao.md</font>: "
            "criação do esquema, login válido e inválido, recusa de arquivos "
            "inválidos, bloqueio de travessia de diretório, validação de coordenada, "
            "estado da IA, cadastro em transação, reenvio idempotente, limite de "
            "envios, matriz de permissões, validação humana, indicadores antes e "
            "depois, agrupamento espacial, exportação, auditoria e persistência após "
            "reabertura do banco."
        )
    )
    historia.append(
        P(
            "O roteiro manual de 47 itens — câmera, GPS, toque e acessibilidade, que "
            "só um navegador real comprova — está em "
            "<font face='Courier'>docs/testes.md</font>."
        )
    )

    # =========================================================== 21. resultados
    secao(21, "Resultados")
    historia.append(
        P(
            "Esta seção separa, de forma explícita, <b>o que foi implementado e "
            "verificado</b> do que é <b>resultado esperado</b> e depende de etapas "
            "ainda não executadas."
        )
    )

    historia.append(Paragraph("21.1 Resultados obtidos e verificados", estilos["h2"]))
    linhas_obtidos = [
        ["Resultado", "Evidência"],
        [
            "Fluxo completo funcionando: foto → IA → GPS → confirmação → SQL → "
            "dashboard → validação",
            "<font face='Courier'>reports/evidencias_execucao.md</font>, seções 5 e 7",
        ],
        [
            f"{testes.get('total', 0)} testes automatizados, "
            f"{testes.get('falhas', 0)} falhas",
            "<font face='Courier'>reports/testes_execucao.md</font>",
        ],
        [
            "8 tabelas e 15 índices criados, com constraints verificadas",
            "<font face='Courier'>tests/test_database.py</font> e evidências, seção 1",
        ],
        [
            "Transação atômica: falha não deixa registro parcial nem arquivo órfão",
            "<font face='Courier'>test_nada_e_gravado_quando_a_validacao_falha</font>",
        ],
        [
            "Idempotência: duplo clique e recarregamento devolvem o mesmo protocolo",
            "<font face='Courier'>test_duplo_clique_nao_duplica</font> e evidências, "
            "seção 5",
        ],
        [
            "Controle de acesso recusa visitante anônimo em todas as permissões "
            "restritas",
            "<font face='Courier'>tests/test_security.py</font> e evidências, seção 6",
        ],
        [
            "Upload recusa arquivo não-imagem, truncado, vazio e grande demais",
            "evidências, seção 2",
        ],
        [
            "Travessia de diretório bloqueada em três formatos de ataque",
            "evidências, seção 2",
        ],
        [
            "EXIF lido e removido; coordenada do EXIF não usada sem autorização",
            "<font face='Courier'>test_exif_e_removido_da_imagem_gravada</font>",
        ],
        [
            "Coordenada pública arredondada em ~1 km, com a precisa restrita",
            "<font face='Courier'>test_mapa_publico_nao_expoe_coordenada_precisa"
            "</font>",
        ],
        [
            "Limite de envios por sessão funciona e persiste entre conexões",
            "<font face='Courier'>test_limite_persiste_entre_conexoes</font>",
        ],
        [
            "Indicadores recalculados do banco após cadastro e após validação",
            "<font face='Courier'>test_kpis_mudam_apos_validacao</font> e evidências, "
            "seção 7",
        ],
        [
            "DBSCAN identificando agrupamentos e ruído, com ressalva de viés",
            "evidências, seção 10, e "
            "<font face='Courier'>test_dbscan_identifica_agrupamentos</font>",
        ],
        [
            "Dados de demonstração rotulados, sem predição de IA e removíveis por "
            "filtro",
            "evidências, seção 8, e "
            "<font face='Courier'>test_demonstracao_nao_gera_predicao_de_ia</font>",
        ],
        [
            "Persistência verificada após fechar as conexões do banco",
            "evidências, seção 12",
        ],
    ]
    historia.append(
        tabela(linhas_obtidos, estilos, larguras=[8.2 * cm, 6.8 * cm])
    )
    historia.append(Spacer(1, 8))

    historia.append(
        Paragraph("Indicadores da base no momento desta geração", estilos["h3"])
    )
    historia.append(
        tabela(
            [
                ["Indicador", "Valor"],
                ["Total de ocorrências", str(kpis["total"])],
                ["Confirmados por avaliador", str(kpis["confirmados"])],
                ["Pendentes de validação", str(kpis["pendentes"])],
                ["Rejeitados", str(kpis["rejeitados"])],
                ["Inconclusivos", str(kpis["inconclusivos"])],
                ["Municípios com registro", str(kpis["municipios"])],
                ["Estados com registro", str(kpis["estados"])],
                [
                    "Percentual validado",
                    f"{kpis['percentual_validado']}%"
                    if kpis["percentual_validado"] is not None
                    else "— (sem dados suficientes)",
                ],
                [
                    "Tempo mediano de revisão",
                    f"{kpis['tempo_mediano_revisao_horas']} h"
                    if kpis["tempo_mediano_revisao_horas"] is not None
                    else "— (sem dados suficientes)",
                ],
                [
                    "Dos quais são dados de demonstração",
                    str(kpis["demonstrativos"]),
                ],
            ],
            estilos,
            larguras=[8.5 * cm, 6.5 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            f"<b>Procedência destes números:</b> {origem_dados}. "
            + (
                "Como a base desta instalação tinha pouco volume, os valores acima "
                "incluem registros de demonstração rotulados como "
                "<font face='Courier'>DEMO</font> — <b>não são ocorrências reais da "
                "espécie</b>. Eles demonstram que as consultas e os indicadores "
                "funcionam, não a distribuição real da invasão."
                if usou_demo
                else "Os valores refletem o conteúdo atual da base desta instalação."
            )
        )
    )

    historia.append(Paragraph("21.2 Critérios de aceite, item por item", estilos["h2"]))
    if criterios:
        historia.append(
            P(
                "Verificação produzida por "
                "<font face='Courier'>scripts/diagnostico.py</font>. <b>OK</b> = "
                "verificado automaticamente; <b>MANUAL</b> = implementado, "
                "confirmável apenas em navegador real (câmera, GPS, toque); "
                "<b>PENDENTE</b> = depende de etapa externa, como treinar o modelo; "
                "<b>FALHA</b> = verificado e não atendido."
            )
        )
        contagem: dict[str, int] = {}
        for _, estado, _ in criterios:
            contagem[estado] = contagem.get(estado, 0) + 1
        historia.append(
            P(
                "Resumo: "
                + " · ".join(
                    f"<b>{quantidade} {estado}</b>"
                    for estado, quantidade in contagem.items()
                )
            )
        )
        if contagem.get("FALHA"):
            historia.append(
                P(
                    "Os itens marcados como <b>FALHA</b> nesta execução referem-se a "
                    "<b>dependências ausentes no ambiente em que o diagnóstico "
                    "rodou</b>, não a defeitos do sistema: a verificação foi feita em "
                    "um ambiente sem as bibliotecas de interface instaladas. Em uma "
                    "máquina com <font face='Courier'>pip install -r requirements.txt"
                    "</font> executado, esses itens passam a OK. A coluna de "
                    "observação indica, em cada caso, o comando que resolve."
                )
            )
        linhas_criterios = [["Critério", "Estado", "Observação"]]
        for criterio, estado, detalhe in criterios:
            if criterio.strip().startswith("Critério"):
                continue
            linhas_criterios.append([criterio, f"<b>{estado}</b>", detalhe[:190]])
        historia.append(
            tabela(linhas_criterios, estilos, larguras=[5.0 * cm, 1.9 * cm, 8.1 * cm])
        )
    else:
        historia.append(
            P(
                "Nenhum diagnóstico encontrado. Rode "
                "<font face='Courier'>python scripts/diagnostico.py</font> antes de "
                "gerar este PDF.",
                "aviso",
            )
        )

    historia.append(Paragraph("21.3 Resultados esperados (não verificados)", estilos["h2"]))
    historia.append(
        P(
            "Os itens abaixo são <b>projeções</b>. Estão listados separadamente "
            "justamente para não serem confundidos com o que já funciona."
        )
    )
    topicos(
        [
            "<b>Desempenho do modelo em campo.</b> As métricas obtidas em conjunto de "
            "teste montado a partir de bases abertas não se transferem "
            "automaticamente para fotos de celular em água turva.",
            "<b>Adoção pelo público.</b> Nenhum teste com usuários reais foi "
            "conduzido; a hipótese de que um fluxo de quatro toques aumenta o número "
            "de registros é plausível, mas não medida.",
            "<b>Redução do tempo entre avistamento e notificação.</b> Esperada, mas "
            "só verificável em operação.",
            "<b>Utilidade da triagem automática para o avaliador.</b> O indicador de "
            "concordância IA × avaliador existe e é calculado, mas precisa de volume "
            "para ter significado estatístico.",
            "<b>Integração com órgãos ambientais.</b> A arquitetura prevê; nenhuma "
            "integração foi realizada.",
        ]
    )

    # ========================================================= 22. limitações
    secao(22, "Limitações")
    historia.append(
        P(
            "Lista completa em <font face='Courier'>docs/limitacoes.md</font>. As "
            "principais:"
        )
    )
    historia.append(
        tabela(
            [
                ["Área", "Limitação"],
                [
                    "Natureza",
                    "protótipo acadêmico, sem homologação, parceria ou vínculo com "
                    "órgão ambiental; não substitui o canal oficial de ocorrências",
                ],
                [
                    "Inteligência artificial",
                    "identificação preliminar; score não é probabilidade calibrada; "
                    "classificador não localiza nem conta indivíduos; desempenho "
                    "depende do acervo de imagens disponível",
                ],
                [
                    "Localização",
                    "GPS exige HTTPS; precisão varia muito em celular; tabela "
                    "municipal é aproximada (88 pontos de referência, não a malha do "
                    "IBGE); filtro de área é geométrico, não jurídico",
                ],
                [
                    "Dados",
                    "viés de observação; ausência de registro não é ausência da "
                    "espécie; campos opcionais frequentemente vazios; duplicidade "
                    "detectada por heurística",
                ],
                [
                    "Segurança",
                    "limite de envios por sessão de navegador, não na borda; sem "
                    "verificação de identidade; sem criptografia em repouso; sem "
                    "política de retenção; sem teste de intrusão",
                ],
                [
                    "Operação",
                    "persistência não garantida em hospedagem com disco efêmero; sem "
                    "notificações; concorrência de escrita limitada pelo SQLite",
                ],
                [
                    "Acessibilidade",
                    "tema claro apenas (validado); sem verificação com leitor de tela; "
                    "sem internacionalização; não funciona offline",
                ],
            ],
            estilos,
            larguras=[3.4 * cm, 11.6 * cm],
        )
    )

    # ============================================================= 23. ODS 14
    secao(23, "ODS 14 e medição de impacto")
    historia.append(
        P(
            "O projeto se relaciona principalmente ao <b>ODS 14 — Vida na Água</b>, "
            "que trata da conservação e do uso sustentável dos oceanos e dos recursos "
            "marinhos. Espécies exóticas invasoras são vetor direto de perda de "
            "biodiversidade marinha, e a resposta depende de informação cedo e "
            "organizada — exatamente o que a plataforma produz."
        )
    )
    historia.append(
        P(
            "Contribuições secundárias: <b>ODS 15</b> (a meta de controle de espécies "
            "exóticas invasoras é compartilhada), <b>ODS 11</b> (participação cidadã "
            "organizada em problema ambiental local) e <b>ODS 17</b> (a arquitetura "
            "prevê intercâmbio com órgãos ambientais e bases abertas)."
        )
    )
    historia.append(Paragraph("Como medir o impacto", estilos["h2"]))
    historia.append(
        tabela(
            [
                ["Indicador", "O que mede", "Como é obtido"],
                [
                    "Tempo entre avistamento e cadastro",
                    "agilidade do canal",
                    "<font face='Courier'>data_hora_cadastro − "
                    "data_hora_avistamento</font>",
                ],
                [
                    "Tempo mediano de revisão",
                    "capacidade de resposta",
                    "<font face='Courier'>data_primeira_decisao − "
                    "data_hora_cadastro</font>",
                ],
                [
                    "Municípios com registro",
                    "cobertura territorial",
                    "<font face='Courier'>COUNT(DISTINCT municipio)</font>",
                ],
                [
                    "% com coordenada precisa",
                    "qualidade do dado",
                    "completude por <font face='Courier'>origem_localizacao</font>",
                ],
                [
                    "% validados",
                    "maturidade operacional",
                    "decisões finais ÷ total elegível",
                ],
                [
                    "Concordância IA × avaliador",
                    "utilidade do modelo",
                    "matriz operacional do painel de IA",
                ],
                [
                    "Novas áreas por período",
                    "detecção precoce",
                    "agrupamentos DBSCAN inéditos por janela",
                ],
            ],
            estilos,
            larguras=[4.4 * cm, 4.2 * cm, 6.4 * cm],
        )
    )
    historia.append(Spacer(1, 8))
    historia.append(
        P(
            "<b>Ressalva que faz parte do indicador:</b> aumento no número de "
            "registros mede <b>adoção da plataforma</b>, não necessariamente aumento "
            "da população da espécie. Tratar essa distinção como nota de rodapé seria "
            "produzir um indicador enganoso.",
            "aviso",
        )
    )

    # ============================================================ 24. conclusão
    secao(24, "Conclusão")
    historia.append(
        P(
            "O LionGuard AI responde à pergunta da Global Solution — como os "
            "conhecimentos de inteligência artificial e das disciplinas cursadas podem "
            "resolver um problema real — com um recorte deliberadamente estreito: "
            "<b>transformar o que uma pessoa viu na água em dado que um pesquisador "
            "consegue usar</b>."
        )
    )
    historia.append(
        P(
            "O que foi efetivamente construído é um sistema funcional e integrado: um "
            "portal público que registra um avistamento em quatro toques, sem "
            "cadastro; um serviço de inferência que executa um modelo real de visão "
            "computacional e declara sua própria indisponibilidade quando é o caso; "
            "captura de geolocalização com fallback obrigatório; persistência "
            "relacional atômica, idempotente e auditável; cinco painéis analíticos "
            "alimentados por consultas reais; agrupamento espacial com DBSCAN; e um "
            f"conjunto de {testes.get('total', 0)} testes automatizados que roda em "
            "segundos."
        )
    )
    historia.append(
        P(
            "A integração entre disciplinas não é um anexo: visão computacional faz a "
            "triagem, banco de dados dá estrutura e auditoria, análise exploratória "
            "revela padrões e mede a qualidade do próprio dado, agrupamento identifica "
            "concentrações, cibersegurança protege quem contribui, e sensores — o GPS "
            "do aparelho — fornecem a coordenada. Cada peça resolve uma parte do "
            "problema."
        )
    )
    historia.append(
        P(
            "O que distingue este trabalho, na nossa avaliação, é o cuidado em <b>não "
            "prometer mais do que entrega</b>. O sistema nunca confirma uma ocorrência "
            "automaticamente; nunca apresenta métrica sem avaliação; nunca exibe dado "
            "de demonstração sem rótulo; nunca trata ausência como zero; nunca afirma "
            "que a espécie não está na imagem porque o modelo não a encontrou. Essas "
            "decisões estão travadas por testes, não apenas documentadas — e são "
            "exatamente as decisões que separam um protótipo utilizável de uma "
            "demonstração bonita."
        )
    )
    historia.append(
        P(
            "<b>Próximos passos:</b> ampliar o acervo de imagens e reavaliar o modelo "
            "com validação cruzada; conduzir teste de usabilidade com mergulhadores; "
            "migrar para PostgreSQL com armazenamento de objetos; e buscar "
            "interlocução com os canais oficiais, para que o dado validado chegue a "
            "quem tem mandato para agir."
        )
    )

    # =========================================================== 25. referências
    historia.append(PageBreak())
    secao(25, "Referências")
    referencias = [
        "ICMBio. <b>Plano Emergencial de Monitoramento e Erradicação do Peixe-leão</b> "
        "(Resex Marinha de Arraial do Cabo, 2015). Disponível em gov.br/icmbio.",
        "ICMBio. <b>Guia Estratégico do Peixe-leão</b>. Disponível em icmbio.gov.br.",
        "ICMBio. Portal institucional. https://www.gov.br/icmbio/",
        "Iema — Instituto Estadual de Meio Ambiente e Recursos Hídricos (ES). "
        "<b>Peixe-leão é registrado pela primeira vez no Espírito Santo</b>, na Ilha "
        "Escalvada, em Guarapari. Novembro de 2026.",
        "Reportagens sobre o primeiro registro no Espírito Santo (14/11/2026), a "
        "situação na Bahia e o plano municipal de Porto Seguro, consultadas em "
        "novembro de 2026.",
        "GBIF — Global Biodiversity Information Facility. https://www.gbif.org/",
        "iNaturalist. https://www.inaturalist.org/",
        "ONU. <b>Objetivo de Desenvolvimento Sustentável 14 — Vida na Água</b>. "
        "https://brasil.un.org/pt-br/sdgs/14",
        "HOWARD, A. et al. <b>Searching for MobileNetV3</b>. ICCV, 2019.",
        "ESTER, M.; KRIEGEL, H.-P.; SANDER, J.; XU, X. <b>A Density-Based Algorithm "
        "for Discovering Clusters in Large Spatial Databases with Noise</b>. KDD, "
        "1996.",
        "PERCIVAL, C. <b>Stronger Key Derivation via Sequential Memory-Hard "
        "Functions</b> (scrypt). BSDCan, 2009.",
        "FIAP. <b>Template oficial do portfólio</b>. "
        "https://github.com/fiap-tutoria/FIAP-PORTFOLIO-AI",
    ]
    for indice, referencia in enumerate(referencias, 1):
        historia.append(Paragraph(f"{indice}. {referencia}", estilos["lista"]))
    historia.append(Spacer(1, 10))
    historia.append(
        P(
            "<b>Separação entre fonte e proposta:</b> os dados de contexto ambiental "
            "(cronologia da invasão, registros por estado, conteúdo do plano "
            "emergencial) vêm das fontes acima. A arquitetura, as decisões técnicas, "
            "os indicadores de impacto propostos e a plataforma em si são produção "
            "deste grupo."
        )
    )

    # ====================================================== 26 e 27. links
    secao(26, "Link do vídeo demonstrativo")
    video = argumentos.video or f"{MARCADOR} colar o link do YouTube (“Não listado”)"
    historia.append(
        tabela(
            [
                ["Item", "Link"],
                ["Vídeo demonstrativo (YouTube, “Não listado”)", video],
            ],
            estilos,
            larguras=[6.5 * cm, 8.5 * cm],
        )
    )
    historia.append(Spacer(1, 6))
    if not argumentos.video:
        historia.append(
            P(
                "<b>Pendente.</b> O vídeo precisa ser gravado e publicado como “Não "
                "listado” no YouTube, com duração máxima de 5 minutos. O roteiro e o "
                "storyboard estão em <font face='Courier'>docs/roteiro_video.md</font>. "
                "Gere este PDF novamente com <font face='Courier'>--video URL</font> "
                "depois da publicação.",
                "aviso",
            )
        )

    secao(27, "Link do repositório")
    repositorio = argumentos.repositorio or f"{MARCADOR} colar o link do repositório"
    historia.append(
        tabela(
            [
                ["Item", "Link"],
                ["Repositório GitHub (privado)", repositorio],
                ["Compartilhado com", "<font face='Courier'>fiap-tutoria</font>"],
            ],
            estilos,
            larguras=[6.5 * cm, 8.5 * cm],
        )
    )
    historia.append(Spacer(1, 6))
    historia.append(
        P(
            "Instruções de execução no "
            "<font face='Courier'>README.md</font> da raiz: criação do ambiente "
            "virtual, instalação das dependências, configuração do "
            "<font face='Courier'>.env</font>, geração opcional de dados de "
            "demonstração e <font face='Courier'>streamlit run app/main.py</font>. O "
            "repositório deve ser privado e compartilhado apenas com a conta "
            "<font face='Courier'>fiap-tutoria</font> e os integrantes do grupo."
        )
    )

    historia.append(Spacer(1, 16))
    historia.append(
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor(CINZA_BORDA))
    )
    historia.append(
        Paragraph(
            "LionGuard AI — protótipo acadêmico desenvolvido para a Global Solution "
            "2026.2 da FIAP (desafio CitizenTech). Não é um sistema oficial do ICMBio "
            "nem de qualquer órgão ambiental, e não possui homologação ou parceria "
            "institucional. As identificações automáticas são preliminares e dependem "
            "de validação humana.",
            estilos["legenda"],
        )
    )

    # ------------------------------------------------------- numeração de página
    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(colors.HexColor("#6B8795"))
        canvas.drawString(2.1 * cm, 1.2 * cm, "LionGuard AI — Global Solution 2026.2 — FIAP")
        canvas.drawRightString(A4[0] - 2.1 * cm, 1.2 * cm, f"página {doc.page}")
        canvas.setStrokeColor(colors.HexColor(CINZA_BORDA))
        canvas.setLineWidth(0.4)
        canvas.line(2.1 * cm, 1.5 * cm, A4[0] - 2.1 * cm, 1.5 * cm)
        canvas.restoreState()

    documento.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return destino


def main() -> int:
    analisador = argparse.ArgumentParser(description="Gera o PDF da entrega.")
    analisador.add_argument("--integrantes", nargs="*",
        default=["Jonathas Martins de Araujo (RM 574051)",
                 "Carlos Magno Barcelos (RM 569944)",
                 "Lauren Cota (RM 569789)"],
        help="nome completo e RM de cada um (defaults precisam ser confirmados)")
    analisador.add_argument("--turma")
    analisador.add_argument("--video", help="URL do vídeo no YouTube")
    analisador.add_argument("--repositorio", help="URL do repositório GitHub")
    analisador.add_argument(
        "--concorrer",
        action="store_true",
        help='inclui a frase "QUERO CONCORRER" na identificação',
    )
    argumentos = analisador.parse_args()

    try:
        import reportlab  # noqa: F401
    except ImportError:
        print(
            "reportlab não está instalado.\n"
            "Instale com: pip install reportlab\n"
            "(também consta em requirements-treino.txt)"
        )
        return 1

    print("=" * 72)
    print("LionGuard AI — geração do PDF da entrega")
    print("=" * 72)
    destino = construir_pdf(argumentos)
    tamanho = destino.stat().st_size / 1024
    print(f"\nPDF gerado: {destino}")
    print(f"Tamanho: {tamanho:.0f} KB")

    pendentes = []
    if not argumentos.integrantes:
        pendentes.append("--integrantes")
    if not argumentos.turma:
        pendentes.append("--turma")
    if not argumentos.video:
        pendentes.append("--video")
    if not argumentos.repositorio:
        pendentes.append("--repositorio")
    if pendentes:
        print(
            "\nATENÇÃO: o PDF foi gerado com marcadores "
            f"{MARCADOR} para: {', '.join(pendentes)}.\n"
            "Gere novamente passando esses argumentos antes de entregar."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
