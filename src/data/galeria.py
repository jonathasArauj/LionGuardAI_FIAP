"""
Galeria de fotografias reais da espécie.

De onde vêm as imagens: da API pública do **iNaturalist**, em tempo de
execução, e **somente** observações com licença Creative Commons declarada. A
atribuição (autor, licença e link para a observação original) acompanha cada
foto na interface — é condição de uso dessas licenças, não enfeite.

Por que buscar em tempo de execução, e não guardar cópias no repositório:

  * o acervo melhora sozinho conforme a comunidade publica observações novas;
  * não redistribuímos arquivos de terceiros no nosso repositório;
  * a licença de cada foto é lida da fonte na hora, e não de uma anotação
    nossa que poderia envelhecer.

Sem internet, a galeria devolve lista vazia e a interface mostra a ilustração
própria do projeto no lugar — nunca uma imagem inventada.

Este módulo não depende do Streamlit, o que o torna testável isoladamente.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

API_INATURALIST = "https://api.inaturalist.org/v1/observations"

# Mesma política de licenças usada na montagem do dataset de treinamento.
LICENCAS_ACEITAS = ("cc0", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa")

NOMES_LICENCA = {
    "cc0": "CC0 (domínio público)",
    "cc-by": "CC BY",
    "cc-by-sa": "CC BY-SA",
    "cc-by-nc": "CC BY-NC",
    "cc-by-nc-sa": "CC BY-NC-SA",
}

URLS_LICENCA = {
    "cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by": "https://creativecommons.org/licenses/by/4.0/",
    "cc-by-sa": "https://creativecommons.org/licenses/by-sa/4.0/",
    "cc-by-nc": "https://creativecommons.org/licenses/by-nc/4.0/",
    "cc-by-nc-sa": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
}

# Táxon do gênero Pterois no iNaturalist (o mesmo usado no download do dataset).
TAXON_PEIXE_LEAO = 110_932

TAMANHOS = ("square", "small", "medium", "large")


@dataclass(slots=True)
class Foto:
    """Uma fotografia com a procedência completa."""

    url: str
    url_miniatura: str
    autor: str
    licenca: str
    url_licenca: str
    especie: str
    url_observacao: str
    local: str | None = None
    observacao_id: int | None = None

    @property
    def licenca_legivel(self) -> str:
        return NOMES_LICENCA.get(self.licenca, self.licenca.upper())

    @property
    def credito(self) -> str:
        """Linha de atribuição exigida pelas licenças Creative Commons."""
        return f"© {self.autor} · {self.licenca_legivel} · iNaturalist"


class GaleriaIndisponivel(Exception):
    """Não foi possível consultar a fonte das imagens."""


def _trocar_tamanho(url: str, tamanho: str) -> str:
    """As URLs do iNaturalist diferem apenas pelo sufixo de tamanho."""
    for conhecido in TAMANHOS:
        if f"/{conhecido}." in url:
            return url.replace(f"/{conhecido}.", f"/{tamanho}.")
    return url


def _consultar(parametros: dict, tempo_limite: int = 12) -> dict:
    endereco = f"{API_INATURALIST}?{urllib.parse.urlencode(parametros)}"
    requisicao = urllib.request.Request(
        endereco,
        headers={"User-Agent": "LionGuard-AI/1.0 (projeto academico FIAP)"},
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except Exception as erro:  # sem rede, limite de taxa, resposta inválida
        raise GaleriaIndisponivel(str(erro)) from erro


def interpretar_observacoes(resultados: Iterable[dict], limite: int = 12) -> list[Foto]:
    """
    Converte a resposta da API em fotos com atribuição.

    Função pura, separada da chamada de rede, para poder ser testada com uma
    resposta gravada. Descarta qualquer foto sem licença aceita — é aqui que a
    política de licenciamento é aplicada.
    """
    fotos: list[Foto] = []

    for observacao in resultados:
        if len(fotos) >= limite:
            break

        taxon = observacao.get("taxon") or {}
        usuario = observacao.get("user") or {}
        autor = usuario.get("name") or usuario.get("login") or "autor não identificado"
        especie = taxon.get("name") or "Pterois sp."
        observacao_id = observacao.get("id")

        for foto in observacao.get("photos", []) or []:
            if len(fotos) >= limite:
                break
            licenca = str(foto.get("license_code") or "").lower()
            if licenca not in LICENCAS_ACEITAS:
                continue
            url_bruta = str(foto.get("url") or "")
            if not url_bruta:
                continue

            fotos.append(
                Foto(
                    url=_trocar_tamanho(url_bruta, "large"),
                    url_miniatura=_trocar_tamanho(url_bruta, "medium"),
                    autor=autor,
                    licenca=licenca,
                    url_licenca=URLS_LICENCA.get(licenca, "https://creativecommons.org/"),
                    especie=especie,
                    url_observacao=f"https://www.inaturalist.org/observations/{observacao_id}",
                    local=observacao.get("place_guess"),
                    observacao_id=observacao_id,
                )
            )
            break  # uma foto por observação, para a galeria não repetir o mesmo animal

    return fotos


def buscar_fotos(
    limite: int = 8,
    taxon_id: int = TAXON_PEIXE_LEAO,
    apenas_brasil: bool = False,
    tempo_limite: int = 12,
) -> list[Foto]:
    """
    Busca fotografias licenciadas da espécie.

    `apenas_brasil=True` restringe às observações registradas no Brasil
    (place_id 6878 no iNaturalist), útil para ilustrar o contexto local.
    Levanta `GaleriaIndisponivel` se não conseguir consultar a API.
    """
    parametros = {
        "taxon_id": taxon_id,
        "quality_grade": "research",
        "photos": "true",
        "per_page": max(limite * 3, 30),
        "order_by": "votes",
        "locale": "pt-BR",
    }
    if apenas_brasil:
        parametros["place_id"] = 6878  # Brasil

    dados = _consultar(parametros, tempo_limite)
    return interpretar_observacoes(dados.get("results", []), limite=limite)


def resumo_creditos(fotos: list[Foto]) -> str:
    """Linha única de créditos, para rodapé de seção ou legenda de figura."""
    if not fotos:
        return ""
    licencas = sorted({foto.licenca_legivel for foto in fotos})
    return (
        f"{len(fotos)} fotografia(s) do iNaturalist sob "
        f"{', '.join(licencas)}. Autoria indicada em cada imagem."
    )
