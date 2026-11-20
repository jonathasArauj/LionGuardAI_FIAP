# Plano e resultados de teste

Duas camadas: **testes automatizados** (Pytest, executados a cada mudança) e
**roteiro manual** (o que só um navegador real pode comprovar — câmera, GPS,
toque). O resultado da última execução automatizada fica em
`reports/testes_execucao.md`, gerado pelo próprio Pytest; nada é transcrito à
mão.

```bash
python scripts/rodar_testes.py       # suíte completa + relatório
python -m pytest -q                  # execução rápida
python -m pytest tests/test_security.py -v
python scripts/gerar_evidencias.py   # fluxo ponta a ponta sem interface
python scripts/diagnostico.py        # critérios de aceite, um por um
```

---

## 1. Cobertura automatizada

| Arquivo | Casos | O que verifica |
| --- | --- | --- |
| `tests/test_database.py` | 30 | esquema, índices, inserções, unicidade, constraints de domínio, integridade referencial, cascata, transação com rollback, transação aninhada, filtros compostos, proteção do `ORDER BY`, detecção de duplicatas, data da primeira decisão, persistência em disco |
| `tests/test_sightings.py` | 28 | formato e unicidade do protocolo, registro completo, status inicial pendente mesmo com score 0,999, registro sem foto e sem IA, idempotência (duplo clique), chave derivada do conteúdo, validações de data/quantidade/profundidade, limpeza de arquivo em falha, hash de contato, consulta por protocolo, persistência |
| `tests/test_geolocation.py` | 58 | validação de coordenadas, caixa envolvente, filtro por distância da costa, distâncias conhecidas, sugestão de município, tabela de referência coerente, cobertura de todas as UFs litorâneas, origem da posição, classificação de precisão, arredondamento público e erro resultante |
| `tests/test_inference.py` | 45 | determinismo do pré-processamento, letterbox, normalização ImageNet, softmax estável, limiares de decisão, rebaixamento por qualidade, estado `SEM_MODELO`, erro de backend tratado, cartão de modelo inválido, reuso do serviço, cálculo de métricas, varredura de limiares, AUC, divisão do dataset sem vazamento |
| `tests/test_security.py` | 75 | hash scrypt com sal, verificação de senha, política mínima, autenticação e usuário inativo, auditoria de falha de login, matriz de permissões por perfil, negação no serviço (não só na interface), validação de upload em quatro camadas, EXIF lido e removido, saneamento de nome, bloqueio de travessia, limite de requisições persistente, proteção da coordenada e da imagem no mapa público |
| `tests/test_dashboards.py` | 50 | KPIs vindos do banco, ausência representada como ausência, mediana do tempo de revisão, filtros aplicados a todas as consultas, separação dos dados de demonstração, atualização após cadastro e após validação, série mensal sem buracos e sem extrapolação, nulos descartados e não zerados, DBSCAN com agrupamentos e ruído, exportação com ressalvas e conforme perfil, painel de IA sem modelo |
| `tests/test_galeria.py` | 24 | política de licenças Creative Commons aplicada na origem, descarte de foto sem licença ou proprietária, normalização do código da licença, atribuição completa em cada foto, nome e URL cadastrados para toda licença aceita, autoria quando falta nome, uma foto por observação, limite, tamanhos de miniatura, resumo de créditos |
| `tests/test_conteudo.py` | 38 | validação de endereço de vídeo (esquema, host, placeholder), extração do identificador do YouTube em seis formatos, ausência de vídeo inventado no conteúdo base, links oficiais todos em HTTPS, nenhum `[PREENCHER]` no texto base, nenhuma orientação de captura, leitura do JSON com arquivo ausente/corrompido/malformado, campo desconhecido ignorado, modelo editável |
| `tests/test_ilustracoes.py` | 60 | SVG bem formado, sem script, sem recurso externo, declaração para leitor de tela, identificadores únicos por chamada, referências internas resolvidas, proporção preservada, geometria dos leques e dos espinhos, membrana que não alcança as pontas, coordenadas finitas, camadas do desenho presentes |
| `tests/test_markup.py` | 24 | normalizador de HTML, varredura do código em busca de bloco entregue cru ao `st.markdown` (recuo vira bloco de código, linha em branco encerra o bloco), `div` sem par dentro do mesmo bloco, e a marcação que os componentes de fato produzem, com um Streamlit falso |
| `tests/test_board.py` | 35 | formato brasileiro dos números, rótulo e valor escritos em todo bloco, escape de HTML, seta de variação independente de cor, largura das barras, barra de valor zero ainda visível, medidor nos extremos e com máximo zero, descrição do medidor para leitor de tela, e coerência entre `.streamlit/config.toml` e o tema |
| **Total** | **569** | |

### Casos que merecem destaque

Alguns testes existem para impedir, de forma executável, exatamente o tipo de
desonestidade que a especificação proíbe:

- `test_status_inicial_e_sempre_pendente` — score de 0,999 **não** confirma;
- `test_demonstracao_nao_gera_predicao_de_ia` — dado de demonstração não ganha
  score fabricado;
- `test_painel_de_ia_sem_modelo_nao_mostra_metricas` — sem avaliação, nenhuma
  métrica aparece;
- `test_kpis_em_base_vazia_nao_inventam_numeros` — percentual sem dados é
  `None`, não 0%;
- `test_profundidade_nula_e_descartada_nao_zerada` — média de 10 e 20 é 15, e
  não 10, que seria o efeito de zerar o ausente;
- `test_habitat_nao_informado_e_categoria_propria` — nada é redistribuído;
- `test_mapa_publico_nao_expoe_coordenada_precisa` — a coordenada pública é
  diferente da armazenada;
- `test_coordenada_exif_nao_e_usada_automaticamente` — EXIF com GPS não define
  o local sozinho;
- `test_servico_de_validacao_recusa_sessao_sem_permissao` — esconder o botão
  não é controle de acesso;
- `test_nada_e_gravado_quando_a_validacao_falha` — sem ocorrência e sem arquivo
  órfão.

### Estratégia de isolamento

Cada teste roda contra um banco SQLite próprio, em diretório temporário, com
diretório de imagens próprio e configuração recarregada. Os testes de inferência
usam um **preditor injetado** (função que devolve logits conhecidos), o que
verifica a lógica de decisão sem depender de modelo treinado. O desempenho do
modelo real é medido por `scripts/avaliar_modelo.py` sobre o conjunto de teste —
não pela suíte.

---

## 2. Teste integrado de ponta a ponta

`scripts/gerar_evidencias.py` executa o sistema completo sem interface e grava
`reports/evidencias_execucao.md` com a saída real de cada passo:

1. criação do esquema (8 tabelas, 15 índices) e das contas;
2. login correto e login recusado;
3. aceitação de imagem válida e recusa de arquivo não-imagem, truncado e vazio;
4. bloqueio de três formas de travessia de diretório e saneamento de nome;
5. validação de coordenada, sugestão de município, arredondamento público e
   recusa de ponto fora da área;
6. estado da IA, classe atribuída e qualidade medida da imagem;
7. cadastro em transação, sanitização do nome enviado, reenvio idempotente e
   limite de envios;
8. matriz de permissões para visitante e pesquisador;
9. recusa de validação sem sessão e sem justificativa;
10. indicadores antes e depois da decisão humana;
11. geração e separação dos dados de demonstração;
12. consultas analíticas, DBSCAN e exportação;
13. contagem de eventos de auditoria;
14. persistência após fechar as conexões.

---

## 3. Roteiro manual

Estes são os itens que dependem de navegador e aparelho reais. Execute com a
aplicação em HTTPS (ou `localhost`) e marque o resultado.

### 3.1 Fluxo do usuário

| # | Passo | Resultado esperado | Status |
| --- | --- | --- | --- |
| 1 | Abrir no celular | Layout em coluna única, botão de registro em destaque, sem rolagem horizontal | ☐ |
| 2 | Toque em "Registrar avistamento" | Vai para a tela de registro | ☐ |
| 3 | Aba "Tirar foto agora" | Navegador pede permissão de câmera; a câmera abre | ☐ |
| 4 | Tirar a foto | Pré-visualização imediata, antes de qualquer processamento | ☐ |
| 5 | Aba "Enviar da galeria" | Seletor de arquivos abre; imagem aparece | ☐ |
| 6 | Enviar arquivo não-imagem renomeado para `.jpg` | Recusa com mensagem clara; o formulário não é perdido | ☐ |
| 7 | Aguardar a análise | Indicador de processamento e, depois, resultado da IA (ou aviso de indisponível) | ☐ |
| 8 | Resultado inconclusivo | Texto não afirma ausência da espécie; permite seguir | ☐ |
| 9 | Responder "Sim, estou no local" | Botão de GPS aparece | ☐ |
| 10 | Autorizar a localização | "Localização identificada" + precisão + prévia no mapa | ☐ |
| 11 | **Negar** a localização | Mensagem explicativa, mapa manual disponível, nada perdido | ☐ |
| 12 | Marcar ponto no mapa | Município sugerido com a distância da referência | ☐ |
| 13 | Informar só estado e município | Registrado como região aproximada, distinto de GPS | ☐ |
| 14 | Responder "Não, vi em outro lugar" | Não usa a posição atual; pede o local do avistamento | ☐ |
| 15 | Foto antiga com data diferente | Aceita a data real do avistamento | ☐ |
| 16 | Foto com GPS no EXIF | Informa, pede autorização e **não** usa sem marcar a caixa | ☐ |
| 17 | Confirmar avistamento | Protocolo exibido em destaque; status pendente | ☐ |
| 18 | Tocar "Confirmar" duas vezes rápido | **Um** registro; o mesmo protocolo | ☐ |
| 19 | Recarregar a página e reenviar | Mesmo protocolo (idempotência) | ☐ |
| 20 | Consultar o protocolo na home | Situação do registro aparece | ☐ |
| 21 | Reiniciar a aplicação e consultar | Registro continua lá | ☐ |
| 22 | Enviar 6 registros seguidos | O sexto é bloqueado pelo limite, com explicação | ☐ |
| 23 | Desligar a rede e confirmar | Erro honesto; **não** diz que salvou | ☐ |

### 3.2 Dashboards

| # | Passo | Resultado esperado | Status |
| --- | --- | --- | --- |
| 24 | Abrir painel sem login | Tela de acesso; nenhum dado restrito visível | ☐ |
| 25 | Login como pesquisador | Menu de monitoramento aparece | ☐ |
| 26 | Visão geral | 8 indicadores preenchidos a partir do banco | ☐ |
| 27 | Alterar período | Cards, gráficos e tabela mudam juntos | ☐ |
| 28 | Filtrar por estado | Mapa e tabela acompanham | ☐ |
| 29 | Desmarcar "Demonstração" | Totais caem; banner de demonstração desaparece | ☐ |
| 30 | Mapa com agrupamento | Marcadores agrupam e desagrupam ao aproximar | ☐ |
| 31 | Clicar em um marcador | Pop-up com protocolo, município, status e aviso de posição aproximada | ☐ |
| 32 | Ativar áreas DBSCAN | Círculos aparecem com a ressalva de viés | ☐ |
| 33 | Painel científico | Histograma de profundidade informa o `n` e os excluídos | ☐ |
| 34 | Exportar CSV | Download com cabeçalho de ressalvas; sem coluna de contato | ☐ |
| 35 | Painel de IA sem modelo | Estado de indisponibilidade e instruções; nenhuma métrica | ☐ |
| 36 | Painel de IA com modelo | Métricas, matriz de confusão e curvas do arquivo real | ☐ |
| 37 | Validar uma ocorrência | Status muda; indicadores e mapa refletem na mesma sessão | ☐ |
| 38 | Validar sem justificativa | Recusa com mensagem | ☐ |
| 39 | Histórico da ocorrência | Decisões anteriores listadas com avaliador e justificativa | ☐ |
| 40 | Login como administrador | Aba Administração disponível | ☐ |
| 41 | Criar conta com senha curta | Recusa | ☐ |
| 42 | Remover dados de demonstração | Só os DEMO somem; registros reais permanecem | ☐ |
| 43 | Aba Auditoria | Eventos de cadastro, validação e login listados | ☐ |

### 3.3 Acessibilidade

| # | Passo | Resultado esperado | Status |
| --- | --- | --- | --- |
| 44 | Navegar só pelo teclado | Foco visível em todos os controles | ☐ |
| 45 | Zoom de 200% | Sem sobreposição nem rolagem horizontal | ☐ |
| 46 | Simular daltonismo | Status distinguíveis por ícone e texto | ☐ |
| 47 | Tela de 320 px | Conteúdo legível, botões alcançáveis | ☐ |

---

## 4. O que não foi testado

Registrado por honestidade:

- **Desempenho do modelo em campo.** As métricas valem para o conjunto de teste
  montado a partir de bases abertas, não para fotos de celular em água turva.
- **Carga e concorrência.** Nenhum teste de carga; o SQLite em WAL suporta a
  demonstração, não uma operação pública.
- **Leitor de tela.** Boas práticas aplicadas, verificação com leitor não feita.
- **Compatibilidade entre navegadores.** A API de geolocalização tem
  comportamentos diferentes entre iOS e Android; não houve matriz de testes.
- **Teste de intrusão.** As defesas são verificadas por testes unitários, não
  por tentativa ativa de exploração.
- **Implantação em nuvem.** `deploy.md` descreve o caminho; nenhum ambiente
  público foi provisionado por este projeto.
