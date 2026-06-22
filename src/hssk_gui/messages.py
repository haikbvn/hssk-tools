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


def _tr_message(message: str) -> str:
    """Localize engine-authored row messages; pass diagnostic detail through unchanged."""
    if not message:
        return ""
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
    # Bare/compound coerce errors (runner joins coerced.errors with "; " — no prefix).
    # _tr_coerce_msgs only substitutes a few distinctive fixed phrases, so raw API/exception
    # text is left intact in practice (a server string containing e.g. " is before " could
    # in theory be partially rewritten, but those phrases are specific enough to be safe).
    return _tr_coerce_msgs(message)
