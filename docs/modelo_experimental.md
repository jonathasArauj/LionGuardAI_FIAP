# Modelo de IA incluído no ZIP — transparência técnica

**Situação:** treinado e integrado como **experimento técnico**, **NÃO VALIDADO para identificação de fauna em campo**.

## Origem das amostras

O treinamento desta versão (`0.2.0-experimental`) utilizou **14 recortes/fotografias rotulados para a demonstração**, sem teste independente:

- **Positivos:** 4 recortes do PDF do ICMBio (xref 42, 36, 20 e 14) **mais 4 fotos de peixe-leão enviadas pelo usuário**, disponíveis em `data/amostras_usuario/peixe_leao/`.
- **Negativos:** 6 recortes sem peixe-leão visível provenientes das figuras do PDF; são principalmente mergulhadores, equipamentos e fundo marinho, **não um conjunto de outros peixes**.
- A obra de 2015 incorpora imagens creditadas a terceiros, como Morris (2012). O modelo pode ser distribuído para demonstração, mas não atribuímos licença às imagens do PDF; elas **não estão incluídas** no ZIP.
- As fotos fornecidas pelo usuário foram incluídas no ZIP para reprodutibilidade de uso privado. **Licença/autoria para distribuição externa não verificada.** Revise os direitos antes de publicar o repositório ou as fotos.
- Alguns recortes podem derivar da mesma fotografia: **14 arquivos de entrada não correspondem a 14 observações científicas independentes**. As aumentações não criam observações independentes.
- As quatro fotos enviadas são dados **de treinamento**, portanto não podem ser utilizadas como validação externa independente.

## Algoritmo e execução

- Arquitetura: CNN pequena (três blocos de convolução, normalização e agrupamento) treinada do zero, **não** MobileNetV3 pré-treinada e **não** YOLO.
- Entrada: imagem 96×96 RGB, redimensionamento `letterbox`, normalização ImageNet usada pela aplicação.
- Saída: dois logits (`NAO_PEIXE_LEAO`, `PEIXE_LEAO`).
- Implementação: `scripts/treinar_modelo_experimental_pdf.py`; artefato TorchScript: `models/lionguard_experimental_icmbio.pt`.
- Hiperparâmetros utilizados: seed 42, 20 épocas, AdamW, lr 0,0015, lote 12, 4 augmentations por exemplo preparadas uma vez e reutilizadas nas épocas.
- O relatório `reports/treino_experimental_icmbio.json` contém somente perdas observadas durante treino. **Não há F1, precisão, recall nem acurácia em conjunto de teste independente.** Esses números não podem ser inferidos da queda de loss.

## Salvaguardas

- Limiares para este modelo: positivo **>= 99,5%** de score, não identificado **< 5%**, restante **inconclusivo**. Esses limiares são conservadores mas **não calibrados nem validados**. É possível uma foto sem peixe-leão obter score próximo de 100%, pois o dataset é minúsculo.
- A classificação pode estar errada mesmo com score muito alto. **Não deve ser usada para confirmar avistamentos nem orientar manejo.**
- Todas as ocorrências seguem **pendentes de revisão humana**, independentemente do resultado.
- O Dashboard de IA exibe o modelo carregado e sua advertência, mas não apresenta métricas de teste inventadas.

## Reproduzir

Com o PDF original disponível no computador:

```bash
pip install -r requirements-modelo-experimental.txt
python scripts/treinar_modelo_experimental_pdf.py \
  --pdf caminho/plano_emergencial_peixe-leao_resex_arraial_do_cabo_2015.pdf \
  --positivos data/amostras_usuario/peixe_leao \
  --epocas 20 --aumentacoes 4 --lote 12
```

Para integrar mais imagens **rotuladas, licenciadas e em arquivo** (incluindo as fotos recebidas do usuário quando disponíveis):

```bash
python scripts/treinar_modelo_experimental_pdf.py \
  --pdf caminho/plano.pdf \
  --positivos caminho/fotos_peixe_leao \
  --negativos caminho/fotos_outros_peixes
```

**Antes de apresentar métricas acadêmicas de generalização:** reunir um conjunto adequado de fotos de observações independentes, contendo espécies negativas relevantes, dividir por observação em treino/validação/teste, treinar MobileNetV3 ou detector adequado, avaliar falsos negativos e falsos positivos e calibrar os limiares sem olhar o conjunto de teste.

## Dependências

Para executar o artefato TorchScript é necessário PyTorch. O `requirements.txt` contém a dependência para que o modelo seja encontrado no caminho padrão do app. Para deploy leve, prefira um modelo ONNX validado quando puder ser exportado; não há ONNX no ZIP experimental.
