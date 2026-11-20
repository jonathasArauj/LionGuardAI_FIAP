"""
Conteúdo educativo sobre a espécie.

Todas as afirmações desta página vêm de fontes citadas ao final. Onde o texto
traz interpretação da equipe do projeto, isso está explicitado. A página não
orienta captura nem manuseio do animal.

As fotografias são observações reais publicadas no iNaturalist com licença
Creative Commons, exibidas com autoria e licença. A ilustração é desenho do
próprio projeto e serve de apoio gráfico, não de material de identificação.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st

from app.components.media import galeria_fotos, guia_identificacao, links_oficiais
from app.components.ui import (
    aviso_perigo,
    cabecalho,
    comparacao,
    faq,
    lista_marcada,
    rodape_institucional,
    secao,
)
from app.styles.markup import escrever_html
from app.styles.ilustracoes import peixe_leao_svg
from src.data.conteudo import carregar_conteudo

conteudo = carregar_conteudo(RAIZ / "data" / "conteudo_educativo.json")

cabecalho(
    "Sobre o peixe-leão",
    "O que é a espécie, como reconhecer, por que ela preocupa e o que fazer "
    "ao encontrar uma.",
)

abas = st.tabs(
    [
        "🔎 Identificar",
        "🌊 A espécie",
        "🇧🇷 No Brasil",
        "🛟 O que fazer",
        "📚 Fontes",
    ]
)

# ========================================================= 1. identificação
with abas[0]:
    secao(
        "Identificação",
        "O que olhar primeiro",
        "Três sinais resolvem a maioria dos casos: nadadeiras em leque, "
        "espinhos soltos nas pontas e faixas verticais até na cabeça.",
    )
    guia_identificacao(conteudo)

    st.markdown("")
    coluna_ilustracao, coluna_legenda = st.columns([1.2, 1], gap="large")
    with coluna_ilustracao:
        st.markdown(
            f'<div style="display:flex;justify-content:center">'
            f'{peixe_leao_svg(420, id_unico="esp")}</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Ilustração esquemática produzida pelo projeto — serve para apontar "
            "as estruturas, não para comparar cores e texturas. Para isso, use "
            "as fotografias abaixo."
        )
    with coluna_legenda:
        escrever_html(st, f"""
            <div class="lg-faixa">
                <span class="lg-sobrenome">Anatomia que denuncia a espécie</span>
                {lista_marcada([
                    "<b>Espinhos dorsais</b> — longos, finos e livres nas pontas; "
                    "são 13, e todos venenosos",
                    "<b>Nadadeiras peitorais</b> — abrem como leque, às vezes "
                    "maiores que o próprio corpo",
                    "<b>Faixas verticais</b> — alternadas, percorrendo também a "
                    "cabeça",
                    "<b>Tentáculos sobre os olhos</b> — pequenos apêndices "
                    "carnudos, visíveis de perto",
                    "<b>Espinhos anais e pélvicos</b> — mais três e mais dois, "
                    "fechando os 18 venenosos",
                ])}
            </div>
            """)

    st.markdown("")
    secao("Fotografias", "Observações reais, com licença aberta")
    galeria_fotos(limite=12)

    st.markdown("")
    comparacao(
        "✅ Provavelmente é peixe-leão",
        [
            "Nadadeiras peitorais em leque, desproporcionais ao corpo",
            "Espinhos dorsais longos e <b>separados</b> nas pontas",
            "Listras verticais alternadas, inclusive na cabeça",
            "Parado junto a toca, costão ou estrutura, sem fugir",
            "Entre 15 e 40 cm",
        ],
        "⚠️ Provavelmente é outra coisa",
        conteudo.nao_confundir,
    )

    st.info(
        "**Na dúvida, registre.** A validação é feita por um avaliador humano. "
        "Um registro a mais custa uma conferência; um registro a menos pode "
        "custar uma ocorrência não detectada."
    )
    if st.button("📷 Registrar um avistamento", type="primary", key="esp_registrar_1"):
        st.switch_page("paginas/registrar.py")

# =============================================================== 2. espécie
with abas[1]:
    secao("Biologia", "Por que uma espécie invasora é um problema")
    escrever_html(st, """
O **peixe-leão** (*Pterois volitans*) é um peixe recifal nativo dos oceanos
Índico e Pacífico. Chama atenção pelas listras marrons e claras e pelas longas
nadadeiras em forma de leque, que lembram uma juba — daí o nome.

Essas nadadeiras carregam **espinhos venenosos**. A picada não costuma ser
fatal para pessoas saudáveis, mas provoca dor intensa, inchaço e, em alguns
casos, reação sistêmica. Por isso a orientação de todos os órgãos ambientais é
a mesma: **não tocar**.

No Atlântico Ocidental a espécie é **invasora**. A dispersão começou a partir
da costa da Flórida, nos Estados Unidos, seguiu pelo Caribe e chegou ao Brasil,
inclusive porque ovos e larvas são transportados por correntes marinhas.
        """
    )

    st.markdown(
        """
        | Característica | Consequência |
        | --- | --- |
        | Poucos predadores naturais no Atlântico | A população cresce sem controle biológico |
        | Reprodução frequente e numerosa | Uma área é recolonizada rapidamente após o manejo |
        | Dieta generalista, com peixes juvenis e crustáceos | Pressão sobre o recrutamento de espécies nativas |
        """
    )
    st.markdown(
        """
O impacto não é só ecológico. Peixes juvenis consumidos hoje são a captura da
pesca artesanal de amanhã, e recifes empobrecidos afetam o turismo de mergulho.
Os órgãos ambientais citam exatamente esses três vetores — biodiversidade,
pesca artesanal e turismo — ao justificar medidas de controle.
        """
    )

# ================================================================ 3. Brasil
with abas[2]:
    secao(
        "Cronologia",
        "A chegada ao litoral brasileiro",
        "Cada linha abaixo tem fonte citada na aba “Fontes”.",
    )
    st.markdown(
        """
        | Quando | O que aconteceu |
        | --- | --- |
        | **2014** | Primeiro registro da espécie no Brasil. |
        | **A partir de 2020** | Os registros passam a ser frequentes e avançam pelo litoral; concentram-se no Norte e Nordeste, incluindo recifes amazônicos e Fernando de Noronha. |
        | **Set. 2026** | Na Bahia, a Secretaria Estadual do Meio Ambiente informa registros em pelo menos **dez municípios**, do Litoral Norte ao Extremo Sul. Porto Seguro institui plano municipal de ação. |
        | **14/11/2026** | **Primeiro registro oficial no Espírito Santo**: exemplar de cerca de 15 cm, a 9,4 m de profundidade, na face oeste da Ilha Escalvada, em Guarapari, filmado por equipe de mergulho recreativo. O Iema inicia mobilização para controle nas ilhas do município. |
        """
    )

    st.markdown("")
    st.markdown(
        f"""
        <div class="lg-faixa-escura">
            <span class="lg-sobrenome">O ponto que este projeto endereça</span>
            <p style="margin:.3rem 0 0 0;font-size:1.02rem;line-height:1.6">
                No Espírito Santo, <b>quem viu primeiro foi um mergulhador
                recreativo</b> — não uma rede oficial de monitoramento. O Plano
                Emergencial do ICMBio reconhece que métodos padronizados têm
                <b>baixa probabilidade de detectar</b> a espécie no estágio
                inicial da invasão, exatamente quando a detecção importa mais.
            </p>
        </div>
        """)

    st.markdown("")
    secao("Registros no Brasil", "Fotografias de observações feitas em território brasileiro")
    fotos_brasil = galeria_fotos(limite=6, apenas_brasil=True, mostrar_creditos=True)
    if not fotos_brasil:
        st.caption(
            "Sem conexão, a galeria não carrega. Ela busca observações "
            "brasileiras licenciadas diretamente do iNaturalist."
        )

# ========================================================== 4. o que fazer
with abas[3]:
    secao("Segurança", "O que fazer ao encontrar um")

    aviso_perigo(
        "<b>Não toque, não persiga e não tente capturar.</b> Os espinhos são "
        "venenosos. O manejo é atribuição de profissionais autorizados."
    )

    st.markdown(
        """
1. **Mantenha distância.** O animal não ataca, mas também não foge — o risco é
   o contato acidental.
2. **Fotografe de longe**, se der. A foto é o que permite confirmar a
   identificação.
3. **Anote onde foi**: ponto de mergulho, praia, profundidade aproximada.
4. **Registre a ocorrência** aqui na plataforma.
5. **Comunique o órgão ambiental competente** da sua região — esta plataforma
   não substitui o canal oficial.
6. **Em caso de acidente**, procure atendimento médico.
        """
    )

    st.info(
        "**Esta plataforma não é um canal oficial.** No Espírito Santo, por "
        "exemplo, as ocorrências podem ser comunicadas ao Iema e ao Centro Tamar "
        "do ICMBio. Procure o órgão ambiental do seu estado para o canal correto."
    )

    coluna_cta, coluna_mapa = st.columns(2, gap="medium")
    with coluna_cta:
        if st.button(
            "📷 Registrar avistamento",
            type="primary",
            use_container_width=True,
            key="esp_registrar_2",
        ):
            st.switch_page("paginas/registrar.py")
    with coluna_mapa:
        if st.button("🗺️ Ver o mapa", use_container_width=True, key="esp_mapa"):
            st.switch_page("paginas/mapa.py")

    st.markdown("")
    secao("Dúvidas", "Perguntas frequentes")
    faq(conteudo.perguntas)

# =============================================================== 5. fontes
with abas[4]:
    secao(
        "Fontes",
        "De onde vêm as informações desta página",
        "Informação documentada e proposta da equipe estão separadas: a "
        "cronologia e o conteúdo técnico vêm das fontes abaixo; a plataforma e "
        "as decisões de projeto são produção do grupo.",
    )
    links_oficiais(conteudo)

    st.markdown("")
    st.caption(
        "As fotografias exibidas nesta plataforma pertencem aos seus autores e "
        "são usadas sob licença Creative Commons, com atribuição em cada imagem. "
        "Elas são carregadas diretamente do iNaturalist — este projeto não "
        "redistribui os arquivos."
    )

rodape_institucional()
