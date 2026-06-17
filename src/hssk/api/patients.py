"""Patient search — resolve the internal ``patientId`` from a medical identifier code.

The exact response shape of the internal API is undocumented, so the list extraction is defensive
and the raw body can be logged on the first call. A returned record is only accepted when its
``medicalIdentifierCode`` matches the query exactly — we never write to a guessed patient.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..errors import MultiMatch, PatientNotFound
from ..mapping import SearchSpec
from .client import ApiClient

SEARCH_PATH = "/api/v1/report/patient/search"

_LIST_KEYS = ("content", "items", "records", "rows", "list", "data")


def _find_patient_list(data: Any) -> list[dict[str, Any]]:
    """Walk the response and return the first list of dicts that look like patient records."""
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list) and any(isinstance(x, dict) for x in val):
                return [x for x in val if isinstance(x, dict)]
        # recurse into nested containers (e.g. {"data": {"content": [...]}})
        for key in ("data", "result", "response", "body"):
            if key in data:
                found = _find_patient_list(data[key])
                if found:
                    return found
        # last resort: any list-of-dicts with a patientId
        for val in data.values():
            if isinstance(val, list) and any(
                isinstance(x, dict) and "patientId" in x for x in val
            ):
                return [x for x in val if isinstance(x, dict)]
    return []


def search(
    client: ApiClient,
    identifier: str,
    search_spec: SearchSpec,
    *,
    on_raw: Callable[[Any], None] | None = None,
) -> list[dict[str, Any]]:
    body = {
        "medicalIdentifierCode": identifier,
        "profileStatus": search_spec.profileStatus,
        "page": search_spec.page,
        "size": search_spec.size,
    }
    data = client.post(SEARCH_PATH, body)
    if on_raw is not None:
        on_raw(data)
    return _find_patient_list(data)


def resolve_patient_id(
    client: ApiClient,
    identifier: str,
    search_spec: SearchSpec,
    *,
    on_raw: Callable[[Any], None] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Return ``(patientId, record)`` for the exact identifier match, or raise."""
    candidates = search(client, identifier, search_spec, on_raw=on_raw)
    wanted = str(identifier).strip()
    exact = [
        p
        for p in candidates
        if str(p.get("medicalIdentifierCode", "")).strip() == wanted
    ]
    if not exact:
        raise PatientNotFound(f"no patient with medicalIdentifierCode {identifier!r}")
    if len(exact) > 1:
        if search_spec.multi_match == "first":
            chosen = exact[0]
        elif search_spec.multi_match == "error":
            raise MultiMatch(
                f"{len(exact)} patients match {identifier!r}", candidates=exact
            )
        else:  # skip
            raise MultiMatch(
                f"{len(exact)} patients match {identifier!r}; skipping", candidates=exact
            )
    else:
        chosen = exact[0]

    pid = chosen.get("patientId") or chosen.get("id")
    if pid is None:
        raise PatientNotFound(f"match for {identifier!r} has no patientId field")
    return pid, chosen
