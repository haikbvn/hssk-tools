"""Tests for hssk.licensing — Polar license-key validation, caching, and offline grace."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from hssk import licensing
from hssk.config import license_cache_path
from hssk.config import settings as _settings_cached

ORG_ID = "11111111-1111-1111-1111-111111111111"
VALIDATE_URL = "https://api.polar.sh" + licensing.VALIDATE_PATH
NOW = datetime(2026, 7, 16, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate the license key/cache location under tmp_path and set a configured org id.

    Pattern mirrors tests/test_config.py: env-var override + settings.cache_clear() in
    try/finally so the process-wide Settings() lru_cache never leaks into other tests.
    """
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HSSK_POLAR_ORGANIZATION_ID", ORG_ID)
    _settings_cached.cache_clear()
    try:
        yield tmp_path
    finally:
        _settings_cached.cache_clear()


def _write_key(key: str = "MY-KEY") -> None:
    licensing.save_key(key)


def _write_cache(
    key: str,
    *,
    validated_at: datetime,
    status: str = "granted",
    expires_at: datetime | None = None,
    display_key: str = "MY-****",
    customer_email: str | None = "clinic@example.com",
) -> None:
    payload = {
        "key_sha256": licensing._hash_key(key),
        "validated_at": validated_at.isoformat(),
        "status": status,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "display_key": display_key,
        "customer_email": customer_email,
    }
    license_cache_path().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# -- unconfigured / missing key -----------------------------------------------------------


@respx.mock
def test_unconfigured_org_id_denies_with_zero_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    # Force the empty/unconfigured case regardless of the real shipped default (delenv alone
    # would now leave a real org id configured).
    monkeypatch.setenv("HSSK_POLAR_ORGANIZATION_ID", "")
    _settings_cached.cache_clear()
    try:
        route = respx.post(VALIDATE_URL).mock(return_value=httpx.Response(200, json={}))
        result = licensing.check_license(now=NOW)
        assert result == licensing.LicenseCheck(ok=False, reason="unconfigured")
        assert route.call_count == 0
    finally:
        _settings_cached.cache_clear()


def test_missing_key_file(sandbox: Path) -> None:
    result = licensing.check_license(now=NOW)
    assert result == licensing.LicenseCheck(ok=False, reason="missing_key")


# -- online validate: granted --------------------------------------------------------------


@respx.mock
def test_granted_response_is_ok_and_writes_cache(sandbox: Path) -> None:
    _write_key("MY-KEY")
    respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "granted",
                "expires_at": None,
                "display_key": "MY-****",
                "customer": {"email": "clinic@example.com"},
            },
        )
    )
    result = licensing.check_license(now=NOW)
    assert result.ok is True
    assert result.source == "validated"
    assert result.customer_email == "clinic@example.com"
    assert result.expires_at is None

    cache_path = license_cache_path()
    assert cache_path.exists()
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["key_sha256"] == licensing._hash_key("MY-KEY")
    assert cache["status"] == "granted"


# -- fresh cache short-circuits the network call --------------------------------------------


@respx.mock
def test_fresh_cache_is_ok_with_zero_http_requests(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(hours=1))
    route = respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(200, json={"status": "granted"})
    )

    result = licensing.check_license(now=NOW)

    assert result.ok is True
    assert result.source == "cache"
    assert route.call_count == 0


@respx.mock
def test_force_refresh_calls_http_even_with_fresh_cache(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(hours=1))
    route = respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "granted",
                "expires_at": None,
                "display_key": "MY-****",
                "customer": {},
            },
        )
    )

    result = licensing.check_license(now=NOW, force_refresh=True)

    assert result.ok is True
    assert result.source == "validated"
    assert route.call_count == 1


# -- definitive denials delete the cache ----------------------------------------------------


@respx.mock
def test_revoked_denies_and_deletes_existing_cache(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=1))
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(200, json={"status": "revoked"}))

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="revoked")
    assert not license_cache_path().exists()


@respx.mock
def test_disabled_denies_and_deletes_existing_cache(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=1))
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(200, json={"status": "disabled"}))

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="disabled")
    assert not license_cache_path().exists()


@respx.mock
def test_404_denies_as_not_found_and_deletes_existing_cache(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=1))
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(404))

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="not_found")
    assert not license_cache_path().exists()


@respx.mock
def test_granted_but_expires_at_in_past_denies_as_expired(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=1))
    respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"status": "granted", "expires_at": (NOW - timedelta(days=1)).isoformat()},
        )
    )

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="expired")
    assert not license_cache_path().exists()


@respx.mock
def test_malformed_non_json_body_denies(sandbox: Path) -> None:
    _write_key("MY-KEY")
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(200, text="not json"))

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="malformed_response")


@respx.mock
def test_malformed_missing_status_field_denies(sandbox: Path) -> None:
    _write_key("MY-KEY")
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(200, json={"foo": "bar"}))

    result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="malformed_response")


# -- network unreachable: offline grace window -----------------------------------------------


def test_network_error_recent_granted_cache_falls_back_to_grace(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=3))

    with respx.mock:
        respx.post(VALIDATE_URL).mock(side_effect=httpx.ConnectError("no network"))
        result = licensing.check_license(now=NOW)

    assert result.ok is True
    assert result.source == "grace"


def test_network_error_old_granted_cache_grace_expired(sandbox: Path) -> None:
    _write_key("MY-KEY")
    _write_cache("MY-KEY", validated_at=NOW - timedelta(days=20))

    with respx.mock:
        respx.post(VALIDATE_URL).mock(side_effect=httpx.ConnectError("no network"))
        result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="offline_grace_expired")


def test_network_error_no_cache_at_all(sandbox: Path) -> None:
    _write_key("MY-KEY")

    with respx.mock:
        respx.post(VALIDATE_URL).mock(side_effect=httpx.ConnectError("no network"))
        result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="offline_no_cache")


def test_network_error_expired_cache_denies_despite_recent_validation(sandbox: Path) -> None:
    """Grace never outlives an actual expiry, even when validated_at is very recent."""
    _write_key("MY-KEY")
    _write_cache(
        "MY-KEY",
        validated_at=NOW - timedelta(hours=1),
        expires_at=NOW - timedelta(days=1),
    )

    with respx.mock:
        respx.post(VALIDATE_URL).mock(side_effect=httpx.ConnectError("no network"))
        result = licensing.check_license(now=NOW)

    assert result == licensing.LicenseCheck(ok=False, reason="expired")


# -- cache belonging to a replaced key is ignored --------------------------------------------


@respx.mock
def test_cache_for_different_key_is_ignored_and_revalidates(sandbox: Path) -> None:
    _write_key("NEW-KEY")
    _write_cache("OLD-KEY", validated_at=NOW - timedelta(hours=1))
    route = respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "granted",
                "expires_at": None,
                "display_key": "NEW-****",
                "customer": {},
            },
        )
    )

    result = licensing.check_license(now=NOW)

    assert result.ok is True
    assert result.source == "validated"
    assert route.call_count == 1


# -- save_key ---------------------------------------------------------------------------------


def test_save_key_strips_whitespace_and_appends_newline(sandbox: Path) -> None:
    licensing.save_key("  SOME-KEY-123  \n")
    from hssk.config import license_path

    assert license_path().read_text(encoding="utf-8") == "SOME-KEY-123\n"
