"""
Envio da fotografia: câmera do celular ou galeria.

`st.camera_input` abre a câmera do dispositivo; `st.file_uploader` permite
escolher uma imagem já existente. As duas entradas passam pela **mesma**
validação de segurança (`src.security.uploads.validar_imagem`), que confere
assinatura binária, integridade, dimensões e remove os metadados EXIF.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from src.config import get_config
from src.security.uploads import ImagemInvalida, ImagemValidada, validar_imagem


@dataclass(slots=True)
class FotoEnviada:
    validada: ImagemValidada
    bytes_originais: bytes
    nome_arquivo: str | None
    origem: str  # "camera" | "galeria"


def componente_foto(prefixo: str = "foto") -> FotoEnviada | None:
    """
    Renderiza as duas formas de envio e devolve a foto validada.

    Devolve `None` quando ainda não há foto ou quando a validação falhou (nesse
    caso a mensagem de erro já foi exibida ao usuário).
    """
    config = get_config()
    limite_mb = config.upload_max_bytes / (1024 * 1024)

    aba_camera, aba_galeria = st.tabs(["📷 Tirar foto agora", "🖼️ Enviar da galeria"])

    arquivo = None
    origem = "camera"

    with aba_camera:
        st.caption(
            "Ao tocar no botão, o navegador pedirá acesso à câmera. "
            "Fotografe o animal **de longe**, sem tentar se aproximar."
        )
        arquivo_camera = st.camera_input(
            "Fotografar o possível peixe-leão",
            key=f"{prefixo}_camera",
            label_visibility="collapsed",
        )
        if arquivo_camera is not None:
            arquivo, origem = arquivo_camera, "camera"

    with aba_galeria:
        st.caption(
            f"Formatos aceitos: JPEG, PNG e WebP. Tamanho máximo: {limite_mb:.0f} MB."
        )
        arquivo_galeria = st.file_uploader(
            "Escolher imagem do aparelho",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"{prefixo}_arquivo",
            label_visibility="collapsed",
            accept_multiple_files=False,
        )
        if arquivo_galeria is not None and arquivo is None:
            arquivo, origem = arquivo_galeria, "galeria"

    if arquivo is None:
        return None

    dados = arquivo.getvalue()

    # Pré-visualização imediata, antes de qualquer processamento.
    st.image(dados, caption="Foto enviada", use_container_width=True)

    try:
        with st.spinner("Verificando a imagem..."):
            validada = validar_imagem(dados, remover_exif=True)
    except ImagemInvalida as erro:
        st.error(f"❌ {erro}")
        st.caption("Envie outra foto — nenhum dado do formulário foi perdido.")
        return None

    for mensagem in validada.avisos:
        st.caption(f"ℹ️ {mensagem}")

    return FotoEnviada(
        validada=validada,
        bytes_originais=dados,
        nome_arquivo=getattr(arquivo, "name", None),
        origem=origem,
    )


def limpar_estado_foto(prefixo: str = "foto") -> None:
    for chave in (f"{prefixo}_camera", f"{prefixo}_arquivo"):
        st.session_state.pop(chave, None)
