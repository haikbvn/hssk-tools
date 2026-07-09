"""Check GitHub Releases for a newer version, and pick the right asset to auto-download.

Deliberately NOT routed through the engine's ApiClient: that client exists to throttle and
serialise traffic to the HSSK host, is token-bearing, and is base-URL-bound to that host. This
single anonymous GET goes to api.github.com and stays a GUI-only concern (`src/hssk/` untouched).

Zero Qt imports so the version logic tests headless (respx mocks httpx globally).
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from typing import Any

import httpx

LATEST_RELEASE_URL = "https://api.github.com/repos/haikbvn/hssk-tools/releases/latest"
RELEASES_PAGE_URL = "https://github.com/haikbvn/hssk-tools/releases"


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int
    sha256: str | None  # from the release API's "digest": "sha256:<hex>" field, when present


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    html_url: str
    assets: list[Asset]


def parse_version(tag: str) -> tuple[int, ...] | None:
    """``v1.4.0`` → ``(1, 4, 0)``; None for anything that isn't int-only dotted parts."""
    tag = tag.strip().lstrip("vV")
    if not tag:
        return None
    try:
        return tuple(int(part) for part in tag.split("."))
    except ValueError:
        return None


def is_newer(latest_tag: str, current: str) -> bool:
    """True when ``latest_tag`` is strictly newer; False if either side is unparseable."""
    latest = parse_version(latest_tag)
    cur = parse_version(current)
    if latest is None or cur is None:
        return False
    width = max(len(latest), len(cur))
    pad = (0,) * width
    return (latest + pad)[:width] > (cur + pad)[:width]


def extract_release(data: Any) -> tuple[str, str] | None:
    """Pull ``(tag_name, html_url)`` from a releases/latest payload; None if unusable."""
    info = extract_release_info(data)
    return None if info is None else (info.tag, info.html_url)


def _parse_digest(value: Any) -> str | None:
    """``"sha256:<hex>"`` → ``"<hex>"``; None for anything else (algo missing/mismatched/absent)."""
    if not isinstance(value, str):
        return None
    prefix = "sha256:"
    return value[len(prefix) :] if value.startswith(prefix) and len(value) > len(prefix) else None


def _extract_assets(raw: Any) -> list[Asset]:
    if not isinstance(raw, list):
        return []
    assets: list[Asset] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("browser_download_url")
        size = item.get("size")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(url, str) or not url:
            continue
        if not isinstance(size, int):
            continue
        sha256 = _parse_digest(item.get("digest"))
        assets.append(Asset(name=name, url=url, size=size, sha256=sha256))
    return assets


def extract_release_info(data: Any) -> ReleaseInfo | None:
    """Pull tag/html_url/assets from a releases/latest payload; None if unusable."""
    if not isinstance(data, dict):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    url = data.get("html_url")
    html_url = url if isinstance(url, str) and url else RELEASES_PAGE_URL
    return ReleaseInfo(tag=tag, html_url=html_url, assets=_extract_assets(data.get("assets")))


def select_asset(
    assets: list[Asset], *, system: str = sys.platform, machine: str = platform.machine()
) -> Asset | None:
    """Pick the installer/DMG matching the running OS/arch; None if nothing matches."""
    if system == "win32":
        return next((a for a in assets if a.name.lower().endswith(".exe")), None)
    if system == "darwin":
        suffix = "-intel.dmg" if machine == "x86_64" else "-apple-silicon.dmg"
        return next((a for a in assets if a.name.lower().endswith(suffix)), None)
    return None


def fetch_release_info(timeout: float = 5.0) -> ReleaseInfo | None:
    """GET the latest release; a :class:`ReleaseInfo` or None on any failure (never raises)."""
    try:
        resp = httpx.get(
            LATEST_RELEASE_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        return extract_release_info(resp.json())
    except Exception:
        return None


def fetch_latest_release(timeout: float = 5.0) -> tuple[str, str] | None:
    """GET the latest release; ``(tag, html_url)`` or None on any failure (never raises)."""
    info = fetch_release_info(timeout=timeout)
    return None if info is None else (info.tag, info.html_url)
