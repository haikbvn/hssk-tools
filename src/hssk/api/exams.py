"""Create a health-examination record."""

from __future__ import annotations

from typing import Any

from .client import ApiClient
from .record_id import extract_record_id

CREATE_PATH = "/api/v1/medical-record/medical-record/health-examination/create"


def create(client: ApiClient, payload: dict[str, Any]) -> tuple[Any, Any]:
    """POST the create payload. Returns ``(record_id_or_None, raw_response)``."""
    data = client.post(CREATE_PATH, payload)
    return extract_record_id(data), data
