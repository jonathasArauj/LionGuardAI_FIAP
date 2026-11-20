# models

Modelo de visão computacional publicado para inferência.

| Arquivo | Conteúdo |
| --- | --- |
| `model_card.json` | metadados lidos pelo serviço de inferência: nome, versão, arquitetura, arquivo, formato, tamanho de entrada, classes, ativação e caminho das métricas |
| `lionguard_classificador.onnx` | modelo exportado para ONNX Runtime (usado em produção) |
| `lionguard_classificador.pt` | versão TorchScript (alternativa) |
| `checkpoint_melhor.pt` | melhor estado do treinamento, por F1 de validação |

O modelo **experimental** `lionguard_experimental_icmbio.pt` (aprox. 125 KB)
é distribuído neste ZIP e liberado no `.gitignore` para facilitar a POC.
Modelos maiores/mais avançados seguem ignorados por padrão. A versão
experimental **não possui validação independente** nem métricas de teste.
Consulte `docs/modelo_experimental.md`.

## Como publicar um modelo

```bash
pip install -r requirements-treino.txt
python scripts/baixar_dados.py        # exige internet
python scripts/preparar_dataset.py
python scripts/treinar_modelo.py      # grava ONNX + model_card.json aqui
python scripts/avaliar_modelo.py      # grava reports/metricas_modelo.json
```

## Enquanto não houver modelo

A aplicação continua funcionando. O serviço de inferência reporta o estado
`SEM_MODELO`, a interface informa que a identificação automática está
indisponível, e o avistamento é gravado normalmente para revisão humana. O
painel de IA exibe o estado de indisponibilidade em vez de métricas de
exemplo — não há caminho de código que produza classe ou score sem executar um
modelo real.
