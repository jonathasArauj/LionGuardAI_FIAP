#!/usr/bin/env python3
"""
Treina o classificador de peixe-leão (MobileNetV3 + transfer learning).

Requer `pip install -r requirements-treino.txt` (PyTorch e torchvision) e o
dataset já preparado em `data/processed/`.

Ao final, grava em `models/`:
  * `lionguard_classificador.onnx` — modelo para inferência;
  * `lionguard_classificador.pt`  — versão TorchScript;
  * `checkpoint_melhor.pt`        — melhor estado de treino;
  * `model_card.json`             — metadados lidos pelo serviço de inferência;
e em `reports/historico_treinamento.json` as curvas por época.

Uso:
    python scripts/treinar_modelo.py
    python scripts/treinar_modelo.py --epocas-cabeca 3 --epocas-ajuste 8 --lote 16
"""

from __future__ import annotations

import argparse
from pathlib import Path

import _caminho  # noqa: F401

from src.ai.train import ConfiguracaoTreino, contar_imagens, treinar


def main() -> int:
    analisador = argparse.ArgumentParser(description="Treina o modelo de classificação.")
    analisador.add_argument("--dados", default="data/processed")
    analisador.add_argument("--saida", default="models")
    analisador.add_argument("--lote", type=int, default=32)
    analisador.add_argument("--epocas-cabeca", type=int, default=4)
    analisador.add_argument("--epocas-ajuste", type=int, default=8)
    analisador.add_argument("--entrada", type=int, default=224)
    analisador.add_argument("--semente", type=int, default=42)
    analisador.add_argument("--versao", default="1.0.0")
    analisador.add_argument("--paciencia", type=int, default=4)
    analisador.add_argument(
        "--sem-onnx", action="store_true", help="não exportar ONNX (usa TorchScript)"
    )
    argumentos = analisador.parse_args()

    print("=" * 72)
    print("LionGuard AI — treinamento do classificador")
    print("=" * 72)

    try:
        import torch  # noqa: F401
        import torchvision  # noqa: F401
    except ImportError:
        print(
            "\nPyTorch não está instalado neste ambiente.\n"
            "Instale com:  pip install -r requirements-treino.txt\n"
            "(Para GPU, siga antes as instruções de https://pytorch.org)"
        )
        return 1

    diretorio_dados = Path(argumentos.dados)
    for conjunto in ("train", "val", "test"):
        caminho = diretorio_dados / conjunto
        if caminho.is_dir():
            print(f"  {conjunto:<6} {contar_imagens(caminho)}")

    configuracao = ConfiguracaoTreino(
        diretorio_dados=diretorio_dados,
        diretorio_saida=Path(argumentos.saida),
        tamanho_entrada=argumentos.entrada,
        lote=argumentos.lote,
        epocas_cabeca=argumentos.epocas_cabeca,
        epocas_ajuste_fino=argumentos.epocas_ajuste,
        semente=argumentos.semente,
        versao_modelo=argumentos.versao,
        paciencia=argumentos.paciencia,
        exportar_onnx=not argumentos.sem_onnx,
    )

    try:
        resumo = treinar(configuracao)
    except FileNotFoundError as erro:
        print(f"\n{erro}")
        return 1

    print("\n" + "=" * 72)
    print("Treinamento concluído")
    print("=" * 72)
    for chave, valor in resumo.items():
        print(f"  {chave}: {valor}")
    print("\nPróximo passo: python scripts/avaliar_modelo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
