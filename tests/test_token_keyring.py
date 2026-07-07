"""token_store keychain behavior: keychain-primary storage, legacy-file migration, file fallback.

The autouse ``_fake_keyring`` fixture (conftest) gives every test a fresh in-memory keychain, so
these never touch — or prompt — the real OS keychain. The file-only path (explicit ``path=``) is
covered by test_token_store.py; here we exercise the default (``path=None``) code path.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import keyring
import pytest

from hssk.auth import token_store as ts
from hssk.auth.token_store import _KR_SERVICE, _KR_USER, load_token, save_token


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point settings' data_dir at a tmp dir so token_path() is never the real user path."""
    import hssk.config as cfg

    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    cfg.settings.cache_clear()
    yield tmp_path
    cfg.settings.cache_clear()


def test_saves_to_keychain_not_file(isolated_data_dir: Path) -> None:
    from hssk.config import token_path

    tok = _make_jwt(int(time.time()) + 3600)
    saved = save_token(tok)
    assert saved.token == tok
    assert not token_path().exists()  # stored in the keychain, no fallback file written
    assert keyring.get_password(_KR_SERVICE, _KR_USER) is not None
    loaded = load_token()
    assert loaded is not None
    assert loaded.token == tok
    assert loaded.exp == saved.exp


def test_migrates_legacy_file_into_keychain(isolated_data_dir: Path) -> None:
    from hssk.config import token_path

    tok = _make_jwt(int(time.time()) + 3600)
    # Seed a legacy chmod-600 file (explicit path bypasses the keychain), keychain starts empty.
    save_token(tok, path=token_path())
    assert token_path().exists()
    assert keyring.get_password(_KR_SERVICE, _KR_USER) is None

    loaded = load_token()  # default path: keychain empty → read file → migrate it in
    assert loaded is not None
    assert loaded.token == tok
    assert keyring.get_password(_KR_SERVICE, _KR_USER) is not None  # migrated
    assert not token_path().exists()  # legacy file removed after migration


def test_falls_back_to_file_when_keychain_unavailable(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hssk.config import token_path

    # Simulate no usable keychain (no backend / locked): every keychain op fails silently.
    monkeypatch.setattr(ts, "_keyring_set", lambda blob: False)
    monkeypatch.setattr(ts, "_keyring_get", lambda: None)

    tok = _make_jwt(int(time.time()) + 3600)
    save_token(tok)
    assert token_path().exists()  # fell back to the chmod-600 file
    loaded = load_token()
    assert loaded is not None
    assert loaded.token == tok
    assert token_path().exists()  # still there (no keychain to migrate into)


def test_keychain_wins_over_stale_file(isolated_data_dir: Path) -> None:
    from hssk.config import token_path

    old = _make_jwt(int(time.time()) + 100)
    new = _make_jwt(int(time.time()) + 9999)
    save_token(old, path=token_path())  # stale file
    keyring.set_password(_KR_SERVICE, _KR_USER, json.dumps({"token": new, "captured_at": 0.0}))

    loaded = load_token()
    assert loaded is not None
    assert loaded.token == new  # keychain is authoritative; the stale file is ignored
