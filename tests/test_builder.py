from __future__ import annotations

from hssk.auth.profile import ProfileData
from hssk.excel.coerce import coerce_row
from hssk.payload import builder, templates


def test_build_payload_shape(mapping):
    raw = {
        "Mã định danh": "2700020596A",
        "Mạch": 80,
        "Nhiệt độ": 36.8,
        "Cân nặng": 18,
        "Chiều cao": 140,
        **_REQUIRED,
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
    # healthfacilitiesId: no profile passed → stays None (template default)
    assert info["healthfacilitiesId"] is None
    # doctorName comes from per-row "Bác sĩ" column
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


_REQUIRED = {
    "Ngày khám": "17/06/2026",
    "Giờ kết thúc": "17/06/2026",
    "Mã hình thức khám": 100,
    "Mã đối tượng khám": 93,
    "Chẩn đoán": "0000 - Bình thường",
    "Mã kết quả khám": 3,
    "Mã tình trạng ra viện": 1,
    "Bác sĩ": "Nguyễn Thị Hoa",
}


def test_organ_desc_and_clinical_fields_routed(mapping):
    raw = {
        "Mã định danh": "2700020596A",
        "Cân nặng": 60,
        "Chiều cao": 170,
        "Tim mạch": "Nhịp tim đều",
        "Chẩn đoán": "J00 - Cảm lạnh",
        "Bác sĩ": "Trần Văn An",
        "Mã kết quả khám": 2,
        **{
            k: v
            for k, v in _REQUIRED.items()
            if k not in ("Chẩn đoán", "Bác sĩ", "Mã kết quả khám")
        },
    }
    row = coerce_row(raw, mapping, row_index=2)
    assert row.ok, row.errors
    payload = builder.build(row, mapping, patient_id=1)
    info = payload["medicalRecordInfo"]

    assert info["heartDesc"] == "Nhịp tim đều"
    assert info["diagnosesDischarge"] == "J00 - Cảm lạnh"
    assert info["doctorName"] == "Trần Văn An"
    assert info["treatmentResultId"] == 2


def test_diagnoses_list_mirrored_from_discharge(mapping):
    raw = {"Mã định danh": "X", **_REQUIRED}
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=1)
    info = payload["medicalRecordInfo"]
    assert info["diagnosesDischargeList"] == ["0000 - Bình thường"]


def test_explicit_diagnoses_list_not_overridden(mapping):
    raw = {
        "Mã định danh": "X",
        **_REQUIRED,
        "Bệnh kèm theo": "0000 - Bình thường; J00 - Cảm lạnh",
    }
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=1)
    info = payload["medicalRecordInfo"]
    assert info["diagnosesDischargeList"] == ["0000 - Bình thường", "J00 - Cảm lạnh"]


_PROFILE = ProfileData(
    display_name="Trạm y tế Liên Bão",
    username="bnh_27084_lienbao",
    healthfacilities_id="27084",
    captured_at=0.0,
)

# Row with no "Bác sĩ" column (doctorName absent from row values)
_REQUIRED_NO_DOCTOR = {k: v for k, v in _REQUIRED.items() if k != "Bác sĩ"}


def test_profile_fills_empty_doctor_and_facility(mapping):
    """Profile values are used when row and mapping defaults are both absent."""
    raw = {"Mã định danh": "X", **_REQUIRED_NO_DOCTOR}
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=1, profile=_PROFILE)
    info = payload["medicalRecordInfo"]
    assert info["doctorName"] == "Trạm y tế Liên Bão"
    assert info["healthfacilitiesId"] == "27084"


def test_per_row_value_wins_over_profile(mapping):
    """An explicit per-row doctor name overrides the profile."""
    raw = {"Mã định danh": "X", **_REQUIRED, "Bác sĩ": "Trần Văn An"}
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=1, profile=_PROFILE)
    assert payload["medicalRecordInfo"]["doctorName"] == "Trần Văn An"


def test_no_profile_leaves_fields_at_template_default(mapping):
    """Without a profile, healthfacilitiesId stays None; doctorName stays blank."""
    raw = {"Mã định danh": "X", **_REQUIRED_NO_DOCTOR}
    row = coerce_row(raw, mapping, row_index=2)
    payload = builder.build(row, mapping, patient_id=1, profile=None)
    info = payload["medicalRecordInfo"]
    assert info["healthfacilitiesId"] is None
    assert info["doctorName"] == ""
