# Roteiro e storyboard do vídeo demonstrativo

Duração máxima: **5 minutos**. Postar no YouTube como **"Não listado"** e
incluir o link no final do PDF da entrega.

> **O vídeo ainda não foi gravado.** Este documento é o roteiro para a
> gravação, não o registro de uma gravação feita.

---

## 0. Preparação antes de gravar

Faça isso **na ordem**, com antecedência:

```bash
# 1. ambiente limpo e dependências
source .venv/bin/activate
pip install -r requirements.txt

# 2. conferir que tudo está no lugar
python scripts/rodar_testes.py        # deve terminar com 0 falhas
python scripts/diagnostico.py         # conferir o que está OK / PENDENTE

# 3. popular os painéis (senão aparecem vazios no vídeo)
python scripts/semear_demonstracao.py --quantidade 150

# 4. se o modelo estiver treinado, confirmar que as métricas existem
ls -la reports/metricas_modelo.json models/model_card.json

# 5. subir a aplicação com HTTPS (necessário para o GPS no celular)
streamlit run app/main.py
npx localtunnel --port 8501           # em outro terminal; use a URL https
```

**Antes de apertar o gravador:**

- [ ] um avistamento real de teste já registrado e **validado**, para mostrar o
      histórico sem gastar tempo;
- [ ] uma foto pronta na galeria do celular (não dependa de improvisar);
- [ ] permissão de localização **ainda não concedida** no navegador, para que o
      pedido apareça na tela durante a gravação;
- [ ] janela do navegador em tela cheia, sem abas pessoais, sem notificações;
- [ ] se for mostrar o celular, prepare espelhamento de tela (QuickTime no
      macOS, scrcpy no Android);
- [ ] zoom do navegador em 110–125%, para o texto ficar legível em vídeo;
- [ ] microfone testado; fale mais devagar do que parece natural.

---

## 1. Storyboard

### 0:00 – 0:30 — Apresentação

**Tela:** página inicial do LionGuard AI, no celular ou em janela estreita.

**Fala:**
> "Somos o grupo **[NOME DO GRUPO]**, da turma **[TURMA]**, da FIAP.
> **QUERO CONCORRER.**
> Este é o **LionGuard AI**: uma plataforma que transforma o avistamento de uma
> espécie invasora em dado estruturado, em menos de um minuto e sem cadastro.
>
> O problema que atacamos é concreto. Em **14 de novembro de 2026**, o
> peixe-leão foi registrado pela primeira vez no Espírito Santo, na Ilha
> Escalvada, em Guarapari. Quem viu foi uma equipe de mergulho recreativo — não
> uma rede oficial de monitoramento."

> Inclua a frase "QUERO CONCORRER" **nos primeiros segundos** e também no
> `README.md` da raiz, se o grupo optar por disputar o pódio. Se não for
> concorrer, apenas omita a frase — o vídeo continua obrigatório.

**Ação de tela:** passar o olho pela home — chamada principal, botão de
registro, indicadores.

---

### 0:30 – 1:00 — Contexto

**Tela:** página "Sobre o peixe-leão".

**Fala:**
> "O peixe-leão é nativo do Índico e do Pacífico. No Atlântico é invasor: tem
> poucos predadores naturais, reproduz-se rápido e come peixes juvenis — o que
> pressiona recifes, pesca artesanal e turismo.
>
> No Brasil, o primeiro registro é de **2014**; desde **2020** os registros se
> tornaram frequentes. Na Bahia já são pelo menos **dez municípios**. E o
> próprio Plano Emergencial do ICMBio reconhece que métodos padronizados de
> monitoramento têm baixa probabilidade de detectar a espécie no início da
> invasão — justamente quando detectar importa mais.
>
> É aí que entra a ciência cidadã: milhares de olhos na água, todos os dias."

**Ação de tela:** rolar a seção "A situação no Brasil" e as fontes citadas.

---

### 1:00 – 2:15 — Registro do avistamento (o núcleo da demonstração)

**Tela:** celular (ou janela estreita), fluxo completo.

**Fala e ações, em paralelo:**

| Tempo | Ação na tela | Fala |
| --- | --- | --- |
| 1:00 | Toque em "Registrar avistamento" | "Sem login, sem cadastro. Quatro passos." |
| 1:10 | Enviar a foto da galeria | "A foto pode vir da câmera ou da galeria. A validação confere a assinatura do arquivo, a integridade e as dimensões — e **remove os metadados EXIF** antes de salvar." |
| 1:25 | Aguardar o resultado da IA | "A imagem passa por uma CNN MobileNetV3 com transfer learning. Três respostas possíveis: possível peixe-leão, não identificado ou **inconclusivo** — e o score aparece junto com a ressalva de que não é probabilidade calibrada." |
| 1:40 | Responder "Sim, estou no local" e autorizar o GPS | "O sistema **pergunta** se você está no local. Ele não assume que a sua posição atual é o lugar onde o peixe foi visto." |
| 1:50 | Mostrar "Localização identificada" com precisão | "Captura latitude, longitude, precisão em metros e horário da leitura. Se você negar a permissão, o registro **não** é bloqueado: marca-se o ponto no mapa." |
| 2:00 | Preencher profundidade e habitat; confirmar | "Todo o resto é opcional. Confirmar." |
| 2:08 | Protocolo na tela | "Protocolo gerado, gravado em transação única, status **pendente de validação**. Nenhum score, por alto que seja, confirma uma ocorrência: isso é decisão humana." |

**Se sobrar tempo (5 s):** tocar "Confirmar" duas vezes e mostrar que o
protocolo é o mesmo — idempotência.

---

### 2:15 – 3:30 — Dashboards e validação

**Tela:** desktop, autenticado como pesquisador.

| Tempo | Ação na tela | Fala |
| --- | --- | --- |
| 2:15 | Login na área de monitoramento | "O registro é público; os painéis são restritos, com permissão verificada no serviço — não só escondendo botões." |
| 2:25 | Visão geral com os 8 indicadores | "Oito indicadores, todos calculados por agregação SQL sobre o banco. Nada fixo no código." |
| 2:35 | Mudar o filtro de período e de estado | "Os filtros valem simultaneamente para cards, gráficos e tabela." |
| 2:45 | Desmarcar "Demonstração" na procedência | "A base distingue quatro procedências. Estes **são dados de demonstração**, rotulados como tal — e o filtro os remove por completo." |
| 2:55 | Mapa: agrupamento, pop-up, legenda | "Mapa com agrupamento de marcadores, legenda explícita e posição **aproximada em cerca de 1 km** no acesso público, para proteger o ponto exato." |
| 3:05 | Ativar áreas DBSCAN | "Agrupamento espacial com DBSCAN e métrica haversine. E a ressalva que precisa estar aqui: concentração de **notificações** não é concentração de peixes." |
| 3:15 | Painel de validação: abrir o registro novo, confirmar com justificativa | "Validação exige justificativa e fica no histórico, com auditoria." |
| 3:25 | Voltar à visão geral | "Indicadores e mapa já refletem a decisão: nenhuma consulta de leitura é cacheada." |

---

### 3:30 – 4:20 — Inteligência artificial e integração entre disciplinas

**Tela:** painel de IA; depois, terminal.

| Tempo | Ação na tela | Fala |
| --- | --- | --- |
| 3:30 | Painel de IA | "Aqui estão acurácia, precisão, revocação, F1 e a matriz de confusão — lidos do arquivo gerado pelo script de avaliação sobre o conjunto de teste." |
| 3:40 | Matriz de confusão e curva por limiar | "A varredura de limiares importa: em detecção precoce, deixar passar uma ocorrência custa mais do que uma checagem extra." |
| 3:48 | Curvas de treinamento | "Perda e métricas por época, em gráficos separados porque as escalas são diferentes." |
| 3:55 | Terminal: `python scripts/rodar_testes.py` | "**569 testes** cobrindo banco, serviços, segurança e IA. Rodando agora." |
| 4:05 | Mostrar o resultado e a integração | "Integramos visão computacional e redes neurais, banco relacional com consultas analíticas, análise exploratória, agrupamento, cibersegurança, sensores via GPS do aparelho, e aplicação interativa — cada uma resolvendo uma parte real do problema." |

> Se o modelo **não** estiver treinado no momento da gravação, mostre o painel
> em estado `SEM_MODELO` e diga a verdade: "o pipeline de treino está pronto e
> documentado; nesta instalação o modelo não está publicado, e o sistema informa
> isso em vez de exibir número inventado". Isso é mais forte do que fingir.

---

### 4:20 – 5:00 — ODS 14 e encerramento

**Tela:** aba "ODS e impacto" da página Sobre o projeto.

**Fala:**
> "O projeto se liga ao **ODS 14 — Vida na Água**, e secundariamente aos ODS
> 15, 11 e 17.
>
> E propomos medir o impacto com indicadores que saem do próprio banco: tempo
> entre avistamento e cadastro, tempo mediano de revisão, número de municípios
> alcançados, percentual de registros com coordenada precisa, taxa de
> concordância entre a IA e o avaliador, e quantas áreas novas foram detectadas
> por período.
>
> Com uma ressalva que faz parte do indicador: mais registros medem adoção da
> plataforma — não necessariamente mais peixes-leão no mar.
>
> O LionGuard AI não substitui o canal oficial. Ele faz uma coisa só, bem:
> transformar o que um mergulhador viu numa segunda-feira em dado que um
> pesquisador consegue usar na terça.
>
> Obrigado."

**Ação de tela final:** voltar à home, com o botão de registro em destaque.

---

## 2. Checklist de gravação

- [ ] "QUERO CONCORRER" nos primeiros segundos (se for concorrer ao pódio);
- [ ] nome do grupo e turma ditos em voz alta;
- [ ] duração **≤ 5:00**;
- [ ] registro demonstrado de ponta a ponta, sem corte durante a gravação;
- [ ] protocolo visível na tela;
- [ ] mapa e dashboards com dados;
- [ ] decisão de validação refletindo nos indicadores;
- [ ] métricas de IA mostradas (ou o estado de indisponibilidade explicado);
- [ ] ODS 14 citado;
- [ ] integração entre disciplinas dita explicitamente;
- [ ] áudio audível, sem notificações na tela;
- [ ] upload no YouTube como **"Não listado"**;
- [ ] link colado no final do PDF e no `README.md`.

---

## 3. Erros a evitar

| Erro | Por quê |
| --- | --- |
| Narrar a arquitetura em vez de mostrar o sistema | A nota recompensa implementação demonstrada |
| Mostrar dados de demonstração sem dizer que são | O vídeo precisa deixar claro o que é real e o que não é |
| Afirmar que a IA "detecta" ou "identifica com certeza" | É identificação **preliminar**, sujeita a validação humana |
| Dizer que há parceria com ICMBio ou Iema | Não há; é protótipo acadêmico |
| Exibir métricas se o modelo não foi avaliado | Métrica inventada é o pior risco da entrega |
| Gravar com o `.env` ou senhas na tela | Vazamento de credencial |
| Estourar os 5 minutos | A regra é eliminatória |
