"""
Serviço de geolocalização.

Responsabilidades:
  * validar coordenadas recebidas do navegador ou marcadas no mapa;
  * distinguir a **origem** da localização (GPS, ponto no mapa, região
    aproximada ou importação) — exigência da seção 4.5 do escopo;
  * sugerir estado e município a partir de um ponto, de forma offline;
  * arredondar coordenadas para exibição pública.

Sobre a tabela de referência municipal: são pontos **aproximados** de
municípios litorâneos brasileiros, usados apenas para sugerir o município de
um ponto marcado no mapa quando não há serviço de geocodificação disponível.
Não são registros de avistamento e não substituem base cartográfica oficial
(IBGE). A sugestão sempre vem acompanhada da distância, e o usuário pode
corrigi-la.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.database.schema import OrigemLocalizacao

# Caixa envolvente do território e do mar territorial brasileiro, incluindo
# ilhas oceânicas (Trindade a leste, Noronha ao norte).
LIMITES_BRASIL = {
    "lat_min": -34.9,
    "lat_max": 5.5,
    "lon_min": -74.1,
    "lon_max": -28.6,
}

# (município, UF, latitude, longitude) — pontos aproximados de referência.
MUNICIPIOS_LITORANEOS: tuple[tuple[str, str, float, float], ...] = (
    # Amapá / Pará
    ("Macapá", "AP", 0.03, -51.07),
    ("Oiapoque", "AP", 3.84, -51.83),
    ("Calçoene", "AP", 2.50, -50.95),
    ("Belém", "PA", -1.46, -48.50),
    ("Salinópolis", "PA", -0.61, -47.36),
    ("Bragança", "PA", -1.05, -46.77),
    ("Soure", "PA", -0.72, -48.52),
    # Maranhão / Piauí
    ("São Luís", "MA", -2.53, -44.30),
    ("Alcântara", "MA", -2.41, -44.42),
    ("Barreirinhas", "MA", -2.75, -42.82),
    ("Tutóia", "MA", -2.76, -42.27),
    ("Parnaíba", "PI", -2.90, -41.78),
    ("Luís Correia", "PI", -2.88, -41.67),
    # Ceará
    ("Fortaleza", "CE", -3.73, -38.52),
    ("Aquiraz", "CE", -3.90, -38.39),
    ("Jijoca de Jericoacoara", "CE", -2.79, -40.51),
    ("Acaraú", "CE", -2.89, -40.12),
    ("Icapuí", "CE", -4.71, -37.35),
    # Rio Grande do Norte
    ("Natal", "RN", -5.79, -35.21),
    ("Maxaranguape", "RN", -5.51, -35.26),
    ("Tibau do Sul", "RN", -6.23, -35.08),
    ("Areia Branca", "RN", -4.95, -37.14),
    ("Galinhos", "RN", -5.09, -36.27),
    # Paraíba
    ("João Pessoa", "PB", -7.12, -34.86),
    ("Cabedelo", "PB", -6.98, -34.83),
    ("Conde", "PB", -7.26, -34.91),
    ("Baía da Traição", "PB", -6.69, -34.93),
    # Pernambuco
    ("Recife", "PE", -8.05, -34.88),
    ("Cabo de Santo Agostinho", "PE", -8.29, -35.04),
    ("Ipojuca", "PE", -8.50, -35.00),
    ("Tamandaré", "PE", -8.76, -35.10),
    ("Goiana", "PE", -7.56, -34.97),
    ("Fernando de Noronha", "PE", -3.85, -32.42),
    # Alagoas / Sergipe
    ("Maceió", "AL", -9.67, -35.74),
    ("Maragogi", "AL", -9.01, -35.22),
    ("Japaratinga", "AL", -9.09, -35.26),
    ("São Miguel dos Milagres", "AL", -9.26, -35.38),
    ("Aracaju", "SE", -10.91, -37.07),
    ("Pirambu", "SE", -10.73, -36.85),
    ("Estância", "SE", -11.27, -37.44),
    # Bahia
    ("Salvador", "BA", -12.97, -38.50),
    ("Mata de São João", "BA", -12.53, -38.00),
    ("Cairu", "BA", -13.38, -38.91),
    ("Ilhéus", "BA", -14.79, -39.03),
    ("Itacaré", "BA", -14.28, -38.99),
    ("Porto Seguro", "BA", -16.44, -39.06),
    ("Prado", "BA", -17.34, -39.22),
    ("Caravelas", "BA", -17.73, -39.25),
    # Espírito Santo
    ("Conceição da Barra", "ES", -18.59, -39.73),
    ("Vitória", "ES", -20.32, -40.34),
    ("Vila Velha", "ES", -20.33, -40.29),
    ("Guarapari", "ES", -20.67, -40.50),
    ("Anchieta", "ES", -20.80, -40.64),
    ("Piúma", "ES", -20.84, -40.73),
    ("Itapemirim", "ES", -21.01, -40.83),
    # Rio de Janeiro
    ("Macaé", "RJ", -22.37, -41.78),
    ("Armação dos Búzios", "RJ", -22.75, -41.88),
    ("Cabo Frio", "RJ", -22.88, -42.02),
    ("Arraial do Cabo", "RJ", -22.97, -42.03),
    ("Niterói", "RJ", -22.88, -43.10),
    ("Rio de Janeiro", "RJ", -22.91, -43.17),
    ("Angra dos Reis", "RJ", -23.01, -44.32),
    ("Paraty", "RJ", -23.22, -44.71),
    # São Paulo
    ("Ubatuba", "SP", -23.43, -45.08),
    ("São Sebastião", "SP", -23.76, -45.41),
    ("Ilhabela", "SP", -23.78, -45.36),
    ("Bertioga", "SP", -23.85, -46.14),
    ("Santos", "SP", -23.96, -46.33),
    ("Guarujá", "SP", -23.99, -46.26),
    ("Ilha Comprida", "SP", -24.73, -47.54),
    ("Cananéia", "SP", -25.01, -47.93),
    # Paraná / Santa Catarina
    ("Paranaguá", "PR", -25.52, -48.51),
    ("Pontal do Paraná", "PR", -25.67, -48.51),
    ("Matinhos", "PR", -25.82, -48.54),
    ("Guaratuba", "PR", -25.88, -48.57),
    ("São Francisco do Sul", "SC", -26.24, -48.64),
    ("Itajaí", "SC", -26.91, -48.66),
    ("Balneário Camboriú", "SC", -26.99, -48.63),
    ("Bombinhas", "SC", -27.14, -48.48),
    ("Florianópolis", "SC", -27.60, -48.55),
    ("Garopaba", "SC", -28.02, -48.61),
    ("Laguna", "SC", -28.48, -48.78),
    # Rio Grande do Sul
    ("Torres", "RS", -29.34, -49.73),
    ("Capão da Canoa", "RS", -29.75, -50.01),
    ("Tramandaí", "RS", -29.98, -50.13),
    ("Rio Grande", "RS", -32.03, -52.10),
)

# Ilhas e arquipélagos oceânicos brasileiros, administrativamente vinculados às
# UFs indicadas. Entram como pontos de referência próprios porque estão a mais
# de 400 km da costa e, sem eles, um avistamento legítimo em Trindade ou em
# Abrolhos seria recusado como "fora da área monitorada".
ILHAS_OCEANICAS: tuple[tuple[str, str, float, float], ...] = (
    ("Ilha da Trindade", "ES", -20.50, -29.32),
    ("Arquipélago de Abrolhos", "BA", -17.96, -38.70),
    ("Atol das Rocas", "RN", -3.86, -33.80),
    ("Arquipélago de São Pedro e São Paulo", "PE", 0.92, -29.35),
)

# Conjunto completo de referências usado nas buscas por proximidade.
REFERENCIAS_LITORAL: tuple[tuple[str, str, float, float], ...] = (
    MUNICIPIOS_LITORANEOS + ILHAS_OCEANICAS
)

ESTADOS_LITORANEOS: tuple[str, ...] = (
    "AP", "PA", "MA", "PI", "CE", "RN", "PB", "PE",
    "AL", "SE", "BA", "ES", "RJ", "SP", "PR", "SC", "RS",
)

RAIO_TERRA_KM = 6371.0088


class CoordenadaInvalida(Exception):
    """Coordenada ausente, fora de faixa ou fora da área de interesse."""


@dataclass(slots=True)
class Localizacao:
    """Localização consolidada de um avistamento."""

    latitude: float | None
    longitude: float | None
    origem: OrigemLocalizacao
    precisao_metros: float | None = None
    estado: str | None = None
    municipio: str | None = None
    municipio_sugerido: bool = False
    distancia_referencia_km: float | None = None

    @property
    def tem_coordenadas(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def precisa(self) -> bool:
        return self.tem_coordenadas and self.origem in (
            OrigemLocalizacao.GPS_DISPOSITIVO,
            OrigemLocalizacao.MAPA_MANUAL,
        )

    def descricao_origem(self) -> str:
        textos = {
            OrigemLocalizacao.GPS_DISPOSITIVO: "GPS do dispositivo",
            OrigemLocalizacao.MAPA_MANUAL: "ponto marcado no mapa",
            OrigemLocalizacao.REGIAO_APROXIMADA: "região aproximada informada",
            OrigemLocalizacao.IMPORTADA: "importada de fonte externa",
        }
        return textos.get(self.origem, str(self.origem))


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância de grande círculo (Haversine) em quilômetros."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


def validar_coordenadas(latitude, longitude) -> tuple[float, float]:
    """Converte e valida o par de coordenadas; levanta `CoordenadaInvalida`."""
    if latitude is None or longitude is None:
        raise CoordenadaInvalida("Latitude e longitude são obrigatórias.")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError) as erro:
        raise CoordenadaInvalida("Coordenadas não numéricas.") from erro
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        raise CoordenadaInvalida("Coordenadas inválidas.")
    if not (-90 <= lat <= 90):
        raise CoordenadaInvalida(f"Latitude fora de faixa: {lat}")
    if not (-180 <= lon <= 180):
        raise CoordenadaInvalida(f"Longitude fora de faixa: {lon}")
    return lat, lon


# Distância máxima aceita entre um ponto e o município litorâneo de referência
# mais próximo. Cobre a plataforma continental e as ilhas oceânicas; descarta
# pontos no interior do continente e em países vizinhos.
DISTANCIA_MAXIMA_REFERENCIA_KM = 450.0


def dentro_do_brasil(latitude: float, longitude: float) -> bool:
    """
    Primeiro filtro, por caixa envolvente.

    É barato e serve para triagem em lote (importação de bases externas), mas
    um retângulo que inclui Oiapoque e Chuí inclui também trechos de países
    vizinhos. Para decidir se um ponto pertence à **área monitorada**, use
    `dentro_da_area_monitorada`.
    """
    return (
        LIMITES_BRASIL["lat_min"] <= latitude <= LIMITES_BRASIL["lat_max"]
        and LIMITES_BRASIL["lon_min"] <= longitude <= LIMITES_BRASIL["lon_max"]
    )


def dentro_da_area_monitorada(
    latitude: float, longitude: float, distancia_maxima_km: float | None = None
) -> tuple[bool, str | None]:
    """
    Verifica se o ponto pertence à área de monitoramento do projeto.

    O critério tem duas partes: estar na caixa envolvente **e** estar a até
    `distancia_maxima_km` de um município litorâneo de referência. A segunda
    condição é o que de fato delimita a área, porque o escopo do projeto é o
    litoral brasileiro e suas ilhas oceânicas — não o interior do continente
    nem a costa de países vizinhos, que um simples retângulo não consegue
    separar.

    Devolve `(dentro, motivo)`; `motivo` é `None` quando o ponto é aceito.
    """
    limite = (
        DISTANCIA_MAXIMA_REFERENCIA_KM if distancia_maxima_km is None else distancia_maxima_km
    )

    if not dentro_do_brasil(latitude, longitude):
        return False, "o ponto está fora da faixa de latitude e longitude monitorada"

    proximo = municipio_mais_proximo(latitude, longitude)
    if proximo is None:  # pragma: no cover - a tabela nunca está vazia
        return True, None

    _, _, distancia = proximo
    if distancia > limite:
        return False, (
            f"o ponto está a {distancia:.0f} km do município litorâneo mais "
            f"próximo (limite de {limite:.0f} km) — o projeto monitora o litoral "
            "brasileiro e as ilhas oceânicas"
        )
    return True, None


def municipio_mais_proximo(
    latitude: float, longitude: float
) -> tuple[str, str, float] | None:
    """
    Município litorâneo de referência mais próximo do ponto.

    Devolve `(municipio, uf, distancia_km)` ou `None` se a tabela estiver vazia.
    A distância permite à interface avisar quando o ponto está longe de
    qualquer referência conhecida.
    """
    melhor: tuple[str, str, float] | None = None
    for municipio, uf, lat, lon in REFERENCIAS_LITORAL:
        distancia = distancia_km(latitude, longitude, lat, lon)
        if melhor is None or distancia < melhor[2]:
            melhor = (municipio, uf, round(distancia, 2))
    return melhor


def municipios_do_estado(uf: str) -> list[str]:
    """Municípios de referência de uma UF, em ordem alfabética."""
    return sorted(
        municipio for municipio, estado, _, _ in REFERENCIAS_LITORAL if estado == uf.upper()
    )


def coordenadas_do_municipio(municipio: str, uf: str) -> tuple[float, float] | None:
    for nome, estado, lat, lon in REFERENCIAS_LITORAL:
        if nome.lower() == municipio.strip().lower() and estado == uf.upper():
            return (lat, lon)
    return None


def arredondar_para_publico(
    latitude: float, longitude: float, casas: int | None = None
) -> tuple[float, float]:
    """
    Reduz a precisão das coordenadas para exibição pública.

    Duas casas decimais correspondem a cerca de 1 km — suficiente para o mapa
    de distribuição e insuficiente para localizar um ponto de mergulho
    específico (seção 5.2 do escopo).
    """
    from src.config import get_config

    casas = get_config().casas_decimais_publicas if casas is None else casas
    return (round(float(latitude), casas), round(float(longitude), casas))


def classificar_precisao(precisao_metros: float | None) -> str:
    """Texto legível sobre a qualidade da leitura do GPS."""
    if precisao_metros is None:
        return "precisão não informada"
    if precisao_metros <= 20:
        return f"alta precisão (±{precisao_metros:.0f} m)"
    if precisao_metros <= 100:
        return f"precisão moderada (±{precisao_metros:.0f} m)"
    if precisao_metros <= 1000:
        return f"precisão baixa (±{precisao_metros:.0f} m)"
    return f"precisão muito baixa (±{precisao_metros / 1000:.1f} km)"


def construir_localizacao(
    latitude,
    longitude,
    origem: OrigemLocalizacao,
    precisao_metros: float | None = None,
    estado: str | None = None,
    municipio: str | None = None,
    exigir_area_brasil: bool = True,
) -> Localizacao:
    """
    Valida o ponto e completa estado/município quando não informados.

    `exigir_area_brasil=True` recusa pontos fora da área de interesse, para
    evitar que um clique acidental no mapa crie um registro no outro hemisfério.
    """
    lat, lon = validar_coordenadas(latitude, longitude)
    if exigir_area_brasil:
        dentro, motivo = dentro_da_area_monitorada(lat, lon)
        if not dentro:
            raise CoordenadaInvalida(
                f"O ponto está fora da área de monitoramento: {motivo}."
            )

    sugerido = False
    distancia = None
    if not municipio or not estado:
        proximo = municipio_mais_proximo(lat, lon)
        if proximo:
            municipio_ref, uf_ref, distancia = proximo
            municipio = municipio or municipio_ref
            estado = estado or uf_ref
            sugerido = True

    return Localizacao(
        latitude=lat,
        longitude=lon,
        origem=origem,
        precisao_metros=float(precisao_metros) if precisao_metros is not None else None,
        estado=(estado or None),
        municipio=(municipio or None),
        municipio_sugerido=sugerido,
        distancia_referencia_km=distancia,
    )


def localizacao_por_regiao(estado: str, municipio: str | None = None) -> Localizacao:
    """
    Localização declarada apenas por região (sem ponto no mapa).

    Usa o ponto de referência do município como coordenada aproximada e marca
    a origem como `REGIAO_APROXIMADA`, para que o dado jamais seja confundido
    com uma leitura de GPS.
    """
    uf = (estado or "").strip().upper()
    if uf not in ESTADOS_LITORANEOS:
        raise CoordenadaInvalida(f"UF não é litorânea ou é inválida: {estado!r}")

    coordenadas = coordenadas_do_municipio(municipio, uf) if municipio else None
    if coordenadas is None:
        # Usa só municípios costeiros: incluir ilhas oceânicas deslocaria o
        # centro da UF para o meio do Atlântico.
        pontos = [
            (lat, lon) for _, est, lat, lon in MUNICIPIOS_LITORANEOS if est == uf
        ]
        if not pontos:  # pragma: no cover - toda UF litorânea tem referência
            raise CoordenadaInvalida(f"sem referência para a UF {uf}")
        coordenadas = (
            sum(p[0] for p in pontos) / len(pontos),
            sum(p[1] for p in pontos) / len(pontos),
        )

    return Localizacao(
        latitude=round(coordenadas[0], 4),
        longitude=round(coordenadas[1], 4),
        origem=OrigemLocalizacao.REGIAO_APROXIMADA,
        precisao_metros=None,
        estado=uf,
        municipio=municipio or None,
        municipio_sugerido=municipio is None,
    )
