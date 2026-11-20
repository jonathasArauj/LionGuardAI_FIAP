"""
Gerenciamento de conexão e transações com o banco de dados.

Regras importantes (seção 7.2 do escopo):
  * o banco **não** é recriado nem apagado a cada inicialização — apenas
    `CREATE TABLE IF NOT EXISTS`;
  * escritas acontecem dentro de transação explícita, com rollback em erro;
  * chaves estrangeiras são verificadas pelo SQLite (PRAGMA foreign_keys).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.config import get_config
from src.database.schema import DDL, INDICES, SCHEMA_VERSION

_local = threading.local()
_lock_inicializacao = threading.Lock()
_inicializados: set[str] = set()


def _caminho_banco(caminho: str | Path | None = None) -> str:
    if caminho is not None:
        return str(caminho)
    return get_config().database_url


def _configurar(conexao: sqlite3.Connection) -> None:
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute("PRAGMA synchronous = NORMAL")
    conexao.execute("PRAGMA busy_timeout = 5000")


def inicializar_banco(caminho: str | Path | None = None, forcar: bool = False) -> None:
    """Cria as tabelas e índices caso ainda não existam. Idempotente."""
    destino = _caminho_banco(caminho)
    with _lock_inicializacao:
        if destino in _inicializados and not forcar:
            return
        if destino != ":memory:":
            Path(destino).parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(destino)
        try:
            _configurar(conexao)
            with conexao:
                for comando in DDL:
                    conexao.execute(comando)
                for comando in INDICES:
                    conexao.execute(comando)
                conexao.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        finally:
            conexao.close()
        _inicializados.add(destino)


def obter_conexao(caminho: str | Path | None = None) -> sqlite3.Connection:
    """
    Conexão reutilizada por thread.

    O Streamlit executa cada interação em uma thread do seu pool; manter uma
    conexão por thread evita reabrir o arquivo a cada widget sem compartilhar
    conexão entre threads (o que o SQLite não permite por padrão).
    """
    destino = _caminho_banco(caminho)
    inicializar_banco(destino)
    cache: dict[str, sqlite3.Connection] = getattr(_local, "conexoes", None) or {}
    conexao = cache.get(destino)
    if conexao is None:
        conexao = sqlite3.connect(destino, check_same_thread=False)
        _configurar(conexao)
        cache[destino] = conexao
        _local.conexoes = cache
    return conexao


@contextmanager
def transacao(caminho: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """
    Transação explícita: commit no sucesso, rollback em qualquer exceção.

    Uso:
        with transacao() as con:
            con.execute(...)
    """
    conexao = obter_conexao(caminho)
    try:
        conexao.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        # Já existe transação aberta nesta conexão (uso aninhado): segue na mesma.
        yield conexao
        return
    try:
        yield conexao
    except Exception:
        conexao.rollback()
        raise
    else:
        conexao.commit()


def consultar(
    sql: str, parametros: tuple | dict = (), caminho: str | Path | None = None
) -> list[sqlite3.Row]:
    """Executa um SELECT e devolve todas as linhas."""
    return list(obter_conexao(caminho).execute(sql, parametros).fetchall())


def consultar_um(
    sql: str, parametros: tuple | dict = (), caminho: str | Path | None = None
) -> sqlite3.Row | None:
    return obter_conexao(caminho).execute(sql, parametros).fetchone()


def consultar_escalar(
    sql: str, parametros: tuple | dict = (), caminho: str | Path | None = None, padrao=0
):
    linha = consultar_um(sql, parametros, caminho)
    if linha is None or linha[0] is None:
        return padrao
    return linha[0]


def fechar_conexoes() -> None:
    """Fecha as conexões desta thread (usado em testes e no encerramento)."""
    cache: dict[str, sqlite3.Connection] = getattr(_local, "conexoes", None) or {}
    for conexao in cache.values():
        try:
            conexao.close()
        except Exception:  # pragma: no cover
            pass
    _local.conexoes = {}


def esquecer_inicializacao(caminho: str | Path | None = None) -> None:
    """Permite reinicializar um banco (usado em testes com arquivos temporários)."""
    with _lock_inicializacao:
        if caminho is None:
            _inicializados.clear()
        else:
            _inicializados.discard(str(caminho))
