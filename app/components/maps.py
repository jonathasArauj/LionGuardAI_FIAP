"""
Mapas interativos (Folium + streamlit-folium).

Três usos:
  1. `mapa_ocorrencias` — visualização dos avistamentos, com camadas de base
     alternáveis, agrupamento de marcadores, mapa de calor opcional, áreas de
     concentração, legenda desenhada e pop-ups ricos;
  2. `mapa_seletor_ponto` — seleção manual do local do avistamento, quando o
     GPS não está disponível (fallback obrigatório da seção 4.5 do escopo);
  3. `mini_mapa` — prévia do ponto capturado, na confirmação do registro.

**Camadas de base.** O padrão é a batimetria do Esri Ocean: para um projeto
marinho, enxergar plataforma continental, bancos e profundidade diz mais do que
um mapa rodoviário. Ficam disponíveis também imagem de satélite e um mapa claro
de referência. Toda camada traz a atribuição exigida pelo provedor.

**Privacidade.** No modo público as coordenadas chegam aqui já arredondadas
pela consulta SQL, e o pop-up informa que a posição é aproximada.
"""

from __future__ import annotations

import html

import folium
import streamlit as st
from folium.plugins import Fullscreen, HeatMap, MarkerCluster, MeasureControl, MiniMap
from streamlit_folium import st_folium

from app.styles.theme import AZUL_MARINHO, ESTILO_STATUS, TURQUESA, estilo_status

# Centro aproximado do litoral brasileiro e zoom que enquadra a costa.
CENTRO_BRASIL = (-14.5, -43.0)
ZOOM_BRASIL = 4

ZOOM_POR_CONTEXTO = {"brasil": 4, "regiao": 7, "municipio": 11, "ponto": 14}

_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services"

# Camadas de base, com a atribuição que cada provedor exige.
CAMADAS_BASE: dict[str, dict] = {
    "Oceano (batimetria)": {
        "tiles": f"{_ESRI}/Ocean/World_Ocean_Base/MapServer/tile/{{z}}/{{y}}/{{x}}",
        "attr": "Esri — GEBCO, NOAA NGDC e outros colaboradores",
        "max_zoom": 13,
    },
    "Satélite": {
        "tiles": f"{_ESRI}/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
        "attr": "Esri — Maxar, Earthstar Geographics e a comunidade de usuários GIS",
        "max_zoom": 19,
    },
    "Mapa claro": {
        "tiles": "cartodbpositron",
        "attr": None,
        "max_zoom": 20,
    },
    "Ruas": {
        "tiles": "OpenStreetMap",
        "attr": None,
        "max_zoom": 19,
    },
}

# Rótulos do oceano (nomes de feições), sobrepostos à batimetria.
CAMADA_ROTULOS_OCEANO = {
    "tiles": f"{_ESRI}/Ocean/World_Ocean_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}",
    "attr": "Esri",
}

GRADIENTE_CALOR = {0.2: "#0891B2", 0.45: "#14B8A6", 0.7: "#F59E0B", 1.0: "#DC2626"}


def _adicionar_camadas(mapa: folium.Map, padrao: str = "Oceano (batimetria)") -> None:
    """Acrescenta as camadas de base, começando pela escolhida."""
    ordem = [padrao] + [nome for nome in CAMADAS_BASE if nome != padrao]
    for nome in ordem:
        definicao = CAMADAS_BASE[nome]
        folium.TileLayer(
            tiles=definicao["tiles"],
            attr=definicao["attr"],
            name=nome,
            overlay=False,
            control=True,
            max_zoom=definicao.get("max_zoom", 19),
        ).add_to(mapa)

    folium.TileLayer(
        tiles=CAMADA_ROTULOS_OCEANO["tiles"],
        attr=CAMADA_ROTULOS_OCEANO["attr"],
        name="Nomes de feições marinhas",
        overlay=True,
        control=True,
        show=False,
        max_zoom=13,
    ).add_to(mapa)


def _popup_ocorrencia(ponto: dict, publico: bool) -> str:
    """HTML do pop-up de um marcador."""
    estilo = estilo_status(ponto.get("status"))
    data = str(ponto.get("data_hora_avistamento") or "")[:16].replace("T", " ")
    protocolo = html.escape(str(ponto.get("protocolo", "—")))

    linhas = [
        "<div style='font-family:system-ui;min-width:238px;max-width:300px'>",
        f"<div style='font-weight:800;color:{AZUL_MARINHO};font-size:14.5px;"
        f"letter-spacing:.02em'>{protocolo}</div>",
        f"<div style='margin:7px 0;padding:3px 9px;border-radius:999px;"
        f"display:inline-block;background:{estilo['cor']}1A;color:{estilo['cor']};"
        f"font-weight:700;font-size:12px'>{estilo['icone']} {estilo['rotulo']}</div>",
        "<table style='font-size:12px;border-collapse:collapse;width:100%'>",
        f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>Município</td>"
        f"<td><b>{html.escape(str(ponto.get('municipio') or '—'))} / "
        f"{html.escape(str(ponto.get('estado') or '—'))}</b></td></tr>",
        f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>Avistamento</td>"
        f"<td>{html.escape(data) or '—'}</td></tr>",
        f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>Origem</td>"
        f"<td>{html.escape(str(ponto.get('origem_registro') or '—')).replace('_', ' ').capitalize()}"
        f"</td></tr>",
    ]

    if ponto.get("quantidade_observada"):
        linhas.append(
            f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>Quantidade</td>"
            f"<td>{ponto['quantidade_observada']}</td></tr>"
        )

    if not publico:
        linhas.append(
            f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>Coordenadas</td>"
            f"<td>{ponto.get('latitude')}, {ponto.get('longitude')}</td></tr>"
        )
        if ponto.get("classe_ia"):
            score = ponto.get("score_ia")
            texto_score = f" ({score * 100:.1f}%)" if score is not None else ""
            linhas.append(
                f"<tr><td style='padding:2px 8px 2px 0;color:#6B8795'>IA</td>"
                f"<td>{html.escape(str(ponto['classe_ia'])).replace('_', ' ')}"
                f"{texto_score}</td></tr>"
            )

    linhas.append("</table>")

    if str(ponto.get("tipo_dado")) == "DEMO":
        linhas.append(
            "<div style='margin-top:7px;padding:5px 7px;border:1px dashed #F59E0B;"
            "border-radius:7px;background:#FFFBF2;color:#7A4B00;font-size:11px'>"
            "🧪 Dado de <b>demonstração</b> — não é avistamento real.</div>"
        )
    elif str(ponto.get("tipo_dado")) == "IMPORTADO":
        linhas.append(
            "<div style='margin-top:7px;color:#6B8795;font-size:11px'>"
            "Registro importado de fonte externa documentada.</div>"
        )

    if publico:
        linhas.append(
            "<div style='margin-top:7px;color:#6B8795;font-size:11px'>"
            "📍 Posição <b>aproximada</b> (~1 km) para proteger o local exato.</div>"
        )
    if str(ponto.get("status")) == "PENDENTE":
        linhas.append(
            "<div style='margin-top:5px;color:#7A4B00;font-size:11px'>"
            "Registro ainda <b>não validado</b> por avaliador — não constitui "
            "ocorrência cientificamente confirmada.</div>"
        )

    linhas.append("</div>")
    return "".join(linhas)


def _legenda_html(contagens: dict[str, int], total: int, publico: bool) -> str:
    """Legenda fixa sobre o mapa, com ícone, cor, rótulo e contagem."""
    itens = []
    for chave, estilo in ESTILO_STATUS.items():
        quantidade = contagens.get(chave, 0)
        if quantidade == 0:
            continue
        itens.append(
            f"<div style='display:flex;align-items:center;gap:7px;margin:3px 0'>"
            f"<span style='width:12px;height:12px;border-radius:50%;"
            f"background:{estilo['cor']};border:1.5px solid #fff;display:inline-block;"
            f"box-shadow:0 0 0 1px {estilo['cor']}55'></span>"
            f"<span>{estilo['icone']} {estilo['rotulo']}: <b>{quantidade}</b></span></div>"
        )
    if not itens:
        itens.append("<div>Nenhum registro no filtro atual</div>")

    nota = (
        "Posições aproximadas (~1 km)."
        if publico
        else "Coordenadas precisas (perfil autorizado)."
    )
    return f"""
    <div style="position:fixed;bottom:26px;left:14px;z-index:9999;
                background:rgba(255,255,255,.97);border:1px solid #D7E3E8;
                border-radius:12px;padding:10px 12px;font-family:system-ui;
                font-size:12px;color:#334155;
                box-shadow:0 6px 22px rgba(6,43,67,.18);max-width:250px">
        <div style="font-weight:800;color:{AZUL_MARINHO};margin-bottom:6px;
                    font-size:12.5px">
            {total} registro(s) no mapa
        </div>
        {"".join(itens)}
        <div style="margin-top:6px;color:#6B8795;font-size:11px;
                    border-top:1px solid #EEF4F6;padding-top:5px">{nota}</div>
    </div>
    """


def mapa_ocorrencias(
    pontos: list[dict],
    publico: bool = True,
    agrupar: bool = True,
    clusters=None,
    mapa_de_calor: bool = False,
    camada_base: str = "Oceano (batimetria)",
    altura: int = 560,
    chave: str = "mapa_ocorrencias",
):
    """
    Desenha o mapa dos avistamentos.

    `clusters` (resultado do DBSCAN) acrescenta círculos com o raio de cada
    agrupamento; `mapa_de_calor` acrescenta uma camada de densidade. As duas
    vêm acompanhadas do aviso de viés de observação na página que as usa.
    """
    if not pontos:
        from app.components.ui import estado_vazio

        estado_vazio(
            "Nenhum avistamento com coordenadas no filtro atual.",
            "Amplie o período ou remova filtros de estado e status.",
            "🗺️",
        )
        return None

    latitudes = [float(p["latitude"]) for p in pontos]
    longitudes = [float(p["longitude"]) for p in pontos]
    centro = (sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes))

    mapa = folium.Map(
        location=centro,
        zoom_start=ZOOM_BRASIL if len(pontos) > 20 else 7,
        tiles=None,  # as camadas são adicionadas abaixo, com atribuição
        control_scale=True,
    )
    _adicionar_camadas(mapa, camada_base)

    camada_marcadores = (
        MarkerCluster(
            name="Avistamentos (agrupados)",
            options={
                "maxClusterRadius": 42,
                "spiderfyOnMaxZoom": True,
                "showCoverageOnHover": False,
            },
        ).add_to(mapa)
        if agrupar
        else folium.FeatureGroup(name="Avistamentos").add_to(mapa)
    )

    contagens: dict[str, int] = {}
    for ponto in pontos:
        status = str(ponto.get("status"))
        contagens[status] = contagens.get(status, 0) + 1
        estilo = estilo_status(status)
        folium.CircleMarker(
            location=(float(ponto["latitude"]), float(ponto["longitude"])),
            radius=7.5,
            color="#FFFFFF",
            weight=2,
            fill=True,
            fill_color=estilo["cor"],
            fill_opacity=0.92,
            popup=folium.Popup(_popup_ocorrencia(ponto, publico), max_width=320),
            tooltip=f"{estilo['icone']} {ponto.get('protocolo', '')} — {estilo['rotulo']}",
        ).add_to(camada_marcadores)

    if mapa_de_calor:
        HeatMap(
            [[float(p["latitude"]), float(p["longitude"])] for p in pontos],
            name="Densidade de notificações",
            radius=20,
            blur=26,
            min_opacity=0.32,
            gradient=GRADIENTE_CALOR,
        ).add_to(mapa)

    if clusters:
        camada_areas = folium.FeatureGroup(name="Áreas de concentração (DBSCAN)")
        for cluster in clusters:
            folium.Circle(
                location=(cluster.latitude_centro, cluster.longitude_centro),
                radius=max(cluster.raio_maximo_km, 1) * 1000,
                color=TURQUESA,
                weight=2,
                fill=True,
                fill_opacity=0.08,
                dash_array="6",
                tooltip=(
                    f"{cluster.nome} — {cluster.quantidade} registros, "
                    f"raio {cluster.raio_maximo_km} km. "
                    "Concentração de notificações, não de indivíduos."
                ),
            ).add_to(camada_areas)
        camada_areas.add_to(mapa)

    Fullscreen(
        position="topleft",
        title="Tela cheia",
        title_cancel="Sair da tela cheia",
    ).add_to(mapa)
    MiniMap(
        tile_layer="cartodbpositron",
        toggle_display=True,
        position="bottomright",
        width=132,
        height=132,
    ).add_to(mapa)
    MeasureControl(
        position="topleft",
        primary_length_unit="kilometers",
        secondary_length_unit="meters",
        primary_area_unit="sqkilometers",
    ).add_to(mapa)
    folium.LayerControl(collapsed=True, position="topright").add_to(mapa)

    mapa.get_root().html.add_child(
        folium.Element(_legenda_html(contagens, len(pontos), publico))
    )

    return st_folium(
        mapa,
        height=altura,
        use_container_width=True,
        returned_objects=[],  # visualização: não precisamos de retorno de clique
        key=chave,
    )


def mapa_seletor_ponto(
    latitude_inicial: float | None = None,
    longitude_inicial: float | None = None,
    altura: int = 400,
    chave: str = "mapa_seletor",
) -> tuple[float, float] | None:
    """
    Mapa para o usuário marcar o local do avistamento.

    Devolve `(latitude, longitude)` do último clique, ou `None` se ainda não
    houve clique. Um marcador mostra a posição atualmente selecionada.
    """
    tem_inicial = latitude_inicial is not None and longitude_inicial is not None
    centro = (
        (float(latitude_inicial), float(longitude_inicial)) if tem_inicial else CENTRO_BRASIL
    )

    mapa = folium.Map(
        location=centro,
        zoom_start=ZOOM_POR_CONTEXTO["ponto"] if tem_inicial else ZOOM_BRASIL,
        tiles=None,
        control_scale=True,
    )
    _adicionar_camadas(mapa, "Satélite")
    Fullscreen(position="topleft", title="Tela cheia").add_to(mapa)
    folium.LayerControl(collapsed=True, position="topright").add_to(mapa)

    if tem_inicial:
        folium.Marker(
            location=centro,
            tooltip="Local selecionado — toque no mapa para ajustar",
            icon=folium.Icon(color="orange", icon="info-sign"),
        ).add_to(mapa)
        folium.Circle(
            location=centro, radius=120, color=TURQUESA, weight=2,
            fill=True, fill_opacity=0.12,
        ).add_to(mapa)

    st.caption(
        "Toque no mapa para marcar o local onde você viu o peixe. "
        "A imagem de satélite ajuda a reconhecer costões, ilhas e recifes."
    )
    retorno = st_folium(
        mapa,
        height=altura,
        use_container_width=True,
        returned_objects=["last_clicked"],
        key=chave,
    )

    clique = (retorno or {}).get("last_clicked")
    if clique and clique.get("lat") is not None:
        return (float(clique["lat"]), float(clique["lng"]))
    return None


def mini_mapa(
    latitude: float,
    longitude: float,
    rotulo: str = "Local do avistamento",
    altura: int = 240,
    chave: str = "mini_mapa",
) -> None:
    """Prévia do ponto capturado, exibida na confirmação do registro."""
    mapa = folium.Map(
        location=(float(latitude), float(longitude)),
        zoom_start=ZOOM_POR_CONTEXTO["municipio"],
        tiles=CAMADAS_BASE["Satélite"]["tiles"],
        attr=CAMADAS_BASE["Satélite"]["attr"],
        control_scale=True,
        zoom_control=False,
    )
    folium.Circle(
        location=(float(latitude), float(longitude)),
        radius=400,
        color=TURQUESA,
        weight=2,
        fill=True,
        fill_opacity=0.15,
    ).add_to(mapa)
    folium.Marker(
        location=(float(latitude), float(longitude)),
        tooltip=rotulo,
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(mapa)
    st_folium(mapa, height=altura, use_container_width=True, returned_objects=[], key=chave)
