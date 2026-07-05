"""Typed exceptions for the engine."""

from __future__ import annotations


class HsskError(Exception):
    """Base class for all hssk errors."""


class ConfigError(HsskError):
    """Invalid mapping / configuration."""


class AlreadyRunning(HsskError):
    """Another hssk batch already holds the run lock (guards the dedup ledger)."""


class BatchCancelled(HsskError):
    """The user cancelled the batch while the client was waiting (throttle/backoff)."""


class AuthExpired(HsskError):
    """No valid token, or the server rejected the token (401)."""


class ApiError(HsskError):
    """A non-retryable API failure (e.g. 4xx other than 401/429)."""

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


class RateLimited(HsskError):
    """Retries exhausted, or the circuit breaker tripped (server looks unhealthy)."""


class PatientNotFound(HsskError):
    """Patient search returned no exact match for the medical identifier code."""


class MultiMatch(HsskError):
    """Patient search returned more than one candidate and policy forbids guessing."""

    def __init__(self, message: str, *, candidates: list | None = None):
        super().__init__(message)
        self.candidates = candidates or []
