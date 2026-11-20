"""
Pré-processamento de imagens para o modelo de classificação.

O **mesmo** código roda no treinamento e na inferência. Divergência entre os
dois é a causa mais comum de modelo que acerta em teste e erra em produção, por
isso o redimensionamento, a ordem dos canais e a normalização ficam centralizados
aqui.

Pipeline:
  1. decodificação com Pillow e conversão para RGB;
  2. redimensionamento com preenchimento (*letterbox*) para manter a proporção
     — esticar a imagem distorce a silhueta das nadadeiras, que é justamente a
     característica discriminante do peixe-leão;
  3. conversão para float32 em [0, 1];
  4. normalização pela média e desvio do ImageNet (os pesos pré-treinados foram
     ajustados nessa escala);
  5. troca para o formato CHW usado pelo PyTorch/ONNX.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MEDIA_IMAGENET = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DESVIO_IMAGENET = np.array([0.229, 0.224, 0.225], dtype=np.float32)

COR_PREENCHIMENTO = (0, 0, 0)


class PreprocessamentoInvalido(Exception):
    """A imagem não pôde ser preparada para o modelo."""


@dataclass(slots=True)
class EntradaModelo:
    """Tensor de entrada e metadados da transformação aplicada."""

    tensor: np.ndarray  # (1, 3, H, W) float32
    largura_original: int
    altura_original: int
    escala: float
    deslocamento_x: int
    deslocamento_y: int

    def coordenada_para_original(self, x: float, y: float) -> tuple[float, float]:
        """
        Converte um ponto do espaço do modelo para o da imagem original.

        Necessário para desenhar caixas de detecção (YOLO) sobre a foto que o
        usuário enviou.
        """
        return (
            (x - self.deslocamento_x) / self.escala,
            (y - self.deslocamento_y) / self.escala,
        )


def abrir_imagem(dados: bytes) -> Image.Image:
    """Decodifica bytes em uma imagem RGB com orientação corrigida."""
    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise PreprocessamentoInvalido("Não foi possível decodificar a imagem.") from erro
    imagem = ImageOps.exif_transpose(imagem)
    if imagem.mode != "RGB":
        imagem = imagem.convert("RGB")
    return imagem


def letterbox(
    imagem: Image.Image, lado: int, cor=COR_PREENCHIMENTO
) -> tuple[Image.Image, float, int, int]:
    """
    Redimensiona preservando a proporção e preenche até `lado` x `lado`.

    Devolve `(imagem, escala, deslocamento_x, deslocamento_y)`.
    """
    largura, altura = imagem.size
    if largura <= 0 or altura <= 0:  # pragma: no cover - Pillow não produz isso
        raise PreprocessamentoInvalido("Dimensões inválidas.")

    escala = min(lado / largura, lado / altura)
    nova_largura = max(1, int(round(largura * escala)))
    nova_altura = max(1, int(round(altura * escala)))
    redimensionada = imagem.resize((nova_largura, nova_altura), Image.BILINEAR)

    tela = Image.new("RGB", (lado, lado), cor)
    deslocamento_x = (lado - nova_largura) // 2
    deslocamento_y = (lado - nova_altura) // 2
    tela.paste(redimensionada, (deslocamento_x, deslocamento_y))
    return tela, escala, deslocamento_x, deslocamento_y


def normalizar(array: np.ndarray) -> np.ndarray:
    """Aplica a normalização do ImageNet sobre um array HWC em [0, 1]."""
    return (array - MEDIA_IMAGENET) / DESVIO_IMAGENET


def preparar(dados: bytes, lado: int = 224) -> EntradaModelo:
    """Converte os bytes da foto no tensor de entrada do modelo."""
    imagem = abrir_imagem(dados)
    largura_original, altura_original = imagem.size
    tela, escala, dx, dy = letterbox(imagem, lado)

    array = np.asarray(tela, dtype=np.float32) / 255.0
    array = normalizar(array)
    tensor = np.transpose(array, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

    return EntradaModelo(
        tensor=np.ascontiguousarray(tensor),
        largura_original=largura_original,
        altura_original=altura_original,
        escala=escala,
        deslocamento_x=dx,
        deslocamento_y=dy,
    )


def preparar_lote(lista_dados: list[bytes], lado: int = 224) -> np.ndarray:
    """Prepara várias imagens em um único tensor (usado na avaliação)."""
    if not lista_dados:
        raise PreprocessamentoInvalido("Lote vazio.")
    tensores = [preparar(dados, lado).tensor for dados in lista_dados]
    return np.concatenate(tensores, axis=0)


def softmax(logits: np.ndarray) -> np.ndarray:
    """Softmax numericamente estável na última dimensão."""
    deslocado = logits - np.max(logits, axis=-1, keepdims=True)
    exponenciais = np.exp(deslocado)
    return exponenciais / np.sum(exponenciais, axis=-1, keepdims=True)


def sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


def estatisticas_imagem(dados: bytes) -> dict:
    """
    Métricas simples de qualidade da foto, usadas para avisar o usuário quando
    a imagem provavelmente não permite classificação confiável.

    Nitidez: variância do Laplaciano sobre a luminância — valores baixos
    indicam desfoque. Os limiares são heurísticos e estão documentados como
    tal; servem para orientar o usuário, não para classificar a espécie.
    """
    imagem = abrir_imagem(dados)
    cinza = np.asarray(imagem.convert("L"), dtype=np.float32)

    # Laplaciano 3x3 por convolução direta (sem dependência externa).
    nucleo = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    altura, largura = cinza.shape
    if altura < 3 or largura < 3:
        nitidez = 0.0
    else:
        janelas = np.lib.stride_tricks.sliding_window_view(cinza, (3, 3))
        nitidez = float(np.var(np.einsum("ijkl,kl->ij", janelas, nucleo)))

    return {
        "largura": imagem.size[0],
        "altura": imagem.size[1],
        "brilho_medio": round(float(np.mean(cinza)), 2),
        "contraste": round(float(np.std(cinza)), 2),
        "nitidez_laplaciano": round(nitidez, 2),
        "provavel_desfoque": nitidez < 60.0,
        "provavel_subexposicao": float(np.mean(cinza)) < 35.0,
    }
