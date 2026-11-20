#!/usr/bin/env python3
"""
Baixa as imagens de treinamento do iNaturalist.

**Requer acesso à internet.** As imagens são salvas em `data/raw/<classe>/` e a
procedência de cada arquivo (fonte, URL, licença, autor, identificador da
observação e data de aquisição) é gravada em `data/raw/manifesto.csv`.

Somente observações com licença Creative Commons declarada são baixadas.

Uso:
    python scripts/baixar_dados.py                      # 250 imagens por classe
    python scripts/baixar_dados.py --limite 400
    python scripts/baixar_dados.py --apenas-positivos
"""

from __future__ import annotations

import argparse

import _caminho  # noqa: F401  (ajusta o sys.path)

from src.data.dataset import (
    TAXONS_NEGATIVOS,
    TAXONS_POSITIVOS,
    baixar_inaturalist,
    resumo_manifesto,
)


def main() -> int:
    analisador = argparse.ArgumentParser(description="Baixa imagens para o treinamento.")
    analisador.add_argument("--limite", type=int, default=250, help="imagens por classe")
    analisador.add_argument("--destino", default="data/raw")
    analisador.add_argument("--apenas-positivos", action="store_true")
    analisador.add_argument(
        "--pausa", type=float, default=1.0, help="segundos entre páginas da API"
    )
    argumentos = analisador.parse_args()

    print("=" * 72)
    print("LionGuard AI — aquisição de imagens (iNaturalist)")
    print("=" * 72)

    total = 0

    for nome, taxon in TAXONS_POSITIVOS.items():
        print(f"\n[positivo] {nome} (taxon {taxon})...")
        resultado = baixar_inaturalist(
            taxon_id=taxon,
            classe="peixe_leao",
            destino=argumentos.destino,
            limite_imagens=argumentos.limite,
            pausa_segundos=argumentos.pausa,
        )
        total += resultado.baixadas
        print(
            f"  {resultado.baixadas} imagens baixadas · "
            f"{resultado.ignoradas_licenca} ignoradas por licença · "
            f"{resultado.ignoradas_erro} com erro · "
            f"{resultado.observacoes} observações percorridas"
        )

    if not argumentos.apenas_positivos:
        # Divide o limite entre os táxons negativos, para equilibrar as classes.
        por_taxon = max(10, argumentos.limite // len(TAXONS_NEGATIVOS))
        for nome, taxon in TAXONS_NEGATIVOS.items():
            print(f"\n[negativo] {nome} (taxon {taxon})...")
            resultado = baixar_inaturalist(
                taxon_id=taxon,
                classe="nao_peixe_leao",
                destino=argumentos.destino,
                limite_imagens=por_taxon,
                pausa_segundos=argumentos.pausa,
            )
            total += resultado.baixadas
            print(
                f"  {resultado.baixadas} imagens baixadas · "
                f"{resultado.ignoradas_licenca} ignoradas por licença"
            )

    print("\n" + "=" * 72)
    resumo = resumo_manifesto(f"{argumentos.destino}/manifesto.csv")
    if resumo.get("disponivel"):
        print(f"Manifesto: {resumo['arquivo']}")
        print(f"Total de imagens: {resumo['total_imagens']}")
        print(f"Por classe: {resumo['por_classe']}")
        print(f"Por licença: {resumo['por_licenca']}")
    print(f"\n{total} imagem(ns) nesta execução.")
    print("Próximo passo: python scripts/preparar_dataset.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
