"""
Registro de avistamento — fluxo principal da plataforma.

Caminho do cidadão:
    foto → análise da IA → localização → detalhes → confirmação → protocolo

Decisões de usabilidade (seção 4 do escopo):
  * sem login e sem cadastro;
  * a maior parte dos campos é preenchida automaticamente, e todos os campos
    adicionais são opcionais;
  * cada etapa só aparece quando a anterior está resolvida, evitando um
    formulário longo na tela do celular;
  * falha em qualquer etapa (IA indisponível, GPS negado) **não** impede o
    registro, e nenhum dado digitado é perdido;
  * a gravação é confirmada no banco antes de a tela anunciar sucesso.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.ai_result import mostrar_resultado
from app.components.location import capturar_localizacao, limpar_estado_localizacao
from app.components.ui import (
    aviso_privacidade,
    cabecalho,
    orientacao_seguranca,
    rodape_institucional,
    stepper,
)
from app.components.upload import componente_foto, limpar_estado_foto
from app.styles.markup import escrever_html
from src.ai.inference import obter_servico_inferencia
from src.database.schema import Habitat, OrigemRegistro
from src.security.rate_limit import LimitadorRequisicoes
from src.services.analytics import ROTULOS_HABITAT
from src.services.image_storage import calcular_hash
from src.services.sightings import (
    DadosAvistamento,
    ErroRegistro,
    ServicoAvistamentos,
)

CHAVE_SESSAO_NAVEGADOR = "lg_sessao_navegador"
CHAVE_INFERENCIA = "lg_inferencia"
CHAVE_HASH_FOTO = "lg_hash_foto"
CHAVE_RESULTADO = "lg_resultado_registro"
CHAVE_SEM_FOTO = "lg_sem_foto"

ETAPAS = ["Fotografia", "Análise da IA", "Local", "Detalhes", "Protocolo"]

ROTULOS_ORIGEM_PESSOA = {
    "Cidadão / banhista": OrigemRegistro.CIDADAO,
    "Mergulhador": OrigemRegistro.MERGULHADOR,
    "Pescador": OrigemRegistro.PESCADOR,
    "Pesquisador": OrigemRegistro.PESQUISADOR,
}


def _identificador_sessao() -> str:
    """
    Identificador da sessão do navegador, usado na idempotência e no limite de
    envios. Não é dado pessoal: é um valor aleatório válido só nesta sessão.
    """
    if CHAVE_SESSAO_NAVEGADOR not in st.session_state:
        st.session_state[CHAVE_SESSAO_NAVEGADOR] = uuid.uuid4().hex
    return st.session_state[CHAVE_SESSAO_NAVEGADOR]


def _reiniciar_fluxo() -> None:
    for chave in (CHAVE_INFERENCIA, CHAVE_HASH_FOTO, CHAVE_RESULTADO, CHAVE_SEM_FOTO):
        st.session_state.pop(chave, None)
    limpar_estado_foto()
    limpar_estado_localizacao()


# ===================================================== tela de sucesso
resultado_anterior = st.session_state.get(CHAVE_RESULTADO)
if resultado_anterior is not None:
    cabecalho("Avistamento registrado!", "Guarde o protocolo para acompanhar a análise.")
    stepper(ETAPAS, 4)
    st.success(f"✅ {resultado_anterior['mensagem']}")
    escrever_html(st, f"""
        <div class="lg-card" style="text-align:center">
            <div style="font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;
                        color:#5C7A88;font-weight:600">Seu protocolo</div>
            <div style="font-size:2rem;font-weight:800;color:#062B43;letter-spacing:.04em">
                {resultado_anterior['protocolo']}
            </div>
            <div style="font-size:.85rem;color:#6B8795;margin-top:.3rem">
                Status atual: pendente de validação por avaliador
            </div>
        </div>
        """)
    st.caption("Copie o protocolo abaixo — é por ele que você consulta o andamento.")
    st.code(resultado_anterior["protocolo"], language=None)

    for aviso_texto in resultado_anterior.get("avisos", []):
        st.caption(f"ℹ️ {aviso_texto}")

    st.info(
        "O que acontece agora: um avaliador vai analisar a sua foto e os dados do "
        "local. O status muda de **pendente** para confirmado, inconclusivo ou "
        "rejeitado, e o seu registro passa a aparecer no mapa e nos indicadores."
    )

    coluna_a, coluna_b, coluna_c = st.columns(3)
    with coluna_a:
        if st.button("🗺️ Ver no mapa", use_container_width=True, key="suc_mapa"):
            st.switch_page("paginas/mapa.py")
    with coluna_b:
        if st.button("📷 Registrar outro", use_container_width=True, key="suc_outro"):
            _reiniciar_fluxo()
            st.rerun()
    with coluna_c:
        if st.button("🏠 Voltar ao início", use_container_width=True, key="suc_inicio"):
            _reiniciar_fluxo()
            st.switch_page("paginas/inicio.py")

    rodape_institucional()
    st.stop()

# ===================================================== fluxo de registro
cabecalho(
    "Registrar avistamento",
    "Quatro passos simples. Nenhum cadastro é necessário.",
)

limitador = LimitadorRequisicoes()
situacao_limite = limitador.verificar(_identificador_sessao())
if not situacao_limite.permitido:
    st.error(f"⏱️ {situacao_limite.mensagem()}")
    st.caption(
        "Esse limite protege a base contra envios automatizados. "
        "Se você realmente tem vários avistamentos, aguarde e continue depois."
    )
    st.stop()

# O indicador de progresso fica no alto, mas só é desenhado no fim do script:
# a etapa atual depende de o que já foi preenchido abaixo.
espaco_progresso = st.empty()


def _pintar_progresso(etapa: int) -> None:
    with espaco_progresso.container():
        stepper(ETAPAS, etapa)


orientacao_seguranca()

# ---------------------------------------------------------- 1. fotografia
st.markdown("### 1️⃣ A fotografia")
foto = componente_foto()

sem_foto = False
if foto is None:
    with st.expander("Não tenho foto do avistamento"):
        st.caption(
            "A foto é o que permite a análise automática e a validação pelo "
            "avaliador. Sem ela, o registro ainda é aceito, mas vai depender "
            "apenas da sua descrição."
        )
        sem_foto = st.checkbox(
            "Quero registrar mesmo sem foto", key=CHAVE_SEM_FOTO, value=False
        )
    if not sem_foto:
        _pintar_progresso(0)
        rodape_institucional()
        st.stop()

# --------------------------------------------------- 2. análise da IA
resultado_ia = None
coordenadas_exif = None

if foto is not None:
    coordenadas_exif = foto.validada.coordenadas_exif
    hash_foto = calcular_hash(foto.validada.conteudo)

    if st.session_state.get(CHAVE_HASH_FOTO) != hash_foto:
        servico = obter_servico_inferencia()
        with st.spinner("Analisando a imagem com o modelo de visão computacional..."):
            resultado_ia = servico.classificar(foto.validada.conteudo)
        st.session_state[CHAVE_HASH_FOTO] = hash_foto
        st.session_state[CHAVE_INFERENCIA] = resultado_ia
    else:
        resultado_ia = st.session_state.get(CHAVE_INFERENCIA)

    st.markdown("### 2️⃣ Análise automática")
    if resultado_ia is not None:
        mostrar_resultado(resultado_ia)
    if resultado_ia is not None and not resultado_ia.disponivel:
        st.caption(
            "Estado do modelo: "
            f"`{obter_servico_inferencia().estado}` — "
            f"{obter_servico_inferencia().descricao_estado}"
        )

# ------------------------------------------------------- 3. localização
st.markdown("### 3️⃣ O local")
localizacao = capturar_localizacao(coordenadas_exif=coordenadas_exif)

if localizacao is None:
    st.info(
        "Defina o local para continuar: use o GPS, marque um ponto no mapa ou "
        "informe a região aproximada."
    )
    _pintar_progresso(2)
    rodape_institucional()
    st.stop()

# ---------------------------------------------------------- 4. detalhes
_pintar_progresso(3)

st.markdown("### 4️⃣ Detalhes e confirmação")
st.caption("Tudo abaixo é opcional, exceto a data do avistamento.")

with st.form("form_avistamento", clear_on_submit=False):
    coluna_data, coluna_hora = st.columns(2)
    with coluna_data:
        data_avistamento = st.date_input(
            "Data do avistamento",
            value=date.today(),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="reg_data",
            help="Se a foto é de outro dia, informe a data real do avistamento.",
        )
    with coluna_hora:
        hora_avistamento = st.time_input(
            "Hora aproximada",
            value=datetime.now().time().replace(second=0, microsecond=0),
            key="reg_hora",
        )

    coluna_quantidade, coluna_profundidade = st.columns(2)
    with coluna_quantidade:
        quantidade = st.number_input(
            "Quantos indivíduos você viu?",
            min_value=0,
            max_value=200,
            value=1,
            step=1,
            key="reg_quantidade",
            help="Deixe 0 se não souber estimar.",
        )
    with coluna_profundidade:
        profundidade = st.number_input(
            "Profundidade aproximada (metros)",
            min_value=0.0,
            max_value=200.0,
            value=0.0,
            step=0.5,
            key="reg_profundidade",
            help="Deixe 0 se não souber. O campo fica em branco, não como zero.",
        )

    coluna_habitat, coluna_quem = st.columns(2)
    with coluna_habitat:
        rotulos_habitat = {ROTULOS_HABITAT[str(h)]: h for h in Habitat}
        habitat_rotulo = st.selectbox(
            "Tipo de ambiente",
            options=list(rotulos_habitat),
            index=list(rotulos_habitat).index(ROTULOS_HABITAT[str(Habitat.NAO_INFORMADO)]),
            key="reg_habitat",
        )
    with coluna_quem:
        origem_rotulo = st.selectbox(
            "Você é...", options=list(ROTULOS_ORIGEM_PESSOA), key="reg_origem"
        )

    descricao = st.text_area(
        "Observações (opcional)",
        placeholder="Ex.: estava sob uma pedra, perto da entrada da enseada.",
        max_chars=2000,
        key="reg_descricao",
    )

    autoriza_imagem = st.checkbox(
        "Autorizo que minha foto apareça no mapa público",
        value=False,
        key="reg_autoriza",
        help=(
            "Sem esta autorização, a foto é usada apenas na análise e na "
            "validação interna."
        ),
    )
    contato = st.text_input(
        "E-mail ou telefone para contato (opcional)",
        key="reg_contato",
        help=(
            "Guardamos apenas um código derivado do contato (hash), nunca o "
            "contato em si. Serve para o avaliador identificar reenvios."
        ),
    )

    confirmar = st.form_submit_button(
        "✅ Confirmar avistamento", type="primary", use_container_width=True
    )

aviso_privacidade(
    "O que será gravado: a foto (sem metadados EXIF), a localização, a data, o "
    "resultado da IA e os detalhes acima. No mapa público, a posição aparece "
    "arredondada (~1 km) e a foto só aparece com a sua autorização."
)

if confirmar:
    data_hora = datetime.combine(data_avistamento, hora_avistamento or time(12, 0))
    if data_hora > datetime.now():
        data_hora = datetime.now().replace(microsecond=0)

    servico_avistamentos = ServicoAvistamentos()
    hash_imagem = calcular_hash(foto.validada.conteudo) if foto else None
    chave_idempotencia = servico_avistamentos.calcular_chave_idempotencia(
        hash_imagem=hash_imagem,
        data_hora_avistamento=data_hora.replace(microsecond=0).isoformat(),
        latitude=localizacao.latitude,
        longitude=localizacao.longitude,
        sessao=_identificador_sessao(),
    )

    dados = DadosAvistamento(
        localizacao=localizacao,
        data_hora_avistamento=data_hora.replace(microsecond=0).isoformat(),
        origem_registro=ROTULOS_ORIGEM_PESSOA[origem_rotulo],
        imagem=foto.validada if foto else None,
        nome_arquivo_original=foto.nome_arquivo if foto else None,
        inferencia=resultado_ia,
        profundidade=float(profundidade) if profundidade and profundidade > 0 else None,
        habitat=rotulos_habitat[habitat_rotulo],
        quantidade_observada=int(quantidade) if quantidade and quantidade > 0 else None,
        descricao=descricao,
        autoriza_publicar_imagem=bool(autoriza_imagem),
        contato=contato,
        chave_idempotencia=chave_idempotencia,
    )

    try:
        with st.spinner("Gravando o avistamento..."):
            resultado = servico_avistamentos.registrar(dados)
    except ErroRegistro as erro:
        st.error(f"❌ {erro}")
        st.caption(
            "Nada foi gravado e seus dados continuam preenchidos acima. "
            "Corrija o que for necessário e tente novamente."
        )
    else:
        if not resultado.duplicado:
            limitador.registrar(_identificador_sessao())
        st.session_state[CHAVE_RESULTADO] = {
            "protocolo": resultado.protocolo,
            "mensagem": resultado.mensagem,
            "avisos": resultado.avisos,
        }
        st.rerun()

rodape_institucional()
