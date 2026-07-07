"""Assemble the create payload from a coerced row, mapping defaults, and the resolved patientId."""

from __future__ import annotations

import copy
from typing import Any

from pydantic import ValidationError

from ..auth.profile import ProfileData
from ..errors import PayloadInvalid
from ..events import MessageCode, Msg
from ..excel.coerce import RowResult
from ..mapping import MappingConfig
from . import templates
from .models import CreateExamPayload


def validate_targets(mapping: MappingConfig) -> list[str]:
    """Return any mapped ``target`` names that aren't real API fields."""
    return [
        spec.target for spec in mapping.columns.values() if spec.target not in templates.ALL_TARGETS
    ]


def _format_errors(exc: ValidationError) -> str:
    """One-line summary of a payload ValidationError from ``loc`` + ``msg`` only.

    Deliberately omits pydantic's ``input`` field so patient cell values are never dumped into the
    (report-persisted, UI-shown) detail text.
    """
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    extra = len(exc.errors()) - 5
    if extra > 0:
        parts.append(f"(+{extra} more)")
    return "; ".join(parts)


def validate_payload(payload: dict[str, Any]) -> None:
    """Gate the assembled payload through the pydantic schema (validate-only, never serialize back).

    Raises :class:`PayloadInvalid` (carrying a typed ``Msg``) when the payload has an unknown field
    or wrong shape — most usefully a typo in ``mapping.yaml``'s otherwise-unvalidated ``defaults``
    blocks, or a drifted payload shape. The payload dict itself is left untouched and sent as-is.
    """
    try:
        CreateExamPayload.model_validate(payload)
    except ValidationError as exc:
        detail = _format_errors(exc)
        raise PayloadInvalid(
            f"payload failed validation: {detail}",
            msg=Msg(MessageCode.ROW_PAYLOAD_INVALID, detail=detail),
        ) from exc


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

    # Final gate: reject an unknown field / bad shape before it can be sent. Runs in dry-run too,
    # so a malformed payload surfaces as INVALID before any commit. Sends the dict unchanged.
    validate_payload(payload)

    return payload
