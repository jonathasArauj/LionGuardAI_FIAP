# Arquitetura do LionGuard AI

Documento técnico da arquitetura, dos fluxos e do modelo de dados. Os diagramas
estão em Mermaid e são renderizados diretamente pelo GitHub.

---

## 1. Visão geral dos componentes

A aplicação separa interface, serviços de domínio, acesso a dados e
infraestrutura. A regra é que a interface **nunca** fala com o banco: ela chama
serviços, e os serviços usam repositórios. Isso é o que permite testar toda a
regra de negócio sem subir o Streamlit — e é por isso que a suíte de testes
cobre o fluxo completo sem navegador.

```mermaid
graph TB
    subgraph APRESENTACAO["Apresentação — Streamlit"]
        PUB["Portal do cidadão<br/>início · registrar · mapa · indicadores"]
        REST["Área restrita<br/>visão geral · científico · IA · validação · admin"]
        COMP["Componentes reutilizáveis<br/>upload · localização · gráficos · mapas · tabelas"]
    end

    subgraph SERVICOS["Serviços de domínio"]
        SAV["sightings<br/>registro e protocolo"]
        SGEO["geolocation<br/>validação e referências"]
        SIMG["image_storage<br/>arquivos e hash"]
        SVAL["validation<br/>fluxo de revisão"]
        SANA["analytics<br/>indicadores e exportação"]
        SESP["spatial<br/>DBSCAN"]
    end

    subgraph IA["Inteligência artificial"]
        PREP["preprocessing<br/>letterbox + normalização"]
        INF["inference<br/>ONNX / TorchScript"]
        TRE["train / evaluate<br/>offline"]
    end

    subgraph SEGURANCA["Segurança"]
        AUTH["auth<br/>scrypt + sessão"]
        PERM["permissions<br/>matriz de perfis"]
        UPL["uploads<br/>validação de imagem"]
        RL["rate_limit"]
        SAN["sanitize"]
        AUD["auditoria"]
    end

    subgraph DADOS["Acesso a dados"]
        REPO["repositories"]
        QRY["queries<br/>SQL analítico"]
        CONN["connection<br/>transações"]
    end

    subgraph INFRA["Infraestrutura"]
        DB[("SQLite<br/>(PostgreSQL em produção)")]
        FS[("Arquivos de imagem<br/>(objetos em produção)")]
        MOD[("models/<br/>modelo + model_card")]
    end

    PUB --> COMP
    REST --> COMP
    COMP --> SAV & SGEO & SVAL & SANA & SESP
    PUB -.->|"permissões"| PERM
    REST -.->|"permissões"| PERM
    REST --> AUTH

    SAV --> SIMG & UPL & RL & SAN & AUD
    SAV --> INF
    INF --> PREP
    INF --> MOD
    TRE --> MOD

    SAV & SVAL & SANA & SESP --> REPO
    SANA & SESP --> QRY
    REPO & QRY --> CONN
    CONN --> DB
    SIMG --> FS
```

---

## 2. Fluxo do avistamento (caminho do cidadão)

Cada etapa só aparece na tela quando a anterior está resolvida, para não
apresentar um formulário longo no celular. Nenhuma falha intermediária
interrompe o registro: IA indisponível e GPS negado têm caminhos alternativos.

```mermaid
flowchart TD
    A["Abrir o site"] --> B{"Como enviar a foto?"}
    B -->|Câmera| C["st.camera_input"]
    B -->|Galeria| D["st.file_uploader"]
    B -->|Sem foto| E["Registro sem imagem<br/>(opção explícita)"]

    C & D --> F["Validação da imagem<br/>assinatura · integridade · dimensões"]
    F -->|Inválida| F1["Mensagem de erro<br/>dados do formulário preservados"]
    F1 --> B
    F -->|Válida| G["Remoção de metadados EXIF"]
    G --> H{"Foto tem GPS no EXIF?"}
    I{"Você está no local<br/>onde viu o peixe?"}
    H -->|Sim| H1["Informar e pedir autorização<br/>— nunca usar em silêncio"]
    H -->|Não| I
    H1 --> I

    G --> J["Inferência da IA"]
    J --> J1{"Modelo disponível?"}
    J1 -->|Não| J2["Estado SEM_MODELO<br/>segue sem classificação"]
    J1 -->|Sim| J3{"Faixa do score"}
    J3 -->|"≥ 0,70"| J4["Possível peixe-leão"]
    J3 -->|"0,45 – 0,70"| J5["Inconclusivo"]
    J3 -->|"< 0,45"| J6["Não identificado"]

    I -->|Sim| K["GPS do navegador<br/>lat · lon · precisão · horário"]
    I -->|Não| L["Marcar ponto no mapa"]
    K -->|Permissão negada ou falha| L
    L -->|Não consegue| M["Informar estado e município<br/>— REGIAO_APROXIMADA"]

    K & L & M --> N["Resumo para confirmação<br/>foto · IA · local · data"]
    E --> N
    J2 & J4 & J5 & J6 --> N

    N --> O["Confirmar avistamento"]
    O --> P{"Limite de envios<br/>da sessão?"}
    P -->|Estourado| P1["Bloquear e explicar"]
    P1 --> N
    P -->|Ok| Q{"Chave de idempotência<br/>já existe?"}
    Q -->|Sim| Q1["Devolver o mesmo protocolo<br/>— duplo clique não duplica"]
    Q -->|Não| R["Transação única:<br/>ocorrência + imagem + predição + auditoria"]
    R -->|Erro| R1["Rollback e remoção do arquivo<br/>nada é gravado"]
    R1 --> N
    R --> S["Reler do banco pelo protocolo"]
    S -->|Não encontrada| R1
    S -->|Confirmada| T["Status PENDENTE<br/>protocolo exibido"]
    Q1 --> T
    T --> U["Aparece no mapa e nos indicadores"]
```

---

## 3. Fluxo da inteligência artificial

```mermaid
flowchart LR
    subgraph OFFLINE["Offline — executado uma vez"]
        A1["iNaturalist / GBIF<br/>download com licença"] --> A2["manifesto.csv<br/>fonte · URL · licença · autor"]
        A2 --> A3["Validação e deduplicação<br/>por SHA-256"]
        A3 --> A4["Divisão por observação<br/>treino 70 / val 15 / teste 15"]
        A4 --> A5["Treino MobileNetV3<br/>2 fases + early stopping"]
        A5 --> A6["Exportação ONNX<br/>+ model_card.json"]
        A5 --> A7["historico_treinamento.json"]
        A6 --> A8["Avaliação no teste"]
        A8 --> A9["metricas_modelo.json"]
    end

    subgraph ONLINE["Online — a cada foto enviada"]
        B1["Bytes da imagem"] --> B2["Decodificação RGB<br/>+ correção de orientação"]
        B2 --> B3["Letterbox 224×224<br/>preserva proporção"]
        B3 --> B4["Normalização ImageNet<br/>→ tensor 1×3×224×224"]
        B4 --> B5["Backend ONNX Runtime<br/>carregado uma vez"]
        B5 --> B6["Softmax → score positivo"]
        B6 --> B7{"Qualidade da imagem"}
        B7 -->|"desfocada ou escura"| B8["Positivo rebaixado<br/>para inconclusivo"]
        B7 -->|ok| B9["Classe pelos limiares"]
        B8 & B9 --> B10["Persistir predição<br/>modelo · versão · score · tempo"]
    end

    A6 -.->|"carrega"| B5
    A9 -.->|"alimenta"| C1["Dashboard de IA"]
    A7 -.->|"alimenta"| C1
    B10 -.->|"rastreamento"| C1
```

**Ponto importante:** não existe caminho de código que produza classe ou score
sem executar o modelo. Sem modelo publicado, o resultado é `SEM_MODELO`; se a
inferência falhar, é `ERRO`. Nos dois casos o avistamento é gravado e segue
para revisão humana.

---

## 4. Modelo entidade-relacionamento

```mermaid
erDiagram
    USUARIO ||--o{ VALIDACAO : "decide"
    USUARIO ||--o{ LOG_AUDITORIA : "gera"
    OCORRENCIA ||--o{ IMAGEM : "possui"
    OCORRENCIA ||--o{ PREDICAO : "recebe"
    OCORRENCIA ||--o{ VALIDACAO : "é revisada em"
    IMAGEM ||--o{ PREDICAO : "analisada em"
    FONTE_DADOS ||--o{ OCORRENCIA : "origina"

    USUARIO {
        INTEGER id PK
        TEXT identificador UK "único, minúsculo"
        TEXT nome
        TEXT senha_hash "scrypt com sal"
        TEXT perfil "CIDADAO | PESQUISADOR | ADMINISTRADOR"
        INTEGER ativo
        TEXT criado_em
        TEXT ultimo_acesso
    }

    OCORRENCIA {
        INTEGER id PK
        TEXT protocolo UK "LG-AAAA-XXXXXX"
        TEXT chave_idempotencia UK "evita duplo clique"
        TEXT data_hora_avistamento "informada pelo usuário"
        TEXT data_hora_cadastro
        TEXT estado
        TEXT municipio
        REAL latitude "CHECK -90..90"
        REAL longitude "CHECK -180..180"
        REAL precisao_metros "do GPS"
        TEXT origem_localizacao "GPS | MAPA | REGIAO | IMPORTADA"
        REAL profundidade "nulo quando não informado"
        TEXT habitat
        INTEGER quantidade_observada "CHECK > 0"
        TEXT descricao
        TEXT origem_registro
        TEXT tipo_dado "REAL | IMPORTADO | DEMO"
        TEXT status "PENDENTE | CONFIRMADO | ..."
        INTEGER fonte_dados_id FK
        INTEGER autoriza_publicar_imagem
        TEXT contato_hash "SHA-256, nunca o contato"
        TEXT data_primeira_decisao "base do tempo de revisão"
    }

    IMAGEM {
        INTEGER id PK
        INTEGER ocorrencia_id FK "ON DELETE CASCADE"
        TEXT identificador_arquivo UK "UUID gerado pelo sistema"
        TEXT nome_original_sanitizado
        TEXT hash_sha256 "detecta reenvio"
        TEXT formato
        INTEGER largura
        INTEGER altura
        INTEGER tamanho_bytes
        INTEGER exif_removido
        TEXT fonte
        TEXT licenca
        TEXT criado_em
    }

    PREDICAO {
        INTEGER id PK
        INTEGER ocorrencia_id FK "ON DELETE CASCADE"
        INTEGER imagem_id FK
        TEXT modelo
        TEXT versao "rastreabilidade"
        TEXT classe
        REAL score "CHECK 0..1"
        REAL tempo_inferencia_ms
        TEXT detalhes "JSON: limiares, qualidade"
        TEXT criado_em
    }

    VALIDACAO {
        INTEGER id PK
        INTEGER ocorrencia_id FK "ON DELETE CASCADE"
        INTEGER avaliador_id FK "ON DELETE RESTRICT"
        TEXT decisao
        TEXT justificativa "obrigatória"
        TEXT status_anterior
        TEXT status_novo
        TEXT data_validacao
    }

    LOG_AUDITORIA {
        INTEGER id PK
        INTEGER usuario_id FK
        TEXT entidade
        TEXT entidade_id
        TEXT acao
        TEXT data_hora
        TEXT detalhes "JSON"
    }

    FONTE_DADOS {
        INTEGER id PK
        TEXT nome
        TEXT url
        TEXT data_importacao
        TEXT licenca
        TEXT tipo_fonte
        TEXT observacoes
    }
```

Além dessas, a tabela `evento_requisicao` (sem relacionamento) sustenta a
limitação de envios por sessão.

**Índices** (15 no total): status, estado, município, tipo de dado, datas de
avistamento e cadastro, par (latitude, longitude), ocorrência e hash em
`imagem`, ocorrência e versão em `predicao`, ocorrência e data em `validacao`,
entidade em `log_auditoria` e a chave composta de `evento_requisicao`.

---

## 5. Fluxo de validação

```mermaid
stateDiagram-v2
    [*] --> PENDENTE : cadastro pelo cidadão

    PENDENTE --> CONFIRMADO : confirmar + justificativa
    PENDENTE --> REJEITADO : rejeitar + justificativa
    PENDENTE --> INCONCLUSIVO : marcar inconclusiva
    PENDENTE --> AGUARDANDO_INFO : solicitar informações

    AGUARDANDO_INFO --> CONFIRMADO : confirmar
    AGUARDANDO_INFO --> REJEITADO : rejeitar
    AGUARDANDO_INFO --> INCONCLUSIVO : inconclusiva

    INCONCLUSIVO --> CONFIRMADO : reanálise
    INCONCLUSIVO --> REJEITADO : reanálise
    CONFIRMADO --> REJEITADO : revisão de decisão
    REJEITADO --> CONFIRMADO : revisão de decisão

    note right of PENDENTE
        Status inicial de todo registro,
        independentemente do score da IA.
    end note

    note right of CONFIRMADO
        A primeira transição para um estado
        final grava data_primeira_decisao,
        que é a base do tempo de revisão.
        Decisões posteriores não a sobrescrevem.
    end note
```

Toda transição exige: sessão autenticada com a permissão
`VALIDAR_OCORRENCIA`, justificativa com no mínimo 10 caracteres, e grava
simultaneamente — na mesma transação — o registro em `validacao`, a mudança em
`ocorrencia` e o evento em `log_auditoria`.

---

## 6. Atualização dos dashboards

```mermaid
sequenceDiagram
    actor C as Cidadão
    participant UI as Portal (Streamlit)
    participant SA as ServicoAvistamentos
    participant IA as ServicoInferencia
    participant DB as SQLite
    actor P as Pesquisador
    participant PV as ServicoValidacao
    participant Q as queries (SQL)

    C->>UI: envia foto
    UI->>IA: classificar(bytes)
    IA-->>UI: classe, score, versão do modelo
    C->>UI: autoriza GPS / marca no mapa
    C->>UI: confirmar avistamento
    UI->>SA: registrar(dados)

    SA->>DB: BEGIN IMMEDIATE
    SA->>DB: INSERT ocorrencia (status=PENDENTE)
    SA->>DB: INSERT imagem
    SA->>DB: INSERT predicao
    SA->>DB: INSERT log_auditoria
    SA->>DB: COMMIT
    SA->>DB: SELECT por protocolo (confirmação)
    DB-->>SA: ocorrência gravada
    SA-->>UI: protocolo + status
    UI-->>C: "Avistamento registrado!" + protocolo

    P->>UI: abre painel de validação
    UI->>Q: fila_operacional(filtros)
    Q->>DB: SELECT com filtros
    DB-->>Q: linhas
    Q-->>UI: fila ordenada (pendentes primeiro)

    P->>UI: confirmar + justificativa
    UI->>PV: decidir(...)
    PV->>PV: exigir(permissão)
    PV->>DB: BEGIN
    PV->>DB: INSERT validacao
    PV->>DB: UPDATE ocorrencia (status, data_primeira_decisao)
    PV->>DB: INSERT log_auditoria
    PV->>DB: COMMIT
    PV->>DB: SELECT (confirmação da mudança)
    PV-->>UI: status anterior → novo

    Note over UI,Q: Nenhuma consulta de leitura é cacheada.<br/>Cada carregamento de página lê o banco,<br/>então KPIs, mapa e gráficos já refletem a decisão.

    UI->>Q: kpis_gerais(filtros)
    Q->>DB: agregações SQL
    DB-->>Q: contagens atualizadas
    Q-->>UI: indicadores novos
```

---

## 7. Decisões de arquitetura e seus motivos

| Decisão | Alternativa descartada | Por quê |
| --- | --- | --- |
| Serviços independentes da interface | Lógica dentro das páginas Streamlit | Permite testar o fluxo completo sem navegador — 569 testes rodam em ~5 s |
| SQL explícito em `queries.py` | ORM | Modelagem e consultas ficam auditáveis e evidenciam a disciplina de banco; as agregações são legíveis |
| Transação única por operação | Gravações sequenciais | Uma falha no meio não deixa ocorrência sem imagem nem arquivo órfão |
| Chave de idempotência derivada do conteúdo | Bloqueio de botão no front-end | Resiste a recarregar a página, não só ao duplo clique |
| Classificação (CNN) em vez de detecção (YOLO) | YOLO | Base de imagens limitada; um detector com poucas anotações de caixa seria pior e sugeriria capacidade que não existe |
| Três respostas da IA | Binária | A faixa intermediária existe de verdade; forçá-la a uma decisão produz erro silencioso |
| `SEM_MODELO` como estado de primeira classe | Fallback silencioso | Interface honesta: o usuário sabe que não houve análise automática |
| Coordenada pública arredondada em SQL | Arredondamento na interface | A coordenada precisa não sai do banco para a camada pública |
| Nenhum cache nas consultas de leitura | `st.cache_data` | Garante que um registro novo apareça na consulta seguinte, sem invalidação manual |
| Conexão por thread | Conexão global | O Streamlit usa um pool de threads e o SQLite não compartilha conexão entre elas por padrão |
| Rate limit em tabela | Em memória | Estado de sessão do Streamlit é reconstruído com facilidade; em memória seria contornável recarregando |
| Demonstração sem predição de IA | Scores sintéticos | Score fabricado é resultado de modelo inventado |
| Tema escuro com paletas revalidadas | Inverter o tema claro | Painel é lido em ambiente escuro; a inversão falha na faixa de luminosidade, então os passos foram refeitos e verificados contra a nova superfície |
| Blocos do painel em HTML/SVG | Um gráfico por número | Bloco de número, barra e medidor não precisam de biblioteca de gráficos, e assim ficam testáveis sem navegador |
| HTML normalizado antes do `st.markdown` | Escrever a marcação direto | O Streamlit roda Markdown antes de liberar o HTML: recuo de 4 espaços vira bloco de código e linha em branco encerra o bloco. Normalizar no centro resolve de uma vez, e um teste varre o código |
| `app/paginas/` em vez de `app/pages/` | Nome padrão | `st.navigation` com um diretório `pages/` ao lado do arquivo de entrada gera aviso de comportamento indeterminado |
| Ilustração em SVG gerado por código | Imagem baixada da internet | Nenhuma questão de licença, o desenho segue a paleta do projeto e a geometria fica testável (`tests/test_ilustracoes.py`) |
| Fotografias buscadas em tempo de execução | Cópias no repositório | Não redistribuímos arquivos de terceiros, a licença é lida da fonte na hora e o acervo melhora sozinho; sem internet a seção se declara indisponível |
| Lista de vídeos vazia por padrão | Links embutidos no código | Um endereço embutido é uma afirmação que ninguém conferiu; o grupo preenche `data/conteudo_educativo.json` |
| Batimetria como camada padrão do mapa | Mapa de ruas | Em um projeto marinho, plataforma continental e profundidade explicam a distribuição; a camada de ruas continua disponível |
| Cache apenas na galeria de fotos | Cache nas consultas ao banco | A galeria é uma chamada externa lenta e imutável por uma hora; os dados do banco precisam refletir o registro novo imediatamente |

---

## 8. Estrutura de diretórios

```text
lionguard-ai/
├── app/                      interface Streamlit
│   ├── main.py               roteador e navegação por perfil
│   ├── paginas/              11 páginas (6 públicas, 5 restritas)
│   ├── components/           componentes reutilizáveis (board, mapas, mídia, gráficos)
│   └── styles/               tema escuro, normalizador de HTML e ilustrações em SVG
├── src/
│   ├── ai/                   preprocessing · inference · train · evaluate
│   ├── data/                 dataset · demo_seed · importers · galeria · conteudo
│   ├── database/             schema · connection · models · repositories · queries
│   ├── services/             sightings · geolocation · image_storage · validation · analytics · spatial
│   ├── security/             auth · permissions · uploads · rate_limit · sanitize
│   └── config.py             configuração por variáveis de ambiente
├── data/                     raw · processed · images · banco SQLite
├── models/                   modelo exportado + model_card.json
├── reports/                  métricas, evidências e resultado dos testes
├── scripts/                  CLIs de dataset, treino, avaliação, evidências e diagnóstico
├── tests/                    11 arquivos de teste (569 casos)
├── docs/                     esta documentação e o PDF da entrega
├── requirements.txt          dependências da aplicação
└── requirements-treino.txt   dependências extras para treinar
```
