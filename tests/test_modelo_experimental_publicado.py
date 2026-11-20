"""Smoke tests do artefato real incluído no ZIP.

Não medem acurácia nem prometem generalização. Verificam somente a integração.
"""
from pathlib import Path
import io
import json

import numpy as np
import pytest
from PIL import Image

from src.ai.inference import ServicoInferencia
from src.database.schema import ClassePredicao


def test_cartao_publicado_com_limites_experimentais():
    raiz = Path(__file__).resolve().parents[1]
    modelos = raiz / 'models'
    if not (modelos / 'model_card.json').exists():
        pytest.skip('Modelo experimental não distribuído neste ambiente')
    cartao = json.loads((modelos / 'model_card.json').read_text(encoding='utf8'))
    assert 'experimental' in cartao['versao']
    assert (modelos / cartao['arquivo']).stat().st_size > 1000
    assert cartao['formato'] == 'torchscript'
    servico = ServicoInferencia(diretorio_modelos=modelos)
    assert servico.estado == 'DISPONIVEL'
    assert servico.limiar_positivo >= 0.995
    assert servico.limiar_inconclusivo <= 0.05


def test_inferencia_real_em_imagem_sintetica():
    pytest.importorskip('torch')
    raiz=Path(__file__).resolve().parents[1]
    if not (raiz / 'models/model_card.json').exists():
        pytest.skip('Modelo experimental não distribuído neste ambiente')
    img=Image.new('RGB',(125,91),color=(25,90,121))
    stream=io.BytesIO(); img.save(stream,format='PNG')
    res=ServicoInferencia(diretorio_modelos=raiz/'models').classificar(stream.getvalue())
    assert res.versao=='0.2.0-experimental'
    assert res.classe in (ClassePredicao.PEIXE_LEAO,ClassePredicao.NAO_PEIXE_LEAO,
                          ClassePredicao.INCONCLUSIVO)
    assert res.score is not None and np.isfinite(res.score)
    assert res.caixas==[]  # classificador não detecta bounding boxes
