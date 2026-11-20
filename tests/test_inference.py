"""
Testes do módulo de inteligência artificial.

Cobertura: pré-processamento (determinismo, proporção, normalização), serviço
de inferência (limiares, estados de indisponibilidade, tratamento de erro),
cálculo de métricas e preparação do dataset sem vazamento entre conjuntos.

Os testes de inferência usam um **preditor injetado** — uma função que devolve
logits conhecidos. Isso testa a lógica de decisão do serviço (faixas de limiar,
rebaixamento por qualidade de imagem, registro da versão) sem depender de um
modelo treinado. O desempenho do modelo real é medido por
`scripts/avaliar_modelo.py` sobre o conjunto de teste, não aqui.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from src.ai.evaluate import area_sob_roc, calcular_metricas, varrer_limiares
from src.ai.inference import (
    CartaoModelo,
    ClassePredicao,
    ResultadoInferencia,
    ServicoInferencia,
    obter_servico_inferencia,
    resetar_servico_inferencia,
)
from src.ai.preprocessing import (
    DESVIO_IMAGENET,
    MEDIA_IMAGENET,
    PreprocessamentoInvalido,
    estatisticas_imagem,
    letterbox,
    preparar,
    preparar_lote,
    sigmoide,
    softmax,
)


def _preditor_fixo(logit_negativo: float, logit_positivo: float):
    """Preditor que sempre devolve os mesmos logits."""

    def preditor(tensor: np.ndarray) -> np.ndarray:
        return np.array([[logit_negativo, logit_positivo]], dtype=np.float32)

    return preditor


# ------------------------------------------------------------ preprocessing
def test_preparar_devolve_tensor_no_formato_do_modelo(imagem_jpeg):
    entrada = preparar(imagem_jpeg(400, 300), lado=224)
    assert entrada.tensor.shape == (1, 3, 224, 224)
    assert entrada.tensor.dtype == np.float32
    assert entrada.largura_original == 400
    assert entrada.altura_original == 300


def test_preparar_e_deterministico(imagem_jpeg):
    dados = imagem_jpeg()
    primeiro = preparar(dados).tensor
    segundo = preparar(dados).tensor
    assert np.array_equal(primeiro, segundo)


def test_letterbox_preserva_proporcao():
    from PIL import Image

    imagem = Image.new("RGB", (400, 200), (10, 20, 30))
    tela, escala, dx, dy = letterbox(imagem, 224)

    assert tela.size == (224, 224)
    assert escala == pytest.approx(224 / 400)
    assert dy > 0  # preenchimento acima e abaixo
    assert dx == 0


def test_letterbox_de_imagem_quadrada_nao_desloca():
    from PIL import Image

    _, escala, dx, dy = letterbox(Image.new("RGB", (300, 300)), 224)
    assert (dx, dy) == (0, 0)
    assert escala == pytest.approx(224 / 300)


def test_conversao_de_coordenada_para_a_imagem_original(imagem_jpeg):
    entrada = preparar(imagem_jpeg(400, 200), lado=224)
    x, y = entrada.coordenada_para_original(
        entrada.deslocamento_x, entrada.deslocamento_y
    )
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_normalizacao_usa_estatisticas_do_imagenet():
    cinza_medio = np.full((2, 2, 3), 0.5, dtype=np.float32)
    from src.ai.preprocessing import normalizar

    esperado = (0.5 - MEDIA_IMAGENET) / DESVIO_IMAGENET
    assert np.allclose(normalizar(cinza_medio)[0, 0], esperado)


def test_preparar_recusa_conteudo_invalido():
    for conteudo in (b"", b"nao sou imagem", b"\xff\xd8\xff" + b"\x00" * 10):
        with pytest.raises(PreprocessamentoInvalido):
            preparar(conteudo)


def test_preparar_lote_concatena(imagem_jpeg):
    lote = preparar_lote([imagem_jpeg(semente=1), imagem_jpeg(semente=2)], lado=224)
    assert lote.shape == (2, 3, 224, 224)


def test_preparar_lote_vazio_falha():
    with pytest.raises(PreprocessamentoInvalido):
        preparar_lote([])


def test_softmax_soma_um():
    resultado = softmax(np.array([2.0, 1.0, 0.1], dtype=np.float32))
    assert resultado.sum() == pytest.approx(1.0)
    assert resultado.argmax() == 0


def test_softmax_e_estavel_com_valores_grandes():
    resultado = softmax(np.array([1000.0, 999.0], dtype=np.float32))
    assert not np.isnan(resultado).any()
    assert resultado.sum() == pytest.approx(1.0)


def test_sigmoide_nos_extremos():
    assert sigmoide(np.array([0.0]))[0] == pytest.approx(0.5)
    assert sigmoide(np.array([-1000.0]))[0] == pytest.approx(0.0, abs=1e-9)
    assert sigmoide(np.array([1000.0]))[0] == pytest.approx(1.0, abs=1e-9)


def test_estatisticas_detectam_imagem_escura():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), (5, 5, 5)).save(buffer, format="JPEG")
    estatisticas = estatisticas_imagem(buffer.getvalue())
    assert estatisticas["provavel_subexposicao"] is True
    assert estatisticas["brilho_medio"] < 35


def test_estatisticas_detectam_imagem_sem_textura():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), (128, 128, 128)).save(buffer, format="JPEG")
    estatisticas = estatisticas_imagem(buffer.getvalue())
    assert estatisticas["provavel_desfoque"] is True


# -------------------------------------------------------- serviço: limiares
@pytest.mark.parametrize(
    "logit_positivo,classe_esperada",
    [
        (5.0, ClassePredicao.PEIXE_LEAO),       # score alto
        (0.0, ClassePredicao.INCONCLUSIVO),     # score ~0,5, faixa intermediária
        (-5.0, ClassePredicao.NAO_PEIXE_LEAO),  # score baixo
    ],
)
def test_limiares_de_decisao(ambiente, imagem_jpeg, logit_positivo, classe_esperada):
    servico = ServicoInferencia(preditor=_preditor_fixo(0.0, logit_positivo))
    resultado = servico.classificar(imagem_jpeg())
    assert resultado.classe == classe_esperada
    assert 0.0 <= resultado.score <= 1.0


def test_faixa_intermediaria_fica_inconclusiva(ambiente, imagem_jpeg):
    """Score entre os dois limiares nunca é forçado a positivo ou negativo."""
    servico = ServicoInferencia(preditor=_preditor_fixo(0.0, 0.0))
    resultado = servico.classificar(imagem_jpeg())
    assert servico.limiar_inconclusivo <= resultado.score < servico.limiar_positivo
    assert resultado.classe == ClassePredicao.INCONCLUSIVO


def test_limiares_vem_da_configuracao(ambiente, monkeypatch, imagem_jpeg):
    from src.config import resetar_config

    monkeypatch.setenv("LIONGUARD_THRESHOLD_POSITIVE", "0.95")
    resetar_config()
    servico = ServicoInferencia(preditor=_preditor_fixo(0.0, 2.0))  # score ~0,88
    resultado = servico.classificar(imagem_jpeg())
    assert servico.limiar_positivo == 0.95
    assert resultado.classe == ClassePredicao.INCONCLUSIVO


def test_positivo_em_imagem_desfocada_e_rebaixado(ambiente):
    """Imagem sem textura não sustenta um positivo, mesmo com score alto."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), (120, 120, 120)).save(buffer, format="JPEG")

    servico = ServicoInferencia(preditor=_preditor_fixo(0.0, 10.0))
    resultado = servico.classificar(buffer.getvalue())
    assert resultado.score > servico.limiar_positivo
    assert resultado.classe == ClassePredicao.INCONCLUSIVO


def test_resultado_registra_modelo_versao_e_tempo(ambiente, imagem_jpeg):
    cartao = CartaoModelo(
        nome="modelo-teste",
        versao="2.1.0",
        arquitetura="injetado",
        arquivo="",
        formato="memoria",
    )
    servico = ServicoInferencia(cartao=cartao, preditor=_preditor_fixo(0.0, 4.0))
    resultado = servico.classificar(imagem_jpeg())
    assert resultado.modelo == "modelo-teste"
    assert resultado.versao == "2.1.0"
    assert resultado.tempo_inferencia_ms is not None
    assert resultado.tempo_inferencia_ms >= 0


def test_classificador_nao_produz_caixas(ambiente, imagem_jpeg):
    servico = ServicoInferencia(preditor=_preditor_fixo(0.0, 6.0))
    resultado = servico.classificar(imagem_jpeg())
    assert resultado.caixas == []


def test_saida_de_uma_dimensao_usa_sigmoide(ambiente, imagem_jpeg):
    cartao = CartaoModelo(
        nome="binario",
        versao="1",
        arquitetura="injetado",
        arquivo="",
        formato="memoria",
        ativacao="sigmoide",
    )

    def preditor(tensor):
        return np.array([[3.0]], dtype=np.float32)

    resultado = ServicoInferencia(cartao=cartao, preditor=preditor).classificar(imagem_jpeg())
    assert resultado.score == pytest.approx(float(sigmoide(np.array([3.0]))[0]), abs=1e-4)
    assert resultado.classe == ClassePredicao.PEIXE_LEAO


# ----------------------------------------------- serviço: indisponibilidade
def test_sem_modelo_publicado_devolve_estado_claro(ambiente, imagem_jpeg):
    servico = ServicoInferencia()
    assert servico.estado == "SEM_MODELO"
    assert servico.disponivel is False

    resultado = servico.classificar(imagem_jpeg())
    assert resultado.classe == ClassePredicao.SEM_MODELO
    assert resultado.score is None
    assert resultado.disponivel is False
    assert "indisponível" in resultado.mensagem_usuario.lower()


def test_cartao_apontando_para_arquivo_ausente(ambiente, imagem_jpeg):
    cartao = CartaoModelo(
        nome="fantasma",
        versao="1",
        arquitetura="x",
        arquivo="nao_existe.onnx",
        formato="onnx",
    )
    servico = ServicoInferencia(cartao=cartao)
    assert servico.estado == "SEM_MODELO"
    resultado = servico.classificar(imagem_jpeg())
    assert resultado.classe == ClassePredicao.SEM_MODELO


def test_erro_do_modelo_nao_quebra_a_aplicacao(ambiente, imagem_jpeg):
    def preditor_com_erro(tensor):
        raise RuntimeError("falha simulada no backend")

    resultado = ServicoInferencia(preditor=preditor_com_erro).classificar(imagem_jpeg())
    assert resultado.classe == ClassePredicao.ERRO
    assert resultado.score is None
    assert "falha simulada" in (resultado.erro or "")
    assert resultado.mensagem_usuario  # mensagem amigável, não traceback


def test_imagem_invalida_vira_erro_tratado(ambiente):
    resultado = ServicoInferencia(preditor=_preditor_fixo(0.0, 1.0)).classificar(b"lixo")
    assert resultado.classe == ClassePredicao.ERRO


def test_cartao_de_modelo_invalido_e_sinalizado(ambiente, tmp_path):
    (tmp_path / "model_card.json").write_text("{nao e json valido", encoding="utf-8")
    servico = ServicoInferencia(diretorio_modelos=tmp_path)
    assert servico.estado == "ERRO_CARREGAMENTO"
    assert "inválido" in servico.descricao_estado


def test_cartao_de_modelo_e_lido_do_arquivo(ambiente, tmp_path):
    import json

    (tmp_path / "model_card.json").write_text(
        json.dumps(
            {
                "nome": "lionguard-teste",
                "versao": "9.9.9",
                "arquitetura": "MobileNetV3",
                "arquivo": "m.onnx",
                "formato": "onnx",
                "entrada": 160,
            }
        ),
        encoding="utf-8",
    )
    servico = ServicoInferencia(diretorio_modelos=tmp_path)
    assert servico.cartao.nome == "lionguard-teste"
    assert servico.cartao.versao == "9.9.9"
    assert servico.cartao.entrada == 160


def test_servico_e_reutilizado_entre_chamadas(ambiente):
    """O modelo não deve ser recarregado a cada interação."""
    resetar_servico_inferencia()
    assert obter_servico_inferencia() is obter_servico_inferencia()


def test_mensagem_de_nao_identificado_nao_afirma_ausencia(ambiente, imagem_jpeg):
    resultado = ServicoInferencia(preditor=_preditor_fixo(0.0, -6.0)).classificar(imagem_jpeg())
    mensagem = resultado.mensagem_usuario.lower()
    assert resultado.classe == ClassePredicao.NAO_PEIXE_LEAO
    assert "não garante" in mensagem or "nao garante" in mensagem


def test_detalhes_json_e_serializavel(ambiente, imagem_jpeg):
    import json

    resultado = ServicoInferencia(preditor=_preditor_fixo(0.0, 3.0)).classificar(imagem_jpeg())
    dados = json.loads(resultado.detalhes_json())
    assert dados["limiar_positivo"] == resultado.limiar_positivo
    assert "qualidade_imagem" in dados


def test_resultado_formata_score_em_percentual():
    resultado = ResultadoInferencia(
        classe=ClassePredicao.PEIXE_LEAO, modelo="m", versao="1", score=0.8767
    )
    assert resultado.score_percentual == "87.7%"
    assert ResultadoInferencia(
        classe=ClassePredicao.SEM_MODELO, modelo="m", versao="1"
    ).score_percentual == "—"


# ------------------------------------------------------------------ métricas
def test_metricas_de_classificacao_perfeita():
    metricas = calcular_metricas([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1], limiar=0.5)
    assert metricas.acuracia == 1.0
    assert metricas.precisao == 1.0
    assert metricas.revocacao == 1.0
    assert metricas.f1 == 1.0
    assert metricas.matriz_confusao == [[2, 0], [0, 2]]


def test_metricas_contam_erros_corretamente():
    # rótulos: 1,1,0,0 | scores: 0.9, 0.3, 0.8, 0.1 -> 1 FN e 1 FP
    metricas = calcular_metricas([1, 1, 0, 0], [0.9, 0.3, 0.8, 0.1], limiar=0.5)
    assert metricas.verdadeiros_positivos == 1
    assert metricas.falsos_negativos == 1
    assert metricas.falsos_positivos == 1
    assert metricas.verdadeiros_negativos == 1
    assert metricas.acuracia == 0.5
    assert metricas.precisao == 0.5
    assert metricas.revocacao == 0.5


def test_metricas_sem_positivos_previstos_nao_divide_por_zero():
    metricas = calcular_metricas([1, 0], [0.1, 0.1], limiar=0.5)
    assert metricas.precisao == 0.0
    assert metricas.f1 == 0.0


def test_limiar_mais_baixo_aumenta_revocacao():
    rotulos = [1, 1, 1, 0, 0, 0]
    scores = [0.9, 0.6, 0.4, 0.3, 0.2, 0.1]
    alto = calcular_metricas(rotulos, scores, limiar=0.8)
    baixo = calcular_metricas(rotulos, scores, limiar=0.35)
    assert baixo.revocacao > alto.revocacao
    assert baixo.falsos_negativos < alto.falsos_negativos


def test_metricas_rejeitam_entradas_incompativeis():
    with pytest.raises(ValueError):
        calcular_metricas([1, 0], [0.5])
    with pytest.raises(ValueError):
        calcular_metricas([], [])


def test_varredura_de_limiares_cobre_a_faixa():
    resultado = varrer_limiares([1, 1, 0, 0], [0.9, 0.6, 0.4, 0.1])
    assert len(resultado) >= 10
    assert all(0.0 < item["limiar"] < 1.0 for item in resultado)
    assert all(0.0 <= item["f1"] <= 1.0 for item in resultado)


def test_auc_de_separacao_perfeita_e_um():
    assert area_sob_roc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0


def test_auc_com_uma_classe_so_e_indefinida():
    assert area_sob_roc([1, 1, 1], [0.9, 0.8, 0.7]) is None


# -------------------------------------------------------------- dataset
def test_divisao_do_dataset_nao_vaza_entre_conjuntos(tmp_path, imagem_jpeg):
    """Fotos da mesma observação precisam ficar no mesmo conjunto."""
    from src.data.dataset import preparar_dataset

    origem = tmp_path / "raw"
    for deslocamento, classe in enumerate(("peixe_leao", "nao_peixe_leao")):
        (origem / classe).mkdir(parents=True)
        for observacao in range(8):
            for foto in range(3):
                (origem / classe / f"obs{observacao}_foto{foto}.jpg").write_bytes(
                    imagem_jpeg(semente=1000 * deslocamento + observacao * 10 + foto)
                )

    resultado = preparar_dataset(origem, tmp_path / "processed", semente=42)

    assert resultado.vazamento_detectado is False
    assert resultado.total_utilizadas == 48
    assert sum(resultado.por_conjunto["train"].values()) > 0
    assert sum(resultado.por_conjunto["test"].values()) > 0
    # cada grupo tem 3 fotos: todo conjunto deve ter múltiplo de 3 por classe
    for classes in resultado.por_conjunto.values():
        for quantidade in classes.values():
            assert quantidade % 3 == 0


def test_divisao_remove_duplicatas_e_arquivos_invalidos(tmp_path, imagem_jpeg):
    from src.data.dataset import preparar_dataset

    origem = tmp_path / "raw"
    for deslocamento, classe in enumerate(("peixe_leao", "nao_peixe_leao")):
        (origem / classe).mkdir(parents=True)
        for observacao in range(4):
            (origem / classe / f"obs{observacao}_foto0.jpg").write_bytes(
                imagem_jpeg(semente=1000 * deslocamento + observacao)
            )
    # duplicata exata e arquivo corrompido
    (origem / "peixe_leao" / "obs99_foto0.jpg").write_bytes(imagem_jpeg(semente=0))
    (origem / "peixe_leao" / "quebrado.jpg").write_bytes(b"nao sou imagem")

    resultado = preparar_dataset(origem, tmp_path / "processed", semente=1)

    assert resultado.duplicadas == 1
    assert resultado.invalidas == 1
    assert resultado.total_utilizadas == 8


def test_divisao_e_reproduzivel_com_a_mesma_semente(tmp_path, imagem_jpeg):
    from src.data.dataset import preparar_dataset

    origem = tmp_path / "raw"
    for deslocamento, classe in enumerate(("peixe_leao", "nao_peixe_leao")):
        (origem / classe).mkdir(parents=True)
        for observacao in range(6):
            (origem / classe / f"obs{observacao}_foto0.jpg").write_bytes(
                imagem_jpeg(semente=1000 * deslocamento + observacao)
            )

    primeira = preparar_dataset(origem, tmp_path / "a", semente=123)
    segunda = preparar_dataset(origem, tmp_path / "b", semente=123)
    assert primeira.por_conjunto == segunda.por_conjunto


def test_imagem_identica_em_duas_classes_e_removida(tmp_path, imagem_jpeg):
    """
    Deduplicação é global, não por classe.

    O mesmo arquivo rotulado como positivo e como negativo seria um rótulo
    contraditório: o pipeline mantém a primeira ocorrência e descarta a outra,
    em vez de treinar com informação conflitante.
    """
    from src.data.dataset import preparar_dataset

    origem = tmp_path / "raw"
    conteudo = imagem_jpeg(semente=77)
    for classe in ("peixe_leao", "nao_peixe_leao"):
        (origem / classe).mkdir(parents=True)
        (origem / classe / "obs1_foto0.jpg").write_bytes(conteudo)

    resultado = preparar_dataset(origem, tmp_path / "processed", semente=5)

    assert resultado.total_encontradas == 2
    assert resultado.duplicadas == 1
    assert resultado.total_utilizadas == 1
