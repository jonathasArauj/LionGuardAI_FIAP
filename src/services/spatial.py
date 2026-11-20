"""
Análise espacial dos avistamentos — agrupamento DBSCAN.

Por que DBSCAN: não exige o número de grupos definido antes, encontra
agrupamentos de forma arbitrária e classifica pontos isolados como ruído, o que
é adequado a notificações de ciência cidadã espalhadas pelo litoral.

Distância: a métrica `haversine` do scikit-learn opera em radianos; o raio
`eps` é convertido de quilômetros dividindo pelo raio da Terra.

**Ressalva obrigatória**: concentração de notificações mede esforço de
observação (gente com celular na água), não densidade populacional da espécie.
Essa advertência acompanha o resultado em `ResultadoAgrupamento.ressalva`.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from src.services.geolocation import RAIO_TERRA_KM, distancia_km

MINIMO_PONTOS_PARA_AGRUPAR = 5

RESSALVA_VIES = (
    "Agrupamentos refletem onde há mais observadores e registros, não "
    "necessariamente onde há mais peixes-leão. Ausência de registros não "
    "significa ausência da espécie."
)


@dataclass(slots=True)
class Cluster:
    """Um agrupamento espacial identificado."""

    rotulo: int
    quantidade: int
    latitude_centro: float
    longitude_centro: float
    raio_maximo_km: float
    protocolos: list[str] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)
    municipios: list[str] = field(default_factory=list)
    primeiro_registro: str | None = None
    ultimo_registro: str | None = None
    confirmados: int = 0

    @property
    def nome(self) -> str:
        if self.municipios:
            return f"Área {self.rotulo + 1} — {self.municipios[0]}"
        return f"Área {self.rotulo + 1}"


@dataclass(slots=True)
class ResultadoAgrupamento:
    executado: bool
    clusters: list[Cluster] = field(default_factory=list)
    ruido: int = 0
    total_pontos: int = 0
    eps_km: float = 0.0
    minimo_amostras: int = 0
    motivo: str | None = None
    biblioteca: str | None = None
    ressalva: str = RESSALVA_VIES

    @property
    def quantidade_clusters(self) -> int:
        return len(self.clusters)


def _centro(pontos: list[tuple[float, float]]) -> tuple[float, float]:
    """Centroide calculado em coordenadas cartesianas 3D (evita erro no antimeridiano)."""
    x = y = z = 0.0
    for lat, lon in pontos:
        phi, lam = math.radians(lat), math.radians(lon)
        x += math.cos(phi) * math.cos(lam)
        y += math.cos(phi) * math.sin(lam)
        z += math.sin(phi)
    n = len(pontos)
    x, y, z = x / n, y / n, z / n
    lon = math.atan2(y, x)
    lat = math.atan2(z, math.hypot(x, y))
    return (math.degrees(lat), math.degrees(lon))


def agrupar_ocorrencias(
    pontos: list[dict],
    eps_km: float = 25.0,
    minimo_amostras: int = 3,
) -> ResultadoAgrupamento:
    """
    Executa DBSCAN sobre os pontos geográficos.

    `pontos` espera dicionários com `latitude`, `longitude` e, opcionalmente,
    `protocolo`, `estado`, `municipio`, `status` e `data_hora_avistamento`
    (o formato devolvido por `queries.dados_geograficos`).

    Quando há poucos pontos, devolve `executado=False` com o motivo — a
    interface exibe a explicação em vez de um gráfico vazio.
    """
    validos = [
        p
        for p in pontos
        if p.get("latitude") is not None and p.get("longitude") is not None
    ]
    total = len(validos)

    if total < MINIMO_PONTOS_PARA_AGRUPAR:
        return ResultadoAgrupamento(
            executado=False,
            total_pontos=total,
            eps_km=eps_km,
            minimo_amostras=minimo_amostras,
            motivo=(
                f"São necessários ao menos {MINIMO_PONTOS_PARA_AGRUPAR} registros com "
                f"coordenadas para a análise espacial; há {total}."
            ),
        )

    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
    except ImportError:  # pragma: no cover - sklearn consta em requirements.txt
        return ResultadoAgrupamento(
            executado=False,
            total_pontos=total,
            motivo="scikit-learn não está instalado neste ambiente.",
        )

    coordenadas = np.radians(
        np.array([[float(p["latitude"]), float(p["longitude"])] for p in validos])
    )
    modelo = DBSCAN(
        eps=eps_km / RAIO_TERRA_KM,
        min_samples=max(2, int(minimo_amostras)),
        metric="haversine",
        algorithm="ball_tree",
    ).fit(coordenadas)

    rotulos = modelo.labels_
    contagem = Counter(int(r) for r in rotulos)
    clusters: list[Cluster] = []

    for rotulo in sorted(r for r in contagem if r >= 0):
        membros = [p for p, r in zip(validos, rotulos) if int(r) == rotulo]
        coords = [(float(p["latitude"]), float(p["longitude"])) for p in membros]
        lat_centro, lon_centro = _centro(coords)
        raio = max(distancia_km(lat_centro, lon_centro, lat, lon) for lat, lon in coords)
        datas = sorted(
            str(p.get("data_hora_avistamento"))
            for p in membros
            if p.get("data_hora_avistamento")
        )
        clusters.append(
            Cluster(
                rotulo=rotulo,
                quantidade=len(membros),
                latitude_centro=round(lat_centro, 4),
                longitude_centro=round(lon_centro, 4),
                raio_maximo_km=round(raio, 2),
                protocolos=[str(p.get("protocolo")) for p in membros if p.get("protocolo")],
                estados=sorted({str(p["estado"]) for p in membros if p.get("estado")}),
                municipios=[
                    municipio
                    for municipio, _ in Counter(
                        str(p["municipio"]) for p in membros if p.get("municipio")
                    ).most_common()
                ],
                primeiro_registro=datas[0] if datas else None,
                ultimo_registro=datas[-1] if datas else None,
                confirmados=sum(1 for p in membros if p.get("status") == "CONFIRMADO"),
            )
        )

    clusters.sort(key=lambda c: c.quantidade, reverse=True)

    return ResultadoAgrupamento(
        executado=True,
        clusters=clusters,
        ruido=contagem.get(-1, 0),
        total_pontos=total,
        eps_km=eps_km,
        minimo_amostras=max(2, int(minimo_amostras)),
        biblioteca="scikit-learn DBSCAN (métrica haversine)",
    )


def evolucao_por_cluster(resultado: ResultadoAgrupamento, pontos: list[dict]) -> list[dict]:
    """Série mensal de registros por agrupamento (evolução temporal por área)."""
    if not resultado.executado:
        return []
    indice = {
        protocolo: cluster
        for cluster in resultado.clusters
        for protocolo in cluster.protocolos
    }
    contagem: Counter[tuple[str, str]] = Counter()
    for ponto in pontos:
        cluster = indice.get(str(ponto.get("protocolo")))
        data = str(ponto.get("data_hora_avistamento") or "")
        if cluster is None or len(data) < 7:
            continue
        contagem[(cluster.nome, data[:7])] += 1
    return [
        {"area": area, "mes": mes, "total": total}
        for (area, mes), total in sorted(contagem.items(), key=lambda item: item[0][1])
    ]
