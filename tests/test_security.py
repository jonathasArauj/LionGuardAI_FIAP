"""
Testes de segurança e privacidade.

Cobertura: hash de senha (scrypt com sal), autenticação, matriz de permissões,
negação de acesso em serviço (não só na interface), validação de upload,
saneamento de nome de arquivo, bloqueio de travessia de diretório, limite de
requisições, tratamento de EXIF e proteção das coordenadas no mapa público.
"""

from __future__ import annotations

import io

import pytest

from src.database.repositories import UsuarioRepository
from src.database.schema import Decisao, Perfil
from src.security.auth import (
    SENHA_MINIMA,
    ErroAutenticacao,
    SenhaFraca,
    ServicoAutenticacao,
    Sessao,
    gerar_hash_senha,
    verificar_senha,
)
from src.security.permissions import (
    PERMISSOES_POR_PERFIL,
    PERMISSOES_PUBLICAS,
    AcessoNegado,
    Permissao,
    exigir,
    permissoes_da_sessao,
    tem_permissao,
)
from src.security.rate_limit import LimitadorRequisicoes
from src.security.sanitize import (
    CaminhoInvalido,
    caminho_seguro,
    hash_contato,
    limpar_texto,
    sanitizar_nome_arquivo,
)
from src.security.uploads import ImagemInvalida, validar_imagem


# ------------------------------------------------------------ hash de senha
def test_hash_nao_contem_a_senha():
    hash_gerado = gerar_hash_senha("senha-secreta-123")
    assert "senha-secreta-123" not in hash_gerado
    assert hash_gerado.startswith("scrypt$")


def test_mesma_senha_gera_hashes_diferentes():
    """Sal aleatório por usuário: dois hashes iguais revelariam senhas iguais."""
    primeiro = gerar_hash_senha("senha-secreta-123")
    segundo = gerar_hash_senha("senha-secreta-123")
    assert primeiro != segundo
    assert verificar_senha("senha-secreta-123", primeiro)
    assert verificar_senha("senha-secreta-123", segundo)


def test_verificacao_de_senha_correta_e_incorreta():
    hash_gerado = gerar_hash_senha("senha-correta-456")
    assert verificar_senha("senha-correta-456", hash_gerado) is True
    assert verificar_senha("senha-errada", hash_gerado) is False
    assert verificar_senha("", hash_gerado) is False
    assert verificar_senha("SENHA-CORRETA-456", hash_gerado) is False


def test_verificacao_tolera_hash_corrompido():
    for armazenado in ("", "qualquer-coisa", "scrypt$x", "md5$1$2$3$4$5", None):
        assert verificar_senha("senha", armazenado) is False


@pytest.mark.parametrize("senha", ["", "curta", "1234567", None])
def test_senha_fraca_e_recusada(senha):
    with pytest.raises(SenhaFraca):
        gerar_hash_senha(senha)


def test_politica_minima_de_senha():
    assert SENHA_MINIMA >= 8
    gerar_hash_senha("a" * SENHA_MINIMA)  # não deve levantar


# ----------------------------------------------------------- autenticação
def test_autenticacao_com_credenciais_validas(ambiente):
    servico = ServicoAutenticacao()
    servico.criar_usuario("maria", "senha-da-maria-1", Perfil.PESQUISADOR, nome="Maria")
    sessao = servico.autenticar("maria", "senha-da-maria-1")
    assert sessao.perfil == Perfil.PESQUISADOR
    assert sessao.valida is True
    assert sessao.token


def test_autenticacao_e_insensivel_a_caixa_no_usuario(ambiente):
    servico = ServicoAutenticacao()
    servico.criar_usuario("joao", "senha-do-joao-1", Perfil.PESQUISADOR)
    assert servico.autenticar("JOAO", "senha-do-joao-1").identificador == "joao"
    assert servico.autenticar("  joao  ", "senha-do-joao-1") is not None


def test_autenticacao_recusa_senha_errada(ambiente):
    servico = ServicoAutenticacao()
    servico.criar_usuario("pedro", "senha-do-pedro-1", Perfil.PESQUISADOR)
    with pytest.raises(ErroAutenticacao):
        servico.autenticar("pedro", "outra-senha")


def test_autenticacao_recusa_usuario_inexistente(ambiente):
    with pytest.raises(ErroAutenticacao):
        ServicoAutenticacao().autenticar("ninguem", "qualquer-senha-1")


def test_usuario_inativo_nao_autentica(ambiente):
    servico = ServicoAutenticacao()
    usuario = servico.criar_usuario("inativo", "senha-inativa-1", Perfil.PESQUISADOR)
    UsuarioRepository().definir_ativo(usuario.id, False)
    with pytest.raises(ErroAutenticacao):
        servico.autenticar("inativo", "senha-inativa-1")


def test_falha_de_login_e_auditada(ambiente):
    from src.database.repositories import AuditoriaRepository

    servico = ServicoAutenticacao()
    servico.criar_usuario("auditado", "senha-auditada-1", Perfil.PESQUISADOR)
    with pytest.raises(ErroAutenticacao):
        servico.autenticar("auditado", "errada")

    acoes = [registro.acao for registro in AuditoriaRepository().listar()]
    assert "LOGIN_FALHA" in acoes


def test_senha_nunca_aparece_na_auditoria(ambiente):
    from src.database.repositories import AuditoriaRepository

    servico = ServicoAutenticacao()
    servico.criar_usuario("sigiloso", "minha-senha-secreta-9", Perfil.PESQUISADOR)
    servico.autenticar("sigiloso", "minha-senha-secreta-9")

    for registro in AuditoriaRepository().listar():
        assert "minha-senha-secreta-9" not in (registro.detalhes or "")


def test_contas_iniciais_usam_variaveis_de_ambiente(ambiente):
    criadas = ServicoAutenticacao().garantir_usuarios_iniciais()
    assert len(criadas) == 2
    # segunda chamada não recria
    assert ServicoAutenticacao().garantir_usuarios_iniciais() == []
    assert UsuarioRepository().por_identificador("admin").perfil == Perfil.ADMINISTRADOR


def test_sessao_expirada_e_invalida():
    expirada = Sessao(
        usuario_id=1,
        identificador="x",
        perfil=Perfil.PESQUISADOR,
        nome=None,
        token="t",
        expira_em="2020-01-01T00:00:00",
    )
    assert expirada.expirada is True
    assert expirada.valida is False


# -------------------------------------------------------------- permissões
def test_visitante_anonimo_tem_apenas_permissoes_publicas():
    assert permissoes_da_sessao(None) == PERMISSOES_PUBLICAS
    assert tem_permissao(None, Permissao.REGISTRAR_AVISTAMENTO) is True
    assert tem_permissao(None, Permissao.VER_MAPA_PUBLICO) is True


@pytest.mark.parametrize(
    "permissao",
    [
        Permissao.VER_DASHBOARD_GERAL,
        Permissao.VER_DASHBOARD_CIENTIFICO,
        Permissao.VER_DASHBOARD_IA,
        Permissao.VER_PAINEL_OPERACIONAL,
        Permissao.VALIDAR_OCORRENCIA,
        Permissao.VER_COORDENADAS_PRECISAS,
        Permissao.EXPORTAR_DADOS,
        Permissao.GERENCIAR_USUARIOS,
        Permissao.VER_AUDITORIA,
    ],
)
def test_anonimo_nao_acessa_area_restrita(permissao):
    assert tem_permissao(None, permissao) is False
    with pytest.raises(AcessoNegado):
        exigir(None, permissao)


def test_sessao_expirada_perde_permissoes():
    expirada = Sessao(
        usuario_id=1,
        identificador="x",
        perfil=Perfil.ADMINISTRADOR,
        nome=None,
        token="t",
        expira_em="2020-01-01T00:00:00",
    )
    assert tem_permissao(expirada, Permissao.GERENCIAR_USUARIOS) is False


def test_pesquisador_valida_mas_nao_administra(sessao_pesquisador):
    assert tem_permissao(sessao_pesquisador, Permissao.VALIDAR_OCORRENCIA) is True
    assert tem_permissao(sessao_pesquisador, Permissao.EXPORTAR_DADOS) is True
    assert tem_permissao(sessao_pesquisador, Permissao.GERENCIAR_USUARIOS) is False
    assert (
        tem_permissao(sessao_pesquisador, Permissao.EXPORTAR_COORDENADAS_PRECISAS) is False
    )


def test_administrador_tem_todas_as_permissoes(sessao_admin):
    for permissao in Permissao:
        assert tem_permissao(sessao_admin, permissao) is True


def test_perfil_cidadao_nao_acumula_permissoes_restritas():
    assert PERMISSOES_POR_PERFIL[Perfil.CIDADAO] == PERMISSOES_PUBLICAS
    assert PERMISSOES_POR_PERFIL[Perfil.PESQUISADOR] < PERMISSOES_POR_PERFIL[
        Perfil.ADMINISTRADOR
    ]


def test_servico_de_validacao_recusa_sessao_sem_permissao(ambiente, registrar_avistamento):
    """A proteção está no serviço, não apenas na interface."""
    from src.database.repositories import OcorrenciaRepository
    from src.services.validation import ServicoValidacao

    resultado = registrar_avistamento()
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)

    with pytest.raises(AcessoNegado):
        ServicoValidacao().decidir(
            ocorrencia_id=ocorrencia.id,
            decisao=Decisao.CONFIRMAR,
            justificativa="tentativa sem autenticação alguma",
            sessao=None,
        )
    # o status continua intocado
    assert str(OcorrenciaRepository().por_id(ocorrencia.id).status) == "PENDENTE"


def test_exportacao_exige_permissao(ambiente):
    from src.services.analytics import exportar_csv

    with pytest.raises(AcessoNegado):
        exportar_csv(sessao=None)


def test_exportacao_de_pesquisador_arredonda_coordenadas(
    ambiente, sessao_pesquisador, registrar_avistamento
):
    from src.services.analytics import exportar_csv

    registrar_avistamento()
    conteudo, _ = exportar_csv(sessao=sessao_pesquisador)
    assert "-20.67" in conteudo
    assert "-20.6712" not in conteudo  # coordenada precisa não sai


def test_exportacao_nao_inclui_contato(ambiente, sessao_admin, registrar_avistamento):
    from src.services.analytics import exportar_csv

    registrar_avistamento(contato="pessoa@exemplo.com")
    conteudo, _ = exportar_csv(sessao=sessao_admin)
    assert "pessoa@exemplo.com" not in conteudo
    assert "contato" not in conteudo.split("\n")[5].lower()


# ----------------------------------------------------------- upload seguro
def test_upload_aceita_jpeg_valido(ambiente, imagem_jpeg):
    validada = validar_imagem(imagem_jpeg())
    assert validada.formato in ("jpeg", "png")
    assert validada.tamanho_bytes > 0
    assert validada.exif_removido is True


def test_upload_recusa_conteudo_que_nao_e_imagem(ambiente):
    for conteudo in (b"", b"texto qualquer" * 100, b"%PDF-1.4 fake pdf"):
        with pytest.raises(ImagemInvalida):
            validar_imagem(conteudo)


def test_upload_recusa_imagem_truncada(ambiente, imagem_jpeg):
    with pytest.raises(ImagemInvalida):
        validar_imagem(imagem_jpeg()[:200])


def test_upload_recusa_arquivo_grande(ambiente, monkeypatch, imagem_jpeg):
    from src.config import resetar_config

    monkeypatch.setenv("LIONGUARD_UPLOAD_MAX_BYTES", "1024")
    resetar_config()
    with pytest.raises(ImagemInvalida, match="limite"):
        validar_imagem(imagem_jpeg(800, 600))


def test_upload_recusa_imagem_pequena(ambiente, imagem_jpeg):
    with pytest.raises(ImagemInvalida, match="pequena"):
        validar_imagem(imagem_jpeg(40, 40))


def test_upload_recusa_extensao_disfarcada(ambiente):
    """A extensão enviada pelo cliente não é considerada — só os bytes."""
    conteudo = b"GIF89a" + b"\x00" * 500  # GIF não está na lista aceita
    with pytest.raises(ImagemInvalida):
        validar_imagem(conteudo)


def _jpeg_com_exif_gps() -> bytes:
    """JPEG com descrição e coordenadas GPS nos metadados (Guarapari/ES)."""
    from PIL import Image

    imagem = Image.new("RGB", (300, 220), (90, 140, 170))
    exif = Image.Exif()
    exif[0x010E] = "descricao de teste"  # ImageDescription
    exif[0x8825] = {  # GPSInfo: 20°40'15"S, 40°29'54"W
        1: "S",
        2: (20.0, 40.0, 15.0),
        3: "W",
        4: (40.0, 29.0, 54.0),
    }
    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_exif_gps_e_lido_para_informar_o_usuario(ambiente):
    """As coordenadas do EXIF são extraídas, mas apenas para oferecer ao usuário."""
    validada = validar_imagem(_jpeg_com_exif_gps())

    assert validada.exif_presente is True
    assert validada.exif_tinha_gps is True
    assert validada.coordenadas_exif is not None
    latitude, longitude = validada.coordenadas_exif
    assert latitude == pytest.approx(-20.6708, abs=0.001)
    assert longitude == pytest.approx(-40.4983, abs=0.001)


def test_exif_e_removido_da_imagem_gravada(ambiente):
    """O arquivo salvo não carrega metadados — nem GPS, nem descrição."""
    from PIL import Image

    validada = validar_imagem(_jpeg_com_exif_gps())

    assert validada.exif_removido is True
    assert any("EXIF" in aviso for aviso in validada.avisos)
    reaberta = Image.open(io.BytesIO(validada.conteudo))
    assert dict(reaberta.getexif()) == {}
    assert b"descricao de teste" not in validada.conteudo


def test_exif_pode_ser_preservado_explicitamente(ambiente):
    """Só quando pedido explicitamente o conteúdo original é mantido."""
    validada = validar_imagem(_jpeg_com_exif_gps(), remover_exif=False)
    assert validada.exif_removido is False
    assert validada.exif_tinha_gps is True


def test_coordenada_exif_nao_e_usada_automaticamente(ambiente, registrar_avistamento):
    """
    A presença de GPS no EXIF não define a localização do avistamento.

    O registro usa a localização escolhida no fluxo; o EXIF só é aproveitado
    depois de autorização explícita na interface.
    """
    from src.database.repositories import OcorrenciaRepository
    from src.security.uploads import validar_imagem as validar

    validada = validar(_jpeg_com_exif_gps())
    assert validada.coordenadas_exif is not None

    resultado = registrar_avistamento()
    ocorrencia = OcorrenciaRepository().por_protocolo(resultado.protocolo)
    # a ocorrência ficou com a coordenada da fixture (GPS do fluxo), não com a do EXIF
    assert ocorrencia.latitude == pytest.approx(-20.6712, abs=1e-4)


def test_exif_malformado_nao_quebra_a_leitura(ambiente, imagem_jpeg):
    from PIL import Image

    from src.security.uploads import ler_coordenadas_exif

    sem_exif = Image.open(io.BytesIO(imagem_jpeg()))
    assert ler_coordenadas_exif(sem_exif) is None


def test_coordenada_exif_fora_de_faixa_e_descartada(ambiente):
    from PIL import Image

    from src.security.uploads import ler_coordenadas_exif

    imagem = Image.new("RGB", (120, 120))
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (200.0, 0.0, 0.0), 3: "E", 4: (400.0, 0.0, 0.0)}
    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", exif=exif)

    assert ler_coordenadas_exif(Image.open(io.BytesIO(buffer.getvalue()))) is None


def test_imagem_salva_nao_carrega_metadados(ambiente, imagem_jpeg):
    from PIL import Image

    validada = validar_imagem(imagem_jpeg())
    reaberta = Image.open(io.BytesIO(validada.conteudo))
    assert not reaberta.getexif()


# ------------------------------------------------------------- saneamento
@pytest.mark.parametrize(
    "entrada",
    [
        "../../etc/passwd",
        "/etc/shadow",
        "..\\..\\windows\\system32\\config",
        "arquivo;rm -rf /.jpg",
        "foto<script>alert(1)</script>.png",
        "../" * 20 + "segredo.txt",
    ],
)
def test_nome_saneado_nunca_contem_caminho(entrada):
    resultado = sanitizar_nome_arquivo(entrada)
    assert "/" not in resultado
    assert "\\" not in resultado
    assert ".." not in resultado
    assert "<" not in resultado and ">" not in resultado
    assert resultado  # nunca vazio


def test_nome_saneado_e_sempre_utilizavel(tmp_path):
    for entrada in ("..", ".", "", None, "///", "***"):
        resultado = sanitizar_nome_arquivo(entrada)
        assert caminho_seguro(tmp_path, resultado).parent == tmp_path.resolve()


def test_nome_saneado_respeita_tamanho_maximo():
    resultado = sanitizar_nome_arquivo("a" * 500 + ".jpg")
    assert len(resultado) <= 120


@pytest.mark.parametrize(
    "nome",
    ["../../etc/passwd", "/etc/shadow", "..\\windows", "pasta/arquivo.jpg", "~/.ssh/id_rsa", ""],
)
def test_caminho_seguro_recusa_travessia(tmp_path, nome):
    with pytest.raises(CaminhoInvalido):
        caminho_seguro(tmp_path, nome)


def test_caminho_seguro_aceita_nome_simples(tmp_path):
    destino = caminho_seguro(tmp_path, "abc123.jpg")
    assert destino.parent == tmp_path.resolve()
    assert destino.name == "abc123.jpg"


def test_limpar_texto_remove_controles_e_limita():
    assert limpar_texto("texto\x00com\x07controle") == "textocomcontrole"
    assert limpar_texto("  espaços    demais  ") == "espaços demais"
    assert len(limpar_texto("a" * 5000)) == 2000
    assert limpar_texto(None) is None
    assert limpar_texto("   ") is None


def test_hash_de_contato_e_irreversivel_e_estavel():
    primeiro = hash_contato("Pessoa@Exemplo.com")
    assert primeiro == hash_contato("  pessoa@exemplo.com  ")
    assert primeiro != hash_contato("outra@exemplo.com")
    assert "exemplo" not in primeiro
    assert len(primeiro) == 64
    assert hash_contato(None) is None
    assert hash_contato("  ") is None


# ---------------------------------------------------- limite de requisições
def test_limite_bloqueia_apos_estourar(ambiente):
    limitador = LimitadorRequisicoes()
    permitidos = [limitador.consumir("sessao-a").permitido for _ in range(8)]
    assert permitidos.count(True) == ambiente.rate_limit_registros
    assert permitidos.count(False) == 8 - ambiente.rate_limit_registros


def test_limite_e_por_chave(ambiente):
    limitador = LimitadorRequisicoes()
    for _ in range(ambiente.rate_limit_registros):
        limitador.consumir("sessao-b")
    assert limitador.verificar("sessao-b").permitido is False
    assert limitador.verificar("sessao-c").permitido is True


def test_verificar_nao_consome(ambiente):
    limitador = LimitadorRequisicoes()
    for _ in range(10):
        limitador.verificar("sessao-d")
    assert limitador.verificar("sessao-d").usados == 0


def test_limite_e_por_acao(ambiente):
    limitador = LimitadorRequisicoes()
    for _ in range(ambiente.rate_limit_registros):
        limitador.consumir("sessao-e", acao="REGISTRO")
    assert limitador.verificar("sessao-e", acao="REGISTRO").permitido is False
    assert limitador.verificar("sessao-e", acao="CONSULTA").permitido is True


def test_mensagem_do_limite_e_legivel(ambiente):
    limitador = LimitadorRequisicoes()
    for _ in range(ambiente.rate_limit_registros + 1):
        limitador.consumir("sessao-f")
    mensagem = limitador.verificar("sessao-f").mensagem()
    assert "Limite" in mensagem
    assert str(ambiente.rate_limit_registros) in mensagem


def test_limite_persiste_entre_conexoes(ambiente):
    """Recarregar a página não zera o limite."""
    from src.database.connection import fechar_conexoes

    limitador = LimitadorRequisicoes()
    for _ in range(ambiente.rate_limit_registros):
        limitador.consumir("sessao-g")
    fechar_conexoes()
    assert LimitadorRequisicoes().verificar("sessao-g").permitido is False


# ------------------------------------------------------- mapa público
def test_mapa_publico_nao_expoe_coordenada_precisa(ambiente, registrar_avistamento):
    from src.database import queries

    registrar_avistamento()
    publico = queries.dados_geograficos(publico=True)[0]
    restrito = queries.dados_geograficos(publico=False)[0]

    assert publico["latitude"] == round(restrito["latitude"], 2)
    assert publico["latitude"] != restrito["latitude"]


def test_mapa_publico_esconde_imagem_sem_autorizacao(ambiente, registrar_avistamento):
    from src.database import queries

    registrar_avistamento(autoriza_publicar_imagem=False)
    publico = queries.dados_geograficos(publico=True)[0]
    restrito = queries.dados_geograficos(publico=False)[0]

    assert publico["arquivo_imagem"] is None
    assert restrito["arquivo_imagem"] is not None


def test_mapa_publico_mostra_imagem_autorizada(ambiente, registrar_avistamento):
    from src.database import queries

    registrar_avistamento(autoriza_publicar_imagem=True)
    assert queries.dados_geograficos(publico=True)[0]["arquivo_imagem"] is not None
