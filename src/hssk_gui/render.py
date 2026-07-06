"""Render engine events (``Msg`` / ``LogEvent``) into the UI language.

The engine emits stable ``MessageCode`` + params; this is the GUI-side counterpart to
``hssk.events.render_en`` — same composition, but pulling the translatable text from the i18n
table so it follows the UI language. Raw server/exception ``detail`` is shown verbatim (there is
nothing to translate); a couple of purely diagnostic codes fall through to the English renderer.
"""

from __future__ import annotations

from hssk.events import LogEvent, MessageCode, Msg, render_en
from hssk.pipeline.results import Status

from .i18n import tr

_C = MessageCode

# Success-shaped rows: a translated verb head, then an optional " — {who}" and no-id suffix.
_ROW_VERBS = {_C.ROW_CREATED, _C.ROW_UPDATED, _C.ROW_DELETED, _C.ROW_DRY_RUN}
# Translated prefix followed by verbatim passthrough detail.
_PREFIX_DETAIL = {_C.ROW_COERCE_ERROR, _C.ROW_FETCH_DETAIL_FAILED}
# Diagnostic-only: no translation, defer to the English renderer (raw server/exception text).
_PASSTHROUGH = {_C.ROW_SEARCH_FAILED, _C.PASSTHROUGH}


def render_status(status: Status) -> str:
    """Localized label for a run-result Status (falls back to the raw enum value)."""
    key = f"status_{status.value}"
    text = tr(key)
    return status.value if text == key else text


def render_all(msgs: list[Msg]) -> str:
    """Join several messages the way a single row's outcome message reads (e.g. INVALID rows
    with more than one coerce error)."""
    return "; ".join(render(m) for m in msgs)


def render_validation_row(errors: list[Msg], warnings: list[Msg]) -> str:
    """Render a validation row's combined errors + warnings, warnings prefixed with '⚠ '."""
    parts = [render(e) for e in errors] + [f"⚠ {render(w)}" for w in warnings]
    return "; ".join(parts)


def render(m: Msg | LogEvent) -> str:
    """Render a Msg/LogEvent to the current UI language."""
    c = m.code
    if c is None or c in _PASSTHROUGH:
        return render_en(m)

    p = m.params
    detail = m.detail or ""
    key = f"msg_{c.value}"

    if c in _ROW_VERBS:
        base = tr(key)
        who = p.get("who")
        if who:
            base = f"{base} — {who}"
        if p.get("no_record_id"):
            base = f"{base} ({tr('msg_no_record_id')})"
        return base

    if c in _PREFIX_DETAIL:
        return tr(key) + detail

    if c == _C.ROW_MULTI_MATCH:
        out = tr(key).format(count=p["count"], query=p["query"])
        return out + tr("msg_multi_match_skip") if p.get("skipping") else out

    # Everything else is a plain format template. Build a superset of params (str.format ignores
    # extras) plus the passthrough detail and, for file errors, a bracket-free column list.
    fmt = dict(p)
    fmt["detail"] = detail
    if c == _C.FILE_MISSING_COLUMNS:
        fmt["cols"] = ", ".join(repr(x) for x in p["missing"])
    elif c == _C.FILE_DUPLICATE_COLUMNS:
        fmt["cols"] = ", ".join(repr(x) for x in p["dups"])
    return tr(key).format(**fmt)
