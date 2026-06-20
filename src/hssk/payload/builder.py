"""Assemble the create payload from a coerced row, mapping defaults, and the resolved patientId."""

from __future__ import annotations

import copy
from typing import Any

from ..auth.profile import ProfileData
from ..excel.coerce import RowResult
from ..mapping import MappingConfig
from . import templates


def validate_targets(mapping: MappingConfig) -> list[str]:
    """Return any mapped ``target`` names that aren't real API fields."""
    return [
        spec.target for spec in mapping.columns.values() if spec.target not in templates.ALL_TARGETS
    ]


def prepare_base(mapping: MappingConfig) -> dict[str, Any]:
    """Build the merged payload base once per run (constant across all rows).

    Layers the mapping's constant defaults on top of the canonical template. The result is
    deep-copied per row inside ``build()`` so each row gets an independent payload.
    """
    base = templates.default_payload(normal=mapping.defaults.normal_desc_value)
    base["medicalRecordInfo"] = templates.deep_merge(
        base["medicalRecordInfo"], mapping.defaults.medicalRecordInfo
    )
    base["medicalPatientDetailInfo"] = templates.deep_merge(
        base["medicalPatientDetailInfo"], mapping.defaults.medicalPatientDetailInfo
    )
    return base


def build(
    row: RowResult,
    base: dict[str, Any],
    patient_id: Any,
    *,
    medical_identifier_code: str | None = None,
    profile: ProfileData | None = None,
) -> dict[str, Any]:
    """Build the full health-examination create payload for one patient.

    ``base`` is the pre-merged template returned by ``prepare_base()`` — call it once per run
    and pass the same dict here for every row.

    ``medical_identifier_code`` (the patient's real code, from the search result) overrides whatever
    the Excel "identifier" column held, since the searched value may be a CCCD/phone/insurance no.
    """
    payload = copy.deepcopy(base)

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

    # healthfacilitiesId is always locked to the logged-in account's facility.
    # doctorName uses the profile as last-resort fallback only.
    if profile is not None:
        if profile.healthfacilities_id:
            record["healthfacilitiesId"] = profile.healthfacilities_id
        if not record.get("doctorName") and profile.display_name:
            record["doctorName"] = profile.display_name

    return payload
