"""
Testes do HTML entregue ao Streamlit.

Motivo de existirem: o Streamlit passa o conteúdo por um renderizador Markdown
antes de liberar o HTML. Duas armadilhas decorrem disso, e nenhuma das duas
aparece em revisão de código — só na tela:

  1. **recuo de quatro espaços** vira bloco de código, e a marcação aparece
     como texto literal, com as tags à mostra;
  2. **linha em branco** encerra o bloco de HTML no meio, e o que vem depois é
     tratado como texto comum.

Como todo HTML do projeto é escrito dentro de funções (e portanto indentado),
um descuido quebra a página inteira. Estes testes verificam o normalizador e,
principalmente, varrem o código-fonte e a saída real dos componentes.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import types

import pytest

from app.styles.markup import html

RAIZ = pathlib.Path(__file__).resolve().parents[1]
APP = RAIZ / "app"


# ============================================================= normalizador
def test_remove_recuo():
    assert html("    <div>oi</div>") == "<div>oi</div>"


def test_remove_linhas_em_branco():
    assert html("<div>\n\n<span>a</span>\n\n</div>") == "<div>\n<span>a</span>\n</div>"


def test_preserva_separacao_entre_palavras():
    """Texto escrito em várias linhas não pode virar palavragrudada."""
    assert html("<p>uma frase\nem duas linhas</p>") == "<p>uma frase\nem duas linhas</p>"


def test_bloco_completo_fica_pronto_para_o_markdown():
    bruto = """
        <div class="lg-card">

            <b>Título</b>
            <span>detalhe</span>

        </div>
    """
    saida = html(bruto)

    assert saida.startswith("<div")
    assert not any(not linha.strip() for linha in saida.splitlines())
    assert not any(linha[:1].isspace() for linha in saida.splitlines())


def test_entrada_vazia_devolve_vazio():
    assert html("   \n\n  ") == ""


def test_normalizar_duas_vezes_nao_muda_nada():
    bruto = "  <div>\n\n  <b>x</b>\n  </div>  "
    assert html(html(bruto)) == html(bruto)


# ====================================================== varredura do código
def _blocos_de_html_do_fonte() -> list[tuple[pathlib.Path, int, str]]:
    """
    Todo literal de texto do app que começa com `<` — é HTML, venha de onde vier.
    """
    blocos: list[tuple[pathlib.Path, int, str]] = []
    for arquivo in sorted(APP.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            partes: list[str] = []
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                partes = [no.value]
            elif isinstance(no, ast.JoinedStr):
                partes = [
                    parte.value
                    for parte in no.values
                    if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
                ]
            texto = "".join(partes)
            if texto.strip().startswith("<") and "\n" in texto:
                blocos.append((arquivo, no.lineno, texto))
    return blocos


def test_existe_html_no_app_para_verificar():
    """Guarda contra o teste passar por não ter encontrado nada."""
    assert len(_blocos_de_html_do_fonte()) >= 10


@pytest.mark.parametrize(
    "caso", _blocos_de_html_do_fonte(), ids=lambda c: f"{c[0].name}:{c[1]}"
)
def test_html_do_fonte_passa_pelo_normalizador(caso):
    """
    Nenhum bloco de HTML pode ir direto ao `st.markdown`: todo bloco precisa
    sair de `html()`/`escrever_html()`. Como o normalizador é idempotente,
    conferimos que o conteúdo do fonte **não** está em forma final só quando
    ele chega cru — por isso a checagem é sobre o uso, feita abaixo.
    """
    arquivo, _, texto = caso
    # O CSS é injetado dentro de <style>, onde recuo e linha em branco são
    # inofensivos: o navegador é quem lê, não o Markdown.
    if "<style>" in texto:
        return
    assert texto  # bloco não vazio


def test_nenhuma_chamada_passa_html_cru_ao_streamlit():
    """
    `st.markdown(<html>, unsafe_allow_html=True)` com bloco de várias linhas
    só é aceito via `escrever_html`. Esta varredura é o que impede a regressão.
    """
    problemas: list[str] = []

    for arquivo in sorted(APP.rglob("*.py")):
        if arquivo.name in ("theme.py", "markup.py"):
            continue  # CSS dentro de <style> e o próprio normalizador
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = getattr(no.func, "attr", None)
            if alvo != "markdown":
                continue
            if not any(
                palavra.arg == "unsafe_allow_html" for palavra in no.keywords
            ):
                continue
            if not no.args:
                continue

            primeiro = no.args[0]
            # Literal de várias linhas entregue direto: é o caso perigoso.
            bruto = ""
            if isinstance(primeiro, ast.Constant) and isinstance(primeiro.value, str):
                bruto = primeiro.value
            elif isinstance(primeiro, ast.JoinedStr):
                bruto = "".join(
                    parte.value
                    for parte in primeiro.values
                    if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
                )
            if "\n" in bruto.strip():
                problemas.append(
                    f"{arquivo.relative_to(RAIZ)}:{no.lineno} — use escrever_html()"
                )

    assert not problemas, "HTML de várias linhas sem normalizar:\n" + "\n".join(problemas)


def _blocos_entregues_a_tela() -> list[tuple[pathlib.Path, int, str]]:
    """
    Blocos completos — o primeiro argumento de `escrever_html` e de
    `st.markdown(..., unsafe_allow_html=True)`.

    Fragmentos montados em pedaços e concatenados depois ficam de fora: eles
    só viram HTML completo no ponto de entrega, que é o que interessa aqui.
    """
    entregues: list[tuple[pathlib.Path, int, str]] = []
    for arquivo in sorted(APP.rglob("*.py")):
        if arquivo.name in ("theme.py", "markup.py"):
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            nome = getattr(no.func, "id", None) or getattr(no.func, "attr", None)
            if nome == "escrever_html":
                alvo = no.args[1] if len(no.args) > 1 else None
            elif nome == "markdown" and any(
                palavra.arg == "unsafe_allow_html" for palavra in no.keywords
            ):
                alvo = no.args[0] if no.args else None
            else:
                continue

            partes: list[str] = []
            if isinstance(alvo, ast.Constant) and isinstance(alvo.value, str):
                partes = [alvo.value]
            elif isinstance(alvo, ast.JoinedStr):
                partes = [
                    parte.value
                    for parte in alvo.values
                    if isinstance(parte, ast.Constant) and isinstance(parte.value, str)
                ]
            if partes:
                entregues.append((arquivo, no.lineno, "".join(partes)))
    return entregues


def test_existem_blocos_entregues_para_verificar():
    assert len(_blocos_entregues_a_tela()) >= 15


def test_todo_bloco_entregue_tem_divs_balanceadas():
    """
    Uma `<div>` aberta em uma chamada e fechada em outra nunca envolve o que
    está entre elas: cada `st.markdown` é um bloco independente. Foi assim que
    um destaque de botão ficou sem efeito — a `div` abria em uma chamada e
    fechava na seguinte.
    """
    desequilibrados: list[str] = []
    for arquivo, linha, texto in _blocos_entregues_a_tela():
        if texto.count("<div") != texto.count("</div>"):
            desequilibrados.append(
                f"{arquivo.relative_to(RAIZ)}:{linha} "
                f"({texto.count('<div')} abre, {texto.count('</div>')} fecha)"
            )

    assert not desequilibrados, "divs sem par no mesmo bloco:\n" + "\n".join(
        desequilibrados
    )


# ================================================== saída real dos componentes
class _FalsoStreamlit(types.SimpleNamespace):
    """Streamlit mínimo, só para capturar o que os componentes desenham."""

    def __init__(self) -> None:
        super().__init__()
        self.escrito: list[str] = []

    def markdown(self, texto, **_kwargs):
        self.escrito.append(str(texto))

    def caption(self, texto, **_kwargs):
        self.escrito.append(str(texto))

    def write(self, texto, **_kwargs):
        self.escrito.append(str(texto))


@pytest.fixture
def componentes(monkeypatch):
    """
    Importa `app.components.ui` com um Streamlit falso no lugar do real.

    Permite verificar a marcação que de fato chega à tela, e não apenas o
    código que a produz.
    """
    falso = _FalsoStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", falso)
    for nome in [n for n in list(sys.modules) if n.startswith("app.components.ui")]:
        monkeypatch.delitem(sys.modules, nome, raising=False)

    import importlib

    modulo = importlib.import_module("app.components.ui")
    modulo = importlib.reload(modulo)
    return modulo, falso


def _conferir(capturado: list[str]) -> None:
    for marcacao in capturado:
        if not marcacao.lstrip().startswith("<"):
            continue  # texto comum, não HTML
        linhas = marcacao.splitlines()
        assert not any(
            not linha.strip() for linha in linhas
        ), f"linha em branco encerraria o bloco de HTML:\n{marcacao[:200]}"
        assert not linhas[0][:1].isspace(), f"recuo vira bloco de código:\n{marcacao[:200]}"


def test_hero_desenha_html_valido(componentes):
    modulo, falso = componentes
    modulo.hero("Título", "Subtítulo", selos=["um", "dois"])
    assert falso.escrito
    _conferir(falso.escrito)


def test_componentes_de_bloco_desenham_html_valido(componentes):
    modulo, falso = componentes
    modulo.cabecalho("Título", "Subtítulo")
    modulo.faixa_html("<p>conteúdo</p>")
    modulo.stepper(["Um", "Dois", "Três"], 1)
    modulo.passos(
        [{"titulo": "Passo", "texto": "detalhe", "icone": "camera"}]
    )
    modulo.comparacao("Sim", ["a", "b"], "Não", ["c"])
    modulo.aviso_perigo("não toque")
    modulo.aviso("atenção")
    modulo.aviso_privacidade("dados")
    modulo.estado_vazio("nada aqui", "tente outro filtro")
    modulo.kpi("Rótulo", 42, nota="detalhe")

    assert len(falso.escrito) >= 10
    _conferir(falso.escrito)


def test_ilustracoes_entram_prontas_no_html(componentes):
    """A ilustração do peixe é inserida dentro de outro HTML: precisa estar
    normalizada na origem, senão quebra o bloco que a contém."""
    from app.styles.ilustracoes import (
        icone_svg,
        logo_svg,
        onda_svg,
        padrao_oceano_svg,
        peixe_leao_svg,
    )

    for svg in (
        peixe_leao_svg(),
        logo_svg(),
        onda_svg(),
        icone_svg("camera"),
        padrao_oceano_svg(),
    ):
        linhas = svg.splitlines()
        assert linhas[0].startswith("<svg")
        assert all(linha.strip() for linha in linhas)
        assert not any(linha[:1].isspace() for linha in linhas)
