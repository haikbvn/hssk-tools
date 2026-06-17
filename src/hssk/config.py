"""Runtime configuration and cross-platform path resolution.

All writable runtime files (token, browser profile, ledger, reports) live in the OS
user-data directory via ``platformdirs`` so a packaged app never tries to write next to a
read-only executable. Bundled read-only resources (the example mapping) are located relative
to the package, or to ``sys._MEIPASS`` when frozen by PyInstaller.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import platformdirs
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "hssk-tools"
APP_AUTHOR = "hssk-tools"


class Settings(BaseSettings):
    """Tunable runtime knobs, overridable via ``HSSK_*`` env vars or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="HSSK_", env_file=".env", extra="ignore")

    # Endpoints
    base_url: str = "https://api.hososuckhoe.com.vn"
    login_url: str = "https://hososuckhoe.com.vn"
    # Host whose Authorization header we sniff during browser login.
    api_host: str = "api.hososuckhoe.com.vn"

    # Rate limiting / resilience (the "don't overload the server" constraint)
    request_delay: float = 1.0  # minimum seconds between consecutive requests
    jitter: float = 0.3  # extra random 0..jitter seconds per request
    max_retries: int = 4
    backoff_base: float = 2.0
    backoff_cap: float = 30.0
    circuit_breaker_threshold: int = 5  # consecutive 5xx/429 before aborting the batch
    connect_timeout: float = 10.0
    read_timeout: float = 30.0

    # Optional base-dir overrides (else platformdirs defaults). Useful for tests/dev.
    data_dir: Path | None = None
    config_dir: Path | None = None


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


# --- Path resolution -------------------------------------------------------------------

def data_dir() -> Path:
    s = settings()
    base = s.data_dir or Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_dir() -> Path:
    s = settings()
    base = s.config_dir or Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
    base.mkdir(parents=True, exist_ok=True)
    return base


def secrets_dir() -> Path:
    d = data_dir() / "secrets"
    d.mkdir(parents=True, exist_ok=True)
    try:
        d.chmod(0o700)
    except OSError:
        pass  # best effort (e.g. Windows)
    return d


def token_path() -> Path:
    return secrets_dir() / "token.json"


def auth_profile_dir() -> Path:
    d = data_dir() / "browser-profile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ledger_path() -> Path:
    return data_dir() / "ledger.jsonl"


def output_dir() -> Path:
    d = data_dir() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def mapping_path() -> Path:
    """User's active mapping file (created from the bundled example on first run)."""
    return config_dir() / "mapping.yaml"


def bundle_root() -> Path:
    """Directory that holds bundled read-only resources (repo root, or _MEIPASS when frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def example_mapping_path() -> Path:
    return bundle_root() / "config" / "mapping.example.yaml"


def ensure_mapping_file() -> Path:
    """Return the active mapping path, seeding it from the bundled example if missing."""
    target = mapping_path()
    if not target.exists():
        example = example_mapping_path()
        if example.exists():
            target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    return target
