from __future__ import annotations

import httpx
import pytest
import respx

from hssk.api import exams, patients
from hssk.api.client import ApiClient
from hssk.config import Settings
from hssk.errors import ApiError, AuthExpired, RateLimited
from hssk.mapping import SearchSpec

BASE = "https://api.test"


def _settings(**over) -> Settings:
    base = dict(
        base_url=BASE,
        request_delay=0.0,
        jitter=0.0,
        max_retries=2,
        backoff_base=0.0,
        backoff_cap=0.0,
        circuit_breaker_threshold=3,
    )
    base.update(over)
    return Settings(**base)


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _client(settings=None, sleep=None) -> ApiClient:
    return ApiClient("tok", settings or _settings(), sleep=sleep or FakeSleep())


@respx.mock
def test_success_returns_json():
    respx.post(f"{BASE}/x").mock(return_value=httpx.Response(200, json={"ok": True}))
    with _client() as c:
        assert c.post("/x", {}) == {"ok": True}


@respx.mock
def test_401_raises_auth_expired():
    respx.post(f"{BASE}/x").mock(return_value=httpx.Response(401))
    with _client() as c, pytest.raises(AuthExpired):
        c.post("/x", {})


@respx.mock
def test_400_raises_api_error_not_retried():
    route = respx.post(f"{BASE}/x").mock(return_value=httpx.Response(400, text="bad"))
    with _client() as c, pytest.raises(ApiError) as exc:
        c.post("/x", {})
    assert exc.value.status == 400
    assert route.call_count == 1  # not retried


@respx.mock
def test_429_then_200_honors_retry_after():
    sleep = FakeSleep()
    respx.post(f"{BASE}/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    with _client(sleep=sleep) as c:
        assert c.post("/x", {}) == {"ok": 1}
    assert 7.0 in sleep.calls  # respected the Retry-After header


@respx.mock
def test_503_exhausts_retries_then_rate_limited():
    route = respx.post(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with _client() as c, pytest.raises(RateLimited):
        c.post("/x", {})
    assert route.call_count == 3  # 1 + max_retries(2)


def test_circuit_breaker_opens():
    c = _client(_settings(circuit_breaker_threshold=2))
    c._consecutive_failures = 2
    with pytest.raises(RateLimited, match="circuit breaker"):
        c.post("/x", {})


@respx.mock
def test_resolve_patient_exact_match():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {"patientId": 1, "medicalIdentifierCode": "OTHER"},
                        {"patientId": 372954970, "medicalIdentifierCode": "2700020596A"},
                    ]
                }
            },
        )
    )
    with _client() as c:
        pid, rec = patients.resolve_patient_id(c, "2700020596A", SearchSpec())
    assert pid == 372954970


@respx.mock
def test_resolve_patient_not_found():
    from hssk.errors import PatientNotFound

    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"content": []}})
    )
    with _client() as c, pytest.raises(PatientNotFound):
        patients.resolve_patient_id(c, "2700020596A", SearchSpec())


@respx.mock
def test_create_extracts_record_id():
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 555}})
    )
    with _client() as c:
        rid, _raw = exams.create(c, {"medicalRecordInfo": {}})
    assert rid == 555
