"""
Apresentação do resultado da identificação automática.

Compromissos de honestidade na interface:
  * "não identificado" nunca é apresentado como "a espécie não está na imagem";
  * o score aparece acompanhado da advertência de que não é probabilidade
    calibrada;
  * quando o modelo está indisponível, isso é dito com clareza e o registro
    continua possível;
  * caixas de detecção só são desenhadas se o modelo em uso for um detector —
    um classificador nunca ganha caixas fictícias.
"""

from __future__ import annotations

import streamlit as st

from app.components.ui import etiqueta_classe_ia
from src.ai.inference import ResultadoInferencia
from src.database.schema import ClassePredicao


def mostrar_resultado(resultado: ResultadoInferencia, mostrar_detalhes: bool = True) -> None:
    """Renderiza o resultado da inferência de forma legível no celular."""
    st.markdown("#### 🤖 Identificação automática")
    if "experimental" in resultado.versao.lower():
        st.warning(
            "**Modelo experimental não validado:** treinado com poucas imagens "
            "de referência, sem avaliação independente. O resultado pode estar errado. "
            "A confirmação depende de especialista; não use para capturar ou manipular animais."
        )
    st.markdown(
        etiqueta_classe_ia(str(resultado.classe), resultado.score), unsafe_allow_html=True
    )

    if resultado.classe == ClassePredicao.PEIXE_LEAO:
        st.warning(resultado.mensagem_usuario)
    elif resultado.classe == ClassePredicao.INCONCLUSIVO:
        st.info(resultado.mensagem_usuario)
    elif resultado.classe == ClassePredicao.NAO_PEIXE_LEAO:
        st.info(resultado.mensagem_usuario)
    else:
        st.warning(resultado.mensagem_usuario)

    if resultado.score is not None:
        st.caption(
            f"Score do modelo: **{resultado.score_percentual}** "
            f"(limiar de positivo: {resultado.limiar_positivo:.0%}; "
            f"abaixo de {resultado.limiar_inconclusivo:.0%} é tratado como não "
            "identificado). O score é a saída do modelo e **não** é uma "
            "probabilidade calibrada."
        )

    qualidade = resultado.qualidade_imagem or {}
    if qualidade.get("provavel_desfoque"):
        st.caption(
            "📷 A imagem parece desfocada, o que reduz a confiança da análise. "
            "Se possível, envie uma foto mais nítida."
        )
    if qualidade.get("provavel_subexposicao"):
        st.caption("📷 A imagem está escura, o que dificulta a identificação.")

    if resultado.caixas:
        st.caption(f"{len(resultado.caixas)} indivíduo(s) localizado(s) pelo detector.")

    if mostrar_detalhes and resultado.disponivel:
        texto_caixas = (
            f"sim ({len(resultado.caixas)})"
            if resultado.caixas
            else "não — o modelo é um classificador e não localiza indivíduos na imagem"
        )
        tempo = (
            f"{resultado.tempo_inferencia_ms:.1f} ms"
            if resultado.tempo_inferencia_ms is not None
            else "—"
        )
        with st.expander("Detalhes técnicos da análise"):
            st.markdown(
                f"- **Modelo:** {resultado.modelo}\n"
                f"- **Versão:** {resultado.versao}\n"
                f"- **Tempo de inferência:** {tempo}\n"
                f"- **Resolução analisada:** "
                f"{qualidade.get('largura', '—')}×{qualidade.get('altura', '—')} px\n"
                f"- **Caixas de detecção:** {texto_caixas}"
            )

    if resultado.erro:
        with st.expander("Diagnóstico do erro"):
            st.code(resultado.erro)

    st.caption(
        "A decisão final é sempre humana: todo registro entra como "
        "**pendente de validação** e é revisado por um avaliador."
    )


def desenhar_caixas(imagem_bytes: bytes, resultado: ResultadoInferencia) -> bytes:
    """
    Desenha as caixas de detecção sobre a foto original.

    Só tem efeito quando o modelo é um detector. Com um classificador, devolve a
    imagem inalterada — nenhuma caixa é inventada.
    """
    if not resultado.caixas:
        return imagem_bytes

    import io

    from PIL import Image, ImageDraw

    from app.styles.theme import VERMELHO

    imagem = Image.open(io.BytesIO(imagem_bytes)).convert("RGB")
    desenho = ImageDraw.Draw(imagem)
    for caixa in resultado.caixas:
        desenho.rectangle(
            [(caixa.x1, caixa.y1), (caixa.x2, caixa.y2)], outline=VERMELHO, width=4
        )
        desenho.text((caixa.x1 + 6, max(0, caixa.y1 - 16)), f"{caixa.score:.0%}", fill=VERMELHO)

    saida = io.BytesIO()
    imagem.save(saida, format="JPEG", quality=90)
    return saida.getvalue()
