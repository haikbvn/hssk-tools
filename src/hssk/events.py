"""Typed events the engine emits instead of English sentences.

The engine used to author human-readable English strings (``"created — {who}"``, ``"retry in
2.5s"``, coercion errors …) that the GUI re-parsed by prefix-matching to translate — a brittle,
comment-enforced contract with no test pinning it. Instead the engine now emits a stable
:class:`MessageCode` plus a ``params`` dict; each frontend owns the wording. The CLI and written
reports render English via :func:`render_en` (byte-identical to the old strings, so artifacts stay
stable); the GUI renders Vietnamese/English from the same code via its own i18n table.

``detail`` carries raw server/exception text that is inherently free-form (an HTTP body, a parse
exception): there is no attempt to type it — it is passed through verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MessageCode(StrEnum):
    # -- per-row outcome messages (RowOutcome.msg) --
    ROW_CREATED = "ROW_CREATED"
    ROW_UPDATED = "ROW_UPDATED"
    ROW_DELETED = "ROW_DELETED"
    ROW_DRY_RUN = "ROW_DRY_RUN"
    ROW_ALREADY_PROCESSED = "ROW_ALREADY_PROCESSED"
    ROW_ID_BLANK = "ROW_ID_BLANK"
    ROW_RECORD_ID_BLANK = "ROW_RECORD_ID_BLANK"
    ROW_COERCE_ERROR = "ROW_COERCE_ERROR"  # coerce_row itself raised (detail = exception text)
    ROW_FETCH_DETAIL_FAILED = "ROW_FETCH_DETAIL_FAILED"
    ROW_SEARCH_FAILED = "ROW_SEARCH_FAILED"
    ROW_NO_PATIENT = "ROW_NO_PATIENT"
    ROW_MULTI_MATCH = "ROW_MULTI_MATCH"
    ROW_MATCH_NO_PATIENT_ID = "ROW_MATCH_NO_PATIENT_ID"
    # -- per-cell coercion errors/warnings (RowResult.errors / .warnings) --
    COERCE_CANNOT_PARSE = "COERCE_CANNOT_PARSE"
    COERCE_MISSING_REQUIRED = "COERCE_MISSING_REQUIRED"
    COERCE_RANGE = "COERCE_RANGE"
    COERCE_DATE_BEFORE = "COERCE_DATE_BEFORE"
    # -- file-level structural errors (ConfigError) --
    FILE_MISSING_COLUMNS = "FILE_MISSING_COLUMNS"
    FILE_DUPLICATE_COLUMNS = "FILE_DUPLICATE_COLUMNS"
    # -- log lines (Callbacks.on_log) --
    LOG_UNMAPPED_COLUMNS = "LOG_UNMAPPED_COLUMNS"
    LOG_FIRST_SEARCH_SAVED = "LOG_FIRST_SEARCH_SAVED"
    LOG_RETRY = "LOG_RETRY"
    LOG_NO_RECORD_ID = "LOG_NO_RECORD_ID"
    LOG_LEDGER_CORRUPT = "LOG_LEDGER_CORRUPT"
    LOG_SEARCH_SAVED_ROW = "LOG_SEARCH_SAVED_ROW"
    LOG_TOKEN_SHORT = "LOG_TOKEN_SHORT"
    # -- browser-login progress (StatusFn) --
    LOGIN_WAITING = "LOGIN_WAITING"
    LOGIN_TOKEN_CAPTURED = "LOGIN_TOKEN_CAPTURED"


# Verb heads for the four "success"-shaped row messages, reused by render_en.
_ROW_VERB: dict[MessageCode, str] = {
    MessageCode.ROW_CREATED: "created",
    MessageCode.ROW_UPDATED: "updated",
    MessageCode.ROW_DELETED: "deleted",
    MessageCode.ROW_DRY_RUN: "payload built (not sent)",
}


@dataclass
class Msg:
    """A translatable message: a stable code, formatting params, and optional passthrough detail."""

    code: MessageCode
    params: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None  # raw server/exception text, rendered verbatim by every frontend


@dataclass
class LogEvent:
    """A log line. ``code=None`` is a pure passthrough (``detail`` shown as-is, untranslated)."""

    code: MessageCode | None
    params: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None
    level: str = "info"  # "info" | "warning"


def render_en(msg: Msg | LogEvent) -> str:
    """Render a message/log event to English, byte-identical to the pre-refactor engine wording.

    This is what the CLI prints and what the written reports (``results.*``, ``events.jsonl``)
    record, so its output must not drift. The GUI does NOT use this — it renders from ``msg.code``
    via its own i18n table.
    """
    c = msg.code
    p = msg.params
    d = msg.detail or ""

    if c is None:
        return d

    if c in _ROW_VERB:
        base = _ROW_VERB[c]
        who = p.get("who")
        if who:
            base = f"{base} — {who}"
        if p.get("no_record_id"):
            base = f"{base} (no record id returned)"
        return base

    if c == MessageCode.ROW_ALREADY_PROCESSED:
        return "already processed"
    if c == MessageCode.ROW_ID_BLANK:
        return "identifier is blank"
    if c == MessageCode.ROW_RECORD_ID_BLANK:
        return "medicalRecordId is blank"
    if c == MessageCode.ROW_COERCE_ERROR:
        return f"coercion error: {d}"
    if c == MessageCode.ROW_FETCH_DETAIL_FAILED:
        return f"fetch detail: {d}"
    if c == MessageCode.ROW_SEARCH_FAILED:
        return f"search: {d}"
    if c == MessageCode.ROW_NO_PATIENT:
        return f"no patient found for {p['query']}"
    if c == MessageCode.ROW_MULTI_MATCH:
        base = f"{p['count']} patients match {p['query']}"
        return f"{base}; skipping" if p.get("skipping") else base
    if c == MessageCode.ROW_MATCH_NO_PATIENT_ID:
        return f"match for {p['query']} has no patientId field"

    if c == MessageCode.COERCE_CANNOT_PARSE:
        return f"{p['col']}: cannot parse {p['value']} as {p['type']} ({d})"
    if c == MessageCode.COERCE_MISSING_REQUIRED:
        return f"missing required column {p['col']}"
    if c == MessageCode.COERCE_RANGE:
        return f"{p['target']}={p['value']} outside expected range {p['lo']}–{p['hi']}"
    if c == MessageCode.COERCE_DATE_BEFORE:
        return f"finishExaminationDate ({p['finish']}) is before examinationDate ({p['start']})"

    if c == MessageCode.FILE_MISSING_COLUMNS:
        return (
            f"Excel {p['name']} is missing mapped column(s): {p['missing']}. "
            f"Found headers: {p['headers']}"
        )
    if c == MessageCode.FILE_DUPLICATE_COLUMNS:
        return (
            f"Excel {p['name']} has duplicate mapped column header(s): {p['dups']}. "
            "Only the right-most copy would be read — rename or remove the duplicates."
        )

    if c == MessageCode.LOG_UNMAPPED_COLUMNS:
        return f"ignoring {p['n']} unmapped Excel column(s): {p['cols']}"
    if c == MessageCode.LOG_FIRST_SEARCH_SAVED:
        return "Logged first search response for inspection."
    if c == MessageCode.LOG_RETRY:
        return f"retry in {p['delay']}s (attempt {p['attempt']})"
    if c == MessageCode.LOG_NO_RECORD_ID:
        return f"row {p['row']}: no record id in server response"
    if c == MessageCode.LOG_LEDGER_CORRUPT:
        return f"{p['n']} unreadable ledger line(s) — those rows may be re-sent"
    if c == MessageCode.LOG_SEARCH_SAVED_ROW:
        return f"saved search response for row {p['row']} ({p['filename']})"
    if c == MessageCode.LOG_TOKEN_SHORT:
        return (
            f"token may expire before this batch finishes "
            f"(~{p['needed']} min needed, ~{p['left']} min left) — consider logging in again first"
        )

    if c == MessageCode.LOGIN_WAITING:
        return "Please log in in the browser window…"
    if c == MessageCode.LOGIN_TOKEN_CAPTURED:
        return "Token captured."

    return d  # pragma: no cover  (every code above is handled)
