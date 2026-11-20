"""
Administração — usuários, dados de demonstração, importação e auditoria.

Exclusivo do perfil administrador. Todas as operações desta página são
registradas no log de auditoria.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd
import streamlit as st

from app.components.auth_ui import faixa_especialista, proteger
from app.components.tables import formatar_data, tabela
from app.components.ui import (
    aviso,
    estado_vazio,
    linha_kpis,
    rodape_institucional,
    titulo_secao,
)
from src.data.demo_seed import GeradorDemonstracao
from src.data.importers import ImportadorOcorrencias
from src.database import queries
from src.database.repositories import (
    AuditoriaRepository,
    FonteDadosRepository,
    OcorrenciaRepository,
    RegistroDuplicado,
    UsuarioRepository,
)
from src.database.schema import Perfil
from src.security.auth import SenhaFraca, ServicoAutenticacao
from src.security.permissions import Permissao
from src.services.image_storage import ArmazenamentoImagens

sessao = proteger(Permissao.GERENCIAR_USUARIOS, "Administração")

faixa_especialista(
    sessao,
    "Administração",
    "Contas de acesso, dados de demonstração, importação de fontes externas e "
    "trilha de auditoria. <b>Exclusivo do perfil administrador.</b>",
)

kpis = queries.kpis_gerais()
armazenamento = ArmazenamentoImagens()

linha_kpis(
    [
        {"rotulo": "Ocorrências na base", "valor": kpis["total"]},
        {
            "rotulo": "Registros de demonstração",
            "valor": kpis["demonstrativos"],
            "nota": "rotulados como DEMO",
        },
        {"rotulo": "Usuários cadastrados", "valor": len(UsuarioRepository().listar())},
        {
            "rotulo": "Imagens armazenadas",
            "valor": round(armazenamento.espaco_utilizado_bytes() / (1024 * 1024), 1),
            "nota": "MB em disco",
            "formato": "{:.1f}",
        },
    ]
)

abas = st.tabs(["Usuários", "Dados de demonstração", "Importar fonte externa", "Auditoria"])

# ----------------------------------------------------------------- usuários
with abas[0]:
    titulo_secao("Contas de acesso")
    usuarios = UsuarioRepository().listar()
    tabela(
        pd.DataFrame(
            [
                {
                    "Usuário": usuario.identificador,
                    "Nome": usuario.nome or "—",
                    "Perfil": str(usuario.perfil),
                    "Ativo": "sim" if usuario.ativo else "não",
                    "Criado em": formatar_data(usuario.criado_em),
                    "Último acesso": formatar_data(usuario.ultimo_acesso),
                }
                for usuario in usuarios
            ]
        ),
        mensagem_vazia="Nenhum usuário cadastrado.",
    )

    titulo_secao("Criar nova conta")
    with st.form("form_novo_usuario"):
        coluna_identificador, coluna_nome = st.columns(2)
        with coluna_identificador:
            identificador = st.text_input("Identificador (login)", key="adm_login")
        with coluna_nome:
            nome = st.text_input("Nome completo", key="adm_nome")
        coluna_perfil, coluna_senha = st.columns(2)
        with coluna_perfil:
            perfil = st.selectbox(
                "Perfil",
                options=[Perfil.PESQUISADOR, Perfil.ADMINISTRADOR],
                format_func=str,
                key="adm_perfil",
            )
        with coluna_senha:
            senha = st.text_input(
                "Senha inicial",
                type="password",
                key="adm_senha",
                help="Mínimo de 8 caracteres. Armazenada como hash scrypt com sal.",
            )
        criar = st.form_submit_button("Criar conta", type="primary", use_container_width=True)

    if criar:
        try:
            criado = ServicoAutenticacao().criar_usuario(
                identificador=identificador,
                senha=senha,
                perfil=perfil,
                nome=nome or None,
                criado_por=sessao.usuario_id,
            )
        except SenhaFraca as erro:
            st.error(f"Senha inválida: {erro}")
        except RegistroDuplicado:
            st.error("Já existe uma conta com esse identificador.")
        except ValueError as erro:
            st.error(str(erro))
        else:
            st.success(f"Conta `{criado.identificador}` criada com perfil {criado.perfil}.")
            st.rerun()

    titulo_secao("Ativar ou desativar")
    if usuarios:
        alvo = st.selectbox(
            "Conta",
            options=[usuario.identificador for usuario in usuarios],
            key="adm_alvo",
        )
        selecionado = next(u for u in usuarios if u.identificador == alvo)
        if selecionado.id == sessao.usuario_id:
            st.caption("Você não pode desativar a sua própria conta nesta tela.")
        else:
            novo_estado = not selecionado.ativo
            rotulo = "Ativar conta" if novo_estado else "Desativar conta"
            if st.button(rotulo, key="adm_toggle"):
                UsuarioRepository().definir_ativo(selecionado.id, novo_estado)
                AuditoriaRepository().registrar(
                    entidade="usuario",
                    acao="ATIVACAO" if novo_estado else "DESATIVACAO",
                    entidade_id=str(selecionado.id),
                    usuario_id=sessao.usuario_id,
                )
                st.success(f"Conta `{alvo}` atualizada.")
                st.rerun()

# ------------------------------------------------------ dados de demonstração
with abas[1]:
    titulo_secao(
        "Dados de demonstração",
        "Servem para exercitar os painéis sem depender de volume real de registros.",
    )
    st.markdown(
        """
Regras aplicadas a estes dados, sem exceção:

- recebem `tipo_dado = DEMO` e `origem_registro = DEMONSTRACAO`;
- a posição é gravada como **região aproximada**, nunca como leitura de GPS;
- **não recebem predição de IA** — score fabricado seria resultado de modelo
  inventado, e o painel de IA mostra apenas inferências reais;
- não têm imagem associada;
- a geração é determinística (semente fixa), portanto reproduzível;
- qualquer filtro de procedência os remove por completo.

Eles **não** representam ocorrências reais em nenhum município.
        """
    )

    coluna_gerar, coluna_remover = st.columns(2)
    with coluna_gerar:
        quantidade = st.number_input(
            "Quantidade a gerar", min_value=10, max_value=1000, value=120, step=10, key="adm_qtd"
        )
        semente = st.number_input(
            "Semente", min_value=1, max_value=999999, value=20262, step=1, key="adm_semente"
        )
        if st.button("🧪 Gerar dados de demonstração", key="adm_gerar", use_container_width=True):
            with st.spinner("Gerando registros..."):
                resultado = GeradorDemonstracao().gerar(
                    quantidade=int(quantidade), semente=int(semente)
                )
            st.success(resultado.mensagem)
            if resultado.ja_existentes:
                st.caption(
                    f"{resultado.ja_existentes} registro(s) já existiam com esta "
                    "semente e foram mantidos (operação idempotente)."
                )
            st.rerun()

    with coluna_remover:
        st.metric("Registros DEMO na base", kpis["demonstrativos"])
        if kpis["demonstrativos"]:
            aviso(
                "A remoção apaga todos os registros de demonstração e, em "
                "cascata, o histórico de validação deles. Registros reais e "
                "importados não são afetados."
            )
            confirmar = st.checkbox(
                "Confirmo a remoção dos dados de demonstração", key="adm_conf_remover"
            )
            if st.button(
                "🗑️ Remover dados de demonstração",
                key="adm_remover",
                disabled=not confirmar,
                use_container_width=True,
            ):
                removidos = GeradorDemonstracao().remover()
                st.success(f"{removidos} registro(s) de demonstração removido(s).")
                st.rerun()

# ------------------------------------------------------------- importação
with abas[2]:
    titulo_secao(
        "Importar ocorrências de fonte documentada",
        "Aceita CSV/TSV exportado do GBIF ou do iNaturalist.",
    )
    st.markdown(
        """
O que a importação faz:

- registra a **procedência** do lote (nome, URL, licença, data) antes de inserir;
- marca cada ocorrência como `IMPORTADO`, com `origem_localizacao = IMPORTADA`;
- mantém o status **pendente** — base externa não confirma ocorrência pela
  nossa equipe de avaliação;
- descarta linhas sem coordenada válida, fora da área de monitoramento, com
  data inválida ou de outra espécie, e informa quantas;
- usa o identificador da observação na chave de idempotência, então reimportar
  o mesmo arquivo não duplica registros.
        """
    )

    arquivo = st.file_uploader(
        "Arquivo CSV/TSV", type=["csv", "tsv", "txt"], key="adm_arquivo_import"
    )
    coluna_nome_fonte, coluna_licenca = st.columns(2)
    with coluna_nome_fonte:
        nome_fonte = st.text_input("Nome da fonte", value="GBIF", key="adm_fonte_nome")
    with coluna_licenca:
        licenca = st.text_input("Licença declarada", value="CC-BY 4.0", key="adm_fonte_licenca")
    url_fonte = st.text_input("URL da fonte", value="https://www.gbif.org", key="adm_fonte_url")
    limite = st.number_input(
        "Limite de registros a importar", min_value=1, max_value=20000, value=500, key="adm_limite"
    )

    if arquivo is not None and st.button(
        "⬆️ Importar", type="primary", key="adm_importar", use_container_width=True
    ):
        destino = RAIZ / "data" / "raw" / f"import_{arquivo.name}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(arquivo.getvalue())
        with st.spinner("Importando..."):
            resultado = ImportadorOcorrencias().importar_csv(
                caminho_csv=destino,
                nome_fonte=nome_fonte.strip() or "FONTE_EXTERNA",
                url=url_fonte.strip() or None,
                licenca=licenca.strip() or None,
                limite=int(limite),
            )
        st.success(resultado.resumo)
        if resultado.erros:
            with st.expander(f"{len(resultado.erros)} erro(s) durante a importação"):
                for erro in resultado.erros[:50]:
                    st.caption(erro)

    titulo_secao("Fontes já registradas")
    fontes = FonteDadosRepository().listar()
    tabela(
        pd.DataFrame(
            [
                {
                    "Fonte": fonte.nome,
                    "Tipo": fonte.tipo_fonte,
                    "Licença": fonte.licenca or "—",
                    "Importado em": formatar_data(fonte.data_importacao),
                    "URL": fonte.url or "—",
                }
                for fonte in fontes
            ]
        ),
        mensagem_vazia="Nenhuma fonte registrada.",
    )

# --------------------------------------------------------------- auditoria
with abas[3]:
    titulo_secao(
        "Trilha de auditoria",
        "Cadastros, decisões de validação, logins, importações e operações "
        "administrativas.",
    )
    registros = AuditoriaRepository().listar(limite=300)
    if not registros:
        estado_vazio("Nenhum evento de auditoria registrado.", None, "📜")
    else:
        repositorio_usuarios = UsuarioRepository()
        linhas = []
        for item in registros:
            usuario = (
                repositorio_usuarios.por_id(item.usuario_id) if item.usuario_id else None
            )
            linhas.append(
                {
                    "Data/hora": formatar_data(item.data_hora),
                    "Ação": item.acao,
                    "Entidade": item.entidade,
                    "Identificador": item.entidade_id or "—",
                    "Usuário": usuario.identificador if usuario else "—",
                    "Detalhes": (item.detalhes or "")[:160],
                }
            )
        tabela(pd.DataFrame(linhas), altura=420)
        st.caption(
            f"{AuditoriaRepository().contar()} evento(s) no total. "
            "Nenhuma senha, contato ou coordenada precisa é gravada na auditoria."
        )

    titulo_secao("Integridade do armazenamento de imagens")
    ocorrencias_com_imagem = OcorrenciaRepository().listar(limite=2000)
    from src.database.repositories import ImagemRepository

    repositorio_imagens = ImagemRepository()
    faltando = []
    for ocorrencia in ocorrencias_com_imagem:
        imagem = repositorio_imagens.primeira_por_ocorrencia(ocorrencia.id)
        if imagem and not armazenamento.existe(imagem.identificador_arquivo):
            faltando.append((ocorrencia.protocolo, imagem.identificador_arquivo))

    if faltando:
        aviso(
            f"{len(faltando)} registro(s) apontam para arquivos de imagem "
            "ausentes no disco. Em hospedagem com disco efêmero, isso acontece "
            "após um redeploy — ver `docs/deploy.md`."
        )
        for protocolo, arquivo_ausente in faltando[:20]:
            st.caption(f"- `{protocolo}` → `{arquivo_ausente}`")
    else:
        st.success("Todos os registros com imagem têm o arquivo correspondente no disco.")

rodape_institucional()
