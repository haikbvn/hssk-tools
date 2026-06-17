from __future__ import annotations

from hssk.excel.coerce import coerce_row
from hssk.payload import builder, templates


def test_build_payload_shape(mapping):
    raw = {
        "Mã định danh": "2700020596A",
        "Mạch": 80,
        "Nhiệt độ": 36.8,
        "Cân nặng": 18,
        "Chiều cao": 140,
    }
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=372954970)

    info = payload["medicalRecordInfo"]
    detail = payload["medicalPatientDetailInfo"]

    # patientId + identifier injected
    assert info["patientId"] == 372954970
    assert info["medicalIdentifierCode"] == "2700020596A"

    # constants from template + mapping defaults
    assert info["typeOfExamination"] == 100
    assert info["healthfacilitiesId"] == "27084"
    assert info["doctorName"] == "Nguyễn Thị Hoa"

    # every *Desc fanned out to normal
    for f in templates.DESC_FIELDS:
        assert info[f] == "Bình thường"

    # money stays null
    for f in templates.MONEY_FIELDS:
        assert info[f] is None

    # vitals routed into the detail sub-object
    assert detail["pulse"] == 80
    assert detail["temperature"] == 36.8
    assert detail["weight"] == "18"
    assert detail["bmi"] == "9.18"

    assert payload["serviceList"] == []
    assert payload["drugList"] == []


def test_validate_targets_clean(mapping):
    assert builder.validate_targets(mapping) == []
