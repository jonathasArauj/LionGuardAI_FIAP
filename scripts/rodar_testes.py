#!/usr/bin/env python3
"""
Executa a suíte de testes e grava o resultado em `reports/`.

O arquivo gerado (`reports/testes_execucao.md`) traz a saída real do Pytest,
com data, versão do Python e contagem por arquivo — é a evidência de teste da
entrega. Nenhum resultado é escrito à mão.

Uso:
    python scripts/rodar_testes.py
    python scripts/rodar_testes.py -k seguranca     # repassa argumentos ao pytest
"""

from __future__ import annotations

import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    extras = sys.argv[1:]
    comando = [sys.executable, "-m", "pytest", "-v", "--tb=short", *extras]

    print("Executando:", " ".join(comando))
    processo = subprocess.run(
        comando, cwd=RAIZ, capture_output=True, text=True, check=False
    )
    saida = processo.stdout + ("\n" + processo.stderr if processo.stderr.strip() else "")
    print(saida)

    # Resumo por arquivo de teste, a partir da saída verbosa.
    por_arquivo: dict[str, dict[str, int]] = {}
    for linha in saida.splitlines():
        if "::" not in linha:
            continue
        arquivo = linha.split("::")[0].strip()
        if not arquivo.endswith(".py"):
            continue
        contagem = por_arquivo.setdefault(arquivo, {"PASSED": 0, "FAILED": 0, "SKIPPED": 0})
        for estado in ("PASSED", "FAILED", "SKIPPED"):
            if estado in linha:
                contagem[estado] += 1
                break

    ultima_linha = next(
        (
            linha
            for linha in reversed(saida.splitlines())
            if "passed" in linha or "failed" in linha or "error" in linha
        ),
        "(resumo não localizado)",
    )

    destino = RAIZ / "reports" / "testes_execucao.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteudo = [
        "# LionGuard AI — execução da suíte de testes",
        "",
        f"- **Data/hora:** {datetime.now().replace(microsecond=0).isoformat()}",
        f"- **Python:** {sys.version.split()[0]}",
        f"- **Sistema:** {platform.system()} {platform.release()} ({platform.machine()})",
        f"- **Comando:** `{' '.join(comando[1:])}`",
        f"- **Código de saída:** {processo.returncode} "
        f"({'todos os testes passaram' if processo.returncode == 0 else 'houve falha'})",
        f"- **Resumo do Pytest:** `{ultima_linha.strip()}`",
        "",
        "## Resultado por arquivo",
        "",
        "| Arquivo | Passou | Falhou | Ignorado |",
        "| --- | --- | --- | --- |",
    ]
    for arquivo in sorted(por_arquivo):
        contagem = por_arquivo[arquivo]
        conteudo.append(
            f"| `{arquivo}` | {contagem['PASSED']} | {contagem['FAILED']} | "
            f"{contagem['SKIPPED']} |"
        )
    conteudo += [
        "",
        "## Saída completa",
        "",
        "```text",
        saida.rstrip(),
        "```",
        "",
    ]
    destino.write_text("\n".join(conteudo), encoding="utf-8")
    print(f">>> Relatório gravado em {destino}")
    return processo.returncode


if __name__ == "__main__":
    raise SystemExit(main())
