"""Pull the record id out of a create/update response (shape is undocumented, so probe)."""

from __future__ import annotations

from typing import Any


def extract_record_id(data: Any) -> Any:
    if isinstance(data, dict):
        for key in ("medicalRecordId", "id", "recordId"):
            if data.get(key) is not None:
                return data[key]
        inner = data.get("data")
        if isinstance(inner, dict):
            return extract_record_id(inner)
        if inner is not None and not isinstance(inner, (list, dict)):
            return inner
    return None
