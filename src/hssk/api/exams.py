"""Create a health-examination record."""

from __future__ import annotations

from typing import Any

from .client import ApiClient

CREATE_PATH = "/api/v1/medical-record/medical-record/health-examination/create"

_ID_KEYS = ("medicalRecordId", "id", "recordId", "data")


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


def create(client: ApiClient, payload: dict[str, Any]) -> tuple[Any, Any]:
    """POST the create payload. Returns ``(record_id_or_None, raw_response)``."""
    data = client.post(CREATE_PATH, payload)
    return _extract_record_id(data), data
