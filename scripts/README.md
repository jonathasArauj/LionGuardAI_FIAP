# scripts

Scripts de apoio, todos executáveis pela linha de comando a partir da raiz do
projeto.

## Dataset e modelo de IA

| Script | O que faz |
| --- | --- |
| `baixar_dados.py` | baixa imagens do iNaturalist (**exige internet**), aceitando apenas licenças Creative Commons, e grava o manifesto com fonte, URL, licença e autor |
| `preparar_dataset.py` | valida, remove duplicatas e divide em treino/validação/teste **por observação**, verificando vazamento ao final |
| `treinar_modelo.py` | treina a MobileNetV3 (exige PyTorch), exporta ONNX e publica o `model_card.json` |
| `avaliar_modelo.py` | avalia no conjunto de teste e gera `reports/metricas_modelo.json` — a única fonte das métricas do painel de IA |

## Operação e verificação

| Script | O que faz |
| --- | --- |
| `semear_demonstracao.py` | gera (ou remove) dados de demonstração rotulados como `DEMO` |
| `rodar_testes.py` | executa a suíte Pytest e grava `reports/testes_execucao.md` |
| `diagnostico.py` | verifica os critérios de aceite um por um e grava `reports/diagnostico_criterios.md` |
| `gerar_evidencias.py` | executa o sistema de ponta a ponta sem interface e grava `reports/evidencias_execucao.md` |
| `gerar_pdf.py` | monta o PDF da entrega a partir dos relatórios acima e de consultas ao banco |

## Ordem recomendada

```bash
# preparação do ambiente
pip install -r requirements.txt
cp .env.example .env

# demonstração
python scripts/semear_demonstracao.py --quantidade 150
streamlit run app/main.py

# verificação e entrega
python scripts/rodar_testes.py
python scripts/diagnostico.py
python scripts/gerar_evidencias.py
python scripts/gerar_pdf.py --integrantes "..." --turma "..." --video "..." --repositorio "..."
```

`_caminho.py` não é executável: é um módulo auxiliar que coloca a raiz do
projeto no `sys.path`, importado pelos demais scripts.
