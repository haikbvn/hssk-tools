"""Tests for auth/token_store.py — save/load, masking, JWT exp decode, corrupt file."""

from __future__ import annotations

import base64
import json
import platform
import stat
import time
from pathlib import Path

import pytest

from hssk.auth.token_store import (
    TokenData,
    decode_exp,
    load_token,
    load_valid_token,
    mask,
    save_token,
)
from hssk.errors import AuthExpired

# -- helpers ---------------------------------------------------------------------------


def _make_jwt(exp: int | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_dict: dict = {"sub": "user1"}
    if exp is not None:
        payload_dict["exp"] = exp
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


# -- decode_exp ------------------------------------------------------------------------


def test_decode_exp_present():
    future = int(time.time()) + 3600
    token = _make_jwt(exp=future)
    assert decode_exp(token) == future


def test_decode_exp_absent():
    token = _make_jwt(exp=None)
    assert decode_exp(token) is None


def test_decode_exp_malformed():
    assert decode_exp("not.a.jwt") is None
    assert decode_exp("onlyone") is None
    assert decode_exp("") is None


# -- mask ------------------------------------------------------------------------------


def test_mask_normal():
    token = "abcdefghij1234"
    result = mask(token)
    assert result.startswith("abcdef")
    assert result.endswith("1234")
    assert "…" in result


def test_mask_short():
    assert mask("abc") == "***"
    assert mask("") == "***"


# -- save_token + load_token round-trip ------------------------------------------------


def test_save_and_load(tmp_path: Path):
    future = int(time.time()) + 7200
    token_str = _make_jwt(exp=future)
    p = tmp_path / "token.json"

    td = save_token(token_str, path=p)
    assert td.token == token_str
    assert td.exp == future

    loaded = load_token(path=p)
    assert loaded is not None
    assert loaded.token == token_str
    assert loaded.exp == future
    assert loaded.captured_at > 0


def test_load_token_missing_file(tmp_path: Path):
    assert load_token(path=tmp_path / "no_such.json") is None


def test_load_token_corrupt_json(tmp_path: Path):
    p = tmp_path / "token.json"
    p.write_text("not valid json", encoding="utf-8")
    assert load_token(path=p) is None


def test_load_token_missing_key(tmp_path: Path):
    p = tmp_path / "token.json"
    p.write_text(json.dumps({"captured_at": 0.0}), encoding="utf-8")
    assert load_token(path=p) is None


# -- chmod 600 -------------------------------------------------------------------------


@pytest.mark.skipif(platform.system() == "Windows", reason="chmod 600 is Unix-only")
def test_save_token_sets_600_permissions(tmp_path: Path):
    p = tmp_path / "token.json"
    save_token(_make_jwt(exp=int(time.time()) + 3600), path=p)
    mode = p.stat().st_mode
    # only owner should have read/write; no group or other bits
    assert not (mode & stat.S_IRGRP)
    assert not (mode & stat.S_IROTH)


# -- TokenData helpers -----------------------------------------------------------------


def test_is_valid_with_future_exp():
    td = TokenData(token="x", captured_at=0.0, exp=int(time.time()) + 3600)
    assert td.is_valid()


def test_is_valid_expired():
    td = TokenData(token="x", captured_at=0.0, exp=int(time.time()) - 1)
    assert not td.is_valid()


def test_is_valid_no_exp_assumed_valid():
    td = TokenData(token="x", captured_at=0.0, exp=None)
    assert td.is_valid()


def test_seconds_remaining():
    future = int(time.time()) + 600
    td = TokenData(token="x", captured_at=0.0, exp=future)
    rem = td.seconds_remaining()
    assert rem is not None
    assert 595 <= rem <= 600


# -- load_valid_token ------------------------------------------------------------------


def test_load_valid_token_ok(tmp_path: Path):
    future = int(time.time()) + 7200
    token_str = _make_jwt(exp=future)
    save_token(token_str, path=tmp_path / "token.json")
    assert load_valid_token(path=tmp_path / "token.json") == token_str


def test_load_valid_token_no_file(tmp_path: Path):
    with pytest.raises(AuthExpired, match="No saved token"):
        load_valid_token(path=tmp_path / "missing.json")


def test_load_valid_token_expired(tmp_path: Path):
    expired = int(time.time()) - 3600
    save_token(_make_jwt(exp=expired), path=tmp_path / "token.json")
    with pytest.raises(AuthExpired, match="expired"):
        load_valid_token(path=tmp_path / "token.json")
