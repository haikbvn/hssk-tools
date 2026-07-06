"""Patient search — resolve the internal ``patientId`` from whatever identifier the Excel holds.

The website's search broadcasts the typed value across several fields at once (name, medical code,
citizen id, phone, insurance number) and matches if any one hits — so the Excel "identifier" may be
a CCCD, an insurance number, a phone, etc. We mirror that request. The matched patient's *real*
``medicalIdentifierCode`` (which usually differs from the searched value) is returned so the create
payload can use it together with ``patientId``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..errors import MultiMatch, PatientNotFound
from ..events import MessageCode, Msg
from ..mapping import SearchSpec
from .client import ApiClient

SEARCH_PATH = "/api/v1/report/patient/search"

# The value is sent in all of these (exactly as the website does).
SEARCH_FIELDS = (
    "fullname",
    "medicalIdentifierCode",
    "identification",
    "homePhoneNumber",
    "personalPhoneNumber",
    "healthInsuranceNumber",
)

# Fields the search result echoes back that we can verify an exact match against.
_ECHOED_ID_FIELDS = (
    "medicalIdentifierCode",
    "healthInsuranceNumber",
    "personalPhoneNumber",
    "householdCode",
)

_LIST_KEYS = ("items", "content", "records", "rows", "list", "data")


@dataclass
class ResolvedPatient:
    patient_id: Any
    medical_identifier_code: str | None
    fullname: str | None
    record: dict[str, Any]


def _find_patient_list(data: Any) -> list[dict[str, Any]]:
    """Walk the response and return the first list of dicts that look like patient records."""
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list) and any(isinstance(x, dict) for x in val):
                return [x for x in val if isinstance(x, dict)]
        for key in ("data", "result", "response", "body"):
            if key in data:
                found = _find_patient_list(data[key])
                if found:
                    return found
        for val in data.values():
            if isinstance(val, list) and any(isinstance(x, dict) and "patientId" in x for x in val):
                return [x for x in val if isinstance(x, dict)]
    return []


def search(
    client: ApiClient,
    query: str,
    search_spec: SearchSpec,
    *,
    on_raw: Callable[[Any], None] | None = None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {field: query for field in SEARCH_FIELDS}
    body["profileStatus"] = search_spec.profileStatus
    body["page"] = search_spec.page
    body["size"] = search_spec.size
    data = client.post(SEARCH_PATH, body)
    if on_raw is not None:
        on_raw(data)
    return _find_patient_list(data)


def _echoed_exact(record: dict[str, Any], query: str) -> bool:
    q = query.strip()
    return any(
        record.get(f) is not None and str(record.get(f)).strip() == q for f in _ECHOED_ID_FIELDS
    )


def resolve(
    client: ApiClient,
    query: str,
    search_spec: SearchSpec,
    *,
    on_raw: Callable[[Any], None] | None = None,
) -> ResolvedPatient:
    """Return the resolved patient for ``query``, or raise PatientNotFound / MultiMatch."""
    candidates = search(client, query, search_spec, on_raw=on_raw)
    if not candidates:
        raise PatientNotFound(
            f"no patient found for {query!r}",
            msg=Msg(MessageCode.ROW_NO_PATIENT, {"query": repr(query)}),
        )

    # Prefer candidates that exactly match an echoed identifier field; otherwise fall back to the
    # full set (e.g. a CCCD match, which the API doesn't echo back).
    exact = [c for c in candidates if _echoed_exact(c, query)]
    pool = exact or candidates

    if len(pool) > 1:
        if search_spec.multi_match == "first":
            chosen = pool[0]
        elif search_spec.multi_match == "error":
            raise MultiMatch(
                f"{len(pool)} patients match {query!r}",
                candidates=pool,
                msg=Msg(MessageCode.ROW_MULTI_MATCH, {"count": len(pool), "query": repr(query)}),
            )
        else:  # skip
            raise MultiMatch(
                f"{len(pool)} patients match {query!r}; skipping",
                candidates=pool,
                msg=Msg(
                    MessageCode.ROW_MULTI_MATCH,
                    {"count": len(pool), "query": repr(query), "skipping": True},
                ),
            )
    else:
        chosen = pool[0]

    pid = chosen.get("patientId")
    if pid is None:
        pid = chosen.get("id")
    if pid is None:
        raise PatientNotFound(
            f"match for {query!r} has no patientId field",
            msg=Msg(MessageCode.ROW_MATCH_NO_PATIENT_ID, {"query": repr(query)}),
        )
    return ResolvedPatient(
        patient_id=pid,
        medical_identifier_code=chosen.get("medicalIdentifierCode"),
        fullname=chosen.get("fullname") or chosen.get("fullName"),
        record=chosen,
    )
