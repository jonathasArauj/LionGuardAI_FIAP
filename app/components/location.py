"""
Captura de localização do avistamento.

Caminhos oferecidos, nesta ordem:
  1. **GPS do dispositivo** pela API de geolocalização do navegador
     (`navigator.geolocation`), que exige contexto seguro — HTTPS em produção
     ou `localhost` em desenvolvimento. Captura latitude, longitude, precisão
     em metros e horário da leitura;
  2. **ponto no mapa**, quando o usuário nega a permissão, o GPS falha ou o
     avistamento ocorreu em outro lugar;
  3. **região aproximada** (estado e município), último recurso, gravada como
     tal e distinguível dos registros com coordenada precisa.

Dois cuidados exigidos pelo escopo (seção 4.4):
  * a localização atual **não** é assumida como o local do avistamento: o
    sistema pergunta explicitamente;
  * coordenadas presentes no EXIF da foto só são usadas com autorização
    explícita do usuário — nunca em silêncio.

A permissão nunca bloqueia o registro: negada, o fluxo segue pelo mapa.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app.components.ui import aviso_privacidade
from src.database.schema import OrigemLocalizacao
from src.services.geolocation import (
    CoordenadaInvalida,
    ESTADOS_LITORANEOS,
    Localizacao,
    classificar_precisao,
    construir_localizacao,
    localizacao_por_regiao,
    municipios_do_estado,
)

CHAVE_GPS_SOLICITADO = "lg_gps_solicitado"
CHAVE_GPS_DADOS = "lg_gps_dados"
CHAVE_PONTO_MANUAL = "lg_ponto_manual"
CHAVE_USO_EXIF = "lg_uso_exif"


@dataclass(slots=True)
class LeituraGPS:
    latitude: float
    longitude: float
    precisao_metros: float | None
    horario: str | None


def _ler_gps(chave: str) -> LeituraGPS | None:
    """
    Executa a API de geolocalização do navegador.

    Usa `streamlit-js-eval`, que injeta o JavaScript necessário e devolve o
    resultado ao Python. Se a biblioteca não estiver instalada, o fluxo cai
    direto no mapa — sem quebrar a página.
    """
    try:
        from streamlit_js_eval import get_geolocation
    except ImportError:
        st.warning(
            "O componente de GPS (`streamlit-js-eval`) não está instalado. "
            "Instale as dependências com `pip install -r requirements.txt` ou "
            "marque o local no mapa abaixo."
        )
        return None

    resultado = get_geolocation(component_key=chave)
    if not resultado:
        return None

    coordenadas = (resultado or {}).get("coords") or {}
    latitude = coordenadas.get("latitude")
    longitude = coordenadas.get("longitude")
    if latitude is None or longitude is None:
        return None

    return LeituraGPS(
        latitude=float(latitude),
        longitude=float(longitude),
        precisao_metros=float(coordenadas["accuracy"])
        if coordenadas.get("accuracy") is not None
        else None,
        horario=str(resultado.get("timestamp")) if resultado.get("timestamp") else None,
    )


def _diagnostico_navegador() -> dict:
    """
    Consulta o estado da permissão e se a página está em contexto seguro.

    Serve para dar uma mensagem precisa ao usuário: "permissão negada" é
    diferente de "HTTPS ausente", e as duas situações pedem ações diferentes.
    """
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return {}

    contexto_seguro = streamlit_js_eval(
        js_expressions="window.isSecureContext", key="lg_contexto_seguro", want_output=True
    )
    return {"contexto_seguro": contexto_seguro}


def _bloco_exif(coordenadas_exif: tuple[float, float] | None) -> Localizacao | None:
    """
    Oferece as coordenadas do EXIF, com consentimento explícito.

    Enquanto o usuário não marcar a caixa, as coordenadas não são usadas.
    """
    if not coordenadas_exif:
        return None

    latitude, longitude = coordenadas_exif
    st.info(
        "📷 Esta foto tem **coordenadas gravadas nos metadados (EXIF)**: "
        f"{latitude:.4f}, {longitude:.4f}. Elas não são usadas sem a sua autorização. "
        "Os metadados são removidos da imagem antes de salvar, de qualquer forma."
    )
    usar = st.checkbox(
        "Autorizo usar as coordenadas da própria foto como local do avistamento",
        key=CHAVE_USO_EXIF,
    )
    if not usar:
        return None
    try:
        return construir_localizacao(
            latitude, longitude, OrigemLocalizacao.MAPA_MANUAL, precisao_metros=None
        )
    except CoordenadaInvalida as erro:
        st.warning(f"Não foi possível usar as coordenadas da foto: {erro}")
        return None


def _bloco_regiao(prefixo: str) -> Localizacao | None:
    """Seleção de estado e município quando não há coordenada alguma."""
    coluna_uf, coluna_municipio = st.columns(2)
    with coluna_uf:
        uf = st.selectbox(
            "Estado (UF) onde você viu",
            options=["—"] + list(ESTADOS_LITORANEOS),
            key=f"{prefixo}_uf",
            help="Apenas estados litorâneos, onde a espécie pode ocorrer.",
        )
    municipio = None
    with coluna_municipio:
        if uf != "—":
            opcoes = ["Não sei / outro"] + municipios_do_estado(uf)
            escolha = st.selectbox("Município (aproximado)", options=opcoes, key=f"{prefixo}_mun")
            municipio = None if escolha == "Não sei / outro" else escolha

    if uf == "—":
        return None
    try:
        localizacao = localizacao_por_regiao(uf, municipio)
    except CoordenadaInvalida as erro:
        st.warning(str(erro))
        return None

    st.caption(
        "Será gravado como **região aproximada** — o sistema diferencia esse "
        "registro dos que têm coordenada precisa."
    )
    return localizacao


def capturar_localizacao(
    coordenadas_exif: tuple[float, float] | None = None,
    prefixo: str = "loc",
) -> Localizacao | None:
    """
    Renderiza o fluxo completo de localização e devolve a escolha final.

    Devolve `None` enquanto o usuário não tiver definido um local válido.
    """
    st.markdown("#### 📍 Onde foi o avistamento?")

    localizacao_exif = _bloco_exif(coordenadas_exif)
    if localizacao_exif is not None:
        _resumo_localizacao(localizacao_exif)
        return localizacao_exif

    # ------------------------------------------------- pergunta obrigatória
    no_local = st.radio(
        "Você está **agora** no local onde viu o peixe?",
        options=["Sim, estou no local", "Não, vi em outro lugar"],
        key=f"{prefixo}_no_local",
        horizontal=False,
        help=(
            "Essa pergunta evita registrar a sua posição atual como se fosse o "
            "local do avistamento."
        ),
    )
    esta_no_local = no_local.startswith("Sim")

    localizacao: Localizacao | None = None

    if esta_no_local:
        if not st.session_state.get(CHAVE_GPS_SOLICITADO):
            if st.button(
                "📡 Usar o GPS do meu aparelho",
                key=f"{prefixo}_btn_gps",
                type="primary",
                use_container_width=True,
            ):
                st.session_state[CHAVE_GPS_SOLICITADO] = True
                st.rerun()
            aviso_privacidade(
                "O navegador vai pedir sua autorização. A posição é usada somente "
                "para localizar o avistamento e aparece no mapa público de forma "
                "aproximada (~1 km)."
            )
            st.caption("Prefere marcar no mapa? Use a opção abaixo.")
        else:
            with st.spinner("Obtendo a localização pelo GPS do aparelho..."):
                leitura = _ler_gps(f"{prefixo}_gps")

            if leitura is not None:
                st.session_state[CHAVE_GPS_DADOS] = {
                    "latitude": leitura.latitude,
                    "longitude": leitura.longitude,
                    "precisao_metros": leitura.precisao_metros,
                    "horario": leitura.horario,
                }
            dados = st.session_state.get(CHAVE_GPS_DADOS)

            if dados:
                try:
                    localizacao = construir_localizacao(
                        dados["latitude"],
                        dados["longitude"],
                        OrigemLocalizacao.GPS_DISPOSITIVO,
                        precisao_metros=dados.get("precisao_metros"),
                    )
                    st.success(
                        "✅ **Localização identificada** — "
                        f"{classificar_precisao(dados.get('precisao_metros'))}."
                    )
                except CoordenadaInvalida as erro:
                    st.warning(f"{erro} Marque o local no mapa abaixo.")
            else:
                diagnostico = _diagnostico_navegador()
                if diagnostico.get("contexto_seguro") is False:
                    st.error(
                        "O navegador só libera o GPS em **contexto seguro**: use "
                        "`https://` em produção ou `localhost` no desenvolvimento. "
                        "Marque o local no mapa abaixo."
                    )
                else:
                    st.warning(
                        "Ainda não recebemos a posição. Autorize o acesso à "
                        "localização na janela do navegador — ou marque o local no "
                        "mapa abaixo. **Seu registro não será perdido.**"
                    )

    # ---------------------------------------- fallback: mapa e, depois, região
    rotulo_mapa = (
        "Prefiro marcar no mapa" if esta_no_local else "Marque no mapa o local do avistamento"
    )
    with st.expander(f"🗺️ {rotulo_mapa}", expanded=(localizacao is None)):
        from app.components.maps import mapa_seletor_ponto

        anterior = st.session_state.get(CHAVE_PONTO_MANUAL)
        clique = mapa_seletor_ponto(
            latitude_inicial=anterior[0] if anterior else None,
            longitude_inicial=anterior[1] if anterior else None,
            chave=f"{prefixo}_mapa",
        )
        if clique:
            st.session_state[CHAVE_PONTO_MANUAL] = clique
            anterior = clique

        if anterior:
            try:
                localizacao_mapa = construir_localizacao(
                    anterior[0], anterior[1], OrigemLocalizacao.MAPA_MANUAL
                )
                st.success(
                    f"📍 Ponto marcado: {localizacao_mapa.municipio or '—'} / "
                    f"{localizacao_mapa.estado or '—'}"
                )
                if st.button(
                    "Usar este ponto do mapa", key=f"{prefixo}_usar_mapa", type="primary"
                ):
                    st.session_state[f"{prefixo}_confirmou_mapa"] = True
                if st.session_state.get(f"{prefixo}_confirmou_mapa") or not esta_no_local:
                    localizacao = localizacao_mapa
            except CoordenadaInvalida as erro:
                st.warning(str(erro))

        st.divider()
        st.caption("Não consegue marcar o ponto? Informe apenas a região:")
        localizacao_regiao = _bloco_regiao(prefixo)
        if localizacao is None and localizacao_regiao is not None:
            localizacao = localizacao_regiao

    if localizacao is not None:
        _resumo_localizacao(localizacao)
    return localizacao


def _resumo_localizacao(localizacao: Localizacao) -> None:
    """Resumo do que será gravado, incluindo a origem da coordenada."""
    from app.components.maps import mini_mapa

    colunas = st.columns([3, 2])
    with colunas[0]:
        st.markdown(
            f"**Local:** {localizacao.municipio or 'não informado'} / "
            f"{localizacao.estado or '—'}  \n"
            f"**Origem da posição:** {localizacao.descricao_origem()}  \n"
            f"**Precisão:** {classificar_precisao(localizacao.precisao_metros)}"
        )
        if localizacao.municipio_sugerido and localizacao.distancia_referencia_km is not None:
            st.caption(
                f"Município sugerido automaticamente pelo ponto mais próximo "
                f"({localizacao.distancia_referencia_km:.1f} km de "
                f"{localizacao.municipio}). Você pode corrigir no formulário."
            )
    with colunas[1]:
        if localizacao.tem_coordenadas:
            mini_mapa(localizacao.latitude, localizacao.longitude)


def limpar_estado_localizacao(prefixo: str = "loc") -> None:
    """Zera o estado da captura (após registrar um avistamento)."""
    for chave in (
        CHAVE_GPS_SOLICITADO,
        CHAVE_GPS_DADOS,
        CHAVE_PONTO_MANUAL,
        CHAVE_USO_EXIF,
        f"{prefixo}_confirmou_mapa",
    ):
        st.session_state.pop(chave, None)
