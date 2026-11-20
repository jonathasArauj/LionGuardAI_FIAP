"""
Dashboard 5 — painel operacional e validação de ocorrências.

Exclusivo de avaliadores e administradores. Toda decisão exige justificativa,
fica registrada no histórico e é refletida imediatamente nos demais painéis,
porque todos leem do banco a cada carregamento (sem cache de consultas).
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.auth_ui import faixa_especialista, proteger
from app.components.filters import barra_de_filtros, resumo_filtros
from app.components.maps import mini_mapa
from app.components.tables import (
    formatar_data,
    formatar_score,
    tabela_ocorrencias,
)
from app.components.ui import (
    aviso,
    banner_demonstracao,
    estado_vazio,
    etiqueta_classe_ia,
    linha_kpis,
    mostrar_status,
    rodape_institucional,
    titulo_secao,
)
from app.styles.theme import LARANJA_ALERTA, TURQUESA
from src.database.repositories import ImagemRepository, PredicaoRepository, UsuarioRepository
from src.database.schema import Decisao
from src.security.permissions import Permissao, tem_permissao
from src.services.analytics import ROTULOS_HABITAT, painel_operacional
from src.services.image_storage import ArmazenamentoImagens
from src.services.validation import ErroValidacao, ServicoValidacao

sessao = proteger(Permissao.VER_PAINEL_OPERACIONAL, "Painel de validação")
pode_validar = tem_permissao(sessao, Permissao.VALIDAR_OCORRENCIA)
pode_ver_preciso = tem_permissao(sessao, Permissao.VER_COORDENADAS_PRECISAS)

faixa_especialista(
    sessao,
    "Validação de ocorrências",
    "Fila de revisão, decisão com justificativa obrigatória e histórico "
    "auditável. É aqui — e só aqui — que um registro deixa de ser pendente.",
)

filtros = barra_de_filtros(prefixo="val", expandido=False)
st.caption(resumo_filtros(filtros))

painel = painel_operacional(filtros)
indicadores = painel["indicadores"]

banner_demonstracao(visivel=filtros.inclui_demonstracao)

linha_kpis(
    [
        {
            "rotulo": "Pendentes",
            "valor": indicadores["pendentes"],
            "nota": "aguardando primeira decisão",
            "cor_borda": LARANJA_ALERTA,
        },
        {
            "rotulo": "Aguardando informações",
            "valor": indicadores["aguardando_info"],
            "nota": "devolvidos ao informante",
        },
        {
            "rotulo": "Revisados",
            "valor": indicadores["revisados"],
            "nota": "com decisão final registrada",
        },
        {
            "rotulo": "Tempo mediano de revisão",
            "valor": indicadores["tempo_mediano_revisao_horas"],
            "nota": "horas até a 1ª decisão",
            "formato": "{:.1f}",
            "cor_borda": TURQUESA,
        },
    ]
)
linha_kpis(
    [
        {
            "rotulo": "Sem coordenadas",
            "valor": indicadores["sem_coordenadas"],
            "nota": "localização incompleta",
        },
        {
            "rotulo": "Sem fotografia",
            "valor": indicadores["sem_imagem"],
            "nota": "sem imagem para análise",
        },
        {
            "rotulo": "Com erro de IA",
            "valor": indicadores["com_erro_ia"],
            "nota": "inferência falhou",
        },
        {
            "rotulo": "Possíveis duplicidades",
            "valor": painel["quantidade_duplicatas"],
            "nota": "pares próximos em tempo e espaço",
        },
    ]
)

if painel["quantidade_duplicatas"]:
    with st.expander(
        f"Ver {painel['quantidade_duplicatas']} par(es) suspeito(s) de duplicidade"
    ):
        st.caption(
            "Heurística: coordenadas a menos de ~1 km e avistamentos na mesma "
            "janela de 24 horas. É um alerta para conferência, **não** uma "
            "afirmação de duplicidade."
        )
        for protocolo_a, protocolo_b in painel["possiveis_duplicatas"][:40]:
            st.write(f"- `{protocolo_a}` ↔ `{protocolo_b}`")

# ------------------------------------------------------------------- fila
st.divider()
titulo_secao("Fila de ocorrências", "Pendentes primeiro, dos mais antigos aos mais novos.")

fila = painel["fila"]
if not fila:
    estado_vazio(
        "Nenhuma ocorrência neste recorte.",
        "Ajuste os filtros para ver outros registros.",
        "✅",
    )
    rodape_institucional()
    st.stop()

tabela_ocorrencias(
    fila,
    altura=320,
    colunas={
        "protocolo": "Protocolo",
        "data_hora_avistamento": "Avistamento",
        "data_hora_cadastro": "Cadastro",
        "municipio": "Município",
        "estado": "UF",
        "classe_ia": "Resultado da IA",
        "score_ia": "Score",
        "status": "Status",
        "tipo_dado": "Procedência",
    },
)

# ----------------------------------------------------------- revisão
st.divider()
titulo_secao("Revisar uma ocorrência")

opcoes = {
    f"{registro['protocolo']} — {registro.get('municipio') or '—'}/"
    f"{registro.get('estado') or '—'} — {registro['status']}": registro
    for registro in fila
}
escolha = st.selectbox("Ocorrência", options=list(opcoes), key="val_escolha")
registro = opcoes[escolha]

coluna_imagem, coluna_dados = st.columns([2, 3])

with coluna_imagem:
    armazenamento = ArmazenamentoImagens()
    imagem = ImagemRepository().primeira_por_ocorrencia(registro["id"])
    if imagem is None:
        aviso("Esta ocorrência não tem fotografia anexada.")
    else:
        conteudo = armazenamento.ler(imagem.identificador_arquivo)
        if conteudo is None:
            aviso(
                "O arquivo de imagem não foi encontrado no armazenamento "
                f"(`{imagem.identificador_arquivo}`). Registro gravado, arquivo ausente."
            )
        else:
            st.image(conteudo, caption="Fotografia enviada", use_container_width=True)
            st.caption(
                f"{imagem.largura}×{imagem.altura} px · {imagem.formato.upper()} · "
                f"{imagem.tamanho_bytes / 1024:.0f} KB · "
                f"EXIF {'removido' if imagem.exif_removido else 'preservado'} · "
                f"hash `{imagem.hash_sha256[:12]}…`"
            )
            iguais = [
                outra
                for outra in ImagemRepository().por_hash(imagem.hash_sha256)
                if outra.ocorrencia_id != registro["id"]
            ]
            if iguais:
                aviso(
                    f"Esta mesma imagem (hash idêntico) consta em {len(iguais)} "
                    "outra(s) ocorrência(s). Verifique duplicidade antes de confirmar."
                )

with coluna_dados:
    st.markdown(f"#### Protocolo `{registro['protocolo']}`")
    mostrar_status(registro["status"])

    predicao = PredicaoRepository().ultima_por_ocorrencia(registro["id"])
    if predicao is not None:
        st.markdown(
            etiqueta_classe_ia(str(predicao.classe), predicao.score), unsafe_allow_html=True
        )
        st.caption(
            f"Modelo {predicao.modelo} v{predicao.versao} · "
            f"{predicao.tempo_inferencia_ms or 0:.0f} ms · "
            f"score {formatar_score(predicao.score)}"
        )
    else:
        st.caption("Sem análise automática para esta ocorrência.")

    localizacao_texto = (
        f"{registro.get('latitude')}, {registro.get('longitude')}"
        if pode_ver_preciso and registro.get("latitude") is not None
        else "coordenadas restritas ao seu perfil"
        if registro.get("latitude") is not None
        else "sem coordenadas"
    )
    st.markdown(
        f"""
- **Avistamento:** {formatar_data(registro.get('data_hora_avistamento'))}
- **Cadastro:** {formatar_data(registro.get('data_hora_cadastro'))}
- **Local:** {registro.get('municipio') or '—'} / {registro.get('estado') or '—'}
- **Coordenadas:** {localizacao_texto}
- **Origem da posição:** {str(registro.get('origem_localizacao') or '—').replace('_', ' ').lower()}
- **Precisão do GPS:** {f"±{registro['precisao_metros']:.0f} m" if registro.get('precisao_metros') else '—'}
- **Profundidade:** {f"{registro['profundidade']:.1f} m" if registro.get('profundidade') is not None else 'não informada'}
- **Habitat:** {ROTULOS_HABITAT.get(str(registro.get('habitat')), '—')}
- **Quantidade observada:** {registro.get('quantidade_observada') or 'não informada'}
- **Origem do registro:** {str(registro.get('origem_registro') or '—').replace('_', ' ').capitalize()}
- **Procedência:** {registro.get('tipo_dado')}
- **Revisões anteriores:** {registro.get('revisoes', 0)}
        """
    )
    if registro.get("descricao"):
        st.markdown(f"**Observações do informante:** {registro['descricao']}")

    if registro.get("latitude") is not None:
        mini_mapa(
            float(registro["latitude"]),
            float(registro["longitude"]),
            rotulo=f"Local informado — {registro['protocolo']}",
            altura=220,
        )

# -------------------------------------------------------------- decisão
st.divider()
if not pode_validar:
    st.info("Seu perfil pode consultar a fila, mas não registrar decisões.")
else:
    titulo_secao("Registrar decisão")
    rotulos_decisao = {
        "✅ Confirmar ocorrência": Decisao.CONFIRMAR,
        "🚫 Rejeitar": Decisao.REJEITAR,
        "🔎 Marcar como inconclusiva": Decisao.INCONCLUSIVO,
        "❓ Solicitar informações adicionais": Decisao.SOLICITAR_INFO,
    }

    with st.form("form_validacao"):
        rotulo_escolhido = st.radio(
            "Decisão", options=list(rotulos_decisao), key="val_decisao"
        )
        justificativa = st.text_area(
            "Justificativa (obrigatória)",
            placeholder=(
                "Ex.: padrão de listras e nadadeiras compatível com Pterois volitans; "
                "profundidade e habitat coerentes com o local informado."
            ),
            key="val_justificativa",
            help="Mínimo de 10 caracteres. Fica registrada no histórico da ocorrência.",
        )
        enviado = st.form_submit_button(
            "Salvar decisão", type="primary", use_container_width=True
        )

    if enviado:
        try:
            resultado = ServicoValidacao().decidir(
                ocorrencia_id=registro["id"],
                decisao=rotulos_decisao[rotulo_escolhido],
                justificativa=justificativa,
                sessao=sessao,
            )
        except ErroValidacao as erro:
            st.error(f"❌ {erro}")
        else:
            st.success(f"✅ {resultado.mensagem}")
            st.caption(
                "Indicadores, mapa e painéis já refletem esta decisão — todas as "
                "consultas são lidas do banco a cada carregamento."
            )
            st.rerun()

# ------------------------------------------------------------- histórico
historico = ServicoValidacao().historico(registro["id"], sessao)
if historico:
    st.divider()
    titulo_secao("Histórico de decisões desta ocorrência")
    repositorio_usuarios = UsuarioRepository()
    for item in reversed(historico):
        avaliador = repositorio_usuarios.por_id(item.avaliador_id)
        with st.container(border=True):
            st.markdown(
                f"**{item.decisao}** — {item.status_anterior} → {item.status_novo}  \n"
                f"*{formatar_data(item.data_validacao)}* por "
                f"`{avaliador.identificador if avaliador else item.avaliador_id}`"
            )
            st.caption(item.justificativa)

rodape_institucional()
