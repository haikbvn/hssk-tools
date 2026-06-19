from __future__ import annotations

from pathlib import Path

from hssk.excel.coerce import RowResult
from hssk.mapping import load_mapping
from hssk.payload.update_builder import build_update

REPO_ROOT = Path(__file__).resolve().parents[1]


def _mapping():
    return load_mapping(REPO_ROOT / "config" / "mapping.example.yaml")


def _make_row(values: dict) -> RowResult:
    r = RowResult(row_index=2)
    r.values.update(values)
    return r


def test_flat_body_shape():
    payload = build_update(_make_row({}), _mapping(), patient_id=99, medical_record_id=1)
    assert "medicalRecordInfo" in payload
    assert "medicalPatientDetailInfo" in payload
    assert "serviceList" in payload
    assert "drugList" in payload
    assert "deletedServiceIds" in payload
    assert "deletedDrugIds" in payload


def test_medical_record_id_is_stamped():
    payload = build_update(_make_row({}), _mapping(), patient_id=99, medical_record_id=443150673)
    assert payload["medicalRecordInfo"]["medicalRecordId"] == 443150673


def test_concludes_disease_key_present():
    payload = build_update(_make_row({}), _mapping(), patient_id=99, medical_record_id=1)
    assert "concludesDisease" in payload["medicalRecordInfo"]


def test_deleted_arrays_empty():
    payload = build_update(_make_row({}), _mapping(), patient_id=99, medical_record_id=1)
    assert payload["deletedServiceIds"] == []
    assert payload["deletedDrugIds"] == []


def test_vitals_land_in_patient_detail():
    row = _make_row({"pulse": 75, "temperature": 37.2, "weight": 65})
    payload = build_update(row, _mapping(), patient_id=99, medical_record_id=1)
    detail = payload["medicalPatientDetailInfo"]
    assert detail["pulse"] == 75
    assert detail["temperature"] == 37.2
    assert detail["weight"] == 65


def test_organ_descs_land_in_record_info():
    row = _make_row({"heartDesc": "Nhịp đều, rõ", "respiratoryDesc": "Thở đều"})
    payload = build_update(row, _mapping(), patient_id=99, medical_record_id=1)
    rec = payload["medicalRecordInfo"]
    assert rec["heartDesc"] == "Nhịp đều, rõ"
    assert rec["respiratoryDesc"] == "Thở đều"


def test_patient_id_and_mic_are_set():
    payload = build_update(
        _make_row({}),
        _mapping(),
        patient_id=364613676,
        medical_record_id=1,
        medical_identifier_code="2721718830",
    )
    rec = payload["medicalRecordInfo"]
    assert rec["patientId"] == 364613676
    assert rec["medicalIdentifierCode"] == "2721718830"


def test_profile_locks_facility_id():
    from hssk.auth.profile import ProfileData

    profile = ProfileData(
        display_name="Test",
        username="bnh_99999_test",
        healthfacilities_id="99999",
        captured_at=0.0,
    )
    payload = build_update(
        _make_row({}), _mapping(), patient_id=99, medical_record_id=1, profile=profile
    )
    assert payload["medicalRecordInfo"]["healthfacilitiesId"] == "99999"
