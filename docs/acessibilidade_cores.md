# Acessibilidade das cores

A paleta não foi escolhida por gosto: cada conjunto foi submetido a um
validador que calcula, em espaço perceptual OKLab, a faixa de luminosidade, o
piso de croma, a separação entre pares sob daltonismo (protanopia, deuteranopia
e tritanopia) e o contraste contra o fundo. Este documento registra o que
passou, o que não passou e o que foi feito a respeito.

---

## 1. Paleta da identidade (seção 9.1 do escopo)

Definida pela especificação do projeto e mantida como identidade visual —
cabeçalhos, botões, bordas e fundos:

| Cor | Hex | Uso |
| --- | --- | --- |
| Azul-marinho | `#062B43` | títulos, texto de destaque, gradiente do cabeçalho |
| Azul-oceano | `#086F8C` | cor primária, botões, bordas de card |
| Turquesa | `#14B8A6` | gradiente, realces, foco visível |
| Branco | `#FFFFFF` | fundo |
| Cinza-claro | `#F3F7F9` | fundo secundário |
| Laranja de alerta | `#F59E0B` | status pendente, avisos |

Essas cores funcionam bem como **superfície e tipografia**, mas duas delas
(azul-marinho e azul-oceano) ficaram fora da faixa de luminosidade e abaixo do
piso de croma exigidos para marcas de dados — ou seja, usadas como cor de série
em gráfico, tendiam a "ler como cinza" e a competir com o texto. Por isso a
paleta de gráficos é derivada, e não idêntica.

---

## 2. Paleta categórica dos gráficos

Ordem fixa, nunca reciclada. Cinco posições no máximo: a sexta série é agregada
em "Outros" em vez de receber uma cor nova.

| Posição | Hex | Nome |
| --- | --- | --- |
| 1 | `#0891B2` | ciano-oceano |
| 2 | `#F59E0B` | laranja de alerta (cor da identidade) |
| 3 | `#15803D` | verde-mar |
| 4 | `#6366F1` | índigo |
| 5 | `#B45309` | âmbar escuro |

**Resultado da validação** (fundo claro, todos os pares):

| Verificação | Resultado |
| --- | --- |
| Faixa de luminosidade | PASSA — todas as 5 dentro de L 0,43–0,77 |
| Piso de croma | PASSA — todas ≥ 0,10 |
| Separação sob daltonismo | ATENÇÃO — pior par `#B45309` ↔ `#15803D`, ΔE 6,8 (protanopia) |
| Piso de visão normal | PASSA — pior par ΔE 16,8 |
| Contraste contra o fundo | ATENÇÃO — `#F59E0B` em 2,09:1 |

As duas marcas de atenção são compensadas por **codificação secundária, sempre
presente nos gráficos deste projeto**:

- toda série com duas ou mais categorias tem **legenda**;
- toda barra tem **rótulo numérico direto**;
- todo painel acompanha **tabela** com os mesmos dados.

Nenhum gráfico depende de distinguir duas cores para ser lido.

### Decisões derivadas

- **Série única usa um matiz só** (`#0891B2`). A maioria dos gráficos do projeto
  (por estado, por município, por hora, por habitat) é de série única, então a
  questão de separação de matizes simplesmente não aparece.
- **Magnitude usa rampa de um matiz** do claro ao escuro (ciano, seis passos),
  nunca arco-íris. Usada na matriz de confusão.
- **Nunca dois eixos y.** Perda e métricas de treinamento, que têm escalas
  diferentes, vão em dois gráficos separados.

---

## 3. Paleta de status

Reservada: essas cores significam estado e não são reaproveitadas como "série
4". A especificação define quatro delas (seção 5.2).

| Status | Hex | Ícone | Origem da escolha |
| --- | --- | --- | --- |
| Pendente de validação | `#F59E0B` | ⏳ | escopo do projeto |
| Confirmado | `#DC2626` | ✅ | escopo do projeto |
| Rejeitado | `#9CA3AF` | 🚫 | escopo do projeto |
| Inconclusivo | `#2563EB` | 🔎 | escopo do projeto |
| Aguardando informações | `#059669` | ❓ | **escolhida com o validador** |

### Por que "aguardando informações" é verde

É um status adicional do nosso fluxo operacional, então a cor era nossa para
escolher. As opções intuitivas falharam na verificação:

| Candidata | Resultado |
| --- | --- |
| `#D97706` (laranja escuro) | **FALHA** — ΔE 10,8 contra o `#F59E0B` de "pendente" em visão normal; indistinguíveis na rosca de status |
| `#7C3AED` (violeta) | **FALHA** — ΔE 0,4 contra o `#2563EB` de "inconclusivo" em deuteranopia; literalmente a mesma cor para quem tem a condição |
| `#0891B2` (ciano) | **FALHA** — ΔE 14,3 contra o cinza de "rejeitado" |
| `#4D7C0F` (oliva) | ATENÇÃO — ΔE 6,1 contra o vermelho de "confirmado" |
| `#059669` (verde-esmeralda) | **PASSA** em todos os pares |

Verde para "aguardando" não é a associação semântica mais óbvia, mas o status
sempre aparece com ícone e texto ("❓ Aguardando informações"), e legibilidade
para quem tem daltonismo pesa mais do que a convenção de matiz.

### Exceção documentada: o cinza

O `#9CA3AF` de "rejeitado" fica **abaixo do piso de croma** (0,019) e com
contraste de 2,47:1. Isso é intencional: cinza é o neutro que comunica
"descartado", e a especificação pede cinza para esse status. A compensação é a
mesma dos outros casos — ícone, rótulo e presença em tabela.

---

## 4. Tema escuro, escolhido e revalidado

A aplicação usa tema **escuro** (`.streamlit/config.toml`, `base = "dark"`).
A superfície dos cartões é `#1C1757`, sobre um fundo índigo com brilho radial.

O tema escuro **não** é a inversão do claro. As paletas das seções 2 e 3 foram
refeitas: a faixa de luminosidade aceitável muda (de 0,43–0,77 para 0,48–0,67
em OKLCH), e cada passo foi revalidado contra a nova superfície. A paleta clara
anterior, colocada sobre fundo escuro sem ajuste, falha na faixa de
luminosidade — foi exatamente essa verificação que motivou refazer os passos em
vez de inverter.

### Paleta categórica do tema escuro

| Posição | Hex | Nome |
| --- | --- | --- |
| 1 | `#1E9CB8` | ciano-oceano |
| 2 | `#C8831A` | âmbar de alerta |
| 3 | `#22A077` | verde-mar |
| 4 | `#7C83E8` | índigo |
| 5 | `#D85F9E` | magenta |

Resultado da validação contra `#1C1757`:

| Verificação | Resultado |
| --- | --- |
| Faixa de luminosidade | **passa** — as cinco dentro de L 0,48–0,67 |
| Piso de croma | **passa** — nenhuma lê como cinza |
| Separação sob daltonismo (pares adjacentes) | **passa** — pior par ΔE 9,4 em protanopia |
| Separação em visão normal | **passa** — pior par ΔE 18,6 |
| Contraste contra o fundo | **passa** — as cinco ≥ 3:1 |

Um ponto fica na faixa de piso: verde-mar ↔ âmbar em **tritanopia** (ΔE 6,3).
A faixa de 6–8 só é admissível com codificação secundária, e os gráficos a
aplicam sempre — legenda presente e rótulo direto nas séries.

### Status no tema escuro

| Status | Hex | Observação |
| --- | --- | --- |
| Pendente | `#C8831A` | âmbar |
| Confirmado | `#E06A6A` | vermelho, conforme a seção 5.2 do escopo |
| Rejeitado | `#7D82A8` | cinza — abaixo do piso de croma, de propósito |
| Inconclusivo | `#5B8BF5` | azul |
| Aguardando informações | `#22A077` | verde-mar |

Comparados **todos contra todos**, dois pares ficam abaixo do piso de visão
normal: laranja ↔ vermelho e azul ↔ cinza. A decisão é a mesma do tema claro e
pelo mesmo motivo — as cores dos status são impostas pelo escopo, e status
nunca aparece só como cor: a interface desenha ícone e rótulo ao lado em todos
os lugares (mapa, tabela, cartão, legenda). Há teste que verifica a presença do
ícone e do texto junto da cor.

### A rampa sequencial inverte de direção

No tema claro a rampa vai do claro ao escuro; no escuro, do escuro ao claro —
é o claro que avança sobre o fundo. Inverter a direção faria o valor alto
desaparecer no fundo. Há teste verificando a monotonicidade da luminosidade.

---

## 5. Outras medidas de acessibilidade

- **Nenhuma informação só por cor.** Status e resultado da IA sempre aparecem
  como ícone + texto + cor.
- **Alvos de toque de 48 px** de altura mínima em botões (`min-height: 3rem`),
  e 64 px no botão principal de registro.
- **Foco visível** com contorno de 3 px em turquesa, em botões, links e campos.
- **Valores ausentes aparecem como "—"**, com nota explicativa, nunca como zero.
- **Estados vazios explicam** o motivo em vez de mostrar gráfico em branco.
- **Tipografia responsiva** com `clamp()`, legível em telas estreitas.
- **Movimento respeita `prefers-reduced-motion`**: a animação da ilustração do
  topo é desligada para quem configurou o sistema assim.
- **Ilustrações se declaram** para o leitor de tela: as decorativas com
  `aria-hidden`, as que carregam informação (o medidor, por exemplo) com
  `role="img"` e `aria-label` contendo o valor por extenso.

---

## 6. Como reproduzir a verificação

A validação foi feita com um script que calcula as métricas em OKLab e simula
as três formas de daltonismo. Para repetir com outra paleta, o que precisa ser
verificado em cada conjunto categórico é:

1. luminosidade de todas as cores dentro de uma faixa média estreita;
2. croma mínimo, para que nenhuma leia como cinza;
3. ΔE ≥ 8 entre todos os pares, nas três simulações de daltonismo;
4. ΔE ≥ 15 entre todos os pares em visão normal;
5. contraste ≥ 3:1 contra o fundo, ou codificação secundária obrigatória.

Os valores registrados neste documento são os obtidos nas combinações finais
descritas acima.
