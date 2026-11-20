"""
Sobre o projeto — problema, público, tecnologias, dados, ODS e limitações.

Esta página é também a prestação de contas técnica do protótipo: o que está
realmente implementado, o que depende de etapa externa e o que são limitações
conhecidas. Os estados exibidos são lidos do sistema em tempo de execução, não
escritos à mão.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.ui import cabecalho, rodape_institucional, titulo_secao
from src.ai.inference import obter_servico_inferencia
from src.data.dataset import resumo_manifesto
from src.database import queries
from src.database.repositories import FonteDadosRepository
from src.services.analytics import carregar_metricas_modelo

cabecalho(
    "Sobre o projeto",
    "LionGuard AI — detecção precoce e monitoramento colaborativo do peixe-leão. "
    "Protótipo acadêmico da Global Solution 2026.2 da FIAP (desafio CitizenTech).",
)

abas = st.tabs(
    [
        "Problema e público",
        "Como funciona",
        "Dados",
        "ODS e impacto",
        "Limitações",
        "Estado do sistema",
    ]
)

# ------------------------------------------------------- problema e público
with abas[0]:
    titulo_secao("O problema concreto")
    st.markdown(
        """
Quando uma espécie marinha invasora chega a um novo trecho de costa, a janela
para agir é curta — e a informação quase sempre chega primeiro a quem está na
água, não a uma rede oficial de monitoramento. O primeiro registro de
peixe-leão no Espírito Santo, em novembro de 2026, foi feito por uma equipe de
mergulho recreativo, que comunicou o órgão ambiental por rede social e depois
oficialmente.

Esse caminho funciona, mas é frágil: depende de alguém saber a quem recorrer,
a informação chega em formato livre (vídeo, mensagem, foto sem coordenada) e
não se acumula em uma base consultável. O resultado é que **avistamentos viram
notícia, não dado**.

**O problema que atacamos:** não existe um caminho simples, de um minuto e sem
cadastro, para que qualquer pessoa transforme um avistamento em registro
estruturado — com foto, coordenada, data e trilha de validação — e para que
pesquisadores acompanhem isso em um painel único.
        """
    )

    titulo_secao("Quem é beneficiado")
    st.markdown(
        """
| Ator | Papel na solução | Benefício |
| --- | --- | --- |
| Banhistas, mergulhadores e pescadores | Registram avistamentos | Caminho claro e sem burocracia para contribuir; orientação de segurança |
| Operadoras de mergulho | Registro sistemático dos pontos que visitam | Protocolo e histórico das próprias observações |
| Pesquisadores e órgãos ambientais | Validam e analisam | Base organizada, com procedência e indicadores de qualidade |
| Gestão municipal e estadual | Consome indicadores | Priorização de onde capacitar e monitorar |
| Comunidade pesqueira | Beneficiária indireta | Resposta mais rápida reduz impacto sobre o estoque pesqueiro |

**Como o impacto poderia ser ampliado:** integração com os canais oficiais
(Iema, ICMBio/Centro Tamar), publicação dos dados validados em bases abertas
como o GBIF, e convênio com operadoras de mergulho, que já são hoje as
sentinelas de fato da costa.
        """
    )

# ------------------------------------------------------------ como funciona
with abas[1]:
    titulo_secao("Fluxo da solução")
    st.markdown(
        """
```
Cidadão → fotografia → validação da imagem → IA (classificação) →
localização (GPS ou mapa) → confirmação → banco de dados →
dashboards → validação humana → indicadores atualizados
```

O cadastro definitivo só acontece com a ação expressa do usuário: o
processamento da imagem pode ocorrer antes, mas nada é gravado sem o toque em
"Confirmar avistamento".
        """
    )

    titulo_secao("Integração entre disciplinas")
    st.markdown(
        """
| Disciplina | Onde aparece no sistema |
| --- | --- |
| Visão computacional / redes neurais | CNN experimental pequena treinada com poucos exemplos (`models/`) e pipeline MobileNetV3 preparado para treino adequado (`src/ai/`) |
| Aplicações interativas | Portal do cidadão e cinco painéis em Streamlit (`app/`) |
| Banco de dados | Modelo relacional com 8 tabelas, constraints, índices e consultas analíticas (`src/database/`) |
| Análise exploratória de dados | Painel científico: distribuições, completude, estatísticas descritivas |
| Agrupamento (*clustering*) | DBSCAN com métrica haversine sobre as coordenadas (`src/services/spatial.py`) |
| Cibersegurança | Hash scrypt, perfis de permissão, validação de upload, auditoria, limite de requisições (`src/security/`) |
| Sensores e conectividade | API de geolocalização do navegador (GPS do aparelho) com precisão registrada |
| Serviços em nuvem | Caminho de implantação documentado (PostgreSQL + armazenamento de objetos) em `docs/deploy.md` |
| Qualidade e testes | Suíte Pytest cobrindo banco, serviços, segurança e IA (`tests/`) |
        """
    )

    titulo_secao("Decisões técnicas e seus motivos")
    st.markdown(
        """
- **Classificação (CNN) em vez de detecção (YOLO):** o modelo incluso é uma
  CNN exploratória pequena, ainda sem validação independente; o pipeline de
  *transfer learning* MobileNetV3 foi implementado para o treino futuro.
  Consequência: o sistema **não** desenha caixas nem conta indivíduos
  automaticamente, e isso está dito na interface.
- **Três respostas, não duas:** positivo, não identificado e **inconclusivo**.
  A faixa intermediária de score vira "inconclusivo" em vez de ser forçada a
  uma decisão binária.
- **Status inicial sempre pendente:** nenhum score, por alto que seja, confirma
  uma ocorrência. A confirmação é ato humano, registrado com justificativa.
- **Coordenada pública arredondada:** o mapa aberto mostra posição aproximada
  (~1 km); a coordenada exata exige perfil autorizado.
- **SQLite com SQL explícito:** a modelagem e as consultas ficam visíveis e
  auditáveis, o que é adequado a um trabalho acadêmico; a migração para
  PostgreSQL está documentada.
        """
    )

# -------------------------------------------------------------------- dados
with abas[2]:
    titulo_secao("Origem dos dados")
    st.markdown(
        """
O sistema trabalha com **quatro categorias**, sempre distinguíveis no banco e
nos filtros:

1. **Registros de usuários** (`REAL`) — enviados pela plataforma;
2. **Registros importados** (`IMPORTADO`) — de bases documentadas (GBIF,
   iNaturalist), com fonte, URL e licença gravadas. Importação **não** confirma
   a ocorrência: o status continua pendente;
3. **Ocorrências revisadas** — qualquer das anteriores após decisão humana,
   com histórico;
4. **Dados de demonstração** (`DEMO`) — gerados pelo sistema para testar os
   painéis. Sempre rotulados, sempre removíveis por filtro, nunca acompanhados
   de predição de IA.
        """
    )

    fontes = FonteDadosRepository().listar()
    if fontes:
        import pandas as pd

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Fonte": fonte.nome,
                        "Tipo": fonte.tipo_fonte,
                        "Licença": fonte.licenca or "—",
                        "Importado em": fonte.data_importacao[:10],
                        "URL": fonte.url or "—",
                    }
                    for fonte in fontes
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Nenhuma fonte de dados registrada ainda nesta instalação.")

    titulo_secao("Imagens usadas no treinamento")
    manifesto = resumo_manifesto()
    if manifesto.get("disponivel"):
        st.markdown(
            f"- **Total de imagens:** {manifesto['total_imagens']}\n"
            f"- **Por classe:** {manifesto['por_classe']}\n"
            f"- **Por licença:** {manifesto['por_licenca']}\n"
            f"- **Fontes:** {manifesto['por_fonte']}"
        )
        st.caption(
            "Só são aceitas imagens com licença Creative Commons declarada; o "
            "manifesto guarda fonte, URL, licença, autor e identificador da "
            "observação de cada arquivo."
        )
    else:
        st.info(
            "Nenhum manifesto de imagens encontrado nesta instalação "
            f"({manifesto.get('motivo')}). O download é feito na máquina do "
            "usuário com `python scripts/baixar_dados.py`, que respeita as "
            "licenças das observações."
        )

    titulo_secao("Qualidade e limitações dos dados")
    completude = queries.estatisticas_completude()
    if completude["total"]:
        st.markdown(
            f"Sobre os **{completude['total']}** registros atuais da base: "
            f"{completude['pct_coordenadas']}% têm coordenadas, "
            f"{completude['pct_localizacao_precisa']}% têm localização precisa "
            f"(GPS ou ponto no mapa), {completude['pct_imagem']}% têm fotografia, "
            f"{completude['pct_profundidade']}% informam profundidade e "
            f"{completude['pct_habitat']}% informam habitat."
        )
    st.markdown(
        """
Limitações intrínsecas, que o painel científico repete a cada visualização:

- **viés de observação** — mais registros onde há mais mergulhadores e sinal de
  celular, não necessariamente mais peixes;
- **ausência não é evidência de ausência** — trecho sem registro pode ser
  trecho sem observador;
- **campos opcionais ficam vazios** — profundidade e habitat ausentes são
  tratados como ausentes, nunca como zero ou como categoria inventada;
- **identificação preliminar** — o resultado da IA é indicação, não laudo.
        """
    )

# ------------------------------------------------------------ ODS e impacto
with abas[3]:
    titulo_secao("ODS 14 — Vida na Água")
    st.markdown(
        """
O projeto se relaciona principalmente ao **ODS 14 (Vida na Água)** da ONU, que
trata da conservação e do uso sustentável dos oceanos e dos recursos marinhos.
Espécies exóticas invasoras são um vetor direto de perda de biodiversidade
marinha, e a resposta depende de informação cedo e organizada.

Contribuições secundárias:

- **ODS 15 (Vida Terrestre)** — a meta de controle de espécies exóticas
  invasoras é compartilhada;
- **ODS 11 (Cidades e Comunidades Sustentáveis)** — participação cidadã
  organizada em um problema ambiental local;
- **ODS 17 (Parcerias)** — a arquitetura prevê intercâmbio com órgãos
  ambientais e bases abertas.
        """
    )

    titulo_secao("Como medir o impacto")
    st.markdown(
        """
Indicadores propostos, todos calculáveis a partir do próprio banco:

| Indicador | O que mede | Como é obtido |
| --- | --- | --- |
| Tempo entre avistamento e cadastro | Agilidade do canal | `data_hora_cadastro − data_hora_avistamento` |
| Tempo mediano de revisão | Capacidade de resposta | `data_primeira_decisao − data_hora_cadastro` |
| Nº de municípios com registro | Cobertura territorial | `COUNT(DISTINCT municipio)` |
| % de registros com coordenada precisa | Qualidade do dado | completude por `origem_localizacao` |
| % validados | Maturidade operacional | decisões finais ÷ total elegível |
| Taxa de concordância IA × avaliador | Utilidade do modelo | painel de IA, matriz operacional |
| Novas áreas detectadas por período | Detecção precoce | agrupamentos DBSCAN inéditos por janela |

**Importante:** aumento no número de registros mede adoção da plataforma, não
necessariamente aumento da população da espécie. Essa distinção é parte do
indicador, não uma ressalva de rodapé.
        """
    )

# -------------------------------------------------------------- limitações
with abas[4]:
    titulo_secao("Limitações conhecidas do protótipo")
    st.markdown(
        """
- **É uma POC acadêmica**, sem homologação, parceria ou vínculo com órgão
  ambiental. Não substitui o canal oficial de comunicação de ocorrências.
- **A identificação automática é preliminar.** O desempenho depende do conjunto
  de imagens disponível, e fotos subaquáticas variam muito em turbidez,
  iluminação e distância. O score não é probabilidade calibrada.
- **O classificador não localiza nem conta indivíduos.** Contagem automática
  exigiria um detector treinado com anotações de caixa.
- **GPS exige contexto seguro.** O navegador só libera a localização em HTTPS
  ou `localhost`; há sempre o caminho manual pelo mapa.
- **Sem persistência garantida em hospedagem gratuita.** SQLite em disco
  efêmero e imagens em sistema de arquivos local se perdem a cada redeploy; o
  caminho de produção está documentado em `docs/deploy.md`.
- **Limite de envios por sessão de navegador.** É uma proteção simples; uma
  operação real exigiria limitação na borda (por IP/edge) e verificação
  anti-automação.
- **Tabela municipal aproximada.** A sugestão de município usa pontos de
  referência, não base cartográfica oficial do IBGE; a distância é informada e
  o usuário pode corrigir.
- **Revisão humana sem SLA.** Não há garantia de prazo de validação neste
  protótipo.
        """
    )

# --------------------------------------------------------- estado do sistema
with abas[5]:
    titulo_secao("Estado verificável desta instalação")
    servico = obter_servico_inferencia()
    metricas = carregar_metricas_modelo()
    kpis = queries.kpis_gerais()

    coluna_ia, coluna_banco = st.columns(2)
    with coluna_ia:
        st.markdown("**Modelo de IA**")
        st.markdown(
            f"- Estado: `{servico.estado}`\n"
            f"- Detalhe: {servico.descricao_estado}\n"
            f"- Avaliação disponível: "
            f"{'sim' if metricas.get('disponivel') else 'não'}"
        )
        if not metricas.get("disponivel"):
            st.caption(metricas.get("motivo", ""))
    with coluna_banco:
        st.markdown("**Banco de dados**")
        st.markdown(
            f"- Ocorrências: {kpis['total']}\n"
            f"- Registros de demonstração: {kpis['demonstrativos']}\n"
            f"- Municípios: {kpis['municipios']} em {kpis['estados']} estado(s)\n"
            f"- Inferências executadas: "
            f"{queries.metricas_inferencia()['total_inferencias']}"
        )

    st.caption(
        "Esta aba lê o estado real do sistema a cada carregamento. Se algo "
        "aparece como indisponível, é porque está indisponível — não há valor "
        "de exemplo nesta página."
    )

rodape_institucional()
