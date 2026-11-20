"""
Testes do conteúdo educativo da área pública.

Duas exigências do escopo são verificadas aqui:

  1. **Nada inventado.** O conteúdo base não traz nenhum vídeo embutido — a
     lista nasce vazia justamente para não publicar um endereço que ninguém
     conferiu. Se alguém acrescentar um vídeo no futuro, ele passa pela
     validação de endereço antes de ser incorporado à página.
  2. **Degradação segura.** Um arquivo JSON ausente, ilegível ou malformado não
     derruba a página pública: o conteúdo base entra no lugar.
"""

from __future__ import annotations

import json

import pytest

from src.data.conteudo import (
    ConteudoEducativo,
    ItemIdentificacao,
    LinkOficial,
    Pergunta,
    Video,
    carregar_conteudo,
    gravar_modelo,
)


# ====================================================== validação de endereço
@pytest.mark.parametrize(
    "endereco",
    [
        "https://www.youtube.com/watch?v=abc123",
        "http://exemplo.org/video.mp4",
        "https://gov.br/icmbio/video",
    ],
)
def test_endereco_valido_e_aceito(endereco):
    assert Video(titulo="t", url=endereco).valido


@pytest.mark.parametrize(
    "endereco",
    [
        "",
        "   ",
        "youtube.com/watch?v=abc",  # sem esquema
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ftp://exemplo.org/video.mp4",
        "https://",  # sem host
        "[PREENCHER]",
    ],
)
def test_endereco_invalido_e_rejeitado(endereco):
    assert not Video(titulo="t", url=endereco).valido


def test_apenas_videos_validos_chegam_a_interface():
    conteudo = ConteudoEducativo(
        videos=[
            Video(titulo="ok", url="https://www.youtube.com/watch?v=aaa"),
            Video(titulo="placeholder", url="[PREENCHER]"),
            Video(titulo="sem esquema", url="exemplo.org/v"),
        ]
    )
    validos = conteudo.videos_validos

    assert [video.titulo for video in validos] == ["ok"]


# ======================================================= identificador YouTube
@pytest.mark.parametrize(
    "endereco,esperado",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=abc123&t=30s", "abc123"),
        ("https://youtu.be/abc123", "abc123"),
        ("https://www.youtube.com/embed/abc123", "abc123"),
        ("https://www.youtube.com/shorts/abc123", "abc123"),
        ("https://www.youtube.com/live/abc123", "abc123"),
        ("https://m.youtube.com/watch?v=abc123", "abc123"),
    ],
)
def test_identificador_do_youtube_e_extraido(endereco, esperado):
    assert Video(titulo="t", url=endereco).id_youtube == esperado


@pytest.mark.parametrize(
    "endereco",
    [
        "https://vimeo.com/123456",
        "https://exemplo.org/video.mp4",
        "https://www.youtube.com/",
        "https://www.youtube.com/watch",  # sem o parâmetro v
        "[PREENCHER]",
    ],
)
def test_endereco_que_nao_e_video_do_youtube_devolve_none(endereco):
    assert Video(titulo="t", url=endereco).id_youtube is None


# ============================================================= conteúdo base
def test_conteudo_base_nao_traz_video_inventado():
    """
    O escopo proíbe apresentar como real algo que não foi verificado. Nenhum
    endereço de vídeo é embutido no código — o grupo acrescenta o seu.
    """
    assert carregar_conteudo("caminho/que/nao/existe.json").videos == []


def test_conteudo_base_traz_links_oficiais_e_identificacao():
    conteudo = carregar_conteudo("caminho/que/nao/existe.json")

    assert len(conteudo.links_oficiais) >= 5
    assert len(conteudo.identificacao) >= 5
    assert len(conteudo.nao_confundir) >= 2
    assert len(conteudo.perguntas) >= 5


def test_todos_os_links_oficiais_tem_endereco_https():
    for link in carregar_conteudo("caminho/que/nao/existe.json").links_oficiais:
        assert link.url.startswith("https://"), link.titulo
        assert link.titulo.strip()
        assert link.organizacao.strip()


def test_nenhum_campo_do_conteudo_base_ficou_por_preencher():
    conteudo = carregar_conteudo("caminho/que/nao/existe.json")
    texto = json.dumps(
        {
            "links": [link.titulo + link.url + link.descricao for link in conteudo.links_oficiais],
            "ident": [i.caracteristica + i.descricao for i in conteudo.identificacao],
            "perguntas": [p.pergunta + p.resposta for p in conteudo.perguntas],
            "confundir": conteudo.nao_confundir,
        },
        ensure_ascii=False,
    )
    assert "PREENCHER" not in texto


def test_conteudo_base_nunca_orienta_captura():
    """Regra de segurança do escopo: a plataforma não manda ninguém pegar o peixe."""
    conteudo = carregar_conteudo("caminho/que/nao/existe.json")
    texto = " ".join(
        [p.pergunta + " " + p.resposta for p in conteudo.perguntas]
        + [i.descricao for i in conteudo.identificacao]
    ).lower()

    for proibido in ("capture o peixe", "pegue o peixe", "retire o animal"):
        assert proibido not in texto


# ============================================================ leitura do JSON
def test_arquivo_inexistente_cai_no_padrao(tmp_path):
    padrao = carregar_conteudo("nao/existe.json")
    assert carregar_conteudo(tmp_path / "ausente.json").perguntas == padrao.perguntas


def test_json_corrompido_cai_no_padrao(tmp_path):
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text("{isso não é json", encoding="utf-8")

    conteudo = carregar_conteudo(arquivo)

    assert len(conteudo.links_oficiais) >= 5


def test_json_que_nao_e_objeto_cai_no_padrao(tmp_path):
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text('["lista", "em vez", "de objeto"]', encoding="utf-8")

    assert len(carregar_conteudo(arquivo).identificacao) >= 5


def test_video_do_arquivo_e_incorporado(tmp_path):
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text(
        json.dumps(
            {
                "videos": [
                    {
                        "titulo": "Apresentação do projeto",
                        "url": "https://www.youtube.com/watch?v=xyz789",
                        "fonte": "Equipe LionGuard",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conteudo = carregar_conteudo(arquivo)

    assert len(conteudo.videos) == 1
    assert conteudo.videos[0].id_youtube == "xyz789"
    # Os demais campos continuam vindo do padrão.
    assert len(conteudo.links_oficiais) >= 5


def test_campo_desconhecido_no_arquivo_e_ignorado(tmp_path):
    """Um JSON editado à mão não deve quebrar a página por causa de um extra."""
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text(
        json.dumps(
            {
                "videos": [
                    {
                        "titulo": "t",
                        "url": "https://youtu.be/abc",
                        "campo_que_nao_existe": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    conteudo = carregar_conteudo(arquivo)

    assert len(conteudo.videos) == 1
    assert conteudo.videos[0].titulo == "t"


def test_entrada_malformada_na_lista_e_descartada(tmp_path):
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text(
        json.dumps(
            {
                "videos": [
                    "uma string em vez de objeto",
                    {"titulo": "válido", "url": "https://youtu.be/abc"},
                    {"sem_titulo_nem_url": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    videos = carregar_conteudo(arquivo).videos

    assert [video.titulo for video in videos] == ["válido"]


def test_lista_vazia_no_arquivo_substitui_o_padrao(tmp_path):
    """Quem escreve `[]` quer a seção vazia, não o padrão de volta."""
    arquivo = tmp_path / "conteudo.json"
    arquivo.write_text(json.dumps({"perguntas": []}), encoding="utf-8")

    assert carregar_conteudo(arquivo).perguntas == []


# ============================================================ modelo editável
def test_gravar_modelo_produz_json_legivel(tmp_path):
    destino = gravar_modelo(tmp_path / "sub" / "conteudo.json")

    assert destino.is_file()
    dados = json.loads(destino.read_text(encoding="utf-8"))

    assert dados["videos"] == []  # o modelo não inventa vídeo
    assert "_comentario" in dados
    assert len(dados["links_oficiais"]) >= 5


def test_modelo_gravado_pode_ser_lido_de_volta(tmp_path):
    destino = gravar_modelo(tmp_path / "conteudo.json")
    conteudo = carregar_conteudo(destino)

    assert isinstance(conteudo.links_oficiais[0], LinkOficial)
    assert isinstance(conteudo.identificacao[0], ItemIdentificacao)
    assert isinstance(conteudo.perguntas[0], Pergunta)
