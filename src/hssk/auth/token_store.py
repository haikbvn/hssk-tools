"""Persist and validate the captured Bearer token (JWT).

The token's ``exp`` is decoded locally (no signature check, no extra dependency) so the app can
warn before it expires. The token is written to a gitignored, ``chmod 600`` file, never logged.
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


def save_token(token: str, path: Path | None = None) -> TokenData:
    p = path or token_path()
    data = TokenData(token=token, captured_at=time.time(), exp=decode_exp(token))
    p.write_text(
        json.dumps(
            {"token": data.token, "captured_at": data.captured_at, "exp": data.exp},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return data


def load_token(path: Path | None = None) -> TokenData | None:
    p = path or token_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return TokenData(
            token=raw["token"], captured_at=raw.get("captured_at", 0.0), exp=raw.get("exp")
        )
    except (ValueError, KeyError):
        return None


def load_valid_token(skew: int | None = None, path: Path | None = None) -> str:
    data = load_token(path)
    if data is None:
        raise AuthExpired("No saved token — please log in.")
    if not data.is_valid(skew):
        raise AuthExpired("Saved token has expired — please log in again.")
    return data.token
