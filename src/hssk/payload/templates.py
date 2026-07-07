"""The canonical health-examination create payload.

This is the single source of truth for the request body shape and its constant default values
(mirrors the sample payload). ``mapping.yaml``'s ``defaults`` block is deep-merged on top, and
per-row Excel values + the resolved ``patientId`` are injected last.
"""

from __future__ import annotations

import copy
from typing import Any

from .models import MedicalPatientDetailInfo, MedicalRecordInfo

NORMAL = "Bình thường"

# Organ/system description fields — all default to "Bình thường" (normal).
DESC_FIELDS: tuple[str, ...] = (
    "bodySkinDesc",
    "bodyOtherDesc",
    "heartDesc",
    "respiratoryDesc",
    "digestDesc",
    "urologyDesc",
    "nerveDesc",
    "osteoarthritisDesc",
    "endocrineDesc",
    "bloodDesc",
    "surgeryDesc",
    "maternityDesc",
    "earNoseThroatDesc",
    "toothDesc",
    "eyeDesc",
    "dermatologyDesc",
    "nutritionDesc",
    "motionDesc",
    "physicalDesc",
    "organsOtherDesc",
)

# Cost fields — always null for a standard checkup.
MONEY_FIELDS: tuple[str, ...] = (
    "testMoney",
    "radiologyMoney",
    "funcExplorationMoney",
    "drugMoney",
    "bloodMoney",
    "bloodProductMoney",
    "surgeryMoney",
    "tricksMoney",
    "materialMoney",
    "transferMoney",
    "examinalMoney",
    "bedOutMoney",
    "bedInMoney",
    "bedTemporaryMoney",
    "externalCapacityMoney",
    "otherSoucesMoney",
    "totalMoney",
    "totalMoneyInsurance",
    "insuranceMoney",
    "patientMoney",
    "patientPayTogetherMoney",
)


def record_info_template(normal: str = NORMAL) -> dict[str, Any]:
    info: dict[str, Any] = {
        "medicalRecordId": None,
        "patientId": None,
        "medicalIdentifierCode": None,
        "examinationDate": None,
        "finishExaminationDate": None,
        "treatmentDayNumber": "1",
        "typeOfExamination": 100,
        "reasonCode": 93,
        "healthfacilitiesArriveId": None,
        "reasonsMedicalexamination": "Khám sức khoẻ",
        "symptoms": "Không",
    }
    for f in DESC_FIELDS:
        info[f] = normal
    info.update(
        {
            "diagnosesDischarge": "0000 - Bình thường",
            "diagnosesDischargeList": ["0000 - Bình thường"],
            "noteDisease": "Không",
            "treatmentDirection": normal,
            "treatmentResultId": 3,
            "dischargeStatusId": 1,
            "healthfacilitiesId": None,
            "doctorName": None,
        }
    )
    for f in MONEY_FIELDS:
        info[f] = None
    return info


def patient_detail_template() -> dict[str, Any]:
    return {
        "patientDetailId": None,
        "pulse": None,
        "temperature": None,
        "bloodPressureMax": None,
        "bloodPressureMin": None,
        "breath": None,
        "weight": None,
        "height": None,
        "bmi": None,
        "waistCircumference": None,
        "chestCircumference": None,
        "leftEyeGlasses": None,
        "leftEyeNoGlasses": None,
        "rightEyeGlasses": None,
        "rightEyeNoGlasses": None,
    }


def default_payload(normal: str = NORMAL) -> dict[str, Any]:
    return {
        "medicalRecordInfo": record_info_template(normal),
        "medicalPatientDetailInfo": patient_detail_template(),
        "serviceList": [],
        "drugList": [],
    }


# The set of valid mapping targets is derived from the pydantic models (the single source of truth
# for the payload shape), not the template dicts. A typo'd mapping target thus errors against the
# model. ``tests/test_payload_models.py`` pins ``model_fields`` ≡ the template dict keys, so the
# templates (source of default *values*) and the models (source of the *shape*) can never drift.
RECORD_INFO_TARGETS: frozenset[str] = frozenset(MedicalRecordInfo.model_fields)
PATIENT_DETAIL_TARGETS: frozenset[str] = frozenset(MedicalPatientDetailInfo.model_fields)
ALL_TARGETS: frozenset[str] = RECORD_INFO_TARGETS | PATIENT_DETAIL_TARGETS


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict: ``override`` merged onto a deep copy of ``base`` (nested dicts merged)."""
    out = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out
