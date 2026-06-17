"""Assemble the create payload from a coerced row, mapping defaults, and the resolved patientId."""

from __future__ import annotations

from typing import Any

from ..excel.coerce import RowResult
from ..mapping import MappingConfig
from . import templates


def validate_targets(mapping: MappingConfig) -> list[str]:
    """Return any mapped ``target`` names that aren't real API fields."""
    return [
        spec.target for spec in mapping.columns.values() if spec.target not in templates.ALL_TARGETS
    ]


def build(
    row: RowResult,
    mapping: MappingConfig,
    patient_id: Any,
    *,
    medical_identifier_code: str | None = None,
) -> dict[str, Any]:
    """Build the full health-examination create payload for one patient.

    ``medical_identifier_code`` (the patient's real code, from the search result) overrides whatever
    the Excel "identifier" column held, since the searched value may be a CCCD/phone/insurance no.
    """
    payload = templates.default_payload(normal=mapping.defaults.normal_desc_value)

    # Layer constant defaults from the mapping on top of the canonical template.
    payload["medicalRecordInfo"] = templates.deep_merge(
        payload["medicalRecordInfo"], mapping.defaults.medicalRecordInfo
    )
    payload["medicalPatientDetailInfo"] = templates.deep_merge(
        payload["medicalPatientDetailInfo"], mapping.defaults.medicalPatientDetailInfo
    )

    record = payload["medicalRecordInfo"]
    detail = payload["medicalPatientDetailInfo"]

    # Inject per-row values into the correct sub-object.
    for target, value in row.values.items():
        if target in templates.PATIENT_DETAIL_TARGETS:
            detail[target] = value
        elif target in templates.RECORD_INFO_TARGETS:
            record[target] = value
        # unknown targets are ignored (validate_targets surfaces them up front)

    record["patientId"] = patient_id
    if medical_identifier_code is not None:
        record["medicalIdentifierCode"] = medical_identifier_code

    # Mirror diagnosesDischarge into the list field when the list was not explicitly provided.
    if "diagnosesDischarge" in row.values and "diagnosesDischargeList" not in row.values:
        record["diagnosesDischargeList"] = [record["diagnosesDischarge"]]

    return payload
