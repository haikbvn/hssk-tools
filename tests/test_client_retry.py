from __future__ import annotations

import json

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
def test_resolve_patient_echoed_exact_match():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {"patientId": 1, "medicalIdentifierCode": "OTHER"},
                        {"patientId": 372954970, "medicalIdentifierCode": "2700020596A"},
                    ]
                }
            },
        )
    )
    with _client() as c:
        resolved = patients.resolve(c, "2700020596A", SearchSpec())
    assert resolved.patient_id == 372954970
    assert resolved.medical_identifier_code == "2700020596A"


@respx.mock
def test_resolve_by_cccd_single_result_uses_real_code():
    # Searching a CCCD: the result's medicalIdentifierCode differs from the query, single match.
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {
                            "patientId": 366921346,
                            "medicalIdentifierCode": "2720551044",
                            "fullname": "VŨ THỊ LẠNG",
                        }
                    ]
                }
            },
        )
    )
    with _client() as c:
        resolved = patients.resolve(c, "027148003240", SearchSpec())
    assert resolved.patient_id == 366921346
    assert resolved.medical_identifier_code == "2720551044"  # real code, not the searched CCCD
    assert resolved.fullname == "VŨ THỊ LẠNG"


@respx.mock
def test_resolve_broadcasts_query_across_fields():
    route = respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"items": []}})
    )
    from hssk.errors import PatientNotFound

    with _client() as c, pytest.raises(PatientNotFound):
        patients.resolve(c, "027148003240", SearchSpec())
    sent = json.loads(route.calls.last.request.content)
    for field in (
        "fullname",
        "medicalIdentifierCode",
        "identification",
        "personalPhoneNumber",
        "healthInsuranceNumber",
    ):
        assert sent[field] == "027148003240"
    assert sent["profileStatus"] == "1"


@respx.mock
def test_create_extracts_record_id():
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 555}})
    )
    with _client() as c:
        rid, _raw = exams.create(c, {"medicalRecordInfo": {}})
    assert rid == 555


@respx.mock
def test_429_http_date_retry_after_is_honored():
    import datetime as dt

    sleep = FakeSleep()
    # Build an HTTP-date ~5 seconds in the future
    future = dt.datetime.now(tz=dt.UTC) + dt.timedelta(seconds=5)
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    respx.post(f"{BASE}/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": http_date}),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    with _client(sleep=sleep) as c:
        assert c.post("/x", {}) == {"ok": 1}
    # Should have slept approximately 5s (within a few seconds of tolerance)
    backoff_delays = [s for s in sleep.calls if s > 0]
    assert backoff_delays, "no backoff sleep was performed"
    assert any(3 <= d <= 10 for d in backoff_delays), f"unexpected delays: {backoff_delays}"
