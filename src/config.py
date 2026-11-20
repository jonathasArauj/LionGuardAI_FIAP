"""
Configuração central do LionGuard AI.

Todas as opções sensíveis ou dependentes de ambiente são lidas de variáveis de
ambiente (arquivo .env no desenvolvimento). Nenhuma credencial fica no código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python-dotenv é opcional: o sistema funciona só com variáveis de ambiente
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - ambiente sem python-dotenv
    pass


BASE_DIR = Path(__file__).resolve().parent.parent


def _env(nome: str, padrao: str) -> str:
    valor = os.getenv(nome)
    return valor if valor not in (None, "") else padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(_env(nome, str(padrao)))
    except ValueError:
        return padrao


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(_env(nome, str(padrao)))
    except ValueError:
        return padrao


def _env_bool(nome: str, padrao: bool) -> bool:
    return _env(nome, "1" if padrao else "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }


@dataclass(frozen=True)
class Config:
    """Configuração imutável da aplicação."""

    # --- Caminhos -----------------------------------------------------------
    base_dir: Path = BASE_DIR
    database_url: str = field(
        default_factory=lambda: _env("LIONGUARD_DB", str(BASE_DIR / "data" / "lionguard.db"))
    )
    diretorio_imagens: Path = field(
        default_factory=lambda: Path(
            _env("LIONGUARD_IMAGE_DIR", str(BASE_DIR / "data" / "images"))
        )
    )
    diretorio_modelos: Path = field(
        default_factory=lambda: Path(_env("LIONGUARD_MODEL_DIR", str(BASE_DIR / "models")))
    )
    diretorio_relatorios: Path = field(
        default_factory=lambda: Path(_env("LIONGUARD_REPORT_DIR", str(BASE_DIR / "reports")))
    )

    # --- Upload de imagens --------------------------------------------------
    upload_max_bytes: int = field(
        default_factory=lambda: _env_int("LIONGUARD_UPLOAD_MAX_BYTES", 8 * 1024 * 1024)
    )
    upload_formatos: tuple[str, ...] = ("jpeg", "jpg", "png", "webp")
    upload_dimensao_minima: int = 64
    upload_dimensao_maxima: int = 8000

    # --- Inteligência artificial -------------------------------------------
    modelo_arquivo: str = field(default_factory=lambda: _env("LIONGUARD_MODEL_FILE", ""))
    limiar_positivo: float = field(
        default_factory=lambda: _env_float("LIONGUARD_THRESHOLD_POSITIVE", 0.70)
    )
    limiar_inconclusivo: float = field(
        default_factory=lambda: _env_float("LIONGUARD_THRESHOLD_INCONCLUSIVE", 0.45)
    )
    entrada_modelo: int = field(default_factory=lambda: _env_int("LIONGUARD_MODEL_INPUT", 224))

    # --- Privacidade / mapa público ----------------------------------------
    # Precisão pública do mapa: 2 casas decimais ~ 1,1 km. Coordenadas exatas
    # ficam restritas a perfis autorizados (seção 10 do escopo).
    casas_decimais_publicas: int = field(
        default_factory=lambda: _env_int("LIONGUARD_PUBLIC_PRECISION", 2)
    )

    # --- Proteção contra abuso ---------------------------------------------
    rate_limit_registros: int = field(
        default_factory=lambda: _env_int("LIONGUARD_RATE_LIMIT_COUNT", 5)
    )
    rate_limit_janela_segundos: int = field(
        default_factory=lambda: _env_int("LIONGUARD_RATE_LIMIT_WINDOW", 600)
    )

    # --- Autenticação -------------------------------------------------------
    sessao_duracao_horas: int = field(
        default_factory=lambda: _env_int("LIONGUARD_SESSION_HOURS", 8)
    )
    demo_usuarios_ativos: bool = field(
        default_factory=lambda: _env_bool("LIONGUARD_DEMO_USERS", True)
    )

    # --- Modo demonstração --------------------------------------------------
    demo_habilitado: bool = field(default_factory=lambda: _env_bool("LIONGUARD_DEMO_MODE", True))

    def garantir_diretorios(self) -> None:
        for caminho in (
            self.diretorio_imagens,
            self.diretorio_modelos,
            self.diretorio_relatorios,
        ):
            caminho.mkdir(parents=True, exist_ok=True)
        Path(self.database_url).parent.mkdir(parents=True, exist_ok=True)


_config: Config | None = None


def get_config() -> Config:
    """Retorna a configuração única do processo."""
    global _config
    if _config is None:
        _config = Config()
        _config.garantir_diretorios()
    return _config


def resetar_config() -> None:
    """Usado pelos testes para reler variáveis de ambiente."""
    global _config
    _config = None
