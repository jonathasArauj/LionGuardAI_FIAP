# 🐠 LionGuard AI

**Detecção precoce e monitoramento colaborativo do peixe-leão no litoral brasileiro**

Global Solution 2026.2 — FIAP · Desafio **CitizenTech: Tecnologia centrada no cidadão**

---
> - **Integrantes:** Jonathas Martins de Araujo (RM 574051), Carlos Magno Barcelos (RM 569944), Lauren Cota (RM 569789) — **confirmar grafias e números antes da entrega**
> - **Turma:** `B`
> - **Link do vídeo demonstrativo (YouTube, "Não listado"):** ``


---


## Modelo de IA incluído — versão experimental (não validada)

Este ZIP inclui o arquivo real `models/lionguard_experimental_icmbio.pt` e
`models/model_card.json`, **treinados de fato em CPU** com uma CNN pequena.
A base contém somente **8 exemplos positivos** (4 recortes do plano ICMBio 2015 e as 4 fotografias enviadas pelo usuário) **e 6 recortes negativos** sem peixe-leão visível, que reproduz
fotografias de outras fontes. Aumentação de dados não cria fotografias
independentes. **Não há conjunto de teste confiável, nem métricas científicas
de desempenho.** As quatro fotos enviadas foram incorporadas ao treino desta versão. Os originais estão em `data/amostras_usuario/peixe_leao/`, para uso acadêmico privado; confirme licença/autoria antes de eventual publicação.

A classificação usa limiares conservadores (positivo acima de 99,5%;
negativo abaixo de 5%; demais resultados inconclusivos). Isso **não garante**
exatidão — o score não é calibrado e o modelo pode errar até com score alto.
Todo registro continua pendente de confirmação humana. **Não usar como sistema
ambiental de produção.**

O programa original de treino com MobileNetV3/ONNX continua disponível para
quando houver um dataset maior e devidamente licenciado. Esta CNN exploratória
foi criada separadamente para não simular a existência de um modelo validado.

**Para iniciar com o modelo incluído:** `pip install -r requirements.txt` e
`python -m streamlit run app/main.py`. Este modelo usa TorchScript/PyTorch;
portanto, `torch` foi incluído nas dependências da aplicação.

**Para reproduzir o treino exploratório** (exige o PDF original enviado):

```bash
pip install -r requirements-modelo-experimental.txt
python scripts/treinar_modelo_experimental_pdf.py \
  --pdf /caminho/plano_emergencial_peixe-leao_resex_arraial_do_cabo_2015.pdf \
  --positivos data/amostras_usuario/peixe_leao \
  --epocas 20 --aumentacoes 4 --lote 12
```

**Para ampliar o treino com fotos JPG/PNG autorizadas** use `--positivos`
(apenas peixe-leão) e `--negativos` (preferencialmente outros peixes).
Separe observações diferentes no treino e no teste antes de produzir métricas.
Confira `docs/modelo_experimental.md` e `reports/treino_experimental_icmbio.json`.

## O problema

Em **14 de novembro de 2026**, o peixe-leão (*Pterois volitans*) foi registrado
pela primeira vez no litoral do Espírito Santo, na Ilha Escalvada, em Guarapari:
um indivíduo de cerca de 15 cm, a 9,4 metros de profundidade. Quem registrou foi
uma equipe de **mergulho recreativo**, que comunicou o Iema por rede social e,
depois, oficialmente.

Esse caminho funcionou — mas é frágil. Depende de a pessoa saber a quem
recorrer, a informação chega em formato livre (um vídeo, uma mensagem, uma foto
sem coordenada) e não se acumula em uma base consultável. O resultado é que
**avistamentos viram notícia, não dado**.

O peixe-leão é espécie invasora no Atlântico: tem poucos predadores naturais,
reproduz-se com rapidez e consome peixes juvenis, pressionando recifes, pesca
artesanal e turismo. O primeiro registro no Brasil é de **2014**; desde **2020**
os registros se tornaram frequentes, e na Bahia já são pelo menos **dez
municípios**. O Plano Emergencial do ICMBio reconhece que métodos padronizados
de monitoramento têm **baixa probabilidade de detectar** a espécie no estágio
inicial da invasão — exatamente quando detectar importa mais.

**O que o LionGuard AI faz:** oferece um caminho de **menos de um minuto e sem
cadastro** para qualquer pessoa transformar um avistamento em registro
estruturado — foto, coordenada, data, análise preliminar por IA e trilha de
validação — e um painel único para pesquisadores acompanharem, validarem e
analisarem esses dados.

## Objetivos

1. Reduzir o atrito entre ver e registrar: foto → IA → GPS → confirmação, em
   quatro toques;
2. produzir **dado estruturado e auditável**, com procedência explícita;
3. apoiar a análise com indicadores, mapa e agrupamento espacial;
4. manter a decisão final **humana**, com justificativa registrada;
5. ser honesto sobre incerteza — da identificação automática ao viés de
   observação.

## Público beneficiado

| Ator | Papel | Benefício |
| --- | --- | --- |
| Banhistas, mergulhadores, pescadores | registram avistamentos | caminho claro, sem burocracia, com orientação de segurança |
| Operadoras de mergulho | registro sistemático dos pontos visitados | protocolo e histórico das próprias observações |
| Pesquisadores e órgãos ambientais | validam e analisam | base organizada, com procedência e qualidade medida |
| Gestão municipal e estadual | consome indicadores | priorização de onde capacitar e monitorar |
| Comunidade pesqueira | beneficiária indireta | resposta mais rápida reduz impacto no estoque |

---

## Como executar

**Requer Python 3.11 ou superior** (o código usa `enum.StrEnum`, do 3.11).

<details open>
<summary><b>Com venv</b> (padrão)</summary>

```bash
# 1. ambiente
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. configuração
cp .env.example .env            # defina LIONGUARD_ADMIN_PASS e LIONGUARD_PESQ_PASS

# 3. dados de demonstração (para os painéis não ficarem vazios)
python scripts/semear_demonstracao.py --quantidade 150

# 4. executar
python -m streamlit run app/main.py      # abre em http://localhost:8501
```
</details>

<details>
<summary><b>Com Anaconda / Miniconda</b></summary>

```bash
conda env create -f environment.yml
conda activate lionguard

cp .env.example .env
python scripts/semear_demonstracao.py --quantidade 150
python -m streamlit run app/main.py
```

**Não instale as dependências no ambiente `base`.** Misturar pacotes do conda
com pacotes do pip no mesmo ambiente produz pares de versões incompatíveis — o
sintoma típico é um `ImportError` dentro do próprio Streamlit (por exemplo,
`cannot import name 'DEFAULT_EXCLUDED_CONTENT_TYPES' from
'starlette.middleware.gzip'`). O `environment.yml` cria um ambiente separado e
resolve tudo pelo pip, de uma vez só.

Se o `base` do conda estiver ativo junto com outro ambiente, ele pode ganhar a
frente do `PATH`. Confira antes de rodar:

```bash
which python
python -c "import sys, streamlit; print(sys.executable, streamlit.__version__)"
```
</details>

Em qualquer um dos dois, prefira `python -m streamlit` a `streamlit`: assim o
módulo vem do interpretador ativo, e não do primeiro binário encontrado no
`PATH`.

Sem as senhas no `.env`, uma senha aleatória é gerada para `admin` e
`pesquisador` na primeira execução e **impressa no terminal** — anote, porque
não é exibida de novo. Nenhuma credencial está escrita no código.

### Verificação

```bash
python scripts/rodar_testes.py       # 569 testes + relatório em reports/
python scripts/diagnostico.py        # critérios de aceite, um por um
python scripts/gerar_evidencias.py   # fluxo ponta a ponta sem interface
```

### Treinar o modelo (opcional, exige internet)

```bash
pip install -r requirements-treino.txt
python scripts/baixar_dados.py --limite 300    # iNaturalist, só licenças CC
python scripts/preparar_dataset.py             # valida, deduplica, divide
python scripts/treinar_modelo.py               # MobileNetV3, exporta ONNX
python scripts/avaliar_modelo.py               # gera reports/metricas_modelo.json
```

Enquanto não houver modelo publicado, **a plataforma funciona**: o registro
opera normalmente e as ocorrências entram com estado `SEM_MODELO`, seguindo para
validação humana. O painel de IA informa a indisponibilidade em vez de exibir
métricas de exemplo.

> **GPS no celular exige HTTPS.** O navegador só libera a geolocalização em
> contexto seguro. Em `http://IP_LOCAL` o botão de GPS não funciona e o fluxo cai
> no mapa manual. Para testar o GPS, use um túnel HTTPS — ver
> [`docs/deploy.md`](docs/deploy.md).

---

## Tecnologias e sua justificativa

| Tecnologia | Onde | Por que esta |
| --- | --- | --- |
| **Python 3.11+** | tudo | linguagem do curso; ecossistema de dados e visão computacional |
| **Streamlit** | interface | entrega uma aplicação interativa e responsiva sem front-end separado, viável no prazo de uma POC |
| **SQLite + SQL explícito** | persistência | modelagem e consultas auditáveis, adequadas à disciplina de banco; migração para PostgreSQL documentada |
| **PyTorch + torchvision** | treinamento | MobileNetV3 pré-treinada; *transfer learning* é o que viabiliza aprender com poucas centenas de imagens |
| **ONNX Runtime** | inferência | roda o modelo sem instalar PyTorch em produção (≈2 GB menos de dependência) |
| **scikit-learn** | DBSCAN e métricas | DBSCAN com métrica haversine; métricas de classificação padronizadas |
| **Plotly** | gráficos | interatividade nativa no Streamlit, com controle fino de layout |
| **Folium / Leaflet** | mapas | agrupamento de marcadores, pop-ups e clique para marcar ponto |
| **streamlit-js-eval** | GPS | acesso à API de geolocalização do navegador (latitude, longitude, precisão) |
| **Pillow + NumPy** | imagens | validação, remoção de EXIF e pré-processamento |
| **hashlib.scrypt** | senhas | derivação com sal, sem dependência externa |
| **Pytest** | testes | 569 casos cobrindo banco, serviços, segurança, IA e interface |

**Decisão técnica de maior impacto:** usar **classificação (CNN)** em vez de
**detecção (YOLO)**. Com base de imagens limitada, um detector treinado com
poucas anotações de caixa teria desempenho pior e sugeriria uma capacidade que
não existe. A consequência é assumida de forma explícita: o sistema **não**
desenha caixas sobre o peixe nem conta indivíduos automaticamente, e a interface
diz isso.

---

## Arquitetura

Documentação completa, com **seis diagramas Mermaid** (componentes, fluxo do
avistamento, fluxo da IA, modelo entidade-relacionamento, máquina de estados da
validação e sequência de atualização dos dashboards):
**[`docs/arquitetura.md`](docs/arquitetura.md)**

```text
Cidadão → fotografia → validação da imagem → IA → localização →
confirmação → banco de dados → dashboards → validação humana
```

A interface nunca fala com o banco: chama serviços, que usam repositórios. É
isso que permite testar o fluxo completo sem navegador — os 569 testes rodam em
cerca de 5 segundos.

```text
lionguard-ai/
├── app/          interface Streamlit (main.py, paginas/, components/, styles/)
├── src/          código-fonte: ai/ · data/ · database/ · services/ · security/
├── assets/       recursos visuais estáticos
├── config/       guia da configuração (.env.example, .streamlit/, src/config.py)
├── data/         raw/ · processed/ · images/ · banco SQLite (não versionados)
├── document/     PDF único da entrega (+ other/ para complementares)
├── docs/         documentação técnica: arquitetura, deploy, testes, limitações…
├── models/       modelo exportado + model_card.json
├── reports/      relatórios gerados por execução (testes, evidências, métricas)
├── scripts/      CLIs de dataset, treino, avaliação, evidências, diagnóstico
└── tests/        11 arquivos, 569 casos
```

Cada pasta tem seu próprio `README.md` explicando o conteúdo e como ele é
produzido.

> **Sobre o template da FIAP.** A estrutura acima segue o padrão do template
> oficial (`assets`, `config`, `document`, `scripts`, `src` e um `README.md` por
> pasta), com as pastas adicionais que este projeto precisa (`app`, `data`,
> `docs`, `models`, `reports`, `tests`). **Antes de entregar, clone
> [o template](https://github.com/fiap-tutoria/FIAP-PORTFOLIO-AI) e confira os
> nomes das pastas e o modelo de `README.md` de cada uma** — o projeto foi
> montado sem acesso de rede ao repositório do template, então essa conferência
> precisa ser feita manualmente. Ajustar nomes de pasta não afeta o código: os
> únicos caminhos referenciados em código são `app/`, `src/`, `data/`,
> `models/`, `reports/`, `document/` e `docs/`.

Dois desvios deliberados, ambos documentados:
`app/paginas/` em vez de `app/pages/` (o Streamlit reserva esse nome e avisa
sobre conflito com `st.navigation`), e o PDF em `document/` enquanto a
documentação técnica em Markdown fica em `docs/`.

---

## Funcionalidades

### Portal do cidadão (público, sem login)

- **Registrar avistamento** em quatro passos, com câmera ou galeria;
- **análise preliminar por IA**, com três respostas possíveis e ressalva
  explícita;
- **GPS do aparelho** com precisão em metros, e a pergunta "você está no local
  onde viu o peixe?" — a posição atual nunca é assumida como local do
  avistamento;
- **fallback obrigatório**: ponto no mapa ou região aproximada, se o GPS falhar
  ou for negado;
- **coordenadas do EXIF** só são usadas com autorização explícita; os metadados
  são removidos da imagem gravada de qualquer forma;
- **protocolo** único para acompanhamento, com indicador de progresso em cinco
  etapas durante o registro;
- mapa público, indicadores abertos e conteúdo educativo sobre a espécie.

### Dois níveis de acesso

A plataforma funciona sem login e revela mais para quem entra. Os três perfis
abaixo não são rótulos de tela: cada um corresponde a um conjunto de permissões
declarado em `src/security/permissions.py` e verificado **dentro dos serviços**,
antes de qualquer leitura ou gravação — esconder um botão não é controle de
acesso.

| | Visitante (sem login) | Pesquisador | Administrador |
| --- | :---: | :---: | :---: |
| Registrar avistamento | ✅ | ✅ | ✅ |
| Consultar protocolo | ✅ | ✅ | ✅ |
| Mapa com posição aproximada (~1 km) | ✅ | ✅ | ✅ |
| Painel público de indicadores | ✅ | ✅ | ✅ |
| Coordenada precisa | — | ✅ | ✅ |
| Painel geral, científico e de IA | — | ✅ | ✅ |
| Validar ocorrências | — | ✅ | ✅ |
| Exportar CSV | — | ✅ | ✅ |
| Exportar coordenadas precisas | — | — | ✅ |
| Contas, auditoria e dados de demonstração | — | — | ✅ |

A tela `Acesso de pesquisador` monta esses cartões a partir da própria matriz
de permissões: se a matriz mudar, a tela muda junto, e não há como prometer um
acesso que o controle não conceda.

### Interface e conteúdo visual

A página inicial é informativa e a ação continua no centro: o botão de registrar
aparece logo abaixo do topo e se repete ao fim de cada bloco de orientação.

| Recurso | Como é produzido |
| --- | --- |
| **Ilustração do peixe-leão** | SVG gerado por código em `app/styles/ilustracoes.py` — desenho do próprio projeto, sem questão de licença; acompanha a paleta da identidade |
| **Fotografias reais** | buscadas em tempo de execução no iNaturalist (`src/data/galeria.py`), apenas observações com licença Creative Commons, com autor, licença e link em cada imagem; sem internet, a seção mostra a ilustração e diz que é ilustração |
| **Guia de identificação** | características, itens "não confundir" e perguntas frequentes em `src/data/conteudo.py`, editáveis por `data/conteudo_educativo.json` |
| **Vídeos** | a lista nasce **vazia** de propósito: nenhum endereço é embutido no código. Para exibir o vídeo da entrega, rode `python -c "from src.data.conteudo import gravar_modelo; print(gravar_modelo())"` e preencha `videos` no JSON gerado |
| **Tema escuro verificado** | o painel é escuro porque é lido em ambiente escuro. Não é a inversão do tema claro: as paletas de série e de status foram **refeitas e revalidadas** contra a superfície escura (faixa de luminosidade, croma, daltonismo e contraste). Ver `docs/acessibilidade_cores.md` |
| **Blocos do painel** | blocos de número, barras de proporção e medidor em arco desenhados em HTML/SVG (`app/components/board.py`), sem carregar um gráfico inteiro para mostrar um número — e testáveis sem navegador |
| **Mapas** | quatro camadas de base (batimetria do oceano como padrão, satélite, mapa claro, ruas), agrupamento de marcadores, mapa de calor opcional com aviso de viés de observação, tela cheia, minimapa e régua |

O mapa de calor e as áreas do DBSCAN sempre vêm acompanhados do aviso de que
mostram densidade **de notificações**, não densidade da espécie.

### Área de monitoramento (restrita)

| Painel | Conteúdo |
| --- | --- |
| **Visão geral** | 8 indicadores, 6 gráficos, filtros globais simultâneos |
| **Mapa geográfico** | marcadores por status, agrupamento, pop-ups, legenda, áreas DBSCAN |
| **Análise científica** | distribuição temporal, batimétrica, habitat, horário, qualidade dos dados, análise espacial, exportação CSV |
| **Inteligência artificial** | métricas do conjunto de teste, matriz de confusão, curvas de treino, distribuição de scores, concordância IA × avaliador, rastreamento de inferências |
| **Validação** | fila priorizada, revisão com justificativa obrigatória, histórico auditável, detecção de duplicidades |
| **Administração** | contas, dados de demonstração, importação de fontes externas, auditoria, integridade do armazenamento |

---

## Dados

Quatro categorias, sempre distinguíveis no banco e nos filtros:

| Categoria | `tipo_dado` | Observação |
| --- | --- | --- |
| Registros de usuários | `REAL` | enviados pela plataforma |
| Importados de fontes documentadas | `IMPORTADO` | GBIF, iNaturalist, com fonte, URL e licença gravadas; **status pendente** — base externa não é validação nossa |
| Revisados | qualquer | após decisão humana, com histórico |
| Demonstração | `DEMO` | gerados pelo sistema, rotulados, **sem imagem e sem predição de IA**, removíveis por filtro |

**Imagens de treinamento:** baixadas do iNaturalist apenas com licença Creative
Commons declarada. O manifesto (`data/raw/manifesto.csv`) guarda fonte, URL,
licença, autor, espécie, identificador da observação, data de aquisição e hash
de cada arquivo. Arquivos corrompidos e duplicatas exatas são removidos.

**Divisão sem vazamento:** a separação treino/validação/teste é feita **por
observação**, não por imagem — duas fotos do mesmo peixe no mesmo dia são quase
idênticas e, separadas entre treino e teste, inflariam as métricas. O script
verifica isso explicitamente e falha se detectar vazamento.

**Qualidade e viés:** mais registros aparecem onde há mais mergulhadores e sinal
de celular. **Ausência de registro não é ausência da espécie.** Campos
opcionais ausentes são descartados das estatísticas, nunca zerados nem
atribuídos a uma categoria inventada, e cada indicador informa o `n` que o
sustenta.

---

## Inteligência artificial

| Item | Escolha |
| --- | --- |
| Arquitetura | MobileNetV3-Large, pré-treinada no ImageNet |
| Abordagem | classificação binária com *transfer learning* |
| Treinamento | duas fases (classificador, depois ajuste fino), early stopping por F1 de validação, pesos de classe para base desbalanceada, semente fixa |
| Pré-processamento | letterbox 224×224 (preserva proporção), normalização ImageNet — **o mesmo código** no treino e na inferência |
| Decisão | score ≥ 0,70 → possível peixe-leão · 0,45–0,70 → **inconclusivo** · < 0,45 → não identificado |
| Salvaguarda | positivo em imagem desfocada ou escura é rebaixado para inconclusivo |
| Formato | ONNX (inferência) + TorchScript (alternativa) |
| Rastreabilidade | toda predição grava modelo, versão, score e tempo de inferência |

**Compromissos de honestidade, implementados em código:**

- não existe caminho que produza classe ou score **sem executar o modelo**;
- sem modelo publicado, o estado é `SEM_MODELO`; erro de inferência é `ERRO` —
  nos dois casos o avistamento é gravado e segue para revisão humana;
- o painel de IA lê métricas **apenas** de `reports/metricas_modelo.json`,
  gerado pelo script de avaliação. Sem esse arquivo, nenhuma métrica aparece;
- o score é apresentado com a ressalva de que **não é probabilidade
  calibrada**;
- "não identificado" nunca é apresentado como "a espécie não está na imagem".

---

## Banco de dados

**8 tabelas, 15 índices**, com chaves estrangeiras ativas, constraints de
domínio (`CHECK`) e unicidade onde o domínio exige. Modelo completo em
[`docs/arquitetura.md`](docs/arquitetura.md).

`usuario` · `ocorrencia` · `imagem` · `predicao` · `validacao` ·
`log_auditoria` · `fonte_dados` · `evento_requisicao`

**Garantias implementadas:**

- **atomicidade** — ocorrência, imagem, predição e auditoria na mesma transação;
  falha em qualquer passo não deixa registro parcial nem arquivo órfão;
- **idempotência** — chave derivada de conteúdo da foto + data + coordenada +
  sessão; duplo clique ou recarregar a página devolve o mesmo protocolo;
- **sucesso verificado** — o serviço relê a ocorrência pelo protocolo **depois**
  do commit, e só então declara sucesso;
- **status inicial sempre `PENDENTE`**, independentemente do score;
- **o banco não é recriado** a cada inicialização (`CREATE TABLE IF NOT
  EXISTS`);
- `data_primeira_decisao` é gravada só na primeira decisão final — é a base do
  indicador de tempo de revisão.

Consultas analíticas reutilizáveis em `src/database/queries.py`: contagem por
status, total por estado e município, evolução mensal, distribuição por origem,
tempo de revisão, registros recentes, dados geográficos e estatísticas de
completude. **Nenhum indicador é fixo**: todos vêm de agregação SQL, com a mesma
cláusula `WHERE` aplicada a cards, gráficos e tabelas.

---

## Segurança e privacidade

| Camada | Implementação |
| --- | --- |
| Senhas | `hashlib.scrypt`, sal de 16 bytes por usuário, comparação em tempo constante |
| Autenticação | registro público **sem login**; painéis exigem sessão com expiração |
| Autorização | matriz explícita de permissões por perfil, verificada **no serviço** — esconder botão não é controle de acesso |
| Upload | quatro camadas: tamanho → assinatura binária → decodificação real → limites de dimensão |
| EXIF | lido para informar o usuário, **removido** antes de gravar; coordenadas só usadas com autorização |
| Caminhos | nome do arquivo gerado pela aplicação (UUID); travessia de diretório recusada |
| Coordenadas | mapa público arredondado em ~1 km; precisão exata exige perfil autorizado |
| Contato | guardado apenas como hash SHA-256 — nunca o contato em si; não entra na exportação |
| Abuso | limite de envios por sessão, persistido em tabela; detecção de imagem repetida por hash |
| Auditoria | cadastros, decisões, logins, importações e operações administrativas |
| Segredos | variáveis de ambiente; `.env` no `.gitignore` |

**Segurança ambiental:** a plataforma **não** orienta captura, perseguição ou
manuseio do animal. Toda tela de registro traz o aviso de manter distância, não
tocar e procurar atendimento médico em caso de acidente. Manejo é atribuição dos
órgãos competentes e de profissionais autorizados.

---

## Testes e resultados

```text
569 testes · 0 falhas · ~5 s
```

| Arquivo | Casos | Foco |
| --- | --- | --- |
| `test_database.py` | 30 | esquema, constraints, transações, persistência |
| `test_sightings.py` | 28 | registro, idempotência, validações, privacidade |
| `test_geolocation.py` | 58 | coordenadas, área monitorada, referências, precisão |
| `test_inference.py` | 45 | pré-processamento, limiares, indisponibilidade, métricas, dataset |
| `test_security.py` | 75 | senhas, permissões, upload, EXIF, saneamento, limite |
| `test_dashboards.py` | 50 | KPIs, filtros, demonstração, atualização, DBSCAN, exportação |

Plano completo, incluindo o **roteiro manual** de 47 itens (câmera, GPS, toque,
acessibilidade): [`docs/testes.md`](docs/testes.md).

**Evidências geradas por execução real**, não transcritas à mão:

| Arquivo | Conteúdo |
| --- | --- |
| `reports/testes_execucao.md` | saída do Pytest, com data, versão do Python e contagem por arquivo |
| `reports/evidencias_execucao.md` | fluxo ponta a ponta: esquema, segurança, cadastro, validação, indicadores antes/depois, DBSCAN, persistência |
| `reports/diagnostico_criterios.md` | critérios de aceite, classificados em OK / MANUAL / PENDENTE / FALHA |
| `reports/metricas_modelo.json` | métricas do conjunto de teste (após treinar o modelo) |
| `reports/historico_treinamento.json` | curvas por época (após treinar o modelo) |

---

## ODS e medição de impacto

**ODS 14 — Vida na Água.** Espécies exóticas invasoras são vetor direto de
perda de biodiversidade marinha, e a resposta depende de informação cedo e
organizada. Contribuições secundárias: **ODS 15** (meta compartilhada de
controle de invasoras), **ODS 11** (participação cidadã em problema ambiental
local) e **ODS 17** (arquitetura prevê intercâmbio com órgãos e bases abertas).

Indicadores propostos, todos calculáveis a partir do próprio banco:

| Indicador | O que mede |
| --- | --- |
| Tempo entre avistamento e cadastro | agilidade do canal |
| Tempo mediano de revisão | capacidade de resposta |
| Nº de municípios com registro | cobertura territorial |
| % de registros com coordenada precisa | qualidade do dado |
| % validados | maturidade operacional |
| Concordância IA × avaliador | utilidade do modelo |
| Novas áreas detectadas por período | detecção precoce |

**Ressalva que faz parte do indicador:** aumento no número de registros mede
**adoção da plataforma**, não necessariamente aumento da população da espécie.

---

## Limitações

Lista completa e honesta em **[`docs/limitacoes.md`](docs/limitacoes.md)**. Em
resumo:

- é **protótipo acadêmico**, sem homologação, parceria ou vínculo com órgão
  ambiental, e **não substitui** o canal oficial de ocorrências;
- a identificação automática é **preliminar**; o score não é probabilidade
  calibrada; o classificador **não** localiza nem conta indivíduos;
- o GPS exige HTTPS; há sempre o caminho manual;
- dados de ciência cidadã têm **viés de observação**;
- persistência **não garantida** em hospedagem gratuita com disco efêmero;
- o limite de envios é por sessão de navegador — uma operação real exigiria
  limitação na borda;
- sem notificações, sem internacionalização, sem teste com leitor de tela, sem
  teste de intrusão, sem teste de carga.

---

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [`docs/arquitetura.md`](docs/arquitetura.md) | componentes, 6 diagramas Mermaid, modelo de dados, decisões técnicas |
| [`docs/deploy.md`](docs/deploy.md) | execução local, HTTPS para GPS, treinamento, migração para PostgreSQL, custos |
| [`docs/testes.md`](docs/testes.md) | cobertura automatizada e roteiro manual de 47 itens |
| [`docs/limitacoes.md`](docs/limitacoes.md) | o que o protótipo não faz, e por quê |
| [`docs/acessibilidade_cores.md`](docs/acessibilidade_cores.md) | validação de contraste e daltonismo da paleta |
| [`docs/roteiro_video.md`](docs/roteiro_video.md) | storyboard do vídeo de 5 minutos |

---

## Referências

- **ICMBio** — *Plano Emergencial de Monitoramento e Erradicação do Peixe-leão*
  (Resex Arraial do Cabo, 2015).
  [PDF](https://www.gov.br/icmbio/pt-br/assuntos/biodiversidade/manejo-de-especies-exoticas-invasoras/guias-e-materiais-orientadores/materias-diversos/plano_emergencial_peixe-leao_resex_arraial_do_cabo_2015.pdf)
- **ICMBio** — *Guia Estratégico do Peixe-leão*.
  [PDF](https://www.icmbio.gov.br/cbc/images/stories/Guia_Estrat%C3%A9gico_Peixe-Le%C3%A3o_2.pdf)
- **ICMBio** — portal institucional. <https://www.gov.br/icmbio/>
- **Iema (ES)** — primeiro registro do peixe-leão no Espírito Santo.
  <https://iema.es.gov.br/peixe-leao-e-registrado-pela-primeira-vez-no-espirito-santo-na-ilha-escavada-em-guarapari>
- Reportagens sobre o registro na Ilha Escalvada (14/11/2026), a situação na
  Bahia e o plano municipal de Porto Seguro, consultadas em novembro de 2026.
- **GBIF** — Global Biodiversity Information Facility. <https://www.gbif.org/>
- **iNaturalist** — <https://www.inaturalist.org/>
- **ONU** — Objetivo de Desenvolvimento Sustentável 14.
  <https://brasil.un.org/pt-br/sdgs/14>
- **FIAP** — template oficial do portfólio.
  <https://github.com/fiap-tutoria/FIAP-PORTFOLIO-AI>

---

## Checklist de entrega

- [ ] Confirmar nomes e RMs dos integrantes, preencher a turma no topo deste arquivo
      e na primeira página do PDF;
- [ ] estrutura do repositório conforme o template da FIAP;
- [ ] `README.md` em cada pasta exigida pelo template;
- [ ] repositório **privado**, compartilhado apenas com `fiap-tutoria` e os
      integrantes do grupo (convite válido por 7 dias);
- [ ] PDF único com Introdução, Desenvolvimento, Resultados e Conclusões;
- [ ] códigos no PDF como **texto legível**, não captura de tela;
- [ ] vídeo de até 5 minutos no YouTube como **"Não listado"**;
- [ ] frase **QUERO CONCORRER** no vídeo e no README, se for disputar o pódio;
- [ ] links do vídeo e do repositório no final do PDF;
- [ ] `python scripts/rodar_testes.py` sem falhas;
- [ ] `python scripts/diagnostico.py` revisado, com os itens PENDENTE descritos
      no PDF;
- [ ] nada de `.env` ou credencial versionado;
- [ ] repositório **não alterado** após o prazo da FIAP.

---

**LionGuard AI** — protótipo acadêmico desenvolvido para a Global Solution
2026.2 da FIAP. Não é um sistema oficial do ICMBio nem de qualquer órgão
ambiental, e não possui homologação ou parceria institucional. As identificações
automáticas são preliminares e dependem de validação humana.
