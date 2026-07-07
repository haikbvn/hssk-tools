"""Pydantic schema for the create-request body — a validation *gate*, not a serializer.

The wire payload is still the hand-built dict assembled by :mod:`.builder` (template ⊕ mapping
defaults ⊕ coerced row values). These models exist only to **reject** a malformed payload before it
is sent: :func:`.builder.validate_payload` runs ``CreateExamPayload.model_validate(payload)`` and,
on failure, the runner turns that row into a clean ``INVALID`` outcome instead of a silent bad send.
The validated dict is sent **unchanged** — we never ``model_dump()`` back, so the bytes on the wire
are byte-identical to before this gate existed.

The real value is ``extra="forbid"``: it catches keys that no template field owns — most importantly
a typo in ``mapping.yaml``'s ``defaults`` blocks (otherwise unvalidated ``dict[str, Any]``) and a
server/payload shape that has drifted. Field *value* types are deliberately permissive:
coercion legitimately yields strings for numeric cells (``str_num`` → ``"18"`` / ``"9.18"``), so
value-level strictness would reject valid payloads for near-zero benefit.

The field lists here are transcribed from :mod:`.templates` (still the single source of *defaults*).
``tests/test_payload_models.py`` pins ``model_fields`` ≡ the template dict keys so the two
transcriptions can never drift apart.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Permissive value-type aliases (see module docstring — the gate's value is key-forbidding, not
# value strictness). Coercion may produce a str for a numeric cell, so numerics accept str too.
Text = str | None
IdCode = str | int | None
Numeric = str | int | float | None


class MedicalRecordInfo(BaseModel):
    """The ``medicalRecordInfo`` sub-object (60 fields, transcribed from
    ``templates.record_info_template``)."""

    model_config = ConfigDict(extra="forbid")

    # -- identifiers / examination framing (11) --
    medicalRecordId: IdCode = None
    patientId: IdCode = None
    medicalIdentifierCode: IdCode = None
    examinationDate: Text = None
    finishExaminationDate: Text = None
    treatmentDayNumber: IdCode = None
    typeOfExamination: IdCode = None
    reasonCode: IdCode = None
    healthfacilitiesArriveId: IdCode = None
    reasonsMedicalexamination: Text = None
    symptoms: Text = None

    # -- organ/system descriptions (20 DESC_FIELDS) --
    bodySkinDesc: Text = None
    bodyOtherDesc: Text = None
    heartDesc: Text = None
    respiratoryDesc: Text = None
    digestDesc: Text = None
    urologyDesc: Text = None
    nerveDesc: Text = None
    osteoarthritisDesc: Text = None
    endocrineDesc: Text = None
    bloodDesc: Text = None
    surgeryDesc: Text = None
    maternityDesc: Text = None
    earNoseThroatDesc: Text = None
    toothDesc: Text = None
    eyeDesc: Text = None
    dermatologyDesc: Text = None
    nutritionDesc: Text = None
    motionDesc: Text = None
    physicalDesc: Text = None
    organsOtherDesc: Text = None

    # -- diagnosis / treatment / facility (8) --
    diagnosesDischarge: Text = None
    diagnosesDischargeList: list[str] = Field(default_factory=list)
    noteDisease: Text = None
    treatmentDirection: Text = None
    treatmentResultId: IdCode = None
    dischargeStatusId: IdCode = None
    healthfacilitiesId: IdCode = None
    doctorName: Text = None

    # -- cost fields (21 MONEY_FIELDS) --
    testMoney: Numeric = None
    radiologyMoney: Numeric = None
    funcExplorationMoney: Numeric = None
    drugMoney: Numeric = None
    bloodMoney: Numeric = None
    bloodProductMoney: Numeric = None
    surgeryMoney: Numeric = None
    tricksMoney: Numeric = None
    materialMoney: Numeric = None
    transferMoney: Numeric = None
    examinalMoney: Numeric = None
    bedOutMoney: Numeric = None
    bedInMoney: Numeric = None
    bedTemporaryMoney: Numeric = None
    externalCapacityMoney: Numeric = None
    otherSoucesMoney: Numeric = None
    totalMoney: Numeric = None
    totalMoneyInsurance: Numeric = None
    insuranceMoney: Numeric = None
    patientMoney: Numeric = None
    patientPayTogetherMoney: Numeric = None


class MedicalPatientDetailInfo(BaseModel):
    """The ``medicalPatientDetailInfo`` sub-object (15 fields, transcribed from
    ``templates.patient_detail_template``)."""

    model_config = ConfigDict(extra="forbid")

    patientDetailId: IdCode = None
    pulse: Numeric = None
    temperature: Numeric = None
    bloodPressureMax: Numeric = None
    bloodPressureMin: Numeric = None
    breath: Numeric = None
    weight: Numeric = None
    height: Numeric = None
    bmi: Numeric = None
    waistCircumference: Numeric = None
    chestCircumference: Numeric = None
    leftEyeGlasses: Numeric = None
    leftEyeNoGlasses: Numeric = None
    rightEyeGlasses: Numeric = None
    rightEyeNoGlasses: Numeric = None


class CreateExamPayload(BaseModel):
    """The full create-request body. ``extra="forbid"`` also at the top level, so an unexpected
    top-level key (drift, a stray default) is rejected. Update-mode's extra keys
    (``deletedServiceIds`` / ``deletedDrugIds`` / ``concludesDisease``) are stamped by
    ``update_builder`` *after* this gate runs, so they are intentionally not modelled here."""

    model_config = ConfigDict(extra="forbid")

    medicalRecordInfo: MedicalRecordInfo
    medicalPatientDetailInfo: MedicalPatientDetailInfo
    serviceList: list[Any] = Field(default_factory=list)
    drugList: list[Any] = Field(default_factory=list)
