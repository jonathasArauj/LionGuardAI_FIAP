#!/usr/bin/env python3
"""
Avalia o modelo publicado sobre o conjunto de teste.

Gera `reports/metricas_modelo.json` — a única fonte das métricas exibidas no
Dashboard de IA. Funciona apenas com `onnxruntime` instalado (não exige
PyTorch) quando o modelo publicado está em formato ONNX.

Uso:
    python scripts/avaliar_modelo.py
    python scripts/avaliar_modelo.py --limiar 0.6
"""

from __future__ import annotations

import argparse

import _caminho  # noqa: F401

from src.ai.evaluate import avaliar


def main() -> int:
    analisador = argparse.ArgumentParser(description="Avalia o modelo no conjunto de teste.")
    analisador.add_argument("--teste", default="data/processed/test")
    analisador.add_argument("--modelos", default="models")
    analisador.add_argument("--saida", default="reports/metricas_modelo.json")
    analisador.add_argument(
        "--limiar",
        type=float,
        default=None,
        help="limiar de decisão (padrão: o configurado na aplicação)",
    )
    argumentos = analisador.parse_args()

    print("=" * 72)
    print("LionGuard AI — avaliação do modelo")
    print("=" * 72)

    try:
        dados = avaliar(
            diretorio_teste=argumentos.teste,
            diretorio_modelos=argumentos.modelos,
            arquivo_saida=argumentos.saida,
            limiar=argumentos.limiar,
        )
    except (FileNotFoundError, ValueError) as erro:
        print(f"\n{erro}")
        return 1

    metricas = dados["metricas"]
    conjunto = dados["conjunto_teste"]
    tempos = dados["tempo_inferencia_ms"]

    print(f"\nModelo: {dados['modelo']['nome']} v{dados['modelo']['versao']}")
    print(f"Imagens de teste: {conjunto['total']} {conjunto['imagens_por_classe']}")
    print(f"\nLimiar de decisão: {metricas['limiar']}")
    print(f"  Acurácia:       {metricas['acuracia']:.4f}")
    print(f"  Precisão:       {metricas['precisao']:.4f}")
    print(f"  Revocação:      {metricas['revocacao']:.4f}")
    print(f"  F1-score:       {metricas['f1']:.4f}")
    print(f"  Especificidade: {metricas['especificidade']:.4f}")
    print(f"  AUC-ROC:        {dados.get('auc_roc')}")
    print("\nMatriz de confusão [[VN, FP], [FN, VP]]:")
    for linha in metricas["matriz_confusao"]:
        print(f"  {linha}")
    print(
        f"\nTempo de inferência: mediana {tempos['mediana']} ms "
        f"(mín {tempos['minimo']} ms, máx {tempos['maximo']} ms, n={tempos['n']})"
    )
    print(f"\nMétricas gravadas em: {argumentos.saida}")
    print("O Dashboard de IA passa a exibir estes números automaticamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
