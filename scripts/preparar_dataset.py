#!/usr/bin/env python3
"""
Valida, deduplica e divide o dataset em treino, validação e teste.

A divisão é **por observação**, não por imagem: todas as fotos de uma mesma
observação ficam no mesmo conjunto, para que fotos quase idênticas não apareçam
em treino e teste ao mesmo tempo. O script confere isso explicitamente ao final
e falha se detectar vazamento.

Uso:
    python scripts/preparar_dataset.py
    python scripts/preparar_dataset.py --semente 7 --proporcoes 0.7 0.15 0.15
"""

from __future__ import annotations

import argparse

import _caminho  # noqa: F401

from src.data.dataset import preparar_dataset


def main() -> int:
    analisador = argparse.ArgumentParser(description="Prepara o dataset de imagens.")
    analisador.add_argument("--origem", default="data/raw")
    analisador.add_argument("--destino", default="data/processed")
    analisador.add_argument("--semente", type=int, default=42)
    analisador.add_argument(
        "--proporcoes",
        type=float,
        nargs=3,
        default=(0.70, 0.15, 0.15),
        metavar=("TREINO", "VAL", "TESTE"),
    )
    argumentos = analisador.parse_args()

    print("=" * 72)
    print("LionGuard AI — preparação do dataset")
    print("=" * 72)

    resultado = preparar_dataset(
        diretorio_origem=argumentos.origem,
        diretorio_destino=argumentos.destino,
        proporcoes=tuple(argumentos.proporcoes),
        semente=argumentos.semente,
    )

    print(f"\nImagens encontradas:      {resultado.total_encontradas}")
    print(f"Descartadas (inválidas):  {resultado.invalidas}")
    print(f"Duplicatas removidas:     {resultado.duplicadas}")
    print(f"Grupos (observações):     {resultado.grupos}")
    print(f"Imagens utilizadas:       {resultado.total_utilizadas}")
    print("\nDivisão por conjunto e classe:")
    for conjunto, classes in resultado.por_conjunto.items():
        total = sum(classes.values())
        print(f"  {conjunto:<6} total={total:<5} {classes}")

    print(f"\nRelatório da divisão: {resultado.relatorio}")

    if resultado.vazamento_detectado:
        print("\n*** ERRO: vazamento detectado — um grupo apareceu em mais de um conjunto.")
        return 1
    print("Verificação de vazamento entre conjuntos: OK (nenhum grupo repetido).")

    if resultado.total_utilizadas == 0:
        print(
            "\nNenhuma imagem utilizável. Execute `python scripts/baixar_dados.py` "
            "antes (requer internet)."
        )
        return 1

    print("\nPróximo passo: python scripts/treinar_modelo.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
