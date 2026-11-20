#!/usr/bin/env python3
"""
Diagnóstico dos critérios de aceite (seção 19 do escopo do projeto).

Para cada critério, informa um de quatro estados:

  OK         verificado automaticamente agora, nesta máquina;
  MANUAL     implementado, mas só confirmável no navegador (câmera, GPS, toque);
  PENDENTE   depende de etapa que ainda não foi executada aqui (ex.: treinar o
             modelo, que exige internet e PyTorch);
  FALHA      verificado e **não** atendido.

O objetivo é não precisar afirmar nada sem base: o que o script não consegue
provar, ele marca como MANUAL ou PENDENTE em vez de declarar aprovado.

Uso:
    python scripts/diagnostico.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import _caminho  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]

CORES = {"OK": "\033[92m", "MANUAL": "\033[94m", "PENDENTE": "\033[93m", "FALHA": "\033[91m"}
RESET = "\033[0m"

resultados: list[tuple[str, str, str]] = []


def avaliar(criterio: str, estado: str, detalhe: str = "") -> None:
    resultados.append((criterio, estado, detalhe))
    cor = CORES.get(estado, "")
    print(f"  [{cor}{estado:<8}{RESET}] {criterio}")
    if detalhe:
        print(f"             {detalhe}")


def dependencia_instalada(nome: str) -> bool:
    return importlib.util.find_spec(nome) is not None


def main() -> int:
    print("=" * 74)
    print("LionGuard AI — diagnóstico dos critérios de aceite")
    print("=" * 74)

    # Banco isolado, para não alterar a base de desenvolvimento.
    temporario = tempfile.mkdtemp(prefix="lionguard_diag_")
    os.environ["LIONGUARD_DB"] = str(Path(temporario) / "diag.db")
    os.environ["LIONGUARD_IMAGE_DIR"] = str(Path(temporario) / "images")
    os.environ.setdefault("LIONGUARD_ADMIN_PASS", "diagnostico-admin-2026")
    os.environ.setdefault("LIONGUARD_PESQ_PASS", "diagnostico-pesq-2026")

    from src.ai.inference import obter_servico_inferencia
    from src.config import get_config, resetar_config
    from src.database import queries
    from src.database.connection import fechar_conexoes, inicializar_banco
    from src.database.repositories import OcorrenciaRepository
    from src.database.schema import Decisao, OrigemLocalizacao
    from src.security.auth import ServicoAutenticacao
    from src.security.permissions import AcessoNegado, Permissao, exigir
    from src.security.uploads import validar_imagem
    from src.services.geolocation import construir_localizacao, localizacao_por_regiao
    from src.services.sightings import DadosAvistamento, ServicoAvistamentos
    from src.services.validation import ServicoValidacao

    resetar_config()
    configuracao = get_config()

    print("\n--- Ambiente -----------------------------------------------------------")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Banco de diagnóstico: {configuracao.database_url}")

    print("\n--- Dependências -------------------------------------------------------")
    for modulo, finalidade, obrigatoria in (
        ("streamlit", "interface web", True),
        ("folium", "mapa", True),
        ("streamlit_folium", "mapa no Streamlit", True),
        ("streamlit_js_eval", "GPS do navegador", True),
        ("plotly", "gráficos", True),
        ("pandas", "análise de dados", True),
        ("sklearn", "DBSCAN e métricas", True),
        ("PIL", "processamento de imagem", True),
        ("onnxruntime", "inferência ONNX", True),
        ("torch", "treinamento (opcional em produção)", False),
        ("reportlab", "geração do PDF da entrega", False),
    ):
        presente = dependencia_instalada(modulo)
        rotulo = f"Dependência `{modulo}` ({finalidade})"
        if presente:
            avaliar(rotulo, "OK")
        else:
            avaliar(
                rotulo,
                "FALHA" if obrigatoria else "PENDENTE",
                "instale com `pip install -r requirements.txt`"
                if obrigatoria
                else "instale com `pip install -r requirements-treino.txt`",
            )

    print("\n--- Critérios de aceite ------------------------------------------------")

    # 1. Aplicação inicializa
    arquivo_principal = RAIZ / "app" / "main.py"
    paginas = sorted((RAIZ / "app" / "paginas").glob("*.py"))
    if arquivo_principal.is_file() and len(paginas) >= 10:
        import py_compile

        erros = []
        for arquivo in [arquivo_principal, *paginas]:
            try:
                py_compile.compile(str(arquivo), doraise=True, quiet=2)
            except py_compile.PyCompileError as erro:
                erros.append(f"{arquivo.name}: {erro}")
        if erros:
            avaliar("Aplicação inicializa corretamente", "FALHA", "; ".join(erros[:3]))
        elif dependencia_instalada("streamlit"):
            avaliar(
                "Aplicação inicializa corretamente",
                "MANUAL",
                "código compila; confirme com `streamlit run app/main.py`",
            )
        else:
            avaliar(
                "Aplicação inicializa corretamente",
                "PENDENTE",
                "Streamlit não instalado neste ambiente",
            )
    else:
        avaliar("Aplicação inicializa corretamente", "FALHA", "arquivos da interface ausentes")

    avaliar(
        "Usuário consegue abrir no celular",
        "MANUAL",
        "layout mobile-first implementado (CSS em app/styles/theme.py); "
        "confirme em um aparelho real na mesma rede",
    )
    avaliar(
        "É possível capturar ou enviar fotografia",
        "MANUAL",
        "st.camera_input e st.file_uploader em app/components/upload.py; "
        "a câmera depende de permissão do navegador",
    )

    # IA
    inicializar_banco()
    servico_ia = obter_servico_inferencia()
    if servico_ia.disponivel:
        import io as _io

        import numpy as _np
        from PIL import Image as _Image

        _buffer = _io.BytesIO()
        _Image.fromarray(
            _np.random.default_rng(3).integers(30, 220, size=(300, 400, 3), dtype=_np.uint8)
        ).save(_buffer, format="JPEG")
        resultado_ia = servico_ia.classificar(_buffer.getvalue())
        avaliar(
            "IA executa inferência real",
            "OK",
            f"modelo {servico_ia.cartao.nome} v{servico_ia.cartao.versao}, "
            f"classe {resultado_ia.classe}, {resultado_ia.tempo_inferencia_ms} ms",
        )
    else:
        avaliar(
            "IA executa inferência real",
            "PENDENTE",
            f"{servico_ia.descricao_estado} — rode baixar_dados.py, "
            "preparar_dataset.py, treinar_modelo.py e avaliar_modelo.py",
        )

    avaliar(
        "Sistema solicita permissão de localização",
        "MANUAL",
        "componente de GPS em app/components/location.py; o navegador exibe o pedido",
    )
    avaliar(
        "GPS funciona em ambiente compatível",
        "MANUAL",
        "exige contexto seguro (HTTPS ou localhost); a interface diagnostica e avisa",
    )

    # Fallback manual de localização — verificável
    try:
        regiao = localizacao_por_regiao("ES", "Guarapari")
        ponto = construir_localizacao(-20.67, -40.49, OrigemLocalizacao.MAPA_MANUAL)
        avaliar(
            "Existe fallback de localização manual",
            "OK",
            f"mapa: {ponto.municipio}/{ponto.estado} ({ponto.origem}); "
            f"região: {regiao.municipio}/{regiao.estado} ({regiao.origem})",
        )
    except Exception as erro:
        avaliar("Existe fallback de localização manual", "FALHA", str(erro))

    # Registro completo
    try:
        import io

        import numpy as np
        from PIL import Image

        gerador = np.random.default_rng(5)
        buffer = io.BytesIO()
        Image.fromarray(
            gerador.integers(30, 220, size=(300, 400, 3), dtype=np.uint8)
        ).save(buffer, format="JPEG")
        validada = validar_imagem(buffer.getvalue())

        localizacao = construir_localizacao(
            -20.6712, -40.4985, OrigemLocalizacao.GPS_DISPOSITIVO, 12.0
        )
        servico = ServicoAvistamentos()
        from datetime import datetime, timedelta

        dados = DadosAvistamento(
            localizacao=localizacao,
            data_hora_avistamento=(datetime.now() - timedelta(hours=2))
            .replace(microsecond=0)
            .isoformat(),
            imagem=validada,
            inferencia=servico_ia.classificar(validada.conteudo),
            chave_idempotencia="diagnostico-1",
        )
        resultado = servico.registrar(dados)
        avaliar("Usuário consegue confirmar o registro", "OK", f"retorno: {resultado.mensagem}")
        avaliar(
            "Banco salva os dados",
            "OK" if OcorrenciaRepository().por_protocolo(resultado.protocolo) else "FALHA",
            f"ocorrência relida do banco: {resultado.protocolo}",
        )
        avaliar(
            "Protocolo é gerado",
            "OK" if resultado.protocolo else "FALHA",
            f"formato LG-ANO-XXXXXX → {resultado.protocolo}",
        )
        repetido = servico.registrar(dados)
        avaliar(
            "Registro duplicado por duplo clique é impedido",
            "OK" if repetido.duplicado and OcorrenciaRepository().contar() == 1 else "FALHA",
            f"duplicado={repetido.duplicado}, total={OcorrenciaRepository().contar()}",
        )
    except Exception as erro:
        avaliar("Usuário consegue confirmar o registro", "FALHA", f"{type(erro).__name__}: {erro}")
        resultado = None

    # Dashboards
    kpis = queries.kpis_gerais()
    avaliar(
        "Dashboard apresenta os registros",
        "OK" if kpis["total"] >= 1 else "FALHA",
        f"KPIs calculados do banco: total={kpis['total']}, pendentes={kpis['pendentes']}",
    )
    pontos = queries.dados_geograficos(publico=True)
    if pontos:
        avaliar(
            "Mapa apresenta a localização aproximada",
            "OK",
            f"{len(pontos)} ponto(s); primeira coordenada pública: "
            f"{pontos[0]['latitude']}, {pontos[0]['longitude']} "
            f"({configuracao.casas_decimais_publicas} casas decimais)",
        )
    else:
        avaliar("Mapa apresenta a localização aproximada", "FALHA", "nenhum ponto retornado")

    # Validação humana
    try:
        autenticacao = ServicoAutenticacao()
        autenticacao.garantir_usuarios_iniciais()
        sessao = autenticacao.autenticar(
            os.environ.get("LIONGUARD_PESQ_USER", "pesquisador"),
            os.environ["LIONGUARD_PESQ_PASS"],
        )
        ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
        decisao = ServicoValidacao().decidir(
            ocorrencia_id=ocorrencia.id,
            decisao=Decisao.CONFIRMAR,
            justificativa="Diagnóstico automatizado dos critérios de aceite.",
            sessao=sessao,
        )
        avaliar("Pesquisador consegue revisar a ocorrência", "OK", decisao.mensagem)
        atualizada = OcorrenciaRepository().por_id(ocorrencia.id)
        avaliar(
            "Status é atualizado",
            "OK" if str(atualizada.status) == "CONFIRMADO" else "FALHA",
            f"status no banco: {atualizada.status}",
        )
        kpis_depois = queries.kpis_gerais()
        avaliar(
            "Gráficos refletem a revisão",
            "OK" if kpis_depois["confirmados"] == kpis["confirmados"] + 1 else "FALHA",
            f"confirmados {kpis['confirmados']} → {kpis_depois['confirmados']}; "
            f"validados {kpis_depois['percentual_validado']}%",
        )
    except Exception as erro:
        avaliar(
            "Pesquisador consegue revisar a ocorrência",
            "FALHA",
            f"{type(erro).__name__}: {erro}",
        )

    # Dados de demonstração
    from src.data.demo_seed import GeradorDemonstracao
    from src.database.queries import Filtros

    GeradorDemonstracao().gerar(quantidade=20, semente=1)
    com_demo = queries.kpis_gerais(Filtros())["total"]
    sem_demo = queries.kpis_gerais(Filtros().sem_demonstracao())["total"]
    avaliar(
        "Dados demonstrativos estão identificados",
        "OK" if com_demo > sem_demo else "FALHA",
        f"com demonstração={com_demo}, sem demonstração={sem_demo} "
        "(rótulo tipo_dado=DEMO e filtro de procedência)",
    )

    # Controle de acesso
    falhas_acesso = []
    for permissao in (
        Permissao.VER_PAINEL_OPERACIONAL,
        Permissao.VALIDAR_OCORRENCIA,
        Permissao.GERENCIAR_USUARIOS,
    ):
        try:
            exigir(None, permissao)
            falhas_acesso.append(str(permissao))
        except AcessoNegado:
            pass
    avaliar(
        "Controle de acesso funciona",
        "OK" if not falhas_acesso else "FALHA",
        "visitante anônimo é recusado em todas as permissões restritas"
        if not falhas_acesso
        else f"permissões concedidas indevidamente: {falhas_acesso}",
    )

    # Resultados de IA documentados
    caminho_metricas = RAIZ / "reports" / "metricas_modelo.json"
    if caminho_metricas.is_file():
        avaliar("Resultados de IA estão documentados", "OK", f"{caminho_metricas}")
    else:
        avaliar(
            "Resultados de IA estão documentados",
            "PENDENTE",
            "reports/metricas_modelo.json é gerado por scripts/avaliar_modelo.py; "
            "o painel de IA exibe estado de indisponibilidade até então",
        )

    # Testes
    testes = sorted((RAIZ / "tests").glob("test_*.py"))
    if testes and dependencia_instalada("pytest"):
        avaliar(
            "Testes foram executados",
            "MANUAL",
            f"{len(testes)} arquivo(s) de teste; rode `python -m pytest -q` "
            "(o resultado da última execução está em reports/)",
        )
    else:
        avaliar("Testes foram executados", "PENDENTE", "pytest ausente ou sem testes")

    # Documentação
    documentos = {
        "README.md": RAIZ / "README.md",
        "docs/arquitetura.md": RAIZ / "docs" / "arquitetura.md",
        "docs/deploy.md": RAIZ / "docs" / "deploy.md",
        "PDF da entrega (document/)": RAIZ / "document" / "LionGuard_AI_Global_Solution_2026_2.pdf",
    }
    faltando = [nome for nome, caminho in documentos.items() if not caminho.is_file()]
    avaliar(
        "README e PDF estão completos",
        "OK" if not faltando else "PENDENTE",
        "todos presentes" if not faltando else f"ausentes: {', '.join(faltando)}",
    )

    limitacoes = RAIZ / "docs" / "limitacoes.md"
    avaliar(
        "Limitações foram identificadas",
        "OK" if limitacoes.is_file() else "PENDENTE",
        str(limitacoes) if limitacoes.is_file() else "docs/limitacoes.md ausente",
    )

    # Persistência
    total_antes = OcorrenciaRepository().contar()
    fechar_conexoes()
    avaliar(
        "Persistência após reinicialização",
        "OK" if OcorrenciaRepository().contar() == total_antes else "FALHA",
        f"{total_antes} registro(s) antes e depois de fechar as conexões",
    )

    # ------------------------------------------------------------- resumo
    print("\n" + "=" * 74)
    contagem = {estado: 0 for estado in CORES}
    for _, estado, _ in resultados:
        contagem[estado] = contagem.get(estado, 0) + 1
    print(
        f"Resumo: {contagem.get('OK', 0)} OK · "
        f"{contagem.get('MANUAL', 0)} MANUAL · "
        f"{contagem.get('PENDENTE', 0)} PENDENTE · "
        f"{contagem.get('FALHA', 0)} FALHA"
    )
    print("=" * 74)

    destino = RAIZ / "reports" / "diagnostico_criterios.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime as _dt

    linhas = [
        "# LionGuard AI — diagnóstico dos critérios de aceite",
        "",
        f"Gerado por `scripts/diagnostico.py` em "
        f"{_dt.now().replace(microsecond=0).isoformat()}.",
        "",
        "| Critério | Estado | Detalhe |",
        "| --- | --- | --- |",
    ]
    for criterio, estado, detalhe in resultados:
        linhas.append(f"| {criterio} | **{estado}** | {detalhe or '—'} |")
    linhas += [
        "",
        "Legenda: **OK** verificado automaticamente · **MANUAL** implementado, "
        "confirmável só no navegador · **PENDENTE** depende de etapa externa "
        "(internet, PyTorch, execução) · **FALHA** verificado e não atendido.",
        "",
    ]
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Relatório gravado em {destino}")

    return 1 if contagem.get("FALHA", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
