"""Tests for auth/browser_login.py — expired-token filtering at capture time."""

from __future__ import annotations

import base64
import json
import time

from hssk.auth.browser_login import _scan_local_storage, _token_unexpired


def _make_jwt(exp: int | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_dict: dict = {"sub": "user1"}
    if exp is not None:
        payload_dict["exp"] = exp
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesignature"


class _FakePage:
    """Minimal stub for playwright Page — only evaluate() is called."""

    def __init__(self, storage: dict[str, str]) -> None:
        self._storage = storage

    def evaluate(self, _script: str) -> dict[str, str]:
        return self._storage


# -- _token_unexpired ------------------------------------------------------------------


def test_token_unexpired_future_exp():
    assert _token_unexpired(_make_jwt(exp=int(time.time()) + 3600)) is True


def test_token_unexpired_past_exp():
    assert _token_unexpired(_make_jwt(exp=int(time.time()) - 1)) is False


def test_token_unexpired_within_skew():
    # exp 60 s from now but skew=120 → should be treated as expired
    assert _token_unexpired(_make_jwt(exp=int(time.time()) + 60), skew=120) is False


def test_token_unexpired_no_exp_assumed_valid():
    assert _token_unexpired(_make_jwt(exp=None)) is True


def test_token_unexpired_malformed():
    assert _token_unexpired("not.a.jwt") is True
    assert _token_unexpired("") is True


# -- _scan_local_storage ---------------------------------------------------------------


def test_scan_returns_valid_jwt():
    valid = _make_jwt(exp=int(time.time()) + 3600)
    page = _FakePage({"k": valid})
    assert _scan_local_storage(page) == valid


def test_scan_skips_expired_jwt():
    expired = _make_jwt(exp=int(time.time()) - 1)
    page = _FakePage({"k": expired})
    assert _scan_local_storage(page) is None


def test_scan_skips_expired_returns_valid():
    expired = _make_jwt(exp=int(time.time()) - 1)
    valid = _make_jwt(exp=int(time.time()) + 3600)
    page = _FakePage({"a": expired, "b": valid})
    assert _scan_local_storage(page) == valid


def test_scan_valid_jwt_nested_in_json():
    valid = _make_jwt(exp=int(time.time()) + 3600)
    nested = json.dumps({"token": valid})
    page = _FakePage({"auth": nested})
    assert _scan_local_storage(page) == valid


def test_scan_expired_jwt_nested_in_json_skipped():
    expired = _make_jwt(exp=int(time.time()) - 1)
    nested = json.dumps({"token": expired})
    page = _FakePage({"auth": nested})
    assert _scan_local_storage(page) is None


def test_scan_evaluate_raises_returns_none():
    class _ErrPage:
        def evaluate(self, _script: str) -> None:
            raise RuntimeError("page crashed")

    assert _scan_local_storage(_ErrPage()) is None


def test_scan_empty_storage():
    assert _scan_local_storage(_FakePage({})) is None
