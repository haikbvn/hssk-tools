"""Fetch and update an existing medical-record detail."""

from __future__ import annotations

from typing import Any

from .client import ApiClient

DETAIL_PATH = "/api/v1/medical-record/medical-record/health-examination/get-detail"

UPDATE_PATH = "/api/v1/medical-record/medical-record/health-examination/update"


def _extract_record_id(data: Any) -> Any:
    if isinstance(data, dict):
        for key in ("medicalRecordId", "id", "recordId"):
            if data.get(key) is not None:
                return data[key]
        inner = data.get("data")
        if isinstance(inner, dict):
            return _extract_record_id(inner)
        if inner is not None and not isinstance(inner, (list, dict)):
            return inner
    return None


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
    return _extract_record_id(data), data
