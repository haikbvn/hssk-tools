"""Tolerant adapters for the site's undocumented response shapes — the one home for JSON probing.

The internal API's response envelopes are not documented, so we defensively probe several candidate
locations for the data we need (a patient list, a patient ref, a record id). This module is the
single place that probing lives; ``patients.py`` / ``records.py`` / ``record_id.py`` re-export from
here so existing call sites and tests keep working.

Two of the three adapters take an optional ``on_drift`` callback. It fires **only** when a response
is clearly not the shape we expect — a non-empty object in which we cannot even *locate* where the
data would sit. A located-but-empty result (``{"data": {"items": []}}``, a record with a null
``patientId``) is a legitimate empty/miss and is **not** drift, so a normal "no matches" run never
raises a false alarm. The runner turns a drift signal into a one-per-endpoint warning the GUI shows
as a "server response not recognised — dry-run first" banner.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

OnDrift = Callable[[str], None]

# Keys under which a patient list may appear (search response).
_LIST_KEYS = ("items", "content", "records", "rows", "list", "data")
# Envelope keys the search response may nest its body under.
_ENVELOPE_KEYS = ("data", "result", "response", "body")
# Keys under which a record's patient ref may appear (get-detail response).
_REF_CONTAINER_KEYS = ("medicalRecordInfo", "medicalRecords")


# ---------------------------------------------------------------------------
# patient search list
# ---------------------------------------------------------------------------


def _find_patient_list(data: Any) -> list[dict[str, Any]]:
    """Walk the response and return the first list of dicts that look like patient records."""
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list) and any(isinstance(x, dict) for x in val):
                return [x for x in val if isinstance(x, dict)]
        for key in _ENVELOPE_KEYS:
            if key in data:
                found = _find_patient_list(data[key])
                if found:
                    return found
        for val in data.values():
            if isinstance(val, list) and any(isinstance(x, dict) and "patientId" in x for x in val):
                return [x for x in val if isinstance(x, dict)]
    return []


def _search_shape_unrecognised(data: Any) -> bool:
    """True only for a non-empty dict that shares no key with the places a patient list can live.

    Conservative on purpose: a top-level list (even empty) is the expected shape, and a dict that
    carries a known list/envelope key is "located but empty" — neither is drift.
    """
    if not isinstance(data, dict) or not data:
        return False
    known = set(_LIST_KEYS) | set(_ENVELOPE_KEYS)
    return not (known & set(data))


def find_patient_list(data: Any, *, on_drift: OnDrift | None = None) -> list[dict[str, Any]]:
    """Patient records from a search response; signal drift on a clearly-unrecognised shape."""
    result = _find_patient_list(data)
    if not result and on_drift is not None and _search_shape_unrecognised(data):
        on_drift(f"patient search: unexpected top-level keys {sorted(map(str, data))[:8]}")
    return result


# ---------------------------------------------------------------------------
# patient ref from a get-detail response
# ---------------------------------------------------------------------------


def _extract_patient_ref(detail: Any) -> tuple[Any, str | None]:
    if not isinstance(detail, dict):
        return None, None

    # Unwrap a data envelope if present
    candidate = detail.get("data")
    if isinstance(candidate, dict):
        detail = candidate

    for container_key in _REF_CONTAINER_KEYS:
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


def _detail_shape_unrecognised(detail: Any) -> bool:
    """True only for a non-empty (unwrapped) detail dict with no place a patient ref could sit."""
    if not isinstance(detail, dict) or not detail:
        return False
    candidate = detail.get("data")
    unwrapped = candidate if isinstance(candidate, dict) else detail
    keys = set(unwrapped)
    return not (keys & set(_REF_CONTAINER_KEYS)) and "patientId" not in keys


def extract_patient_ref(detail: Any, *, on_drift: OnDrift | None = None) -> tuple[Any, str | None]:
    """Extract ``(patientId, medicalIdentifierCode)`` from a get-detail response.

    Signals drift only when the response has no container and no top-level ``patientId`` — i.e. we
    could not locate the ref at all (a located record with a null ``patientId`` is not drift).
    """
    pid, mic = _extract_patient_ref(detail)
    if pid is None and on_drift is not None and _detail_shape_unrecognised(detail):
        on_drift(f"record detail: unexpected keys {sorted(map(str, detail))[:8]}")
    return pid, mic


# ---------------------------------------------------------------------------
# record id from a create/update response
# ---------------------------------------------------------------------------


def extract_record_id(data: Any) -> Any:
    """Pull the record id out of a create/update response (shape undocumented, so probe).

    No ``on_drift``: a missing record id is already surfaced by the runner's ``LOG_NO_RECORD_ID``
    warning (create mode) or falls back to the known ``medicalRecordId`` (update mode), so a second
    drift signal here would just double-warn.
    """
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
