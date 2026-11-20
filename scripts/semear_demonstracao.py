#!/usr/bin/env python3
"""
Gera (ou remove) os dados de demonstração.

Todos os registros criados recebem `tipo_dado = DEMO`, não têm imagem nem
predição de IA e podem ser excluídos por filtro em qualquer painel. Eles não
representam ocorrências reais.

Uso:
    python scripts/semear_demonstracao.py                 # 120 registros
    python scripts/semear_demonstracao.py --quantidade 300 --semente 7
    python scripts/semear_demonstracao.py --remover
"""

from __future__ import annotations

import argparse

import _caminho  # noqa: F401

from src.data.demo_seed import GeradorDemonstracao
from src.database.connection import inicializar_banco
from src.security.auth import ServicoAutenticacao


def main() -> int:
    analisador = argparse.ArgumentParser(description="Dados de demonstração.")
    analisador.add_argument("--quantidade", type=int, default=120)
    analisador.add_argument("--semente", type=int, default=20262)
    analisador.add_argument("--remover", action="store_true")
    argumentos = analisador.parse_args()

    inicializar_banco()
    gerador = GeradorDemonstracao()

    if argumentos.remover:
        removidos = gerador.remover()
        print(f"{removidos} registro(s) de demonstração removido(s).")
        return 0

    credenciais = ServicoAutenticacao().garantir_usuarios_iniciais()
    for linha in credenciais:
        print(f"conta criada -> {linha}")

    resultado = gerador.gerar(quantidade=argumentos.quantidade, semente=argumentos.semente)
    print(resultado.mensagem)
    if resultado.ja_existentes:
        print(
            f"{resultado.ja_existentes} registro(s) já existiam com esta semente "
            "(operação idempotente)."
        )
    print(
        "\nLembrete: estes dados são rotulados como DEMO e existem apenas para "
        "demonstrar os painéis. Não indicam ocorrência real em nenhum município."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
