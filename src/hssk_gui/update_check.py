"""Check GitHub Releases for a newer version — notification only, never blocks or raises.

Deliberately NOT routed through the engine's ApiClient: that client exists to throttle and
serialise traffic to the HSSK host, is token-bearing, and is base-URL-bound to that host. This
single anonymous GET goes to api.github.com and stays a GUI-only concern (`src/hssk/` untouched).

Zero Qt imports so the version logic tests headless (respx mocks httpx globally).
"""

from __future__ import annotations

from typing import Any

import httpx

LATEST_RELEASE_URL = "https://api.github.com/repos/haikbvn/hssk-tools/releases/latest"
RELEASES_PAGE_URL = "https://github.com/haikbvn/hssk-tools/releases"


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
    if not isinstance(data, dict):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    url = data.get("html_url")
    return tag, (url if isinstance(url, str) and url else RELEASES_PAGE_URL)


def fetch_latest_release(timeout: float = 5.0) -> tuple[str, str] | None:
    """GET the latest release; ``(tag, html_url)`` or None on any failure (never raises)."""
    try:
        resp = httpx.get(
            LATEST_RELEASE_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        return extract_release(resp.json())
    except Exception:
        return None
