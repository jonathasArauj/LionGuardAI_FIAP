"""
Dashboard 4 — desempenho do modelo de inteligência artificial.

Este painel **não** gera números: ele lê duas fontes reais.

  1. `reports/metricas_modelo.json`, produzido por `scripts/avaliar_modelo.py`
     sobre o conjunto de teste;
  2. a tabela `predicao`, com as inferências efetivamente executadas em
     produção.

Se o modelo não estiver publicado ou avaliado, o painel mostra o estado de
indisponibilidade e explica o que falta. Nenhuma métrica de exemplo é exibida.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import json

import streamlit as st

from app.components.auth_ui import faixa_especialista, proteger
from app.components.charts import (
    curvas_treinamento,
    distribuicao_scores_por_classe,
    exibir,
    histograma,
    matriz_confusao,
    metricas_por_limiar,
)
from app.components.tables import tabela
from app.components.ui import (
    estado_vazio,
    linha_kpis,
    rodape_institucional,
    titulo_secao,
)
from app.styles.theme import TURQUESA
from src.security.permissions import Permissao
from src.services.analytics import painel_ia

sessao = proteger(Permissao.VER_DASHBOARD_IA, "Painel de inteligência artificial")

faixa_especialista(
    sessao,
    "Inteligência artificial",
    "Desempenho do modelo de classificação e rastreamento das inferências "
    "executadas pela plataforma. <b>Não aparece na visão pública</b>: métricas "
    "de modelo exigem contexto para não serem lidas como certeza.",
)

painel = painel_ia()
cartao = painel["cartao"]
metricas = painel["metricas_treinamento"]
producao = painel["metricas_producao"]

# -------------------------------------------------------- estado do modelo
if painel["estado_modelo"] != "DISPONIVEL":
    st.error(
        f"**Modelo indisponível** (`{painel['estado_modelo']}`) — "
        f"{painel['descricao_modelo']}"
    )
    st.markdown(
        """
Para publicar um modelo nesta instalação:

```bash
python scripts/baixar_dados.py      # baixa imagens licenciadas (precisa de internet)
python scripts/preparar_dataset.py  # valida, deduplica e divide treino/val/teste
python scripts/treinar_modelo.py    # treina e exporta ONNX + model_card.json
python scripts/avaliar_modelo.py    # gera reports/metricas_modelo.json
```

Enquanto não houver modelo, a plataforma continua operando: o registro de
avistamentos funciona normalmente e as ocorrências são gravadas com o estado
`SEM_MODELO`, seguindo para validação humana.
        """
    )
else:
    st.success(f"**Modelo técnico carregado:** {painel['descricao_modelo']}")
    if cartao and "experimental" in cartao.versao.lower():
        st.warning(
            "Versão experimental com amostra extremamente pequena, SEM conjunto "
            "de teste independente. Não há métricas válidas de precisão/recall "
            "para uso no mundo real. Imagens negativas não representam todos os outros peixes."
        )
    linha_kpis(
        [
            {"rotulo": "Modelo", "valor": cartao.nome},
            {"rotulo": "Versão", "valor": cartao.versao},
            {"rotulo": "Arquitetura", "valor": cartao.arquitetura},
            {"rotulo": "Entrada", "valor": f"{cartao.entrada}×{cartao.entrada} px"},
        ]
    )
    if cartao.observacoes:
        st.caption(cartao.observacoes)

# --------------------------------------------------- métricas de avaliação
st.divider()
titulo_secao(
    "Métricas no conjunto de teste",
    "Conjunto separado por observação, sem sobreposição com treino e validação.",
)

if not metricas.get("disponivel"):
    estado_vazio(
        "Nenhuma avaliação de modelo disponível.",
        metricas.get("motivo", ""),
        "🤖",
    )
else:
    principais = metricas["metricas"]
    conjunto = metricas.get("conjunto_teste", {})

    linha_kpis(
        [
            {
                "rotulo": "Acurácia",
                "valor": principais["acuracia"] * 100,
                "nota": f"limiar {principais['limiar']:.2f}",
                "formato": "{:.1f}%",
            },
            {
                "rotulo": "Precisão",
                "valor": principais["precisao"] * 100,
                "nota": "dos positivos apontados, quantos eram",
                "formato": "{:.1f}%",
            },
            {
                "rotulo": "Revocação",
                "valor": principais["revocacao"] * 100,
                "nota": "dos positivos reais, quantos achou",
                "formato": "{:.1f}%",
            },
            {
                "rotulo": "F1-score",
                "valor": principais["f1"] * 100,
                "nota": "média harmônica",
                "formato": "{:.1f}%",
                "cor_borda": TURQUESA,
            },
        ]
    )
    linha_kpis(
        [
            {
                "rotulo": "Imagens no teste",
                "valor": conjunto.get("total"),
                "nota": str(conjunto.get("imagens_por_classe", "")),
            },
            {
                "rotulo": "AUC-ROC",
                "valor": metricas.get("auc_roc"),
                "nota": "área sob a curva ROC",
                "formato": "{:.3f}",
            },
            {
                "rotulo": "Falsos negativos",
                "valor": principais["falsos_negativos"],
                "nota": "peixe-leão não identificado",
            },
            {
                "rotulo": "Falsos positivos",
                "valor": principais["falsos_positivos"],
                "nota": "apontado sem ser",
            },
        ]
    )

    coluna_matriz, coluna_limiar = st.columns(2)
    with coluna_matriz:
        titulo_secao("Matriz de confusão")
        exibir(
            matriz_confusao(principais["matriz_confusao"]),
            "Matriz indisponível.",
        )
        st.caption(
            "VN = verdadeiro negativo · FP = falso positivo · "
            "FN = falso negativo · VP = verdadeiro positivo."
        )
    with coluna_limiar:
        titulo_secao("Desempenho por limiar")
        exibir(
            metricas_por_limiar(metricas.get("por_limiar", [])),
            "Varredura de limiares indisponível.",
        )
        st.caption(
            "Em detecção precoce de espécie invasora, um falso negativo "
            "(deixar passar uma ocorrência) custa mais do que um falso positivo "
            "(uma checagem extra). Isso favorece limiares mais baixos — e a "
            "decisão final continua sendo humana."
        )

    tempos = metricas.get("tempo_inferencia_ms", {})
    if tempos.get("n"):
        st.caption(
            f"Tempo de inferência no teste: mediana "
            f"{tempos.get('mediana')} ms (mín {tempos.get('minimo')} ms, "
            f"máx {tempos.get('maximo')} ms, n = {tempos.get('n')})."
        )

    for observacao in metricas.get("observacoes", []):
        st.caption(f"• {observacao}")

# -------------------------------------------------- histórico de treinamento
st.divider()
titulo_secao("Histórico de treinamento")

caminho_historico = RAIZ / "reports" / "historico_treinamento.json"
if not caminho_historico.is_file():
    estado_vazio(
        "Nenhum histórico de treinamento encontrado.",
        "O arquivo reports/historico_treinamento.json é gerado por "
        "scripts/treinar_modelo.py.",
        "📉",
    )
else:
    try:
        dados_historico = json.loads(caminho_historico.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as erro:
        st.warning(f"Histórico ilegível: {erro}")
        dados_historico = {}

    historico = dados_historico.get("historico", {})
    figura_perda, figura_metricas = curvas_treinamento(historico)
    coluna_perda, coluna_metricas = st.columns(2)
    with coluna_perda:
        exibir(figura_perda, "Sem curva de perda registrada.")
    with coluna_metricas:
        exibir(figura_metricas, "Sem métricas por época registradas.")

    if dados_historico:
        st.caption(
            f"Dispositivo: {dados_historico.get('dispositivo', '—')} · "
            f"melhor F1 de validação: {dados_historico.get('melhor_f1_validacao', '—')} · "
            f"duração: {dados_historico.get('duracao_segundos', '—')} s · "
            f"imagens de treino: {dados_historico.get('imagens_treino', '—')}"
        )
        st.caption(
            "Perda e métricas aparecem em gráficos separados porque têm escalas "
            "diferentes — nunca em eixo duplo."
        )

# -------------------------------------------------- scores e produção
st.divider()
titulo_secao("Distribuição dos scores", "Inferências executadas pela plataforma.")

if not painel["scores"]:
    estado_vazio(
        "Nenhuma inferência executada ainda nesta instalação.",
        "Os scores aparecem aqui conforme fotos reais são analisadas. "
        "Dados de demonstração não recebem predição de IA, de propósito.",
        "📈",
    )
else:
    coluna_caixas, coluna_histograma = st.columns(2)
    with coluna_caixas:
        exibir(
            distribuicao_scores_por_classe(painel["scores"], "Score por resultado"),
            "Sem scores registrados.",
        )
    with coluna_histograma:
        exibir(
            histograma(painel["histograma_scores"], rotulo_x="Faixa de score"),
            "Sem scores registrados.",
        )
    st.caption(
        "Os scores são saídas do modelo e **não** são probabilidades calibradas: "
        "um score de 0,80 não significa 80% de chance de ser peixe-leão."
    )

linha_kpis(
    [
        {
            "rotulo": "Inferências executadas",
            "valor": producao["total_inferencias"],
            "nota": "em produção, nesta instalação",
        },
        {
            "rotulo": "Tempo mediano",
            "valor": producao["tempo_mediano_ms"],
            "nota": "milissegundos por imagem",
            "formato": "{:.1f} ms",
        },
        {
            "rotulo": "Tempo mínimo",
            "valor": producao["tempo_minimo_ms"],
            "formato": "{:.1f} ms",
        },
        {
            "rotulo": "Tempo máximo",
            "valor": producao["tempo_maximo_ms"],
            "formato": "{:.1f} ms",
        },
    ]
)

# ------------------------------------------- concordância IA × avaliador
concordancia = painel["concordancia"]
if concordancia["total"] > 0:
    st.divider()
    titulo_secao(
        "Concordância entre IA e avaliador",
        "Comparação operacional, diferente da matriz de confusão do conjunto de teste.",
    )
    matriz_operacional = [
        [
            concordancia["ia_negativa_humano_rejeitou"],
            concordancia["ia_negativa_humano_confirmou"],
        ],
        [
            concordancia["ia_positiva_humano_rejeitou"],
            concordancia["ia_positiva_humano_confirmou"],
        ],
    ]
    coluna_matriz_op, coluna_texto = st.columns([1, 1])
    with coluna_matriz_op:
        exibir(
            matriz_confusao(
                matriz_operacional,
                rotulos=("rejeitado pelo avaliador", "confirmado pelo avaliador"),
            ),
            "Sem casos decididos.",
        )
    with coluna_texto:
        acertos = (
            concordancia["ia_positiva_humano_confirmou"]
            + concordancia["ia_negativa_humano_rejeitou"]
        )
        st.markdown(
            f"- Casos com decisão humana e classe da IA: **{concordancia['total']}**\n"
            f"- Concordância: **{acertos}** "
            f"({100 * acertos / concordancia['total']:.1f}%)\n"
            f"- IA positiva, avaliador rejeitou: "
            f"{concordancia['ia_positiva_humano_rejeitou']}\n"
            f"- IA negativa, avaliador confirmou: "
            f"{concordancia['ia_negativa_humano_confirmou']}"
        )
        st.caption(
            "Esta tabela mede o acordo entre modelo e avaliador em casos reais "
            "revisados. Não substitui a avaliação no conjunto de teste: a "
            "amostra é pequena e enviesada pelos registros que chegam."
        )

# ----------------------------------------------- rastreamento de inferências
st.divider()
titulo_secao(
    "Rastreamento de inferências",
    "Toda predição guarda a versão do modelo que a produziu.",
)
tabela(
    painel["inferencias"],
    altura=340,
    mensagem_vazia="Nenhuma inferência registrada nesta instalação.",
)

# ---------------------------------------------------------- análise de erros
if metricas.get("disponivel") and metricas.get("erros"):
    st.divider()
    titulo_secao("Análise dos erros do conjunto de teste")
    import pandas as pd

    st.dataframe(
        pd.DataFrame(metricas["erros"]),
        use_container_width=True,
        hide_index=True,
        height=260,
    )
    st.caption(
        "Lista dos casos classificados incorretamente, ordenados pela confiança "
        "do erro. São os exemplos mais úteis para orientar a próxima rodada de "
        "coleta de imagens."
    )

rodape_institucional()
