"""Fetch and persist the logged-in operator's profile (name + facility).

The site's /api/v1/resource/sys-users/?isLogin=true endpoint returns the account record.
No dedicated healthfacilitiesId field exists; it is embedded in the username as
``<prefix>_<id>_<slug>`` (e.g. ``bnh_27084_lienbao``).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Settings, profile_path
from ..config import settings as default_settings

# DEBUG-level only: with no handler configured these records drop silently (the engine never
# prints), but a developer can logging.basicConfig(level=DEBUG) to see the swallowed tracebacks.
logger = logging.getLogger(__name__)

_FACILITY_ID_RE = re.compile(r"_(\d+)_")
_PROFILE_ENDPOINT = "/api/v1/resource/sys-users/"
# Headers required to pass the site's WAF (Cloudrity).
_EXTRA_HEADERS = {
    "Origin": "https://hososuckhoe.com.vn",
    "Referer": "https://hososuckhoe.com.vn/",
}


@dataclass
class ProfileData:
    display_name: str  # operator / facility name shown in the GUI
    username: str
    healthfacilities_id: str | None  # extracted from username
    captured_at: float

    def identity_label(self) -> str:
        if self.healthfacilities_id:
            return f"{self.display_name} ({self.healthfacilities_id})"
        return self.display_name


def _extract_facility_id(username: str) -> str | None:
    m = _FACILITY_ID_RE.search(username)
    return m.group(1) if m else None


def parse_profile(raw: Any) -> ProfileData | None:
    """Parse the sys-users API response into ProfileData; return None if unusable."""
    try:
        data: Any = raw.get("data") if isinstance(raw, dict) else raw
        if not isinstance(data, dict):
            return None
        display_name: str = data.get("fullname") or data.get("fullName") or ""
        username: str = data.get("username") or data.get("userName") or ""
        if not display_name and not username:
            return None
        return ProfileData(
            display_name=display_name,
            username=username,
            healthfacilities_id=_extract_facility_id(username),
            captured_at=time.time(),
        )
    except Exception:
        logger.debug("could not parse profile response", exc_info=True)
        return None


def save_profile(data: ProfileData, path: Path | None = None) -> None:
    p = path or profile_path()
    p.write_text(
        json.dumps(
            {
                "display_name": data.display_name,
                "username": data.username,
                "healthfacilities_id": data.healthfacilities_id,
                "captured_at": data.captured_at,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    try:
        p.chmod(0o600)
    except OSError:
        pass


def load_profile(path: Path | None = None) -> ProfileData | None:
    p = path or profile_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return ProfileData(
            display_name=raw["display_name"],
            username=raw.get("username", ""),
            healthfacilities_id=raw.get("healthfacilities_id"),
            captured_at=raw.get("captured_at", 0.0),
        )
    except (ValueError, KeyError):
        return None


def fetch_profile(token: str, settings: Settings | None = None) -> ProfileData | None:
    """Call the sys-users endpoint with the captured token; return parsed profile or None."""
    try:
        import httpx

        s = settings or default_settings()
        resp = httpx.get(
            f"{s.base_url}{_PROFILE_ENDPOINT}",
            params={"isLogin": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "hssk-tools/0.1",
                **_EXTRA_HEADERS,
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            return parse_profile(resp.json())
    except Exception:
        logger.debug("profile fetch failed", exc_info=True)
    return None
