"""Open the website in a persistent browser, let the user log in, and capture the Bearer token.

Primary capture: sniff the ``Authorization`` header off any XHR the SPA sends to the API host
(this is the exact token the site uses). Fallback: scan ``localStorage`` for a JWT-shaped string.
The browser uses a persistent profile so the login session is remembered across runs.

Must run in a thread without an asyncio event loop (a plain ``QThread`` worker or the CLI main
thread) because it uses Playwright's sync API.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

from ..config import Settings, auth_profile_dir
from ..config import settings as default_settings
from ..errors import AuthExpired, HsskError
from .token_store import TokenData, save_token

_JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")

StatusFn = Callable[[str], None]
CancelFn = Callable[[], bool]


def _walk_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_walk_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_walk_strings(v))
    return out


def _scan_local_storage(page: Any) -> str | None:
    try:
        items = page.evaluate(
            "() => { const o={}; for (let i=0;i<localStorage.length;i++)"
            "{const k=localStorage.key(i); o[k]=localStorage.getItem(k);} return o; }"
        )
    except Exception:
        return None
    for value in (items or {}).values():
        if not isinstance(value, str):
            continue
        if _JWT_RE.match(value):
            return value
        try:
            for candidate in _walk_strings(json.loads(value)):
                if _JWT_RE.match(candidate):
                    return candidate
        except (ValueError, TypeError):
            continue
    return None


def capture_token(
    *,
    settings: Settings | None = None,
    on_status: StatusFn | None = None,
    should_cancel: CancelFn | None = None,
    timeout: float = 300.0,
) -> TokenData:
    """Drive the login flow and return the saved TokenData, or raise on timeout/cancel."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise HsskError(
            "Playwright is not installed. Run: playwright install chromium"
        ) from exc

    s = settings or default_settings()
    status = on_status or (lambda _m: None)
    captured: dict[str, str | None] = {"token": None}

    def on_request(req: Any) -> None:
        try:
            if s.api_host in req.url:
                auth = req.headers.get("authorization")
                if auth and auth.lower().startswith("bearer "):
                    captured["token"] = auth.split(" ", 1)[1]
        except Exception:
            pass

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=str(auth_profile_dir()),
                headless=False,
                accept_downloads=False,
            )
        except Exception as exc:  # e.g. profile already open / locked
            raise HsskError(
                "Could not open the browser. If another hssk browser window is already "
                f"open, close it and try again. ({exc})"
            ) from exc

        try:
            ctx.on("request", on_request)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(s.login_url, wait_until="domcontentloaded")
            status("Please log in in the browser window…")

            deadline = time.time() + timeout
            while captured["token"] is None and time.time() < deadline:
                if should_cancel and should_cancel():
                    raise AuthExpired("Login cancelled.")
                if not ctx.pages:
                    raise AuthExpired("Browser was closed before login completed.")
                token = _scan_local_storage(ctx.pages[0])
                if token:
                    captured["token"] = token
                    break
                ctx.pages[0].wait_for_timeout(500)
        finally:
            ctx.close()

    if captured["token"] is None:
        raise AuthExpired("Timed out waiting for login — no token captured.")

    data = save_token(captured["token"])
    status("Token captured.")
    return data
