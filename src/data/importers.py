"""
Importação de registros de fontes documentadas (GBIF, iNaturalist e afins).

O que este módulo faz e não faz:
  * registra a **procedência** de cada lote em `fonte_dados` (nome, URL,
    licença, data de importação) antes de inserir qualquer ocorrência;
  * marca as ocorrências com `tipo_dado = IMPORTADO` e
    `origem_localizacao = IMPORTADA`, para que nunca sejam confundidas com
    leitura de GPS da plataforma;
  * mantém o status `PENDENTE`: um registro externo não é "confirmado" pela
    nossa equipe de avaliação só por existir em outra base (regra 5 da seção
    20 do escopo). O identificador externo fica na descrição, permitindo
    rastrear a observação original;
  * usa o identificador da observação na chave de idempotência, de modo que
    reimportar o mesmo arquivo não duplica registros.

O download dos arquivos é feito pelo usuário (ou por `scripts/baixar_dados.py`)
e o caminho é passado aqui — este módulo não acessa a rede.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.database.models import FonteDados, Ocorrencia
from src.database.repositories import (
    AuditoriaRepository,
    FonteDadosRepository,
    OcorrenciaRepository,
    RegistroDuplicado,
)
from src.database.schema import (
    Habitat,
    OrigemLocalizacao,
    OrigemRegistro,
    StatusOcorrencia,
    TipoDado,
)
from src.services.geolocation import (
    CoordenadaInvalida,
    dentro_da_area_monitorada,
    municipio_mais_proximo,
    validar_coordenadas,
)

# Nomes de coluna aceitos para cada campo, em ordem de preferência.
# Cobre Darwin Core (GBIF) e a exportação CSV do iNaturalist.
MAPEAMENTO_COLUNAS: dict[str, tuple[str, ...]] = {
    "latitude": ("decimalLatitude", "latitude", "lat"),
    "longitude": ("decimalLongitude", "longitude", "lon", "lng"),
    "data": ("eventDate", "observed_on", "date", "data"),
    "estado": ("stateProvince", "place_state_name", "estado", "uf"),
    "municipio": ("municipality", "place_city_name", "municipio", "locality"),
    "identificador": ("occurrenceID", "gbifID", "id", "catalogNumber", "uuid"),
    "profundidade": ("depth", "minimumDepthInMeters", "profundidade"),
    "quantidade": ("individualCount", "organismQuantity", "quantidade"),
    "licenca": ("license", "licenca", "rights"),
    "especie": ("scientificName", "species_guess", "taxon_name", "especie"),
}

ESPECIES_ACEITAS = ("pterois", "peixe-leão", "peixe leao", "lionfish")

UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapá": "AP", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceará": "CE", "ceara": "CE", "distrito federal": "DF",
    "espírito santo": "ES", "espirito santo": "ES", "goiás": "GO", "goias": "GO",
    "maranhão": "MA", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "pará": "PA", "para": "PA",
    "paraíba": "PB", "paraiba": "PB", "paraná": "PR", "parana": "PR",
    "pernambuco": "PE", "piauí": "PI", "piaui": "PI",
    "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondônia": "RO", "rondonia": "RO",
    "roraima": "RR", "santa catarina": "SC", "são paulo": "SP", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}


@dataclass(slots=True)
class ResultadoImportacao:
    fonte: str
    total_linhas: int = 0
    importados: int = 0
    ignorados_sem_coordenada: int = 0
    ignorados_fora_area: int = 0
    ignorados_data_invalida: int = 0
    ignorados_outra_especie: int = 0
    duplicados: int = 0
    fonte_id: int | None = None
    erros: list[str] = field(default_factory=list)

    @property
    def resumo(self) -> str:
        return (
            f"{self.importados} de {self.total_linhas} linhas importadas de {self.fonte}. "
            f"Descartadas: {self.ignorados_sem_coordenada} sem coordenada, "
            f"{self.ignorados_fora_area} fora da área, "
            f"{self.ignorados_data_invalida} com data inválida, "
            f"{self.ignorados_outra_especie} de outra espécie. "
            f"{self.duplicados} já existiam."
        )


def _valor(linha: dict, campo: str) -> str | None:
    for coluna in MAPEAMENTO_COLUNAS[campo]:
        if coluna in linha and str(linha[coluna]).strip() not in ("", "NA", "null", "None"):
            return str(linha[coluna]).strip()
    return None


def _normalizar_uf(valor: str | None) -> str | None:
    if not valor:
        return None
    bruto = valor.strip()
    if len(bruto) == 2 and bruto.isalpha():
        return bruto.upper()
    return UF_POR_NOME.get(bruto.lower())


def _converter_data(valor: str | None) -> str | None:
    """
    Interpreta os formatos de data mais comuns nas duas bases.

    Datas com intervalo (`2026-01-01/2026-01-05`) usam o início do intervalo.
    Devolve `None` quando não consegue interpretar — a linha é descartada em vez
    de receber uma data arbitrária.
    """
    if not valor:
        return None
    bruto = valor.split("/")[0].strip().replace("Z", "")
    formatos = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%Y-%m",
        "%Y",
    )
    for formato in formatos:
        try:
            data = datetime.strptime(bruto[: len(datetime.now().strftime(formato))], formato)
        except ValueError:
            continue
        if data > datetime.now():
            return None
        return data.replace(microsecond=0).isoformat()
    return None


def _numero(valor: str | None) -> float | None:
    if valor is None:
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


class ImportadorOcorrencias:
    def __init__(self, caminho_banco: str | Path | None = None) -> None:
        self.caminho = caminho_banco
        self.ocorrencias = OcorrenciaRepository(caminho_banco)
        self.fontes = FonteDadosRepository(caminho_banco)
        self.auditoria = AuditoriaRepository(caminho_banco)

    def importar_csv(
        self,
        caminho_csv: Path | str,
        nome_fonte: str,
        url: str | None = None,
        licenca: str | None = None,
        tipo_fonte: str = "BASE_EXTERNA",
        filtrar_especie: bool = True,
        limite: int | None = None,
    ) -> ResultadoImportacao:
        """Importa um CSV exportado de uma base de biodiversidade."""
        arquivo = Path(caminho_csv)
        resultado = ResultadoImportacao(fonte=nome_fonte)
        if not arquivo.is_file():
            resultado.erros.append(f"arquivo não encontrado: {arquivo}")
            return resultado

        fonte = self.fontes.criar(
            FonteDados(
                nome=nome_fonte,
                url=url,
                licenca=licenca,
                tipo_fonte=tipo_fonte,
                observacoes=f"importado do arquivo {arquivo.name}",
            )
        )
        resultado.fonte_id = fonte.id

        # GBIF usa TSV; iNaturalist usa CSV. O sniffer resolve os dois.
        with arquivo.open("r", encoding="utf-8-sig", newline="") as manipulador:
            amostra = manipulador.read(8192)
            manipulador.seek(0)
            try:
                dialeto = csv.Sniffer().sniff(amostra, delimiters=",;\t")
            except csv.Error:
                dialeto = csv.excel
            leitor = csv.DictReader(manipulador, dialect=dialeto)

            for numero_linha, linha in enumerate(leitor, start=2):
                if limite is not None and resultado.importados >= limite:
                    break
                resultado.total_linhas += 1

                if filtrar_especie:
                    especie = (_valor(linha, "especie") or "").lower()
                    if especie and not any(termo in especie for termo in ESPECIES_ACEITAS):
                        resultado.ignorados_outra_especie += 1
                        continue

                latitude = _numero(_valor(linha, "latitude"))
                longitude = _numero(_valor(linha, "longitude"))
                if latitude is None or longitude is None:
                    resultado.ignorados_sem_coordenada += 1
                    continue
                try:
                    latitude, longitude = validar_coordenadas(latitude, longitude)
                except CoordenadaInvalida:
                    resultado.ignorados_sem_coordenada += 1
                    continue
                dentro, _ = dentro_da_area_monitorada(latitude, longitude)
                if not dentro:
                    resultado.ignorados_fora_area += 1
                    continue

                data_avistamento = _converter_data(_valor(linha, "data"))
                if data_avistamento is None:
                    resultado.ignorados_data_invalida += 1
                    continue

                estado = _normalizar_uf(_valor(linha, "estado"))
                municipio = _valor(linha, "municipio")
                if not estado or not municipio:
                    proximo = municipio_mais_proximo(latitude, longitude)
                    if proximo:
                        municipio = municipio or proximo[0]
                        estado = estado or proximo[1]

                identificador = _valor(linha, "identificador") or f"{arquivo.stem}-{numero_linha}"
                quantidade = _numero(_valor(linha, "quantidade"))

                ocorrencia = Ocorrencia(
                    protocolo=self._protocolo_importacao(nome_fonte, identificador),
                    chave_idempotencia=f"import:{nome_fonte}:{identificador}",
                    data_hora_avistamento=data_avistamento,
                    estado=estado,
                    municipio=municipio,
                    latitude=latitude,
                    longitude=longitude,
                    precisao_metros=None,
                    origem_localizacao=OrigemLocalizacao.IMPORTADA,
                    profundidade=_numero(_valor(linha, "profundidade")),
                    habitat=Habitat.NAO_INFORMADO,
                    quantidade_observada=int(quantidade) if quantidade and quantidade > 0 else None,
                    descricao=(
                        f"Registro importado de {nome_fonte}. "
                        f"Identificador na origem: {identificador}. "
                        f"Licença: {licenca or 'não informada'}."
                    ),
                    origem_registro=OrigemRegistro.IMPORTACAO,
                    tipo_dado=TipoDado.IMPORTADO,
                    status=StatusOcorrencia.PENDENTE,  # nunca confirmado automaticamente
                    fonte_dados_id=fonte.id,
                )

                try:
                    self.ocorrencias.criar(ocorrencia)
                    resultado.importados += 1
                except RegistroDuplicado:
                    resultado.duplicados += 1
                except Exception as erro:  # pragma: no cover
                    resultado.erros.append(f"linha {numero_linha}: {erro}")

        self.auditoria.registrar(
            entidade="fonte_dados",
            acao="IMPORTACAO",
            entidade_id=str(fonte.id),
            detalhes={
                "fonte": nome_fonte,
                "arquivo": arquivo.name,
                "importados": resultado.importados,
                "total_linhas": resultado.total_linhas,
            },
        )
        return resultado

    def _protocolo_importacao(self, nome_fonte: str, identificador: str) -> str:
        """Protocolo estável e legível para registros importados."""
        sigla = "".join(c for c in nome_fonte.upper() if c.isalnum())[:4] or "EXT"
        limpo = "".join(c for c in str(identificador) if c.isalnum())[-8:].upper()
        base = f"LG-{sigla}-{limpo}"
        candidato = base
        sufixo = 1
        while self.ocorrencias.protocolo_existe(candidato):
            existente = self.ocorrencias.por_protocolo(candidato)
            if existente and existente.chave_idempotencia == f"import:{nome_fonte}:{identificador}":
                return candidato  # mesmo registro: a inserção cairá em duplicado
            sufixo += 1
            candidato = f"{base}-{sufixo}"
        return candidato
