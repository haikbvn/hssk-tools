"""Throttled, retrying HTTP client for the hososuckhoe.com.vn internal API.

Enforces the "don't overload the server" constraint: strictly sequential calls, a minimum
interval between requests (+jitter), exponential backoff with full jitter on 429/5xx and transient
errors (honoring ``Retry-After``), and a circuit breaker that aborts after too many consecutive
failures. A 401 surfaces as ``AuthExpired`` so the pipeline can stop and prompt re-login.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..config import Settings
from ..config import settings as default_settings
from ..errors import ApiError, AuthExpired, RateLimited

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_USER_AGENT = "hssk-tools/0.1"


class ApiClient:
    def __init__(
        self,
        token: str,
        settings: Settings | None = None,
        *,
        on_log: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.s = settings or default_settings()
        self.token = token
        self.on_log = on_log or (lambda _m: None)
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request = 0.0
        self._consecutive_failures = 0
        self._client = httpx.Client(
            base_url=self.s.base_url,
            timeout=httpx.Timeout(
                connect=self.s.connect_timeout,
                read=self.s.read_timeout,
                write=self.s.read_timeout,
                pool=self.s.connect_timeout,
            ),
        )

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- internals ----------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": _USER_AGENT,
        }

    def _throttle(self) -> None:
        wait = self.s.request_delay - (self._monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        if self.s.jitter > 0:
            self._sleep(random.uniform(0, self.s.jitter))
        self._last_request = self._monotonic()

    def _backoff(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            delay = retry_after
        else:
            capped = min(self.s.backoff_cap, self.s.backoff_base * (2**attempt))
            delay = random.uniform(0, capped)  # full jitter
        self.on_log(f"retry in {delay:.1f}s (attempt {attempt + 1})")
        self._sleep(delay)

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float | None:
        raw = resp.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    # -- public -------------------------------------------------------------------------

    def post(self, path: str, json: Any) -> Any:
        if self._consecutive_failures >= self.s.circuit_breaker_threshold:
            raise RateLimited(
                f"circuit breaker open after {self._consecutive_failures} consecutive failures"
            )

        last_detail = ""
        for attempt in range(self.s.max_retries + 1):
            self._throttle()
            try:
                resp = self._client.post(path, json=json, headers=self._headers())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_detail = f"transport error: {exc}"
                if attempt < self.s.max_retries:
                    self._backoff(attempt, None)
                    continue
                self._consecutive_failures += 1
                raise RateLimited(last_detail) from exc

            status = resp.status_code
            if status == 401:
                self._consecutive_failures = 0
                raise AuthExpired("server returned 401 — token invalid or expired")
            if status in _RETRYABLE_STATUS:
                last_detail = f"HTTP {status}"
                if attempt < self.s.max_retries:
                    self._backoff(attempt, self._retry_after(resp))
                    continue
                self._consecutive_failures += 1
                raise RateLimited(f"{last_detail} after {attempt + 1} attempts")
            if status >= 400:
                self._consecutive_failures = 0  # client error, not server overload
                raise ApiError(f"HTTP {status}", status=status, body=resp.text[:1000])

            # success
            self._consecutive_failures = 0
            if not resp.content:
                return None
            try:
                return resp.json()
            except ValueError:
                return resp.text

        raise RateLimited(last_detail or "request failed")  # pragma: no cover
