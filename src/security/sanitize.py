"""
Saneamento de entradas: nomes de arquivo, texto livre e identificadores.

Objetivos (seção 10): impedir path traversal, limitar tamanho de texto e
remover caracteres de controle antes de gravar qualquer coisa no banco.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

_CARACTERES_PERMITIDOS = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

TAMANHO_MAXIMO_NOME = 120
TAMANHO_MAXIMO_DESCRICAO = 2000


class CaminhoInvalido(Exception):
    """Tentativa de acessar arquivo fora do diretório permitido."""


def sanitizar_nome_arquivo(nome: str | None) -> str:
    """
    Reduz o nome a um conjunto seguro de caracteres.

    Remove acentos, separadores de diretório e caracteres especiais. Nunca
    devolve string vazia nem nome iniciado por ponto.

    O resultado é guardado apenas para rastreabilidade (coluna
    `nome_original_sanitizado`): o arquivo em disco recebe um identificador
    gerado pela aplicação, e a resolução de caminhos passa por
    `caminho_seguro`, que recusa qualquer nome com separador. Por isso o
    saneamento preserva o máximo possível do nome informado, em vez de
    reduzi-lo ao último segmento — o que, em entradas como
    `foto;rm -rf /.JPG`, descartaria toda a informação útil.
    """
    if not nome:
        return "arquivo"
    bruto = str(nome)
    base = unicodedata.normalize("NFKD", bruto).encode("ascii", "ignore").decode("ascii")
    base = _CARACTERES_PERMITIDOS.sub("_", base)
    # Remove qualquer segmento de travessia que tenha sobrado como texto.
    base = re.sub(r"(^|_)\.{2,}(_|$)", "_", base).strip("._-")
    base = re.sub(r"_{2,}", "_", base)
    if not base:
        base = "arquivo"
    return base[:TAMANHO_MAXIMO_NOME]


def caminho_seguro(diretorio_base: Path, nome_arquivo: str) -> Path:
    """
    Resolve `nome_arquivo` dentro de `diretorio_base`, **recusando** escapes.

    Esta função é estrita de propósito: ela não reescreve silenciosamente um
    nome perigoso em um nome seguro. Um nome com separador de diretório, com
    `..` ou absoluto é rejeitado com `CaminhoInvalido`, porque nos pontos em
    que ela é usada o nome vem do banco (identificador gerado pela própria
    aplicação) — se chegar algo diferente disso, é sinal de problema, não de
    entrada a ser corrigida.

    Para nomes digitados pelo usuário, use `sanitizar_nome_arquivo` antes de
    gravar; é ela que reduz o nome a uma forma segura.
    """
    base = Path(diretorio_base).resolve()
    bruto = str(nome_arquivo or "")

    if not bruto.strip():
        raise CaminhoInvalido("nome de arquivo vazio")
    if "/" in bruto or "\\" in bruto:
        raise CaminhoInvalido(f"nome de arquivo não pode conter diretório: {bruto!r}")
    if ".." in Path(bruto).parts or bruto.startswith(("..", "~")):
        raise CaminhoInvalido(f"nome de arquivo com travessia de diretório: {bruto!r}")
    if Path(bruto).is_absolute():
        raise CaminhoInvalido(f"nome de arquivo absoluto não é aceito: {bruto!r}")

    destino = (base / bruto).resolve()
    # Dupla verificação: mesmo com o nome aprovado acima, o caminho resolvido
    # precisa continuar sob a base (protege contra links simbólicos).
    if base != destino and base not in destino.parents:
        raise CaminhoInvalido(f"caminho fora do diretório permitido: {bruto!r}")
    return destino


def limpar_texto(texto: str | None, maximo: int = TAMANHO_MAXIMO_DESCRICAO) -> str | None:
    """Remove caracteres de controle, normaliza espaços e corta no limite."""
    if texto is None:
        return None
    limpo = _CONTROLE.sub("", str(texto))
    limpo = re.sub(r"[ \t]+", " ", limpo)
    limpo = re.sub(r"\n{3,}", "\n\n", limpo).strip()
    return limpo[:maximo] or None


def hash_contato(contato: str | None) -> str | None:
    """
    Guarda apenas o hash de um contato opcional.

    Permite que o avaliador identifique reenvios do mesmo informante sem que
    telefone ou e-mail fiquem legíveis no banco.
    """
    if not contato or not contato.strip():
        return None
    return hashlib.sha256(contato.strip().lower().encode("utf-8")).hexdigest()
