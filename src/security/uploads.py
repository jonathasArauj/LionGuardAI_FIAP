"""
Validação de upload de imagens.

Camadas de verificação, da mais barata para a mais custosa:
  1. tamanho em bytes (limite configurável);
  2. assinatura binária do arquivo (magic bytes) — a extensão enviada pelo
     cliente nunca é confiável;
  3. decodificação real com Pillow (`verify` + `load`), o que rejeita arquivos
     truncados ou que apenas se parecem com imagem;
  4. limites de dimensão, que também barram "bombas de descompressão".

Tratamento de EXIF (seção 10): os metadados são **lidos** para informar o
usuário e, por padrão, **removidos** antes da gravação. Coordenadas EXIF nunca
são usadas automaticamente como localização do avistamento.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageOps, UnidentifiedImageError

from src.config import get_config

# Assinaturas binárias dos formatos aceitos.
_ASSINATURAS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
)

Image.MAX_IMAGE_PIXELS = 80_000_000  # proteção contra decompression bomb


class ImagemInvalida(Exception):
    """A imagem enviada não passou na validação."""


@dataclass(slots=True)
class ImagemValidada:
    conteudo: bytes
    formato: str
    largura: int
    altura: int
    tamanho_bytes: int
    exif_presente: bool
    exif_tinha_gps: bool
    exif_removido: bool
    coordenadas_exif: tuple[float, float] | None = None
    avisos: list[str] = field(default_factory=list)


def _detectar_formato(dados: bytes) -> str | None:
    for assinatura, formato in _ASSINATURAS:
        if dados.startswith(assinatura):
            return formato
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def _converter_gps(valor, referencia) -> float | None:
    """Converte graus/minutos/segundos do EXIF em grau decimal."""
    try:
        graus, minutos, segundos = (float(x) for x in valor)
    except (TypeError, ValueError):
        return None
    decimal = graus + minutos / 60.0 + segundos / 3600.0
    if str(referencia).upper() in {"S", "W"}:
        decimal = -decimal
    return decimal


def ler_coordenadas_exif(imagem: Image.Image) -> tuple[float, float] | None:
    """
    Extrai coordenadas do EXIF, se existirem.

    O valor é apenas **informado** ao usuário; a aplicação só o utiliza após
    autorização explícita na interface.
    """
    try:
        exif = imagem.getexif()
        if not exif:
            return None
        gps = exif.get_ifd(0x8825)  # GPSInfo
        if not gps:
            return None
        latitude = _converter_gps(gps.get(2), gps.get(1))
        longitude = _converter_gps(gps.get(4), gps.get(3))
        if latitude is None or longitude is None:
            return None
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None
        return (latitude, longitude)
    except Exception:  # pragma: no cover - EXIF malformado
        return None


def validar_imagem(dados: bytes, remover_exif: bool = True) -> ImagemValidada:
    """
    Valida e normaliza a imagem recebida.

    Levanta `ImagemInvalida` com mensagem legível para a interface.
    """
    config = get_config()
    avisos: list[str] = []

    if not dados:
        raise ImagemInvalida("Arquivo vazio. Tente enviar a foto novamente.")

    tamanho = len(dados)
    if tamanho > config.upload_max_bytes:
        limite_mb = config.upload_max_bytes / (1024 * 1024)
        raise ImagemInvalida(
            f"A imagem tem {tamanho / (1024 * 1024):.1f} MB e o limite é {limite_mb:.0f} MB."
        )

    formato = _detectar_formato(dados)
    if formato is None:
        raise ImagemInvalida("Formato não reconhecido. Envie uma foto JPEG, PNG ou WebP.")
    if formato not in config.upload_formatos:
        raise ImagemInvalida(f"Formato {formato} não aceito.")

    # Verificação de integridade: `verify` precisa de um buffer novo depois.
    try:
        Image.open(io.BytesIO(dados)).verify()
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise ImagemInvalida("O arquivo parece corrompido ou incompleto.") from erro

    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise ImagemInvalida("Não foi possível abrir a imagem.") from erro

    largura, altura = imagem.size
    if min(largura, altura) < config.upload_dimensao_minima:
        raise ImagemInvalida(
            f"Imagem muito pequena ({largura}x{altura}). "
            f"O mínimo é {config.upload_dimensao_minima} pixels no menor lado."
        )
    if max(largura, altura) > config.upload_dimensao_maxima:
        avisos.append(
            f"Imagem redimensionada de {largura}x{altura} para o limite de "
            f"{config.upload_dimensao_maxima} pixels."
        )
        imagem.thumbnail(
            (config.upload_dimensao_maxima, config.upload_dimensao_maxima), Image.LANCZOS
        )

    exif_bruto = imagem.info.get("exif")
    exif_presente = bool(exif_bruto) or bool(imagem.getexif())
    coordenadas = ler_coordenadas_exif(imagem)
    exif_tinha_gps = coordenadas is not None

    if not remover_exif:
        return ImagemValidada(
            conteudo=dados,
            formato=formato,
            largura=largura,
            altura=altura,
            tamanho_bytes=tamanho,
            exif_presente=exif_presente,
            exif_tinha_gps=exif_tinha_gps,
            exif_removido=False,
            coordenadas_exif=coordenadas,
            avisos=avisos,
        )

    # Reescreve a imagem sem metadados, respeitando a orientação original.
    imagem = ImageOps.exif_transpose(imagem)
    if imagem.mode not in ("RGB", "L"):
        imagem = imagem.convert("RGB")

    buffer = io.BytesIO()
    if formato == "png":
        imagem.save(buffer, format="PNG", optimize=True)
        formato_saida = "png"
    else:
        imagem.save(buffer, format="JPEG", quality=88, optimize=True)
        formato_saida = "jpeg"
    conteudo = buffer.getvalue()

    if exif_presente:
        avisos.append("Metadados da foto (incluindo EXIF) foram removidos antes de salvar.")

    return ImagemValidada(
        conteudo=conteudo,
        formato=formato_saida,
        largura=imagem.size[0],
        altura=imagem.size[1],
        tamanho_bytes=len(conteudo),
        exif_presente=exif_presente,
        exif_tinha_gps=exif_tinha_gps,
        exif_removido=True,
        coordenadas_exif=coordenadas,
        avisos=avisos,
    )
