"""
Testes da galeria de fotografias licenciadas.

O que importa verificar aqui é a **política de licenciamento**: nenhuma foto
sem licença Creative Commons aceita pode chegar à interface, e toda foto que
chega precisa levar autoria e link para a licença. A função de interpretação é
pura, então estes testes rodam sem rede, com uma resposta gravada que imita o
formato da API do iNaturalist.
"""

from __future__ import annotations

import pytest

from src.data.galeria import (
    LICENCAS_ACEITAS,
    NOMES_LICENCA,
    URLS_LICENCA,
    Foto,
    _trocar_tamanho,
    interpretar_observacoes,
    resumo_creditos,
)


def observacao(
    identificador: int = 1,
    licenca: str | None = "cc-by",
    autor: str | None = "Maria Fotógrafa",
    login: str | None = "maria",
    especie: str = "Pterois volitans",
    url: str = "https://static.inaturalist.org/photos/9/square.jpg",
    lugar: str | None = "Guarapari, ES, Brasil",
    quantidade_fotos: int = 1,
) -> dict:
    """Resposta mínima no formato da API, com os campos que o código lê."""
    return {
        "id": identificador,
        "taxon": {"name": especie},
        "user": {"name": autor, "login": login},
        "place_guess": lugar,
        "photos": [
            {"license_code": licenca, "url": url} for _ in range(quantidade_fotos)
        ],
    }


# =========================================================== política de licença
def test_foto_sem_licenca_e_descartada():
    fotos = interpretar_observacoes([observacao(licenca=None)])
    assert fotos == []


def test_licenca_proprietaria_e_descartada():
    """`None` no iNaturalist significa "todos os direitos reservados"."""
    fotos = interpretar_observacoes([observacao(licenca="c")])
    assert fotos == []


@pytest.mark.parametrize("licenca", LICENCAS_ACEITAS)
def test_todas_as_licencas_aceitas_passam(licenca):
    fotos = interpretar_observacoes([observacao(licenca=licenca)])
    assert len(fotos) == 1
    assert fotos[0].licenca == licenca


def test_licenca_em_maiuscula_tambem_e_aceita():
    """A API já devolve minúsculas, mas normalizar evita descarte indevido."""
    fotos = interpretar_observacoes([observacao(licenca="CC-BY-NC")])
    assert len(fotos) == 1
    assert fotos[0].licenca == "cc-by-nc"


def test_toda_licenca_aceita_tem_nome_e_url_cadastrados():
    """Sem isso a interface exibiria um link quebrado na atribuição."""
    for licenca in LICENCAS_ACEITAS:
        assert licenca in NOMES_LICENCA
        assert URLS_LICENCA[licenca].startswith("https://creativecommons.org/")


# ================================================================== atribuição
def test_foto_aceita_carrega_atribuicao_completa():
    foto = interpretar_observacoes([observacao(identificador=4242)])[0]

    assert foto.autor == "Maria Fotógrafa"
    assert foto.licenca_legivel == "CC BY"
    assert foto.url_licenca.startswith("https://creativecommons.org/licenses/by/")
    assert foto.url_observacao.endswith("/observations/4242")
    assert foto.especie == "Pterois volitans"
    assert foto.local == "Guarapari, ES, Brasil"


def test_credito_reune_autor_licenca_e_fonte():
    foto = interpretar_observacoes([observacao()])[0]
    credito = foto.credito

    assert "Maria Fotógrafa" in credito
    assert "CC BY" in credito
    assert "iNaturalist" in credito


def test_usa_login_quando_nao_ha_nome():
    foto = interpretar_observacoes([observacao(autor=None, login="joao_mergulho")])[0]
    assert foto.autor == "joao_mergulho"


def test_autor_desconhecido_nao_fica_vazio():
    """A licença exige atribuição; sem autor, o rótulo precisa dizer isso."""
    foto = interpretar_observacoes([observacao(autor=None, login=None)])[0]
    assert foto.autor.strip() != ""
    assert "não identificado" in foto.autor


def test_especie_ausente_cai_para_o_genero():
    bruta = observacao()
    bruta["taxon"] = {}
    foto = interpretar_observacoes([bruta])[0]
    assert foto.especie == "Pterois sp."


# ====================================================================== seleção
def test_uma_foto_por_observacao():
    """Várias fotos do mesmo animal deixariam a galeria repetitiva."""
    fotos = interpretar_observacoes([observacao(quantidade_fotos=5)])
    assert len(fotos) == 1


def test_limite_e_respeitado():
    entradas = [observacao(identificador=i) for i in range(20)]
    assert len(interpretar_observacoes(entradas, limite=6)) == 6


def test_lista_vazia_devolve_lista_vazia():
    assert interpretar_observacoes([]) == []


def test_observacao_sem_campo_photos_nao_quebra():
    bruta = observacao()
    del bruta["photos"]
    assert interpretar_observacoes([bruta]) == []


def test_foto_sem_url_e_descartada():
    assert interpretar_observacoes([observacao(url="")]) == []


# ================================================================== miniaturas
def test_miniatura_e_imagem_grande_usam_tamanhos_diferentes():
    foto = interpretar_observacoes([observacao()])[0]
    assert "/large." in foto.url
    assert "/medium." in foto.url_miniatura


def test_troca_de_tamanho_preserva_url_desconhecida():
    endereco = "https://exemplo.org/foto.jpg"
    assert _trocar_tamanho(endereco, "large") == endereco


# ===================================================================== créditos
def test_resumo_creditos_lista_licencas_distintas():
    fotos = interpretar_observacoes(
        [
            observacao(identificador=1, licenca="cc-by"),
            observacao(identificador=2, licenca="cc0"),
            observacao(identificador=3, licenca="cc-by"),
        ]
    )
    resumo = resumo_creditos(fotos)

    assert "3 fotografia(s)" in resumo
    assert "CC BY" in resumo
    assert "CC0" in resumo
    assert resumo.count("CC BY") == 1  # sem repetir a mesma licença


def test_resumo_creditos_vazio_quando_nao_ha_fotos():
    assert resumo_creditos([]) == ""


def test_foto_e_dataclass_com_slots():
    """Evita que um campo de atribuição seja criado por engano em runtime."""
    foto = Foto(
        url="u",
        url_miniatura="m",
        autor="a",
        licenca="cc0",
        url_licenca="l",
        especie="e",
        url_observacao="o",
    )
    with pytest.raises(AttributeError):
        foto.campo_inexistente = 1
