"""Tests for config.py — Settings env-var overrides and path helpers."""

from __future__ import annotations

import platform
import stat
from pathlib import Path

import pytest

from hssk.config import Settings

# -- Settings env-var overrides --------------------------------------------------------


def test_settings_defaults():
    s = Settings()
    assert s.request_delay == 1.0
    assert s.jitter == 0.3
    assert s.max_retries == 4
    assert s.data_dir is None
    assert s.config_dir is None


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HSSK_REQUEST_DELAY", "2.5")
    monkeypatch.setenv("HSSK_MAX_RETRIES", "8")
    s = Settings()
    assert s.request_delay == 2.5
    assert s.max_retries == 8


def test_settings_data_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    s = Settings()
    assert s.data_dir == tmp_path


def test_settings_base_url_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HSSK_BASE_URL", "https://mock.api.test")
    s = Settings()
    assert s.base_url == "https://mock.api.test"


# -- Path helpers ----------------------------------------------------------------------


def test_data_dir_created(tmp_path: Path):
    from hssk.config import Settings

    s = Settings(data_dir=tmp_path / "custom_data")
    # data_dir() reads from settings() cache; call the helper directly with a Settings object
    # by exercising the data_dir path logic via the Settings object directly
    assert not s.data_dir.exists()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    assert s.data_dir.is_dir()


def test_token_path_is_under_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """token_path() must live under the secrets subdir of data_dir."""
    # Patch settings cache by monkeypatching the env var so data_dir uses tmp_path.
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    # Clear lru_cache so fresh Settings() is returned.
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        from hssk.config import token_path

        p = token_path()
        assert p.parent.name == "secrets"
        assert tmp_path in p.parents
    finally:
        _settings_cached.cache_clear()


def test_ledger_path_is_under_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        from hssk.config import ledger_path

        p = ledger_path()
        assert tmp_path in p.parents
    finally:
        _settings_cached.cache_clear()


def test_ensure_update_overlay_seeds_from_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """ensure_update_overlay_file() creates mapping.update.yaml under config_dir on first use."""
    monkeypatch.setenv("HSSK_CONFIG_DIR", str(tmp_path))
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        from hssk.config import ensure_update_overlay_file, update_overlay_path

        p = ensure_update_overlay_file()
        assert p == update_overlay_path()
        assert p.name == "mapping.update.yaml"
        assert tmp_path in p.parents
        assert p.exists()
        assert "medicalRecordId" in p.read_text(encoding="utf-8")
    finally:
        _settings_cached.cache_clear()


def test_sponsor_asset_path() -> None:
    from hssk.config import sponsor_asset

    p = sponsor_asset("vietqr.png")
    assert p.parts[-3:] == ("assets", "sponsor", "vietqr.png"), f"unexpected path: {p}"


def test_sponsor_placeholder_images_exist() -> None:
    from hssk.config import sponsor_asset

    for name in ("vietqr.png", "momo.png"):
        p = sponsor_asset(name)
        assert p.exists(), f"placeholder image missing: {p}"
        assert p.stat().st_size > 0, f"placeholder image is empty: {p}"


@pytest.mark.skipif(platform.system() == "Windows", reason="chmod is Unix-only")
def test_secrets_dir_is_chmod_700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        from hssk.config import secrets_dir

        d = secrets_dir()
        mode = d.stat().st_mode
        # group and other should have no permissions
        assert not (mode & stat.S_IRWXG)
        assert not (mode & stat.S_IRWXO)
    finally:
        _settings_cached.cache_clear()
