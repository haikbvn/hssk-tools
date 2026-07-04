"""Translate engine-authored result/validation messages into the UI language.

The engine (``hssk/pipeline/runner.py``, ``hssk/excel/coerce.py``) emits English/diagnostic strings
with stable shapes; these pure helpers map the parts we control to localized text and pass raw
server/exception detail through unchanged. Keep the matched prefixes in sync with the engine.
"""

from __future__ import annotations

from hssk.pipeline.results import Status

from .i18n import tr


def _tr_status(status: Status) -> str:
    """Localized label for a run-result Status (falls back to the raw enum value)."""
    key = f"status_{status.value}"
    text = tr(key)
    return status.value if text == key else text


# Engine-authored row messages from hssk/pipeline/runner.py. Anything not matched here
# (raw API/exception text, per-cell coercion detail) is shown as-is — it is server or
# diagnostic content we don't control. Keep these prefixes in sync with the runner.
# Engine log strings emitted via Callbacks.on_log (runner.py + api/client.py).
_LOG_EXACT: dict[str, str] = {
    "Logged first search response for inspection.": "log_first_search_response",
}


# "row N: no record id in server response" — runner warns when a create response had no id.
_NO_RID_LOG_SUFFIX = ": no record id in server response"

# "N unreadable ledger line(s) — those rows may be re-sent" — runner warns on corrupt ledger.
_LEDGER_CORRUPT_SUFFIX = " unreadable ledger line(s) — those rows may be re-sent"

# "token may expire before this batch finishes (~X min needed, ~Y min left) — consider…"
_TOKEN_SHORT_HEAD = "token may expire before this batch finishes (~"
_TOKEN_SHORT_MID = " min needed, ~"
_TOKEN_SHORT_TAIL = " min left) — consider logging in again first"


_UNMAPPED_HEAD = "ignoring "
_UNMAPPED_MID = " unmapped Excel column(s): "


def _tr_unmapped(msg: str) -> str | None:
    """Translate the reader's unmapped-columns warning; None if the message isn't that shape."""
    if msg.startswith(_UNMAPPED_HEAD) and _UNMAPPED_MID in msg:
        n, _, cols = msg[len(_UNMAPPED_HEAD) :].partition(_UNMAPPED_MID)
        return tr("msg_unmapped_columns").format(n=n, cols=cols)
    return None


def _tr_log(msg: str) -> str:
    """Translate known engine log strings; pass diagnostic/API detail through unchanged."""
    exact = _LOG_EXACT.get(msg)
    if exact is not None:
        return tr(exact)
    unmapped = _tr_unmapped(msg)
    if unmapped is not None:
        return unmapped
    # "retry in 2.5s (attempt 3)" from api/client.py — translate the two fixed phrases
    if msg.startswith("retry in "):
        msg = msg.replace("retry in ", tr("log_retry_in"), 1)
        msg = msg.replace(" (attempt ", tr("log_retry_attempt"), 1)
        return msg
    if msg.startswith("row ") and msg.endswith(_NO_RID_LOG_SUFFIX):
        return tr("log_no_record_id").format(row=msg[len("row ") : -len(_NO_RID_LOG_SUFFIX)])
    if msg.endswith(_LEDGER_CORRUPT_SUFFIX):
        return tr("log_ledger_corrupt").format(n=msg[: -len(_LEDGER_CORRUPT_SUFFIX)])
    # "saved search response for row N (search_response_row_N.json)" — keep the filename tail
    if msg.startswith("saved search response for row "):
        return tr("log_saved_search_response") + msg[len("saved search response for row ") :]
    if msg.startswith(_TOKEN_SHORT_HEAD) and msg.endswith(_TOKEN_SHORT_TAIL):
        body = msg[len(_TOKEN_SHORT_HEAD) : -len(_TOKEN_SHORT_TAIL)]
        needed, sep, left = body.partition(_TOKEN_SHORT_MID)
        if sep:
            return tr("log_token_short_for_batch").format(needed=needed, left=left)
    return msg


# Browser-login progress strings emitted by hssk/auth/browser_login.py.
_LOGIN_STATUS_KEYS: dict[str, str] = {
    "Please log in in the browser window…": "lbl_login_waiting",
    "Token captured.": "lbl_login_captured",
}


def _tr_login_status(msg: str) -> str:
    """Translate a browser-login progress string; pass unknown strings through unchanged."""
    key = _LOGIN_STATUS_KEYS.get(msg)
    return tr(key) if key else msg


_MSG_EXACT = {
    "already processed": "msg_row_already",
    "identifier is blank": "msg_row_id_blank",
    "medicalRecordId is blank": "msg_row_recordid_blank",
}
_MSG_HEADS = [  # "<head>" or "<head> — <name>"
    ("created", "msg_row_created"),
    ("updated", "msg_row_updated"),
    ("payload built (not sent)", "msg_row_dryrun"),
]


def _tr_coerce_msg(msg: str) -> str:
    """Translate a single coerce error/warning line from the engine (no ⚠ prefix)."""
    unmapped = _tr_unmapped(msg)
    if unmapped is not None:
        return unmapped
    if msg.startswith("missing required column "):
        return tr("msg_coerce_missing_col") + msg[len("missing required column ") :]
    if ": cannot parse " in msg:
        # "'COL': cannot parse 'VAL' as TYPE (detail)" — translate the two fixed phrases
        msg = msg.replace(": cannot parse ", tr("msg_coerce_cannot_parse"), 1)
        msg = msg.replace(" as ", tr("msg_coerce_as_type"), 1)
        return msg
    if " outside expected range " in msg:
        return msg.replace(" outside expected range ", tr("msg_coerce_range"), 1)
    if " is before " in msg:
        return msg.replace(" is before ", tr("msg_coerce_date_before"), 1)
    return msg


def _tr_coerce_msgs(compound: str) -> str:
    """Translate a semicolon-joined string of coerce errors/warnings (validation path)."""
    parts = compound.split("; ")
    result = []
    for part in parts:
        if part.startswith("⚠ "):
            result.append("⚠ " + _tr_coerce_msg(part[2:]))
        else:
            result.append(_tr_coerce_msg(part))
    return "; ".join(result)


# Appended by the runner when a create succeeded but no record id could be extracted.
# Must be stripped before head matching (it defeats both the exact and "head — " forms).
_NO_RID_MSG_SUFFIX = " (no record id returned)"


def _tr_message(message: str) -> str:
    """Localize engine-authored row messages; pass diagnostic detail through unchanged."""
    if not message:
        return ""
    if message.endswith(_NO_RID_MSG_SUFFIX):
        base = _tr_message(message[: -len(_NO_RID_MSG_SUFFIX)])
        return f"{base} ({tr('msg_no_record_id')})"
    exact = _MSG_EXACT.get(message)
    if exact is not None:
        return tr(exact)
    for head, key in _MSG_HEADS:
        if message == head:
            return tr(key)
        if message.startswith(f"{head} — "):
            return f"{tr(key)} — {message[len(head) + 3 :]}"
    # "coercion error: <coerce detail>" — translate prefix and coerce detail
    if message.startswith("coercion error: "):
        return tr("msg_row_coercion") + _tr_coerce_msg(message[len("coercion error: ") :])
    # "fetch detail: <diagnostic tail>" — translate prefix, diagnostic passes through
    if message.startswith("fetch detail: "):
        return tr("msg_row_fetch") + message[len("fetch detail: ") :]
    # "no patient found for 'QUERY'" — patients.resolve / PatientNotFound
    if message.startswith("no patient found for "):
        return tr("msg_no_patient_for") + message[len("no patient found for ") :]
    # "match for 'QUERY' has no patientId field" — malformed API response
    if message.startswith("match for ") and message.endswith(" has no patientId field"):
        identifier = message[len("match for ") : -len(" has no patientId field")]
        return tr("msg_match_for") + identifier + tr("msg_no_patient_id")
    # "N patients match 'QUERY'" or "N patients match 'QUERY'; skipping" — MultiMatch
    if " patients match " in message:
        count, rest = message.split(" patients match ", 1)
        skipping = rest.endswith("; skipping")
        identifier = rest[: -len("; skipping")] if skipping else rest
        out = count + tr("msg_patients_match") + identifier
        return (out + tr("msg_multi_match_skip")) if skipping else out
    # Bare/compound coerce errors (runner joins coerced.errors with "; " — no prefix).
    # _tr_coerce_msgs only substitutes a few distinctive fixed phrases, so raw API/exception
    # text is left intact in practice (a server string containing e.g. " is before " could
    # in theory be partially rewritten, but those phrases are specific enough to be safe).
    return _tr_coerce_msgs(message)
