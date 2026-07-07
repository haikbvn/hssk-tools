"""The pre-run token-lifetime estimate (pipeline/runner.py pure helpers)."""

from __future__ import annotations

import base64
import json

from hssk.config import Settings
from hssk.events import MessageCode, render_en
from hssk.pipeline.runner import estimate_batch_seconds, token_expiry_warning


def _make_jwt(exp: int | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_dict: dict = {"sub": "user1"}
    if exp is not None:
        payload_dict["exp"] = exp
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def _settings(delay: float = 1.0, jitter: float = 0.3) -> Settings:
    return Settings(base_url="https://api.test", request_delay=delay, jitter=jitter)


def test_estimate_arithmetic() -> None:
    # rows × 2 requests × (delay + jitter/2 + 0.8s overhead)
    assert estimate_batch_seconds(10, _settings(delay=1.0, jitter=0.3)) == 10 * 2 * 1.95


def test_far_future_exp_no_warning() -> None:
    token = _make_jwt(exp=1_000_000)
    assert token_expiry_warning(token, rows=10, settings=_settings(), now=0.0) is None


def test_near_exp_warns_with_estimates() -> None:
    # 100 rows need ~390s (~7 min); token has only 60s (~1 min) left.
    token = _make_jwt(exp=60)
    warning = token_expiry_warning(token, rows=100, settings=_settings(), now=0.0)
    assert warning is not None
    assert warning.code == MessageCode.LOG_TOKEN_SHORT
    assert warning.params == {"needed": "6", "left": "1"}
    assert render_en(warning).startswith("token may expire before this batch finishes")
    assert "(~6 min needed, ~1 min left)" in render_en(warning)


def test_already_expired_clamps_to_zero_minutes() -> None:
    token = _make_jwt(exp=0)
    warning = token_expiry_warning(token, rows=100, settings=_settings(), now=1000.0)
    assert warning is not None
    assert warning.params["left"] == "0"


def test_undecodable_token_no_warning() -> None:
    assert token_expiry_warning("not-a-jwt", rows=100, settings=_settings(), now=0.0) is None
    assert (
        token_expiry_warning(_make_jwt(exp=None), rows=100, settings=_settings(), now=0.0) is None
    )


def test_zero_rows_no_warning() -> None:
    token = _make_jwt(exp=60)
    assert token_expiry_warning(token, rows=0, settings=_settings(), now=0.0) is None
