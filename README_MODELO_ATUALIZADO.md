# LionGuard AI — atualização do ZIP com modelo de IA

**Modelo real incluído:** `models/lionguard_experimental_icmbio.pt` (TorchScript; `models/model_card.json` v0.2.0-experimental).

**Amostras usadas no treino:** 10 recortes positivos de figuras do plano ICMBio 2015 + 10 fotos positivas fornecidas pelo usuário + 6 recortes negativos (mergulhadores/equipamentos/fundo do mar).  Fotos do usuário em `data/amostras_usuario/peixe_leao/`. Direitos autorais dessas fotos não foram verificados para publicação externa.

**Treinamento executado:** 20 épocas, seed 42, CNN pequena, 4 aumentações por exemplo (pré-geradas e reutilizadas); `reports/treino_experimental_icmbio.json` documenta as perdas por época. As fotos do treino não são teste independente. **Nenhuma métrica de acurácia, precisão, recall ou F1 em dados de teste está disponível.**

**Teste de integração:** o classificador carregou e produziu scores nas quatro fotos, mas todas ficaram com status `INCONCLUSIVO` usando os limiares conservadores do modelo experimental. É um pipeline de IA funcional, mas **NÃO** um reconhecedor confiável de peixe-leão. Ver `reports/checagem_inferencia_fotos_treino.md`.

**Testes de software:** 569 aprovados. A avaliação científica da IA 

## Executar

```bash
python -m venv .venv
source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app/main.py
```


```bash
pip install -r requirements-modelo-experimental.txt
python scripts/treinar_modelo_experimental_pdf.py \
  --pdf /caminho/plano_emergencial_peixe-leao_resex_arraial_do_cabo_2015.pdf \
  --positivos data/amostras_usuario/peixe_leao \
  --epocas 20 --aumentacoes 4 --lote 12
```

