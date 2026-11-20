"""
Armazenamento de imagens dos avistamentos.

Decisões:
  * o nome do arquivo gravado é gerado pela aplicação (UUID + formato), nunca
    o nome enviado pelo cliente — isso elimina a classe de ataques de path
    traversal e colisão de nomes;
  * o nome original é guardado apenas sanitizado, para rastreabilidade;
  * o conteúdo é identificado por SHA-256, o que permite detectar reenvio da
    mesma foto;
  * em produção na nuvem, substituir o backend local por armazenamento de
    objetos (ver `docs/deploy.md`) — a interface pública deste módulo não muda.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.config import get_config
from src.security.sanitize import caminho_seguro, sanitizar_nome_arquivo
from src.security.uploads import ImagemValidada

_EXTENSOES = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp"}


@dataclass(slots=True)
class ArquivoArmazenado:
    identificador_arquivo: str
    caminho: Path
    hash_sha256: str
    tamanho_bytes: int
    formato: str
    largura: int | None = None
    altura: int | None = None
    nome_original_sanitizado: str | None = None


def calcular_hash(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


class ArmazenamentoImagens:
    def __init__(self, diretorio: Path | str | None = None) -> None:
        self.diretorio = Path(diretorio) if diretorio else get_config().diretorio_imagens
        self.diretorio.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ escrita
    def salvar(
        self, imagem: ImagemValidada, nome_original: str | None = None
    ) -> ArquivoArmazenado:
        extensao = _EXTENSOES.get(imagem.formato, ".jpg")
        identificador = f"{uuid.uuid4().hex}{extensao}"
        destino = self.diretorio / identificador
        destino.write_bytes(imagem.conteudo)
        return ArquivoArmazenado(
            identificador_arquivo=identificador,
            caminho=destino,
            hash_sha256=calcular_hash(imagem.conteudo),
            tamanho_bytes=imagem.tamanho_bytes,
            formato=imagem.formato,
            largura=imagem.largura,
            altura=imagem.altura,
            nome_original_sanitizado=sanitizar_nome_arquivo(nome_original)
            if nome_original
            else None,
        )

    # ------------------------------------------------------------------ leitura
    def caminho_de(self, identificador_arquivo: str) -> Path:
        """Resolve o caminho do arquivo, recusando qualquer escape de diretório."""
        return caminho_seguro(self.diretorio, identificador_arquivo)

    def existe(self, identificador_arquivo: str) -> bool:
        try:
            return self.caminho_de(identificador_arquivo).is_file()
        except Exception:
            return False

    def ler(self, identificador_arquivo: str) -> bytes | None:
        try:
            caminho = self.caminho_de(identificador_arquivo)
        except Exception:
            return None
        return caminho.read_bytes() if caminho.is_file() else None

    def remover(self, identificador_arquivo: str) -> bool:
        try:
            caminho = self.caminho_de(identificador_arquivo)
        except Exception:
            return False
        if caminho.is_file():
            caminho.unlink()
            return True
        return False

    def espaco_utilizado_bytes(self) -> int:
        return sum(
            arquivo.stat().st_size for arquivo in self.diretorio.glob("*") if arquivo.is_file()
        )
