"""The pydantic payload gate (payload/models.py + builder.validate_payload).

Two guarantees: (1) the models stay a faithful transcription of the templates — their
``model_fields`` must equal the template dict keys, both directions, so the shape and the defaults
(templates) can never silently drift; (2) the gate accepts every payload the builder produces today
and rejects an unknown field (the real new coverage — mapping ``defaults`` blocks are otherwise
unvalidated).
"""

from __future__ import annotations

import pytest

from hssk.errors import PayloadInvalid
from hssk.events import MessageCode
from hssk.payload import builder, templates
from hssk.payload.models import MedicalPatientDetailInfo, MedicalRecordInfo
from hssk.payload.templates import default_payload


def test_record_model_fields_equal_template_keys() -> None:
    assert set(MedicalRecordInfo.model_fields) == set(templates.record_info_template())


def test_detail_model_fields_equal_template_keys() -> None:
    assert set(MedicalPatientDetailInfo.model_fields) == set(templates.patient_detail_template())


def test_field_counts() -> None:
    # Guards against an accidental add/drop when the payload shape is next touched.
    assert len(MedicalRecordInfo.model_fields) == 60
    assert len(MedicalPatientDetailInfo.model_fields) == 15


def test_targets_derive_from_models() -> None:
    assert templates.RECORD_INFO_TARGETS == frozenset(MedicalRecordInfo.model_fields)
    assert templates.PATIENT_DETAIL_TARGETS == frozenset(MedicalPatientDetailInfo.model_fields)


def test_gate_accepts_default_payload() -> None:
    builder.validate_payload(default_payload())  # must not raise


def test_gate_accepts_populated_payload() -> None:
    payload = default_payload()
    payload["medicalRecordInfo"]["patientId"] = 372954970
    payload["medicalRecordInfo"]["medicalIdentifierCode"] = "2700020596A"
    payload["medicalPatientDetailInfo"]["pulse"] = 80
    payload["medicalPatientDetailInfo"]["weight"] = "18"  # str_num coercion output
    payload["medicalPatientDetailInfo"]["bmi"] = "9.18"
    builder.validate_payload(payload)  # permissive value types accept coerced strings


def test_gate_rejects_unknown_record_field() -> None:
    payload = default_payload()
    payload["medicalRecordInfo"]["symptomss"] = "typo"  # the classic unvalidated-defaults typo
    with pytest.raises(PayloadInvalid) as ei:
        builder.validate_payload(payload)
    assert ei.value.msg is not None
    assert ei.value.msg.code == MessageCode.ROW_PAYLOAD_INVALID
    assert "symptomss" in (ei.value.msg.detail or "")


def test_gate_rejects_unknown_detail_field() -> None:
    payload = default_payload()
    payload["medicalPatientDetailInfo"]["pluse"] = 80  # typo for pulse
    with pytest.raises(PayloadInvalid):
        builder.validate_payload(payload)


def test_gate_rejects_unknown_top_level_key() -> None:
    payload = default_payload()
    payload["surprise"] = 1
    with pytest.raises(PayloadInvalid):
        builder.validate_payload(payload)


def test_gate_detail_omits_input_value() -> None:
    # The detail must be built from loc+msg only — never dump the (potentially PII) input value.
    payload = default_payload()
    payload["medicalRecordInfo"]["secret_patient_note"] = "Nguyễn Văn A — HIV+"
    with pytest.raises(PayloadInvalid) as ei:
        builder.validate_payload(payload)
    detail = ei.value.msg.detail or ""
    assert "secret_patient_note" in detail  # the field name is fine
    assert "HIV" not in detail  # the value must not leak into the detail


def test_gate_validate_only_does_not_mutate_payload() -> None:
    # The gate validates; it must not serialize the model back over the dict (wire bytes unchanged).
    import copy

    payload = default_payload()
    snapshot = copy.deepcopy(payload)
    builder.validate_payload(payload)
    assert payload == snapshot
