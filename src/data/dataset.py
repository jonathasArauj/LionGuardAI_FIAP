"""
Construção do dataset de imagens.

Duas etapas independentes:

1. **Aquisição** (`baixar_inaturalist`): consulta a API pública do iNaturalist e
   baixa fotografias de observações com grau de pesquisa, registrando no
   manifesto a fonte, a URL, a licença, o autor, a espécie, o identificador da
   observação e a data de aquisição. Somente licenças Creative Commons
   explícitas são aceitas; observações sem licença declarada são ignoradas.
   Esta etapa **exige acesso à internet** e é executada na máquina do usuário.

2. **Preparação** (`preparar_dataset`): valida, remove duplicatas por hash e
   divide em treino/validação/teste. A divisão é feita **por observação**
   (agrupada), nunca por imagem: duas fotos do mesmo peixe no mesmo dia são
   quase idênticas e, separadas entre treino e teste, inflariam
   artificialmente as métricas. Esta etapa é offline e determinística.

Referências de origem dos dados: iNaturalist (https://www.inaturalist.org) e
GBIF (https://www.gbif.org).
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CLASSES = ("nao_peixe_leao", "peixe_leao")
EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".webp")

API_INATURALIST = "https://api.inaturalist.org/v1/observations"

# Licenças aceitas: permitem uso com atribuição. `None` (sem licença declarada)
# é recusado de propósito.
LICENCAS_ACEITAS = ("cc0", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa")

# Táxons usados na POC. O positivo é o gênero Pterois; os negativos são peixes
# recifais que convivem no mesmo ambiente — negativos "difíceis", que ensinam o
# modelo a discriminar de verdade em vez de reagir a "foto subaquática".
TAXONS_POSITIVOS = {"Pterois": 110_932}
TAXONS_NEGATIVOS = {
    "Scorpaenidae": 50_827,
    "Pomacanthidae": 49_251,
    "Chaetodontidae": 49_250,
    "Serranidae": 49_116,
    "Labridae": 49_119,
}

CABECALHO_MANIFESTO = (
    "arquivo",
    "classe",
    "especie",
    "fonte",
    "url",
    "licenca",
    "autor",
    "observacao_id",
    "imagem_id",
    "data_aquisicao",
    "hash_sha256",
)


@dataclass
class ResultadoAquisicao:
    classe: str
    baixadas: int = 0
    ignoradas_licenca: int = 0
    ignoradas_erro: int = 0
    observacoes: int = 0
    manifesto: str | None = None
    erros: list[str] = field(default_factory=list)


def _requisitar_json(url: str, parametros: dict, tentativas: int = 3) -> dict:
    """GET com repetição simples. Usa apenas a biblioteca padrão."""
    endereco = f"{url}?{urllib.parse.urlencode(parametros)}"
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            requisicao = urllib.request.Request(
                endereco, headers={"User-Agent": "LionGuard-AI/1.0 (projeto academico FIAP)"}
            )
            with urllib.request.urlopen(requisicao, timeout=30) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except Exception as erro:  # rede instável, limite de taxa, etc.
            ultimo_erro = erro
            time.sleep(2 * (tentativa + 1))
    raise RuntimeError(f"falha ao consultar {url}: {ultimo_erro}")


def baixar_inaturalist(
    taxon_id: int,
    classe: str,
    destino: Path | str = Path("data/raw"),
    limite_imagens: int = 300,
    por_pagina: int = 50,
    tamanho_foto: str = "medium",
    pausa_segundos: float = 1.0,
) -> ResultadoAquisicao:
    """
    Baixa imagens de um táxon do iNaturalist para `destino/classe/`.

    Grava/atualiza `destino/manifesto.csv` com a procedência de cada arquivo.
    Respeita a licença declarada de cada observação e identifica o autor.
    """
    if classe not in CLASSES:
        raise ValueError(f"classe deve ser uma de {CLASSES}")

    pasta_classe = Path(destino) / classe
    pasta_classe.mkdir(parents=True, exist_ok=True)
    caminho_manifesto = Path(destino) / "manifesto.csv"
    novo_manifesto = not caminho_manifesto.is_file()

    resultado = ResultadoAquisicao(classe=classe, manifesto=str(caminho_manifesto))
    hashes_existentes = _hashes_do_manifesto(caminho_manifesto)

    with caminho_manifesto.open("a", encoding="utf-8", newline="") as arquivo_manifesto:
        escritor = csv.DictWriter(arquivo_manifesto, fieldnames=CABECALHO_MANIFESTO)
        if novo_manifesto:
            escritor.writeheader()

        pagina = 1
        while resultado.baixadas < limite_imagens:
            dados = _requisitar_json(
                API_INATURALIST,
                {
                    "taxon_id": taxon_id,
                    "quality_grade": "research",
                    "photos": "true",
                    "per_page": por_pagina,
                    "page": pagina,
                    "order_by": "votes",
                    "locale": "pt-BR",
                },
            )
            observacoes = dados.get("results", [])
            if not observacoes:
                break

            for observacao in observacoes:
                resultado.observacoes += 1
                especie = (observacao.get("taxon") or {}).get("name") or "desconhecida"
                autor = (observacao.get("user") or {}).get("login") or "desconhecido"
                observacao_id = observacao.get("id")

                for foto in observacao.get("photos", []):
                    if resultado.baixadas >= limite_imagens:
                        break
                    licenca = (foto.get("license_code") or "").lower()
                    if licenca not in LICENCAS_ACEITAS:
                        resultado.ignoradas_licenca += 1
                        continue

                    url_foto = str(foto.get("url", "")).replace("square", tamanho_foto)
                    if not url_foto:
                        resultado.ignoradas_erro += 1
                        continue

                    try:
                        requisicao = urllib.request.Request(
                            url_foto,
                            headers={"User-Agent": "LionGuard-AI/1.0 (projeto academico FIAP)"},
                        )
                        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
                            conteudo = resposta.read()
                    except Exception as erro:
                        resultado.ignoradas_erro += 1
                        resultado.erros.append(f"{url_foto}: {erro}")
                        continue

                    digest = hashlib.sha256(conteudo).hexdigest()
                    if digest in hashes_existentes:
                        continue
                    hashes_existentes.add(digest)

                    extensao = Path(urllib.parse.urlparse(url_foto).path).suffix.lower()
                    if extensao not in EXTENSOES_IMAGEM:
                        extensao = ".jpg"
                    nome = f"obs{observacao_id}_foto{foto.get('id')}{extensao}"
                    (pasta_classe / nome).write_bytes(conteudo)

                    escritor.writerow(
                        {
                            "arquivo": f"{classe}/{nome}",
                            "classe": classe,
                            "especie": especie,
                            "fonte": "iNaturalist",
                            "url": url_foto,
                            "licenca": licenca,
                            "autor": autor,
                            "observacao_id": observacao_id,
                            "imagem_id": foto.get("id"),
                            "data_aquisicao": date.today().isoformat(),
                            "hash_sha256": digest,
                        }
                    )
                    resultado.baixadas += 1

            pagina += 1
            time.sleep(pausa_segundos)  # cortesia com a API pública

    return resultado


def _hashes_do_manifesto(caminho: Path) -> set[str]:
    if not caminho.is_file():
        return set()
    with caminho.open("r", encoding="utf-8", newline="") as arquivo:
        return {
            linha["hash_sha256"]
            for linha in csv.DictReader(arquivo)
            if linha.get("hash_sha256")
        }


# ----------------------------------------------------------------- preparação
@dataclass
class ResultadoPreparacao:
    total_encontradas: int = 0
    invalidas: int = 0
    duplicadas: int = 0
    por_conjunto: dict[str, dict[str, int]] = field(default_factory=dict)
    grupos: int = 0
    semente: int = 42
    vazamento_detectado: bool = False
    relatorio: str | None = None

    @property
    def total_utilizadas(self) -> int:
        return sum(
            quantidade
            for conjunto in self.por_conjunto.values()
            for quantidade in conjunto.values()
        )


def _grupo_do_arquivo(caminho: Path) -> str:
    """
    Identificador do grupo de uma imagem.

    Arquivos nomeados `obs<ID>_foto<ID>.jpg` (padrão do download) agrupam pela
    observação. Para arquivos avulsos, o grupo é o próprio nome — mais
    conservador do que supor que são independentes.
    """
    nome = caminho.stem
    if nome.startswith("obs") and "_" in nome:
        return nome.split("_", 1)[0]
    return nome


def _imagem_valida(caminho: Path) -> tuple[bool, str | None]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(caminho) as imagem:
            imagem.verify()
        with Image.open(caminho) as imagem:
            largura, altura = imagem.size
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        return False, str(erro)
    if min(largura, altura) < 64:
        return False, f"dimensão insuficiente ({largura}x{altura})"
    return True, None


def preparar_dataset(
    diretorio_origem: Path | str = Path("data/raw"),
    diretorio_destino: Path | str = Path("data/processed"),
    proporcoes: tuple[float, float, float] = (0.70, 0.15, 0.15),
    semente: int = 42,
    limpar_destino: bool = True,
) -> ResultadoPreparacao:
    """
    Valida, deduplica e divide as imagens em treino/validação/teste.

    Garantias:
      * arquivos corrompidos ou pequenos demais são descartados e contados;
      * duplicatas exatas (mesmo SHA-256) são removidas;
      * todas as imagens de uma mesma observação ficam no **mesmo** conjunto;
      * a divisão é determinística para uma dada semente;
      * ao final, a função verifica explicitamente se algum grupo aparece em
        mais de um conjunto e registra `vazamento_detectado`.
    """
    import random

    origem = Path(diretorio_origem)
    destino = Path(diretorio_destino)
    if abs(sum(proporcoes) - 1.0) > 1e-6:
        raise ValueError("as proporções devem somar 1,0")

    resultado = ResultadoPreparacao(semente=semente)
    rng = random.Random(semente)

    if limpar_destino:
        for conjunto in ("train", "val", "test"):
            caminho_conjunto = destino / conjunto
            if caminho_conjunto.exists():
                shutil.rmtree(caminho_conjunto)

    for conjunto in ("train", "val", "test"):
        for classe in CLASSES:
            (destino / conjunto / classe).mkdir(parents=True, exist_ok=True)
        resultado.por_conjunto[conjunto] = dict.fromkeys(CLASSES, 0)

    hashes_vistos: set[str] = set()
    registro_divisao: list[dict] = []

    for classe in CLASSES:
        pasta = origem / classe
        if not pasta.is_dir():
            continue

        grupos: dict[str, list[Path]] = defaultdict(list)
        for arquivo in sorted(pasta.iterdir()):
            if arquivo.suffix.lower() not in EXTENSOES_IMAGEM:
                continue
            resultado.total_encontradas += 1

            valida, motivo = _imagem_valida(arquivo)
            if not valida:
                resultado.invalidas += 1
                continue

            digest = hashlib.sha256(arquivo.read_bytes()).hexdigest()
            if digest in hashes_vistos:
                resultado.duplicadas += 1
                continue
            hashes_vistos.add(digest)

            grupos[_grupo_do_arquivo(arquivo)].append(arquivo)

        chaves = sorted(grupos)
        rng.shuffle(chaves)
        resultado.grupos += len(chaves)

        total_grupos = len(chaves)
        corte_treino = int(round(total_grupos * proporcoes[0]))
        corte_validacao = corte_treino + int(round(total_grupos * proporcoes[1]))
        # Com poucos grupos, garante ao menos um grupo em validação e teste.
        if total_grupos >= 3:
            corte_treino = min(corte_treino, total_grupos - 2)
            corte_validacao = min(max(corte_validacao, corte_treino + 1), total_grupos - 1)

        divisao = {
            "train": chaves[:corte_treino],
            "val": chaves[corte_treino:corte_validacao],
            "test": chaves[corte_validacao:],
        }

        for conjunto, chaves_conjunto in divisao.items():
            for chave in chaves_conjunto:
                for arquivo in grupos[chave]:
                    shutil.copy2(arquivo, destino / conjunto / classe / arquivo.name)
                    resultado.por_conjunto[conjunto][classe] += 1
                registro_divisao.append(
                    {"classe": classe, "grupo": chave, "conjunto": conjunto}
                )

    # Verificação de vazamento entre conjuntos.
    conjuntos_por_grupo: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in registro_divisao:
        conjuntos_por_grupo[(item["classe"], item["grupo"])].add(item["conjunto"])
    resultado.vazamento_detectado = any(
        len(conjuntos) > 1 for conjuntos in conjuntos_por_grupo.values()
    )

    caminho_relatorio = destino / "divisao_dataset.json"
    caminho_relatorio.write_text(
        json.dumps(
            {
                "gerado_em": date.today().isoformat(),
                "semente": semente,
                "proporcoes": list(proporcoes),
                "total_encontradas": resultado.total_encontradas,
                "invalidas": resultado.invalidas,
                "duplicadas_removidas": resultado.duplicadas,
                "grupos": resultado.grupos,
                "por_conjunto": resultado.por_conjunto,
                "vazamento_detectado": resultado.vazamento_detectado,
                "divisao": registro_divisao,
                "observacao": (
                    "A divisão é por observação (grupo), não por imagem, para "
                    "impedir que fotos quase idênticas caiam em conjuntos diferentes."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    resultado.relatorio = str(caminho_relatorio)
    return resultado


def resumo_manifesto(caminho: Path | str = Path("data/raw/manifesto.csv")) -> dict:
    """Agrega o manifesto por classe, fonte e licença (vai para a documentação)."""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        return {"disponivel": False, "motivo": f"manifesto não encontrado em {arquivo}"}

    por_classe: dict[str, int] = defaultdict(int)
    por_licenca: dict[str, int] = defaultdict(int)
    por_fonte: dict[str, int] = defaultdict(int)
    especies: dict[str, int] = defaultdict(int)
    total = 0

    with arquivo.open("r", encoding="utf-8", newline="") as manipulador:
        for linha in csv.DictReader(manipulador):
            total += 1
            por_classe[linha.get("classe", "?")] += 1
            por_licenca[linha.get("licenca", "?")] += 1
            por_fonte[linha.get("fonte", "?")] += 1
            especies[linha.get("especie", "?")] += 1

    return {
        "disponivel": True,
        "arquivo": str(arquivo),
        "total_imagens": total,
        "por_classe": dict(por_classe),
        "por_licenca": dict(por_licenca),
        "por_fonte": dict(por_fonte),
        "especies": dict(sorted(especies.items(), key=lambda item: -item[1])),
    }
