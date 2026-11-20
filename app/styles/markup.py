"""
Normalização de HTML para o `st.markdown`.

Por que este módulo existe: o Streamlit passa o conteúdo por um renderizador
Markdown **antes** de liberar o HTML. No Markdown, uma linha com quatro espaços
de recuo é um bloco de código, e uma linha em branco encerra um bloco de HTML.
Resultado: um trecho escrito assim, que parece correto no editor…

    st.markdown(
        \"\"\"
        <div class="lg-card">...</div>
        \"\"\",
        unsafe_allow_html=True,
    )

…chega ao navegador como texto literal, com as tags à mostra. Como todo HTML
do projeto é escrito dentro de funções (e portanto indentado), a correção
precisa ser central, e não repetida em cada chamada.

`html` remove o recuo de todas as linhas e descarta as linhas em branco,
mantendo as quebras de linha como separador — que o HTML trata como espaço,
preservando o espaçamento entre palavras de um texto escrito em várias linhas.
"""

from __future__ import annotations

__all__ = ["html", "escrever_html"]


def html(marcacao: str) -> str:
    """
    Prepara um bloco de HTML para ser entregue ao `st.markdown`.

    Sem recuo (que viraria bloco de código) e sem linhas em branco (que
    encerrariam o bloco de HTML no meio).
    """
    return "\n".join(
        linha.strip() for linha in marcacao.strip().splitlines() if linha.strip()
    )


def escrever_html(st, marcacao: str) -> None:
    """Atalho para `st.markdown(html(...), unsafe_allow_html=True)`."""
    st.markdown(html(marcacao), unsafe_allow_html=True)
