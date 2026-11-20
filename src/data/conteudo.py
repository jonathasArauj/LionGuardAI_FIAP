"""
Conteúdo educativo da área pública: vídeos, links oficiais, guia de
identificação e perguntas frequentes.

Separar conteúdo de código tem uma razão prática: o grupo pode trocar o texto,
acrescentar o vídeo da própria entrega ou incluir um link novo editando
`data/conteudo_educativo.json`, sem mexer na aplicação.

**Nenhum vídeo vem preenchido.** O sistema não inventa endereços: a lista de
vídeos começa vazia e a interface exibe um convite para adicioná-los. O vídeo
demonstrativo que o grupo precisa gravar para a entrega é justamente o primeiro
candidato a entrar aí.

Os links oficiais, esses sim, vêm preenchidos — foram conferidos e estão
citados na documentação do projeto.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ARQUIVO_PADRAO = Path("data/conteudo_educativo.json")

ESQUEMAS_ACEITOS = ("http", "https")


@dataclass(slots=True)
class Video:
    titulo: str
    url: str
    descricao: str = ""
    fonte: str = ""

    @property
    def valido(self) -> bool:
        try:
            endereco = urlparse(self.url)
        except ValueError:
            return False
        return endereco.scheme in ESQUEMAS_ACEITOS and bool(endereco.netloc)

    @property
    def id_youtube(self) -> str | None:
        """Identificador do vídeo no YouTube, quando for o caso."""
        try:
            endereco = urlparse(self.url)
        except ValueError:
            return None
        hospedeiro = endereco.netloc.lower().removeprefix("www.")
        if hospedeiro in ("youtu.be",):
            return endereco.path.lstrip("/") or None
        if hospedeiro in ("youtube.com", "m.youtube.com", "youtube-nocookie.com"):
            if endereco.path == "/watch":
                return (parse_qs(endereco.query).get("v") or [None])[0]
            for prefixo in ("/embed/", "/shorts/", "/live/"):
                if endereco.path.startswith(prefixo):
                    return endereco.path[len(prefixo) :].split("/")[0] or None
        return None


@dataclass(slots=True)
class LinkOficial:
    titulo: str
    url: str
    descricao: str = ""
    organizacao: str = ""


@dataclass(slots=True)
class ItemIdentificacao:
    """Uma característica usada para reconhecer a espécie."""

    caracteristica: str
    descricao: str
    icone: str = "lupa"


@dataclass(slots=True)
class Pergunta:
    pergunta: str
    resposta: str


@dataclass(slots=True)
class ConteudoEducativo:
    videos: list[Video] = field(default_factory=list)
    links_oficiais: list[LinkOficial] = field(default_factory=list)
    identificacao: list[ItemIdentificacao] = field(default_factory=list)
    nao_confundir: list[str] = field(default_factory=list)
    perguntas: list[Pergunta] = field(default_factory=list)

    @property
    def videos_validos(self) -> list[Video]:
        return [video for video in self.videos if video.valido]


# --------------------------------------------------------------- conteúdo base
def _conteudo_padrao() -> ConteudoEducativo:
    """
    Conteúdo que acompanha o projeto.

    Os links apontam para páginas institucionais e para as bases de dados
    citadas na documentação. A lista de vídeos fica vazia de propósito.
    """
    return ConteudoEducativo(
        videos=[],
        links_oficiais=[
            LinkOficial(
                titulo="ICMBio — manejo de espécies exóticas invasoras",
                url="https://www.gov.br/icmbio/",
                organizacao="ICMBio",
                descricao=(
                    "Portal do órgão federal responsável pela conservação da "
                    "biodiversidade e pelos planos de manejo da espécie."
                ),
            ),
            LinkOficial(
                titulo="Plano Emergencial de Monitoramento e Erradicação do Peixe-leão",
                url=(
                    "https://www.gov.br/icmbio/pt-br/assuntos/biodiversidade/"
                    "manejo-de-especies-exoticas-invasoras/guias-e-materiais-orientadores/"
                    "materias-diversos/plano_emergencial_peixe-leao_resex_arraial_do_cabo_2015.pdf"
                ),
                organizacao="ICMBio",
                descricao=(
                    "Documento que embasa o projeto, inclusive o reconhecimento de "
                    "que métodos padronizados têm baixa probabilidade de detectar "
                    "a espécie no início da invasão."
                ),
            ),
            LinkOficial(
                titulo="Guia Estratégico do Peixe-leão",
                url=(
                    "https://www.icmbio.gov.br/cbc/images/stories/"
                    "Guia_Estrat%C3%A9gico_Peixe-Le%C3%A3o_2.pdf"
                ),
                organizacao="ICMBio",
                descricao="Orientações sobre identificação, riscos e resposta.",
            ),
            LinkOficial(
                titulo="Primeiro registro no Espírito Santo",
                url=(
                    "https://iema.es.gov.br/peixe-leao-e-registrado-pela-primeira-vez-"
                    "no-espirito-santo-na-ilha-escavada-em-guarapari"
                ),
                organizacao="Iema (ES)",
                descricao=(
                    "Registro de 14/11/2026 na Ilha Escalvada, em Guarapari, feito "
                    "por uma equipe de mergulho recreativo."
                ),
            ),
            LinkOficial(
                titulo="ODS 14 — Vida na Água",
                url="https://brasil.un.org/pt-br/sdgs/14",
                organizacao="ONU Brasil",
                descricao="Objetivo de Desenvolvimento Sustentável a que o projeto se liga.",
            ),
            LinkOficial(
                titulo="iNaturalist — observações do gênero Pterois",
                url="https://www.inaturalist.org/taxa/110932",
                organizacao="iNaturalist",
                descricao=(
                    "Base colaborativa de observações; origem das fotografias "
                    "licenciadas exibidas nesta plataforma."
                ),
            ),
            LinkOficial(
                titulo="GBIF — ocorrências registradas",
                url="https://www.gbif.org/species/search?q=Pterois%20volitans",
                organizacao="GBIF",
                descricao="Infraestrutura global de dados de biodiversidade.",
            ),
        ],
        identificacao=[
            ItemIdentificacao(
                caracteristica="Nadadeiras em leque, muito longas",
                descricao=(
                    "As peitorais se abrem como asas e os espinhos dorsais ficam "
                    "soltos nas pontas. É a característica mais fácil de notar, "
                    "mesmo de longe e com água turva."
                ),
                icone="lupa",
            ),
            ItemIdentificacao(
                caracteristica="Faixas verticais alternadas",
                descricao=(
                    "Listras avermelhadas ou marrons alternadas com faixas claras, "
                    "percorrendo o corpo inteiro, inclusive a cabeça."
                ),
                icone="camera",
            ),
            ItemIdentificacao(
                caracteristica="18 espinhos venenosos",
                descricao=(
                    "Treze dorsais, três anais e dois pélvicos. Não são usados para "
                    "atacar, mas a picada acidental é intensamente dolorosa."
                ),
                icone="aviso",
            ),
            ItemIdentificacao(
                caracteristica="Não foge quando se aproxima",
                descricao=(
                    "Costuma permanecer parado junto a tocas, pedras e estruturas, "
                    "o que facilita a fotografia — e aumenta o risco de contato."
                ),
                icone="relogio",
            ),
            ItemIdentificacao(
                caracteristica="Tentáculos acima dos olhos",
                descricao=(
                    "Pequenos apêndices carnudos sobre os olhos, visíveis em fotos "
                    "de perto."
                ),
                icone="lupa",
            ),
            ItemIdentificacao(
                caracteristica="Entre 15 e 40 cm",
                descricao=(
                    "O exemplar registrado no Espírito Santo tinha cerca de 15 cm, "
                    "a 9,4 metros de profundidade."
                ),
                icone="grafico",
            ),
        ],
        nao_confundir=[
            "Peixes-escorpião nativos (família Scorpaenidae) — também têm espinhos "
            "venenosos, mas são camuflados, de cor parda e sem as nadadeiras longas "
            "em leque.",
            "Peixes-anjo e peixes-borboleta — têm faixas, mas o corpo é achatado e "
            "alto, e as nadadeiras são curtas.",
            "Na dúvida, registre assim mesmo: a validação é feita por avaliador "
            "humano, e um registro a mais custa uma conferência, enquanto um "
            "registro a menos custa uma ocorrência não detectada.",
        ],
        perguntas=[
            Pergunta(
                "Preciso criar conta para registrar?",
                "Não. O registro é público e anônimo. Nenhum dado pessoal é "
                "solicitado, e o campo de contato é opcional — quando preenchido, "
                "guardamos apenas um código derivado dele, nunca o contato em si.",
            ),
            Pergunta(
                "O que acontece depois que eu registro?",
                "O avistamento entra com status **pendente de validação**. Um "
                "avaliador analisa a foto e os dados do local e decide se confirma, "
                "rejeita ou marca como inconclusivo, sempre com justificativa "
                "registrada. Acompanhe pelo protocolo que você recebe.",
            ),
            Pergunta(
                "A inteligência artificial decide sozinha?",
                "Não. A IA faz uma triagem preliminar e nunca confirma uma "
                "ocorrência: mesmo com score alto, o registro entra como pendente. "
                "Se o modelo estiver indisponível, o sistema avisa e grava o "
                "registro assim mesmo, para revisão humana.",
            ),
            Pergunta(
                "E se a IA não identificar o peixe na minha foto?",
                "Você ainda pode registrar. “Não identificado” significa que o "
                "modelo não reconheceu a espécie naquela imagem — e não que a "
                "espécie não esteja lá. Fotos subaquáticas variam muito em "
                "iluminação, distância e turbidez.",
            ),
            Pergunta(
                "Minha localização exata fica pública?",
                "Não. No mapa público as posições aparecem arredondadas em cerca de "
                "1 km, o que protege pontos de mergulho específicos. A coordenada "
                "precisa fica acessível apenas a perfis autorizados.",
            ),
            Pergunta(
                "O GPS não está funcionando. Posso registrar mesmo assim?",
                "Sim. Se a permissão for negada ou o navegador não liberar o GPS "
                "(ele exige conexão segura, por HTTPS), você marca o ponto no mapa "
                "ou informa apenas estado e município. O sistema diferencia essas "
                "origens e nunca trata uma região aproximada como leitura de GPS.",
            ),
            Pergunta(
                "Devo capturar ou matar o animal?",
                "**Não.** Mantenha distância, não toque e não tente capturar. Os "
                "espinhos são venenosos. Ações de manejo e remoção cabem aos órgãos "
                "competentes e a profissionais autorizados. Em caso de acidente, "
                "procure atendimento médico.",
            ),
            Pergunta(
                "Esta plataforma é oficial?",
                "Não. É um protótipo acadêmico da Global Solution 2026.2 da FIAP, "
                "sem vínculo, homologação ou parceria com ICMBio, Iema ou qualquer "
                "órgão ambiental. Registre aqui, mas comunique também o órgão "
                "ambiental do seu estado.",
            ),
        ],
    )


# ------------------------------------------------------------------- leitura
def carregar_conteudo(caminho: Path | str | None = None) -> ConteudoEducativo:
    """
    Lê o conteúdo educativo do arquivo JSON, caindo no padrão quando necessário.

    Campos ausentes no arquivo recebem o valor padrão; campos presentes
    substituem o padrão. Um arquivo ilegível não derruba a página: o conteúdo
    base é usado no lugar.
    """
    padrao = _conteudo_padrao()
    arquivo = Path(caminho) if caminho else ARQUIVO_PADRAO
    if not arquivo.is_file():
        return padrao

    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return padrao
    if not isinstance(dados, dict):
        return padrao

    def _lista(chave: str, classe, atual):
        bruto = dados.get(chave)
        if not isinstance(bruto, list):
            return atual
        itens = []
        for elemento in bruto:
            if not isinstance(elemento, dict):
                continue
            campos = {c.name for c in classe.__dataclass_fields__.values()}
            try:
                itens.append(classe(**{k: v for k, v in elemento.items() if k in campos}))
            except TypeError:
                continue
        return itens

    return ConteudoEducativo(
        videos=_lista("videos", Video, padrao.videos),
        links_oficiais=_lista("links_oficiais", LinkOficial, padrao.links_oficiais),
        identificacao=_lista("identificacao", ItemIdentificacao, padrao.identificacao),
        nao_confundir=(
            dados["nao_confundir"]
            if isinstance(dados.get("nao_confundir"), list)
            else padrao.nao_confundir
        ),
        perguntas=_lista("perguntas", Pergunta, padrao.perguntas),
    )


def gravar_modelo(caminho: Path | str | None = None) -> Path:
    """
    Grava um arquivo de conteúdo com o padrão do projeto, pronto para editar.

    Útil para o grupo acrescentar o vídeo da entrega sem precisar escrever o
    JSON do zero.
    """
    destino = Path(caminho) if caminho else ARQUIVO_PADRAO
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteudo = asdict(_conteudo_padrao())
    conteudo["_comentario"] = (
        "Conteúdo educativo da área pública. Para exibir vídeos na página "
        "inicial, acrescente objetos em 'videos' com titulo, url, descricao e "
        "fonte. O vídeo demonstrativo da entrega é o primeiro candidato."
    )
    conteudo["videos"] = []
    destino.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destino
