"""The consolidated response adapters (api/adapters.py) + their narrow drift signalling.

Drift must fire *only* when a response is clearly not the expected shape (no place the data could
sit), never on a legitimate empty result — otherwise a normal "no matches" run would false-alarm.
``extract_record_id`` keeps parity with its old home (no drift there).
"""

from __future__ import annotations

import pytest

from hssk.api import adapters

# ---------------------------------------------------------------------------
# find_patient_list — drift signalling
# ---------------------------------------------------------------------------


def test_find_patient_list_drifts_on_unrecognised_dict() -> None:
    hits: list[str] = []
    result = adapters.find_patient_list({"unexpected": "shape"}, on_drift=hits.append)
    assert result == []
    assert len(hits) == 1


def test_find_patient_list_no_drift_on_located_but_empty() -> None:
    hits: list[str] = []
    result = adapters.find_patient_list({"data": {"items": []}}, on_drift=hits.append)
    assert result == []
    assert hits == []  # located the container; it's just empty — a legitimate no-match


def test_find_patient_list_no_drift_on_bare_empty_list() -> None:
    hits: list[str] = []
    assert adapters.find_patient_list([], on_drift=hits.append) == []
    assert hits == []  # a list is the expected top-level shape


def test_find_patient_list_no_drift_on_success() -> None:
    hits: list[str] = []
    result = adapters.find_patient_list(
        {"data": {"items": [{"patientId": 1}]}}, on_drift=hits.append
    )
    assert len(result) == 1
    assert hits == []


def test_find_patient_list_no_drift_without_callback() -> None:
    # Bare probing (the drift-free wrapper used by patients._find_patient_list and its tests).
    assert adapters.find_patient_list({"weird": 1}) == []


# ---------------------------------------------------------------------------
# extract_patient_ref — drift signalling
# ---------------------------------------------------------------------------


def test_extract_patient_ref_drifts_on_unrecognised_detail() -> None:
    hits: list[str] = []
    pid, mic = adapters.extract_patient_ref({"junk": 1, "more": 2}, on_drift=hits.append)
    assert (pid, mic) == (None, None)
    assert len(hits) == 1


def test_extract_patient_ref_no_drift_on_located_null_patient() -> None:
    hits: list[str] = []
    pid, mic = adapters.extract_patient_ref(
        {"medicalRecordInfo": {"patientId": None}}, on_drift=hits.append
    )
    assert pid is None
    assert hits == []  # the record container is present; patientId is just null — not drift


def test_extract_patient_ref_no_drift_on_data_envelope() -> None:
    hits: list[str] = []
    pid, mic = adapters.extract_patient_ref(
        {"data": {"medicalRecordInfo": {"patientId": 7, "medicalIdentifierCode": "M"}}},
        on_drift=hits.append,
    )
    assert (pid, mic) == (7, "M")
    assert hits == []


def test_extract_patient_ref_flat_top_level() -> None:
    hits: list[str] = []
    pid, mic = adapters.extract_patient_ref(
        {"patientId": 9, "medicalIdentifierCode": "X"}, on_drift=hits.append
    )
    assert (pid, mic) == (9, "X")
    assert hits == []


def test_extract_patient_ref_no_drift_on_empty() -> None:
    hits: list[str] = []
    assert adapters.extract_patient_ref({}, on_drift=hits.append) == (None, None)
    assert adapters.extract_patient_ref(None, on_drift=hits.append) == (None, None)
    assert hits == []  # an empty/None response is not treated as drift (could be a genuine miss)


# ---------------------------------------------------------------------------
# extract_record_id — parity with the old record_id.py (no drift)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["medicalRecordId", "id", "recordId"])
def test_extract_record_id_direct_key(key: str) -> None:
    assert adapters.extract_record_id({key: 555}) == 555


def test_extract_record_id_nested_and_scalar() -> None:
    assert adapters.extract_record_id({"data": {"medicalRecordId": 7}}) == 7
    assert adapters.extract_record_id({"data": 42}) == 42
    assert adapters.extract_record_id({"id": 0}) == 0


@pytest.mark.parametrize("data", [None, "x", 5, [1, 2], {}, {"data": None}, {"other": 1}])
def test_extract_record_id_unrecognised_return_none(data: object) -> None:
    assert adapters.extract_record_id(data) is None
