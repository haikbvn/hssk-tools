"""Persist and validate the captured Bearer token (JWT).

The token's ``exp`` is decoded locally (no signature check) so the app can warn before it expires.

**Storage.** By default the token lives in the **OS keychain** (macOS Keychain / Windows Credential
Manager / Linux Secret Service) under service ``hssk-tools``. If the keychain is unavailable — no
backend, a locked/again-prompting store, any error — we **silently fall back** to the previous
gitignored, ``chmod 600`` file so login never breaks. A legacy token file is migrated into the
keychain on first read (file → keychain → delete file). Passing an explicit ``path`` bypasses the
keychain entirely and uses that file only (dev/tests/inspection). The token is never logged.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import settings as default_settings
from ..config import token_path
from ..errors import AuthExpired

# OS-keychain coordinates. One entry holds the whole serialized TokenData JSON blob.
_KR_SERVICE = "hssk-tools"
_KR_USER = "token"


@dataclass
class TokenData:
    token: str
    captured_at: float
    exp: int | None  # unix seconds, or None if undecodable

    def seconds_remaining(self, now: float | None = None) -> int | None:
        if self.exp is None:
            return None
        return int(self.exp - (now if now is not None else time.time()))

    def is_valid(self, skew: int | None = None, now: float | None = None) -> bool:
        if skew is None:
            skew = default_settings().token_exp_skew
        rem = self.seconds_remaining(now)
        if rem is None:
            return True  # can't decode exp; assume usable and let a 401 catch it
        return rem > skew


def decode_exp(token: str) -> int | None:
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        exp = data.get("exp")
        return int(exp) if exp is not None else None
    except (IndexError, ValueError, binascii.Error, json.JSONDecodeError):
        return None


def mask(token: str) -> str:
    if len(token) <= 12:
        return "***"
    return f"{token[:6]}…{token[-4:]}"


def _to_blob(data: TokenData) -> str:
    return json.dumps(
        {"token": data.token, "captured_at": data.captured_at, "exp": data.exp},
        ensure_ascii=False,
    )


def _from_blob(blob: str) -> TokenData | None:
    try:
        raw = json.loads(blob)
        return TokenData(
            token=raw["token"], captured_at=raw.get("captured_at", 0.0), exp=raw.get("exp")
        )
    except (ValueError, KeyError, TypeError):
        return None


def _keyring_get() -> str | None:
    try:
        import keyring

        return keyring.get_password(_KR_SERVICE, _KR_USER)
    except Exception:  # no backend / locked / any keyring failure → treat as absent
        return None


def _keyring_set(blob: str) -> bool:
    try:
        import keyring

        keyring.set_password(_KR_SERVICE, _KR_USER, blob)
        return True
    except Exception:
        return False


def _write_file(blob: str, p: Path) -> None:
    p.write_text(blob, encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:
        pass


def _read_file(p: Path) -> TokenData | None:
    if not p.exists():
        return None
    try:
        return _from_blob(p.read_text(encoding="utf-8"))
    except OSError:
        return None


def save_token(token: str, path: Path | None = None) -> TokenData:
    """Persist the token. Default → OS keychain (file fallback); explicit ``path`` → file only."""
    data = TokenData(token=token, captured_at=time.time(), exp=decode_exp(token))
    blob = _to_blob(data)
    if path is not None:
        _write_file(blob, path)
        return data
    if _keyring_set(blob):
        # Keychain is now the source of truth — drop any legacy fallback file.
        token_path().unlink(missing_ok=True)
    else:
        _write_file(blob, token_path())
    return data


def load_token(path: Path | None = None) -> TokenData | None:
    """Load the token. Default → OS keychain, else migrate a legacy file; ``path`` → file only."""
    if path is not None:
        return _read_file(path)
    blob = _keyring_get()
    if blob:
        return _from_blob(blob)
    # Keychain empty (or unavailable): fall back to a legacy file and migrate it in on first read.
    data = _read_file(token_path())
    if data is None:
        return None
    if _keyring_set(_to_blob(data)):
        token_path().unlink(missing_ok=True)
    return data


def load_valid_token(skew: int | None = None, path: Path | None = None) -> str:
    data = load_token(path)
    if data is None:
        raise AuthExpired("No saved token — please log in.")
    if not data.is_valid(skew):
        raise AuthExpired("Saved token has expired — please log in again.")
    return data.token
