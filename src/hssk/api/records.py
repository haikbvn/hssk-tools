"""Fetch and update an existing medical-record detail."""

from __future__ import annotations

from typing import Any

from .adapters import extract_patient_ref, extract_record_id
from .client import ApiClient

DETAIL_PATH = "/api/v1/medical-record/medical-record/health-examination/get-detail"

UPDATE_PATH = "/api/v1/medical-record/medical-record/health-examination/update"

DELETE_PATH = "/api/v1/medical-record/medical-record/medical-record-object-information/delete"

# Response probing lives in api/adapters.py; re-exported so callers keep ``records.extract_*``.
__all__ = [
    "DELETE_PATH",
    "DETAIL_PATH",
    "UPDATE_PATH",
    "delete",
    "extract_patient_ref",
    "extract_record_id",
    "fetch_detail",
    "update",
]


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
