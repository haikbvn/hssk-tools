"""Build the update payload by reusing the create builder and stamping the record ID."""

from __future__ import annotations

from typing import Any

from ..auth.profile import ProfileData
from ..excel.coerce import RowResult
from ..mapping import MappingConfig
from . import builder


def build_update(
    row: RowResult,
    mapping: MappingConfig,
    patient_id: Any,
    *,
    medical_record_id: Any,
    medical_identifier_code: str | None = None,
    profile: ProfileData | None = None,
) -> dict[str, Any]:
    """Build the health-examination update payload for one patient.

    The update endpoint uses the same flat body shape as create, differing only by
    a populated ``medicalRecordId``, an added ``concludesDisease`` key, and two
    empty ``deleted*`` lists required by the server.
    """
    payload = builder.build(
        row,
        mapping,
        patient_id,
        medical_identifier_code=medical_identifier_code,
        profile=profile,
    )
    rec = payload["medicalRecordInfo"]
    rec["medicalRecordId"] = medical_record_id
    rec.setdefault("concludesDisease", None)
    payload["deletedServiceIds"] = []
    payload["deletedDrugIds"] = []
    return payload
