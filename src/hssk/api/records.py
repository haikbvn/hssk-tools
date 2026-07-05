"""Fetch and update an existing medical-record detail."""

from __future__ import annotations

from typing import Any

from .client import ApiClient
from .record_id import extract_record_id

DETAIL_PATH = "/api/v1/medical-record/medical-record/health-examination/get-detail"

UPDATE_PATH = "/api/v1/medical-record/medical-record/health-examination/update"

DELETE_PATH = "/api/v1/medical-record/medical-record/medical-record-object-information/delete"


def extract_patient_ref(detail: Any) -> tuple[Any, str | None]:
    """Extract (patientId, medicalIdentifierCode) from a GET-detail response.

    The response shape is not formally documented so this probes several candidate
    locations — same defensive style as ``_find_patient_list`` in ``api/patients.py``.
    """
    if not isinstance(detail, dict):
        return None, None

    # Unwrap a data envelope if present
    candidate = detail.get("data")
    if isinstance(candidate, dict):
        detail = candidate

    for container_key in ("medicalRecordInfo", "medicalRecords"):
        container = detail.get(container_key)
        if isinstance(container, dict):
            pid = container.get("patientId")
            mic = container.get("medicalIdentifierCode")
            if pid is not None:
                return pid, mic

    # Flat top-level fallback
    pid = detail.get("patientId")
    mic = detail.get("medicalIdentifierCode")
    return pid, mic


def fetch_detail(client: ApiClient, medical_record_id: Any) -> dict[str, Any]:
    """GET the full record structure for an existing medical record."""
    data = client.get(f"{DETAIL_PATH}/{medical_record_id}")
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        if isinstance(inner, dict):
            return inner
    return data if isinstance(data, dict) else {}


def update(client: ApiClient, payload: dict[str, Any]) -> tuple[Any, Any]:
    """POST the update payload. Returns ``(record_id_or_None, raw_response)``."""
    data = client.post(UPDATE_PATH, payload)
    return extract_record_id(data), data


def delete(client: ApiClient, medical_record_id: Any) -> tuple[Any, Any]:
    """POST the empty-body delete for one record. Returns ``(medical_record_id, raw_response)``.

    The endpoint carries the id in the path and takes no body (``json=None`` → httpx sends no
    content, matching the website's ``content-length: 0`` request). We return the known id as the
    record id so the results table stays populated and ``_run_batch`` never warns about a missing
    id in the response.
    """
    data = client.post(f"{DELETE_PATH}/{medical_record_id}", None)
    return medical_record_id, data
