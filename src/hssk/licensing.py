"""Polar (polar.sh) license-key validation — the app's hard paywall gate.

Deliberately NOT routed through the engine's ``ApiClient``: that client exists to throttle and
serialise traffic to the HSSK host, is token-bearing, and is base-URL-bound to that host. This
module talks to a different host (``api.polar.sh``), anonymously, and makes at most one HTTP call
per :func:`check_license` invocation (see below) — a single bounded attempt, never a retry loop,
so a Polar hiccup can never turn into hammering their API. A local cache (``license-cache.json``)
plus an offline grace window keep normal launches fast and keep clinics with flaky internet
working day-to-day.

**Honest-enforcement stance.** HSSK Tools is MIT-licensed and its source is public. This module is
a payment gate on the official prebuilt binaries, not DRM: it does not obfuscate itself, does not
detect debuggers or tampered clocks, and does not defend against a modified build that skips the
check entirely. The gate exists so operators who download the official release pay for it, funding
continued development — not to stop a determined person from building their own copy.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import Settings, license_cache_path, license_path
from .config import settings as default_settings

VALIDATE_PATH = "/v1/customer-portal/license-keys/validate"

# Statuses Polar can return that map 1:1 onto a LicenseCheck.reason of the same name.
_DIRECT_DENIAL_STATUSES = {"revoked", "disabled", "not_found"}


class LicenseServerUnreachable(Exception):
    """Raised by :func:`validate_key` for any httpx transport error/timeout (never a retry)."""


@dataclass(frozen=True)
class LicenseCheck:
    """Result of :func:`check_license`.

    ``source`` is one of ``"cache" | "validated" | "grace"`` when ``ok`` is True, else ``""``.
    ``reason`` is set (and one of a fixed vocabulary — see module tests) when ``ok`` is False.
    """

    ok: bool
    source: str = ""
    reason: str | None = None
    display_key: str | None = None
    customer_email: str | None = None
    expires_at: datetime | None = None


# -- Polar HTTP call ------------------------------------------------------------------------


def validate_key(key: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """One bounded call to Polar's public license-key validate endpoint.

    Single attempt, no retries — this runs at every app launch; never hammer Polar. Transport
    failures (timeout, DNS, connection refused, …) raise :class:`LicenseServerUnreachable` so the
    caller can fall back to the cached grace window. A 404 means the key doesn't exist (a
    definitive denial). Any other status code, or a 200 whose body isn't the JSON object we
    expect, is reported back as a ``"malformed_response"`` status rather than raised — Polar
    returning something unexpected is a denial to investigate, not a reason to retry.
    """
    s = settings or default_settings()
    try:
        resp = httpx.post(
            f"{s.polar_api_base}{VALIDATE_PATH}",
            json={"key": key, "organization_id": s.polar_organization_id},
            timeout=s.license_timeout,
        )
    except httpx.HTTPError as exc:
        raise LicenseServerUnreachable(str(exc)) from exc

    if resp.status_code == 404:
        return {"status": "not_found"}
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            return {"status": "malformed_response"}
        if isinstance(data, dict) and isinstance(data.get("status"), str):
            return data
        return {"status": "malformed_response"}
    return {"status": "malformed_response"}


# -- datetime / cache helpers ----------------------------------------------------------------


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _read_key() -> str | None:
    path = license_path()
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def _read_cache(key: str) -> dict[str, Any] | None:
    path = license_cache_path()
    if not path.exists():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("key_sha256") != _hash_key(key):
        return None  # cache belongs to a different (replaced) key — ignore it
    return data


def _write_cache(key: str, data: dict[str, Any]) -> None:
    path = license_cache_path()
    payload = {"key_sha256": _hash_key(key), **data}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _delete_cache() -> None:
    try:
        license_cache_path().unlink()
    except FileNotFoundError:
        pass


def _customer_email(data: dict[str, Any]) -> str | None:
    customer = data.get("customer")
    if isinstance(customer, dict) and isinstance(customer.get("email"), str):
        return customer["email"]
    return None


def _display_key(data: dict[str, Any]) -> str | None:
    value = data.get("display_key")
    return value if isinstance(value, str) else None


# -- check_license and its two "return ok" sub-paths ------------------------------------------


def _fresh_granted_cache(
    cache: dict[str, Any], moment: datetime, s: Settings
) -> LicenseCheck | None:
    """A cached ``granted`` entry that's still unexpired and within the refresh window."""
    if cache.get("status") != "granted":
        return None
    expires_at = _parse_dt(cache.get("expires_at"))
    if expires_at is not None and expires_at <= moment:
        return None
    validated_at = _parse_dt(cache.get("validated_at"))
    if validated_at is None:
        return None
    age_hours = (moment - validated_at).total_seconds() / 3600
    if age_hours >= s.license_refresh_hours:
        return None
    return LicenseCheck(
        ok=True,
        source="cache",
        display_key=cache.get("display_key"),
        customer_email=cache.get("customer_email"),
        expires_at=expires_at,
    )


def _offline_result(cache: dict[str, Any] | None, moment: datetime, s: Settings) -> LicenseCheck:
    """Polar was unreachable — fall back to the cache's offline grace window, if any.

    Grace never outlives an actual expiry: a granted cache whose ``expires_at`` has since passed
    is reported as expired regardless of how recently it was validated.
    """
    if cache is None or cache.get("status") != "granted":
        return LicenseCheck(ok=False, reason="offline_no_cache")
    expires_at = _parse_dt(cache.get("expires_at"))
    if expires_at is not None and expires_at <= moment:
        return LicenseCheck(ok=False, reason="expired")
    validated_at = _parse_dt(cache.get("validated_at"))
    if validated_at is None:
        return LicenseCheck(ok=False, reason="offline_no_cache")
    age_days = (moment - validated_at).total_seconds() / 86400
    if age_days > s.license_grace_days:
        return LicenseCheck(ok=False, reason="offline_grace_expired")
    return LicenseCheck(
        ok=True,
        source="grace",
        display_key=cache.get("display_key"),
        customer_email=cache.get("customer_email"),
        expires_at=expires_at,
    )


def check_license(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    force_refresh: bool = False,
) -> LicenseCheck:
    """The one function both frontends call to decide whether the app may run.

    Order: unconfigured build → missing key file → fresh granted cache (no network) → online
    revalidation → offline grace fallback. See the module tests for the exact reason vocabulary.
    """
    s = settings or default_settings()
    moment = now if now is not None else datetime.now(UTC)

    if not s.polar_organization_id:
        return LicenseCheck(ok=False, reason="unconfigured")

    key = _read_key()
    if not key:
        return LicenseCheck(ok=False, reason="missing_key")

    cache = _read_cache(key)

    if not force_refresh and cache is not None:
        fresh = _fresh_granted_cache(cache, moment, s)
        if fresh is not None:
            return fresh

    try:
        data = validate_key(key, settings=s)
    except LicenseServerUnreachable:
        return _offline_result(cache, moment, s)

    status = data.get("status")
    expires_at = _parse_dt(data.get("expires_at"))
    if status == "granted" and (expires_at is None or expires_at > moment):
        _write_cache(
            key,
            {
                "validated_at": moment.isoformat(),
                "status": "granted",
                "expires_at": data.get("expires_at"),
                "display_key": _display_key(data),
                "customer_email": _customer_email(data),
            },
        )
        return LicenseCheck(
            ok=True,
            source="validated",
            display_key=_display_key(data),
            customer_email=_customer_email(data),
            expires_at=expires_at,
        )

    # Definitive denial (revoked/disabled/not_found/malformed, or granted-but-expired): the cache
    # must not resurrect a denial via the offline grace window on some later run.
    _delete_cache()
    if status == "granted":  # expires_at was in the past
        reason = "expired"
    elif status in _DIRECT_DENIAL_STATUSES:
        reason = status
    else:
        reason = "malformed_response"
    return LicenseCheck(ok=False, reason=reason)


def save_key(key: str) -> None:
    """Persist the license key locally (no validation here).

    Callers call :func:`check_license` with ``force_refresh=True`` right after, so the on-disk
    key and the cache can never disagree about what "the current key" is.
    """
    license_path().write_text(key.strip() + "\n", encoding="utf-8")
