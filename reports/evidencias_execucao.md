# LionGuard AI — evidências de execução

Execução automática de ponta a ponta, gerada por `scripts/gerar_evidencias.py` em **2026-11-19T22:37:26**.

> Toda saída abaixo é produto da execução real do código deste repositório. Nenhum valor foi escrito à mão.

## Ambiente

- **Python:** 3.13.18
- **Sistema:** Linux 6.18.44-fc-v726 (x86_64)
- **Banco de dados:** /tmp/lionguard_evid_azck7y9_/evidencias.db
- **Diretório de imagens:** /tmp/lionguard_evid_azck7y9_/images
- **Modo:** banco temporário isolado

## 1. Criação do esquema e contas de acesso

- **Tabelas criadas:** 8 — evento_requisicao, fonte_dados, imagem, log_auditoria, ocorrencia, predicao, usuario, validacao
- **Índices de consulta:** 15
- **Contas criadas nesta execução:** 2
  (as senhas vêm de variáveis de ambiente; nenhuma credencial consta no código-fonte)
- **Login de pesquisador:** OK — perfil PESQUISADOR, sessão válida até 2026-11-20T06:37:26
- **Login com senha incorreta:** recusado corretamente (ErroAutenticacao)

## 2. Validação de imagem e saneamento de entrada

- **Imagem sintética aceita:** JPEG 640×480, 187 KB, EXIF removido: True
  *A imagem é sintética e serve só para exercitar o pipeline — não é uma fotografia da espécie, e nenhuma conclusão de identificação é tirada dela.*
- **Rejeição de arquivo que não é imagem:** recusado — “Formato não reconhecido. Envie uma foto JPEG, PNG ou WebP.”
- **Rejeição de JPEG truncado:** recusado — “O arquivo parece corrompido ou incompleto.”
- **Rejeição de arquivo vazio:** recusado — “Arquivo vazio. Tente enviar a foto novamente.”
- **Bloqueio de `../../etc/passwd`:** recusado — “nome de arquivo não pode conter diretório: '../../etc/passwd'”
- **Bloqueio de `/etc/shadow`:** recusado — “nome de arquivo não pode conter diretório: '/etc/shadow'”
- **Bloqueio de `..\..\windows\system.ini`:** recusado — “nome de arquivo não pode conter diretório: '..\\..\\windows\\system.ini'”
- **Saneamento de nome enviado pelo usuário:** `../../etc/passwd` → `etc_passwd` · `foto;rm -rf /.JPG` → `foto_rm_-rf_.JPG`
- **Nome legítimo resolvido dentro do diretório:** `abc123.jpg` → dentro de `/tmp/lionguard_evid_azck7y9_/images`: True

## 3. Geolocalização

- **Coordenada do GPS validada:** -20.6712, -40.4985 → Guarapari/ES (referência a 0.21 km), origem: GPS do dispositivo
- **Coordenada no mapa público:** -20.67, -40.5 — arredondada para 2 casas (~1 km)
- **Rejeição de ponto fora da área:** recusado — “O ponto está fora da área de monitoramento: o ponto está fora da faixa de latitude e longitude monitorada.”

## 4. Inferência

- **Estado do modelo:** `SEM_MODELO`
- **Detalhe:** nenhum modelo publicado em models/. Treine com `python scripts/treinar_modelo.py` e publique o model_card.json.
- **Classe atribuída:** `SEM_MODELO`
- **Score:** — (indisponível)
- **Mensagem ao usuário:** “A identificação automática está indisponível neste momento. Seu registro será salvo e analisado por um avaliador.”
- **Qualidade medida da imagem:** nitidez 23727.06, brilho 127.14, contraste 36.85
  *Nenhum modelo publicado nesta execução: o sistema devolve o estado de indisponibilidade e o registro segue para revisão humana, sem classificação inventada.*

## 5. Cadastro do avistamento (transação)

- **Registro gravado:** protocolo `LG-2026-W27HK5`
- **Status inicial:** `PENDENTE` (nunca confirmado automaticamente)
- **Sucesso confirmado relendo do banco:** True
- **Nome de arquivo sanitizado:** original `../../../etc/shadow;rm -rf.jpg` → gravado como `bca6004d6400411eb2b3c196dfeab64a.jpg` (nome original guardado como `etc_shadow_rm_-rf.jpg`)
- **Arquivo existe no disco:** True
- **Reenvio com a mesma chave (duplo clique):** protocolo `LG-2026-W27HK5` · duplicado=True · total de ocorrências: 1
- **Limite de envios por sessão:** limite 5 em 600s → permitidos: 5, bloqueados: 2

## 6. Controle de acesso

- `REGISTRAR_AVISTAMENTO` para visitante anônimo: **permitido**
- `REGISTRAR_AVISTAMENTO` para pesquisador: **permitido**
- `VER_PAINEL_OPERACIONAL` para visitante anônimo: **negado**
- `VER_PAINEL_OPERACIONAL` para pesquisador: **permitido**
- `VALIDAR_OCORRENCIA` para visitante anônimo: **negado**
- `VALIDAR_OCORRENCIA` para pesquisador: **permitido**
- `GERENCIAR_USUARIOS` para visitante anônimo: **negado**
- `GERENCIAR_USUARIOS` para pesquisador: **negado**
- **Validação sem autenticação:** recusada corretamente (AcessoNegado)
- **Validação sem justificativa adequada:** recusada — “Descreva a justificativa da decisão (mínimo 10 caracteres).”

## 7. Validação humana e atualização dos indicadores

- **Indicadores antes da decisão:** total=1, pendentes=1, confirmados=0, validados=0.0%
- **Decisão registrada:** Ocorrência LG-2026-W27HK5 atualizada: PENDENTE → CONFIRMADO.
- **Indicadores depois da decisão:** total=1, pendentes=0, confirmados=1, validados=100.0%, tempo mediano de revisão=0.0h
- **Histórico de validação:** 1 decisão(ões) registrada(s) — PENDENTE → CONFIRMADO

## 8. Dados de demonstração e separação por procedência

- **Registros de demonstração criados:** 90
- **Total com demonstração:** 91
- **Total sem demonstração (filtro aplicado):** 1
- **Rotulagem:** 90 registro(s) marcados como `DEMO`; o filtro de procedência os remove por completo
- **Predições de IA em registros de demonstração:** 0 (por decisão de projeto: dado de demonstração não recebe score de modelo)

## 9. Consultas analíticas dos dashboards

- **Estados com registro:** 16
- **Cinco primeiros estados:** BA=14, ES=14, RN=10, PE=9, AL=8
- **Meses na série temporal:** 18
- **Distribuição por status:** [{'status': 'PENDENTE', 'total': 36}, {'status': 'CONFIRMADO', 'total': 24}, {'status': 'REJEITADO', 'total': 14}, {'status': 'INCONCLUSIVO', 'total': 13}, {'status': 'AGUARDANDO_INFO', 'total': 4}]
- **Completude:** coordenadas 100.0%, imagem 1.1%, profundidade 64.8%, habitat 74.7%
- **Indicadores operacionais:** {'pendentes': 36, 'aguardando_info': 4, 'revisados': 51, 'sem_coordenadas': 0, 'sem_imagem': 90, 'com_erro_ia': 0, 'tempo_mediano_revisao_horas': 128.0}

## 10. Análise espacial (DBSCAN)

- **Pontos analisados:** 91
- **Executado:** True
- **Agrupamentos encontrados:** 8
- **Pontos de ruído (isolados):** 58
- **Biblioteca:** scikit-learn DBSCAN (métrica haversine)
  - Área 2 — Japaratinga: 8 registros, raio 31.16 km, UFs ['AL', 'PE']
  - Área 1 — Guarapari: 5 registros, raio 24.8 km, UFs ['ES']
  - Área 5 — Cabedelo: 4 registros, raio 17.88 km, UFs ['PB']
  - Área 6 — Mata de São João: 4 registros, raio 12.78 km, UFs ['BA']
  - Área 3 — Anchieta: 3 registros, raio 6.45 km, UFs ['ES']
  - Ressalva registrada: *Agrupamentos refletem onde há mais observadores e registros, não necessariamente onde há mais peixes-leão. Ausência de registros não significa ausência da espécie.*

## 11. Exportação e auditoria

- **Exportação CSV:** `lionguard_ocorrencias_2026-11-19.csv` com 97 linha(s), coordenadas arredondadas (perfil pesquisador não exporta precisas)
- **Contato exportado:** não — a coluna de contato não entra no CSV
- **Eventos de auditoria registrados:** 7
  Ações auditadas: CRIACAO=2, VALIDACAO_CONFIRMAR=1, SEMEADURA_DEMONSTRACAO=1, LOGIN_SUCESSO=1, LOGIN_FALHA=1, CADASTRO=1

## 12. Persistência após reabertura do banco

- **Conexões fechadas:** sim (simula reinicialização da aplicação)
- **Total de ocorrências após reabrir:** 91
- **Ocorrência relida:** `LG-2026-W27HK5` com status `CONFIRMADO`
- **Integridade:** OK — nenhum registro perdido

## Resumo

O fluxo **foto → IA → GPS → confirmação → SQL → dashboard → validação** foi executado de ponta a ponta nesta máquina, com transação atômica, idempotência, controle de acesso, auditoria e persistência verificados. O estado do modelo de IA é reportado como encontrado: se não houver modelo publicado, o sistema informa a indisponibilidade em vez de produzir uma classificação.


## Atualização posterior à execução original

Os estados `SEM_MODELO` acima são evidências anteriores à inclusão do artefato. Em uma etapa posterior, foi treinada uma CNN experimental com 10 recortes do plano ICMBio 2015 e 4 fotos fornecidas pelo usuário. Testes e status atual: `docs/modelo_experimental.md` e o resultado da suíte de testes atualizado. Não há conjunto de teste científico para a nova versão.
