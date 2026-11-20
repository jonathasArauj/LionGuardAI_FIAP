# Limitações conhecidas

Documento de prestação de contas: o que o protótipo **não** faz, o que faz com
ressalva, e o que foi deixado de fora de propósito. A lista é parte da entrega
— uma POC honesta vale mais do que uma demonstração que esconde as bordas.

---

## 1. Natureza do projeto

- **É um protótipo acadêmico.** Desenvolvido para a Global Solution 2026.2 da
  FIAP (desafio CitizenTech). Não tem homologação, convênio ou qualquer vínculo
  com ICMBio, Iema, Ibama ou outro órgão ambiental, e **não substitui** o canal
  oficial de comunicação de ocorrências.
- **Não é uma base científica de referência.** Os registros não passaram por
  curadoria taxonômica formal. "Confirmado" significa que um avaliador cadastrado
  na plataforma revisou o registro — não que exista validação institucional.
- **Sem acordo de nível de serviço.** Não há prazo garantido de revisão.

---

## 2. Inteligência artificial

| Limitação | Consequência prática |
| --- | --- |
| O desempenho depende do conjunto de imagens disponível em bases abertas | Métricas obtidas com poucas centenas de imagens não se transferem automaticamente para campo |
| Fotos subaquáticas variam muito (turbidez, luz, distância, enquadramento) | Um modelo treinado com fotos "boas" de catálogo erra mais em fotos reais de celular |
| O score **não** é probabilidade calibrada | 0,80 não significa 80% de chance de ser peixe-leão; é a saída do softmax |
| É um classificador, não um detector | Não localiza o animal na imagem, não desenha caixas e **não conta indivíduos** |
| Espécies do mesmo gênero e peixes-escorpião nativos são visualmente próximos | Confusão plausível; por isso toda ocorrência passa por revisão humana |
| Sem modelo publicado, não há inferência | O painel de IA mostra `SEM_MODELO` e o registro segue sem classificação — por projeto |
| A avaliação é de um conjunto de teste pequeno | Intervalos de confiança largos; a diferença entre duas versões pode ser ruído |

O que **não** fazemos: apresentar a identificação automática como laudo,
confirmar ocorrência por score, ou exibir métricas quando não há avaliação.

---

## 3. Localização

- **O GPS exige contexto seguro.** O navegador só libera `navigator.geolocation`
  em HTTPS ou `localhost`. Em rede local por IP (`http://192.168.x.x`), o botão
  de GPS não funciona — a interface detecta e explica, e o fluxo segue pelo mapa.
- **A precisão varia muito.** Em celular pode ir de poucos metros a centenas,
  dependendo de céu aberto, GPS versus triangulação e do próprio aparelho. O
  valor informado pelo navegador é gravado e exibido, sem suavização.
- **A tabela municipal é aproximada.** A sugestão de município usa 88 pontos de
  referência do litoral (incluindo quatro ilhas oceânicas), não a malha
  cartográfica do IBGE. A distância até a referência é sempre informada e o
  usuário pode corrigir.
- **O filtro de área é geométrico.** Um ponto é aceito se estiver na caixa
  envolvente **e** a menos de 450 km de uma referência litorânea. Isso recusa
  Buenos Aires e o interior do continente, mas não é um recorte jurídico de
  mar territorial.
- **Coordenada pública arredondada em ~1 km.** Protege pontos de mergulho, mas
  reduz a resolução de qualquer análise feita a partir do mapa público.

---

## 4. Dados

- **Viés de observação.** Há mais registros onde há mais mergulhadores,
  turismo e sinal de celular. Um mapa de notificações é um mapa de observadores
  tanto quanto de peixes.
- **Ausência não é evidência de ausência.** Trecho de costa sem registro pode
  ser trecho sem ninguém olhando.
- **Campos opcionais ficam vazios.** Profundidade e habitat são informados em
  parte dos registros. Valores ausentes são descartados das estatísticas (nunca
  zerados nem atribuídos a uma categoria), e cada indicador mostra o `n` que o
  sustenta.
- **Registros importados não são confirmados automaticamente.** Vêm de bases
  documentadas (GBIF, iNaturalist) com fonte e licença gravadas, mas entram como
  pendentes: base externa não é validação da nossa equipe.
- **Dados de demonstração existem e são rotulados.** Geração determinística,
  marcados como `DEMO`, sem imagem e **sem predição de IA**, removíveis por
  filtro em qualquer painel. Não representam ocorrência real em município algum.
- **Duplicidade é heurística.** O alerta compara coordenadas próximas na mesma
  janela de 24 horas e hash idêntico de imagem. É pista para conferência, não
  afirmação.

---

## 5. Segurança

Implementada de forma proporcional a uma POC. O que existe: hash scrypt com
sal, permissões por perfil verificadas no serviço, validação de upload em quatro
camadas, bloqueio de travessia de diretório, remoção de EXIF, limite de envios
por sessão, auditoria de operações, contato guardado apenas como hash.

O que **falta** para uma operação real:

- **Limitação de requisições na borda.** O limite atual é por sessão de
  navegador; um atacante determinado abre sessões novas. O correto é limitar por
  IP/ASN na borda, com verificação anti-automação.
- **Sem verificação de identidade.** O registro é anônimo por decisão de
  usabilidade; isso significa que a plataforma é vulnerável a envio em massa de
  registros falsos. Mitigação parcial: hash de imagem, detecção de duplicatas e
  revisão humana obrigatória.
- **Sessão em memória do processo.** Não há revogação centralizada de sessões
  nem segundo fator.
- **Sem criptografia em repouso** do banco e das imagens.
- **Sem política de retenção.** Imagens e registros ficam indefinidamente.
- **A aplicação não foi submetida a teste de intrusão.**

---

## 6. Interface e acessibilidade

- O tema é **claro apenas**. As cores foram validadas contra o fundo claro com
  verificação de contraste e daltonismo; um tema escuro exigiria uma segunda
  paleta validada, não uma inversão automática (ver `acessibilidade_cores.md`).
- Nenhum teste com leitor de tela foi realizado. O que existe: nenhuma
  informação transmitida só por cor (sempre ícone + texto), alvos de toque de no
  mínimo 48 px, foco visível e contraste verificado.
- O mapa (Folium/Leaflet) tem limitações próprias de navegação por teclado.
- A aplicação **não funciona offline**. Sem conexão, o Streamlit perde a sessão;
  a interface avisa em vez de simular gravação. Um aplicativo nativo com fila
  local resolveria — está fora do escopo.
- Não há internacionalização: a interface é só em português.

---

## 7. Operação

- **Persistência não garantida em hospedagem gratuita.** SQLite em disco
  efêmero e imagens em sistema de arquivos local se perdem a cada *redeploy*.
  Ver `deploy.md`; a aba de Auditoria detecta imagens ausentes.
- **Sem notificações.** Nada avisa o avaliador de registro novo, nem o cidadão
  de mudança de status. Ele precisa consultar o protocolo.
- **Sem integração com órgãos ambientais.** A arquitetura prevê, mas nenhuma
  integração existe.
- **Concorrência de escrita limitada.** O SQLite em modo WAL suporta a carga de
  uma POC; muitos registros simultâneos exigem PostgreSQL.

---

## 8. Validação dos critérios de aceite

`python scripts/diagnostico.py` verifica os critérios da especificação um por
um e classifica cada um como **OK** (verificado automaticamente), **MANUAL**
(implementado, confirmável só no navegador), **PENDENTE** (depende de etapa
externa, como treinar o modelo) ou **FALHA**. O relatório vai para
`reports/diagnostico_criterios.md`.

Nesta implementação, os itens que **não** podem ser verificados por script são:
abrir no celular, capturar foto pela câmera, o pedido de permissão de
localização e o funcionamento do GPS. Todos estão implementados, e todos
dependem de um navegador real para serem comprovados — por isso aparecem como
MANUAL, e não como aprovados.


## Atualização: modelo experimental (novembro/2026)

O pacote agora inclui uma CNN treinada em 14 imagens/recortes (incluindo 4 fotos do usuário), com pesos reais e cartão de modelo, mas o treinamento **não tem validade de generalização**. A situação "sem modelo" documentada anteriormente continua aplicável quando o arquivo for removido ou o backend de inferência não estiver instalado. A versão atual não foi avaliada em imagens independentes; detalhes em `docs/modelo_experimental.md`.
