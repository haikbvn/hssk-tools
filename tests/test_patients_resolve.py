from __future__ import annotations

import httpx
import pytest
import respx

from hssk.api import patients
from hssk.api.client import ApiClient
from hssk.config import Settings
from hssk.errors import MultiMatch, PatientNotFound
from hssk.mapping import SearchSpec

BASE = "https://api.test"


def _settings(**over) -> Settings:
    base = dict(
        base_url=BASE,
        request_delay=0.0,
        jitter=0.0,
        max_retries=0,
        backoff_base=0.0,
        backoff_cap=0.0,
        circuit_breaker_threshold=10,
    )
    base.update(over)
    return Settings(**base)


def _client() -> ApiClient:
    return ApiClient("tok", _settings())


def _resp(items: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"data": {"items": items}})


# ---------------------------------------------------------------------------
# multi_match modes
# ---------------------------------------------------------------------------


@respx.mock
def test_multi_match_error_raises():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"patientId": 1, "medicalIdentifierCode": "ABC"},
                {"patientId": 2, "medicalIdentifierCode": "DEF"},
            ]
        )
    )
    spec = SearchSpec(multi_match="error")
    with _client() as c, pytest.raises(MultiMatch):
        patients.resolve(c, "query", spec)


@respx.mock
def test_multi_match_skip_raises():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"patientId": 1, "medicalIdentifierCode": "ABC"},
                {"patientId": 2, "medicalIdentifierCode": "DEF"},
            ]
        )
    )
    spec = SearchSpec(multi_match="skip")
    with _client() as c, pytest.raises(MultiMatch):
        patients.resolve(c, "query", spec)


@respx.mock
def test_multi_match_first_returns_first():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"patientId": 10, "medicalIdentifierCode": "FIRST"},
                {"patientId": 20, "medicalIdentifierCode": "SECOND"},
            ]
        )
    )
    spec = SearchSpec(multi_match="first")
    with _client() as c:
        r = patients.resolve(c, "query", spec)
    assert r.patient_id == 10


# ---------------------------------------------------------------------------
# patientId == 0 regression
# ---------------------------------------------------------------------------


@respx.mock
def test_patient_id_zero_resolves_correctly():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"patientId": 0, "medicalIdentifierCode": "ZERO_ID"},
            ]
        )
    )
    with _client() as c:
        r = patients.resolve(c, "ZERO_ID", SearchSpec())
    assert r.patient_id == 0


@respx.mock
def test_patient_id_missing_falls_back_to_id_field():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"id": 77, "medicalIdentifierCode": "MIC"},
            ]
        )
    )
    with _client() as c:
        r = patients.resolve(c, "MIC", SearchSpec())
    assert r.patient_id == 77


@respx.mock
def test_patient_id_and_id_both_missing_raises():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"medicalIdentifierCode": "MIC"},
            ]
        )
    )
    with _client() as c, pytest.raises(PatientNotFound, match="no patientId"):
        patients.resolve(c, "MIC", SearchSpec())


# ---------------------------------------------------------------------------
# _find_patient_list response shapes
# ---------------------------------------------------------------------------


def _list_from_response(data) -> list:
    return patients._find_patient_list(data)


def test_find_patient_list_bare_list():
    data = [{"patientId": 1}, {"patientId": 2}]
    assert len(_list_from_response(data)) == 2


def test_find_patient_list_items_key():
    data = {"data": {"items": [{"patientId": 1}]}}
    result = _list_from_response(data)
    assert len(result) == 1
    assert result[0]["patientId"] == 1


def test_find_patient_list_nested_content():
    data = {"data": {"content": [{"patientId": 5}]}}
    result = _list_from_response(data)
    assert result[0]["patientId"] == 5


def test_find_patient_list_unknown_shape_returns_empty():
    data = {"something_else": "nope"}
    assert _list_from_response(data) == []


def test_find_patient_list_non_dict_entries_filtered():
    data = [{"patientId": 1}, "not a dict", 42]
    result = _list_from_response(data)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# fullname fallback
# ---------------------------------------------------------------------------


@respx.mock
def test_fullname_fallback_to_fullName():
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=_resp(
            [
                {"patientId": 5, "medicalIdentifierCode": "MIC", "fullName": "Nguyen Van A"},
            ]
        )
    )
    with _client() as c:
        r = patients.resolve(c, "MIC", SearchSpec())
    assert r.fullname == "Nguyen Van A"
