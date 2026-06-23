"""Throttled, retrying HTTP client for the hososuckhoe.com.vn internal API.

Enforces the "don't overload the server" constraint: strictly sequential calls, a minimum
interval between requests (+jitter), exponential backoff with full jitter on 429/5xx and transient
errors (honoring ``Retry-After``), and a circuit breaker that aborts after too many consecutive
failures. A 401 surfaces as ``AuthExpired`` so the pipeline can stop and prompt re-login.
"""

from __future__ import annotations

import datetime as dt
import random
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .. import __version__
from ..config import Settings
from ..config import settings as default_settings
from ..errors import ApiError, AuthExpired, RateLimited

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "*/*",
                "User-Agent": f"hssk-tools/{__version__}",
            },
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
            pass
        try:
            # RFC 7231 HTTP-date format (e.g. "Wed, 21 Oct 2015 07:28:00 GMT")
            then = parsedate_to_datetime(raw)
            delay = (then - dt.datetime.now(tz=dt.UTC)).total_seconds()
            return max(0.0, delay)
        except Exception:
            return None

    # -- public -------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        if self._consecutive_failures >= self.s.circuit_breaker_threshold:
            raise RateLimited(
                f"circuit breaker open after {self._consecutive_failures} consecutive failures"
            )

        last_detail = ""
        for attempt in range(self.s.max_retries + 1):
            self._throttle()
            try:
                resp = self._client.request(method, path, params=params, json=json)
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

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Any) -> Any:
        return self._request("POST", path, json=json)
