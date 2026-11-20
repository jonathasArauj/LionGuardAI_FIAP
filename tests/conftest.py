"""
Configuração compartilhada dos testes.

Cada teste roda contra um banco SQLite **próprio**, em diretório temporário.
Isso garante isolamento (um teste não vê dados de outro) e permite verificar
persistência de verdade, com arquivo em disco, em vez de banco em memória.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """
    Ambiente isolado: banco, diretório de imagens e configuração próprios.

    Devolve o objeto de configuração já apontando para o diretório temporário.
    """
    from src.ai.inference import resetar_servico_inferencia
    from src.config import get_config, resetar_config
    from src.database.connection import (
        esquecer_inicializacao,
        fechar_conexoes,
        inicializar_banco,
    )

    banco = tmp_path / "teste.db"
    monkeypatch.setenv("LIONGUARD_DB", str(banco))
    monkeypatch.setenv("LIONGUARD_IMAGE_DIR", str(tmp_path / "imagens"))
    monkeypatch.setenv("LIONGUARD_MODEL_DIR", str(tmp_path / "modelos"))
    monkeypatch.setenv("LIONGUARD_REPORT_DIR", str(tmp_path / "relatorios"))
    monkeypatch.setenv("LIONGUARD_ADMIN_PASS", "senha-admin-de-teste")
    monkeypatch.setenv("LIONGUARD_PESQ_PASS", "senha-pesq-de-teste")

    fechar_conexoes()
    esquecer_inicializacao()
    resetar_config()
    resetar_servico_inferencia()

    configuracao = get_config()
    inicializar_banco()

    yield configuracao

    fechar_conexoes()
    esquecer_inicializacao()
    resetar_config()
    resetar_servico_inferencia()


@pytest.fixture
def imagem_jpeg():
    """
    Fábrica de imagens JPEG sintéticas válidas.

    São imagens geradas proceduralmente para exercitar validação,
    pré-processamento e armazenamento. **Não** são fotografias da espécie, e
    nenhum teste extrai delas conclusão sobre identificação.
    """

    def _criar(largura: int = 400, altura: int = 300, semente: int = 7) -> bytes:
        import numpy as np
        from PIL import Image

        gerador = np.random.default_rng(semente)
        matriz = gerador.integers(30, 225, size=(altura, largura, 3), dtype=np.uint8)
        matriz[:, ::25, :] = 240  # estrutura visual, para não ser só ruído
        buffer = io.BytesIO()
        Image.fromarray(matriz).save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

    return _criar


@pytest.fixture
def imagem_validada(imagem_jpeg):
    from src.security.uploads import validar_imagem

    return validar_imagem(imagem_jpeg())


@pytest.fixture
def localizacao_guarapari():
    """Localização de GPS válida no litoral do Espírito Santo."""
    from src.database.schema import OrigemLocalizacao
    from src.services.geolocation import construir_localizacao

    return construir_localizacao(
        -20.6712, -40.4985, OrigemLocalizacao.GPS_DISPOSITIVO, precisao_metros=12.0
    )


@pytest.fixture
def sessao_pesquisador(ambiente):
    from src.security.auth import ServicoAutenticacao

    servico = ServicoAutenticacao()
    servico.garantir_usuarios_iniciais()
    return servico.autenticar("pesquisador", "senha-pesq-de-teste")


@pytest.fixture
def sessao_admin(ambiente):
    from src.security.auth import ServicoAutenticacao

    servico = ServicoAutenticacao()
    servico.garantir_usuarios_iniciais()
    return servico.autenticar("admin", "senha-admin-de-teste")


@pytest.fixture
def registrar_avistamento(ambiente, imagem_validada, localizacao_guarapari):
    """
    Fábrica que registra um avistamento completo e devolve o resultado.

    Útil nos testes de dashboard e validação, que precisam de dados na base.
    """
    from datetime import datetime, timedelta

    from src.ai.inference import obter_servico_inferencia
    from src.services.sightings import DadosAvistamento, ServicoAvistamentos

    def _registrar(
        horas_atras: int = 2,
        chave: str | None = "chave-teste",
        com_imagem: bool = True,
        com_inferencia: bool = True,
        **extras,
    ):
        servico = ServicoAvistamentos()
        data = (datetime.now() - timedelta(hours=horas_atras)).replace(microsecond=0)
        inferencia = None
        if com_inferencia:
            inferencia = obter_servico_inferencia().classificar(imagem_validada.conteudo)
        dados = DadosAvistamento(
            localizacao=extras.pop("localizacao", localizacao_guarapari),
            data_hora_avistamento=data.isoformat(),
            imagem=imagem_validada if com_imagem else None,
            inferencia=inferencia,
            chave_idempotencia=chave,
            **extras,
        )
        return servico.registrar(dados)

    return _registrar
