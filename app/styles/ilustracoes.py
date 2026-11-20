"""
Ilustrações vetoriais originais do LionGuard AI.

Todo SVG deste módulo é **desenhado pelo projeto**, gerado por código a partir
de parâmetros geométricos. Nenhuma imagem é copiada da internet, o que resolve
duas coisas de uma vez: não há questão de licença e o desenho acompanha a
paleta da identidade visual.

Fotografias reais da espécie aparecem na galeria (`app/components/media.py`),
vindas do iNaturalist com licença Creative Commons e **sempre com atribuição**.
A ilustração não substitui a fotografia: ela é o elemento gráfico da interface,
e a foto é o material de identificação.

As funções devolvem `str` com o SVG pronto para `st.markdown(..., unsafe_allow_html=True)`.
"""

from __future__ import annotations

import math

from app.styles.markup import html

# Cores da ilustração. O peixe-leão tem faixas avermelhadas e esbranquiçadas,
# nadadeiras translúcidas com raios longos e espinhos dorsais destacados.
#
# Os tons foram escolhidos para o fundo escuro da interface: a membrana das
# nadadeiras é clara e translúcida, para brilhar sobre o índigo em vez de
# virar uma mancha escura, e os raios são claros o bastante para se
# destacarem. Em fundo claro a ilustração continua legível, mas é o fundo
# escuro que ela precisa atender.
CORPO_CLARO = "#FDF4E9"
CORPO_SOMBRA = "#EBD9C4"
FAIXA = "#B9452C"
FAIXA_ESCURA = "#8A3020"
MEMBRANA = "#FFC9A8"
RAIO = "#F0A98A"
RAIO_ESCURO = "#C9704F"
OLHO = "#1F2937"


def _ponto(cx: float, cy: float, raio: float, graus: float) -> tuple[float, float]:
    radianos = math.radians(graus)
    return (cx + raio * math.cos(radianos), cy + raio * math.sin(radianos))


def _leque(
    cx: float,
    cy: float,
    comprimento: float,
    angulo_inicial: float,
    angulo_final: float,
    quantidade: int,
    curvatura: float = 0.22,
    variacao: float = 0.0,
) -> tuple[str, str]:
    """
    Desenha um leque de raios — a estrutura das nadadeiras do peixe-leão.

    Devolve `(membrana, raios)`: o primeiro é um polígono translúcido que une as
    pontas, o segundo são as linhas dos raios. Separar os dois permite dar
    opacidades diferentes, que é o que faz a nadadeira parecer translúcida.
    """
    pontas: list[tuple[float, float]] = []
    raios: list[str] = []

    for indice in range(quantidade):
        fracao = indice / max(1, quantidade - 1)
        angulo = angulo_inicial + (angulo_final - angulo_inicial) * fracao
        # Raios do meio do leque são mais longos: dá a silhueta arredondada.
        escala = 1.0 - variacao * abs(fracao - 0.5) * 2
        alcance = comprimento * escala

        ponta = _ponto(cx, cy, alcance, angulo)
        # Ponto de controle deslocado perpendicularmente, para o raio curvar.
        meio = _ponto(cx, cy, alcance * 0.55, angulo)
        normal = angulo + 90
        controle = (
            meio[0] + math.cos(math.radians(normal)) * alcance * curvatura,
            meio[1] + math.sin(math.radians(normal)) * alcance * curvatura,
        )
        raios.append(
            f"M {cx:.1f} {cy:.1f} Q {controle[0]:.1f} {controle[1]:.1f} "
            f"{ponta[0]:.1f} {ponta[1]:.1f}"
        )
        pontas.append(ponta)

    membrana = f"M {cx:.1f} {cy:.1f} " + " ".join(
        f"L {x:.1f} {y:.1f}" for x, y in pontas
    ) + " Z"
    return membrana, " ".join(raios)


def _curva(p0, p1, p2, t: float) -> tuple[float, float]:
    """Ponto de uma curva quadrática de Bézier, usado para distribuir espinhos."""
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def _espinhos(
    inicio: tuple[float, float],
    controle: tuple[float, float],
    fim: tuple[float, float],
    quantidade: int,
    angulo_inicial: float,
    angulo_final: float,
    comprimento_inicial: float,
    comprimento_final: float,
    curvatura: float = 0.12,
    fracao_membrana: float = 0.45,
) -> tuple[str, str]:
    """
    Espinhos nascendo **ao longo de uma curva**, e não de um ponto único.

    É assim no animal: os espinhos dorsais saem de toda a extensão do dorso.
    Um leque com origem única fica parecendo asa de borboleta; distribuir as
    bases ao longo do dorso é o que dá a silhueta espinhosa característica.

    `fracao_membrana` controla até que altura a membrana sobe entre os
    espinhos: no peixe-leão ela cobre só a parte de baixo, e as pontas ficam
    livres. É esse detalhe que diferencia a silhueta espinhosa de uma vela
    sólida.

    Devolve `(membrana, espinhos)`.
    """
    bases: list[tuple[float, float]] = []
    pontas: list[tuple[float, float]] = []
    pontas_membrana: list[tuple[float, float]] = []
    tracos: list[str] = []

    for indice in range(quantidade):
        fracao = indice / max(1, quantidade - 1)
        base = _curva(inicio, controle, fim, fracao)
        angulo = angulo_inicial + (angulo_final - angulo_inicial) * fracao
        alcance = comprimento_inicial + (comprimento_final - comprimento_inicial) * fracao

        ponta = _ponto(base[0], base[1], alcance, angulo)
        meio = _ponto(base[0], base[1], alcance * 0.5, angulo)
        normal = angulo + 90
        controle_traco = (
            meio[0] + math.cos(math.radians(normal)) * alcance * curvatura,
            meio[1] + math.sin(math.radians(normal)) * alcance * curvatura,
        )
        tracos.append(
            f"M {base[0]:.1f} {base[1]:.1f} "
            f"Q {controle_traco[0]:.1f} {controle_traco[1]:.1f} "
            f"{ponta[0]:.1f} {ponta[1]:.1f}"
        )
        bases.append(base)
        pontas.append(ponta)
        pontas_membrana.append(
            _ponto(base[0], base[1], alcance * fracao_membrana, angulo)
        )

    # Membrana: sobe só até a fração definida e volta pelas bases.
    membrana = (
        f"M {bases[0][0]:.1f} {bases[0][1]:.1f} "
        + " ".join(f"L {x:.1f} {y:.1f}" for x, y in pontas_membrana)
        + " "
        + " ".join(f"L {x:.1f} {y:.1f}" for x, y in reversed(bases))
        + " Z"
    )
    return membrana, " ".join(tracos)


def peixe_leao_svg(largura: int = 520, id_unico: str = "pl") -> str:
    """
    Ilustração estilizada do peixe-leão, de perfil, voltado para a esquerda.

    Construída por código: corpo, faixas, espinhos dorsais e anais nascendo ao
    longo do dorso e do ventre, nadadeiras peitorais em leque e caudal. A
    membrana sobe apenas até parte dos espinhos, deixando as pontas livres —
    é esse detalhe que dá a silhueta espinhosa da espécie.
    """
    altura = int(largura * 0.72)

    # --- geometria base ----------------------------------------------------
    corpo = (
        "M 196 250 "
        "C 232 176, 356 158, 452 196 "
        "C 506 217, 540 238, 556 250 "
        "C 540 262, 506 283, 452 304 "
        "C 356 342, 232 324, 196 250 Z"
    )
    # Pedúnculo: liga o corpo à nadadeira caudal, sem deixar vão no desenho.
    pedunculo = "M 530 232 C 548 240, 556 246, 560 250 C 556 254, 548 260, 530 268 Z"

    # Espinhos dorsais: longos, finos e bem separados — o traço mais
    # reconhecível da espécie, e o que a torna perigosa ao toque.
    dorsal_membrana, dorsal_espinhos = _espinhos(
        inicio=(254, 196), controle=(370, 158), fim=(498, 202),
        quantidade=12,
        angulo_inicial=-124, angulo_final=-64,
        comprimento_inicial=152, comprimento_final=92,
        curvatura=0.10, fracao_membrana=0.34,
    )
    # Espinhos anais, no ventre, mais curtos.
    anal_membrana, anal_espinhos = _espinhos(
        inicio=(430, 312), controle=(478, 318), fim=(518, 288),
        quantidade=6,
        angulo_inicial=96, angulo_final=56,
        comprimento_inicial=84, comprimento_final=54,
        curvatura=-0.10, fracao_membrana=0.46,
    )
    # Peitoral do lado próximo: grande leque que abre para trás e para baixo.
    peitoral_membrana, peitoral_raios = _leque(
        cx=338, cy=286, comprimento=156, angulo_inicial=42,
        angulo_final=108, quantidade=11, curvatura=0.06, variacao=0.16,
    )
    # Caudal, começando dentro do pedúnculo para não haver descontinuidade.
    caudal_membrana, caudal_raios = _leque(
        cx=548, cy=250, comprimento=132, angulo_inicial=-54,
        angulo_final=54, quantidade=10, curvatura=0.0, variacao=0.34,
    )

    # Faixas verticais do corpo, acompanhando a curvatura.
    faixas = []
    for indice, (x, largura_faixa) in enumerate(
        ((252, 17), (296, 13), (338, 19), (386, 13), (432, 17), (480, 12))
    ):
        inclinacao = 16 - indice * 1.6
        faixas.append(
            f'<path d="M {x} 186 C {x + inclinacao} 218, {x + inclinacao} 282, '
            f'{x} 314 L {x + largura_faixa} 314 C {x + largura_faixa + inclinacao} 282, '
            f'{x + largura_faixa + inclinacao} 218, {x + largura_faixa} 186 Z" '
            f'fill="{FAIXA if indice % 2 == 0 else FAIXA_ESCURA}" opacity="0.92"/>'
        )

    return html(f"""
<svg viewBox="0 0 760 500" width="{largura}" height="{altura}"
     xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Ilustração de um peixe-leão, com faixas e nadadeiras em leque"
     style="max-width:100%;height:auto;display:block">
  <defs>
    <linearGradient id="{id_unico}-corpo" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{CORPO_CLARO}"/>
      <stop offset="100%" stop-color="{CORPO_SOMBRA}"/>
    </linearGradient>
    <linearGradient id="{id_unico}-membrana" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{MEMBRANA}" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="{MEMBRANA}" stop-opacity="0.06"/>
    </linearGradient>
    <clipPath id="{id_unico}-recorte"><path d="{corpo}"/></clipPath>
    <filter id="{id_unico}-sombra" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="10" stdDeviation="14"
                    flood-color="#062B43" flood-opacity="0.18"/>
    </filter>
  </defs>

  <g filter="url(#{id_unico}-sombra)">
    <!-- camada de trás: caudal, espinhos e a peitoral do lado oposto -->
    <g>
      <path d="{caudal_membrana}" fill="url(#{id_unico}-membrana)"/>
      <path d="{caudal_raios}" stroke="{RAIO}" stroke-width="2.4"
            fill="none" stroke-linecap="round" opacity="0.85"/>
      <path d="{caudal_raios}" stroke="{RAIO_ESCURO}" stroke-width="2.4"
            fill="none" stroke-linecap="butt" stroke-dasharray="7 9"
            opacity="0.75"/>

      <path d="{dorsal_membrana}" fill="url(#{id_unico}-membrana)"
            opacity="0.6"/>
      <path d="{dorsal_espinhos}" stroke="{RAIO}" stroke-width="3.4"
            fill="none" stroke-linecap="round" opacity="0.95"/>
      <path d="{dorsal_espinhos}" stroke="{RAIO_ESCURO}" stroke-width="3.4"
            fill="none" stroke-linecap="butt" stroke-dasharray="9 11"
            opacity="0.8"/>

      <path d="{anal_membrana}" fill="url(#{id_unico}-membrana)"
            opacity="0.72"/>
      <path d="{anal_espinhos}" stroke="{RAIO}" stroke-width="3"
            fill="none" stroke-linecap="round" opacity="0.92"/>
      <path d="{anal_espinhos}" stroke="{RAIO_ESCURO}" stroke-width="3"
            fill="none" stroke-linecap="butt" stroke-dasharray="7 9"
            opacity="0.78"/>
    </g>

    <!-- corpo -->
    <path d="{pedunculo}" fill="{CORPO_SOMBRA}"/>
    <path d="{corpo}" fill="url(#{id_unico}-corpo)"/>
    <g clip-path="url(#{id_unico}-recorte)">{''.join(faixas)}</g>
    <path d="{corpo}" fill="none" stroke="{FAIXA_ESCURA}"
          stroke-width="3" opacity="0.55"/>

    <!-- peitoral do lado próximo, na frente do corpo -->
    <path d="{peitoral_membrana}" fill="url(#{id_unico}-membrana)"/>
    <path d="{peitoral_raios}" stroke="{RAIO}" stroke-width="3"
          fill="none" stroke-linecap="round" opacity="0.95"/>
    <path d="{peitoral_raios}" stroke="{RAIO_ESCURO}" stroke-width="3"
          fill="none" stroke-linecap="butt" stroke-dasharray="8 10"
          opacity="0.8"/>

    <!-- cabeça: olho, boca e os tentáculos acima dos olhos -->
    <circle cx="246" cy="238" r="15" fill="{CORPO_CLARO}"/>
    <circle cx="246" cy="238" r="10" fill="{OLHO}"/>
    <circle cx="250" cy="234" r="3.4" fill="#FFFFFF" opacity="0.9"/>
    <path d="M 198 258 Q 214 268, 232 264" stroke="{FAIXA_ESCURA}"
          stroke-width="3.6" fill="none" stroke-linecap="round"/>
    <path d="M 228 216 Q 212 198, 216 176" stroke="{RAIO}" stroke-width="3.2"
          fill="none" stroke-linecap="round" opacity="0.85"/>
    <path d="M 242 212 Q 236 190, 246 172" stroke="{RAIO}" stroke-width="3"
          fill="none" stroke-linecap="round" opacity="0.8"/>
  </g>
</svg>
""")


def logo_svg(tamanho: int = 44) -> str:
    """Marca do projeto: silhueta do peixe dentro de um escudo marinho."""
    return html(f"""
<svg viewBox="0 0 64 64" width="{tamanho}" height="{tamanho}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="LionGuard AI"
     style="display:block">
  <defs>
    <linearGradient id="lg-escudo" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#14B8A6"/>
      <stop offset="100%" stop-color="#086F8C"/>
    </linearGradient>
  </defs>
  <path d="M32 3 L57 12 V32 C57 46 46 56 32 61 C18 56 7 46 7 32 V12 Z"
        fill="url(#lg-escudo)"/>
  <path d="M32 3 L57 12 V32 C57 46 46 56 32 61 C18 56 7 46 7 32 V12 Z"
        fill="none" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="1.6"/>
  <g transform="translate(0,2)">
    <path d="M18 32 C23 24, 36 23, 43 28 C45.5 29.5, 47 31, 47 32
             C47 33, 45.5 34.5, 43 36 C36 41, 23 40, 18 32 Z"
          fill="#FFFFFF" opacity="0.95"/>
    <path d="M47 32 L55 27 Q57 32, 55 37 Z" fill="#FFFFFF" opacity="0.8"/>
    <g stroke="#FFFFFF" stroke-width="1.7" stroke-linecap="round" opacity="0.85"
       fill="none">
      <path d="M31 25 L27 15"/><path d="M35 25 L34 14"/><path d="M39 26 L41 16"/>
      <path d="M31 39 L28 47"/><path d="M36 39 L37 48"/>
    </g>
    <circle cx="23" cy="30" r="2.3" fill="#062B43"/>
  </g>
</svg>
""")


def onda_svg(cor: str = "#FFFFFF", altura: int = 56, virada: bool = False) -> str:
    """Divisor de seção em forma de onda, usado entre blocos de cor."""
    transformacao = 'transform="scale(1,-1) translate(0,-120)"' if virada else ""
    return html(f"""
<svg viewBox="0 0 1440 120" preserveAspectRatio="none"
     width="100%" height="{altura}" xmlns="http://www.w3.org/2000/svg"
     aria-hidden="true" style="display:block">
  <g {transformacao}>
    <path fill="{cor}" fill-opacity="0.35"
          d="M0,64 C180,110 360,18 540,42 C720,66 900,118 1080,100
             C1200,88 1320,56 1440,38 L1440,120 L0,120 Z"/>
    <path fill="{cor}"
          d="M0,86 C180,124 360,56 540,70 C720,84 900,124 1080,112
             C1200,104 1320,82 1440,70 L1440,120 L0,120 Z"/>
  </g>
</svg>
""")


def icone_svg(nome: str, tamanho: int = 28, cor: str = "#086F8C") -> str:
    """
    Ícones de linha desenhados no projeto, para os cards de etapa.

    Conjunto pequeno e consistente: câmera, cérebro (IA), alfinete de mapa,
    escudo (validação), aviso e gráfico.
    """
    caminhos = {
        "camera": (
            "M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"
            "|M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"
        ),
        "ia": (
            "M12 3a4 4 0 0 0-4 4 3 3 0 0 0-1 5.8V17a3 3 0 0 0 5 2.2A3 3 0 0 0 17 17v-4.2"
            "A3 3 0 0 0 16 7a4 4 0 0 0-4-4z|M12 3v18|M8 10h2|M14 14h2"
        ),
        "mapa": (
            "M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z|M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"
        ),
        "escudo": (
            "M12 3l8 3v6c0 5-3.4 8.3-8 9.6C7.4 20.3 4 17 4 12V6z|M9 12l2.2 2.2L15.5 10"
        ),
        "aviso": (
            "M12 3.5 2.8 19.5h18.4z|M12 10v4|M12 17.2v.1"
        ),
        "grafico": (
            "M4 20V10|M10 20V4|M16 20v-7|M22 20H2"
        ),
        "lupa": (
            "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z|M21 21l-4.3-4.3"
        ),
        "relogio": (
            "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z|M12 7v5l3 2"
        ),
    }
    traçados = caminhos.get(nome, caminhos["lupa"]).split("|")
    corpo = "".join(f'<path d="{d}"/>' for d in traçados)
    return (
        f'<svg viewBox="0 0 24 24" width="{tamanho}" height="{tamanho}" fill="none" '
        f'stroke="{cor}" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true" style="display:block">{corpo}</svg>'
    )


def padrao_oceano_svg(id_unico: str = "oc") -> str:
    """Textura sutil de ondas para o fundo do cabeçalho."""
    return html(f"""
<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"
     aria-hidden="true" style="position:absolute;inset:0;opacity:.18">
  <defs>
    <pattern id="{id_unico}-ondas" width="110" height="46"
             patternUnits="userSpaceOnUse">
      <path d="M0 32 Q 27 16, 55 32 T 110 32" fill="none"
            stroke="#FFFFFF" stroke-width="1.5" stroke-opacity="0.55"/>
      <path d="M0 12 Q 27 -4, 55 12 T 110 12" fill="none"
            stroke="#FFFFFF" stroke-width="1" stroke-opacity="0.3"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#{id_unico}-ondas)"/>
</svg>
""")
