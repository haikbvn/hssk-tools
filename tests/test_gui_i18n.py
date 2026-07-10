"""Contract test: every engine ``MessageCode`` renders in both GUI languages.

The engine emits typed events (``hssk.events.MessageCode`` + params); ``hssk_gui/render.py`` is
the GUI-side renderer, the counterpart to the engine's own ``render_en``. This file is what used
to pin ``hssk_gui/messages.py``'s prefix-matching of raw engine strings — that module is gone, so
the contract is now: every code has a real vi + en translation, and produces the exact wording the
pre-refactor GUI showed (pinned against ``tests/golden/vi_messages_golden.json``, captured from the
old messages.py before this refactor).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hssk.events import MessageCode, Msg, render_en
from hssk.pipeline.results import Status
from hssk_gui.i18n import set_language, tr
from hssk_gui.render import render, render_all, render_status, render_validation_row
from hssk_gui.workers import ValidationSummary

GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "vi_messages_golden.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


# -- render_status ------------------------------------------------------------------------


def test_status_every_enum_value_translates() -> None:
    set_language("vi")
    for status in Status:
        out = render_status(status)
        assert out
        assert not out.startswith("status_")


def test_status_specific_labels() -> None:
    set_language("en")
    assert render_status(Status.CREATED) == "Created"
    assert render_status(Status.SKIPPED_ALREADY) == "Skipped (already sent)"
    set_language("vi")
    assert render_status(Status.CREATED) == "Đã tạo"


# -- every MessageCode has a real translation, matched against the pre-refactor golden ----

_WHO = "Nguyễn Thị Hoa"
_Q = "'027148003240'"

# label (matches the golden's key) -> Msg built the way the engine would build it.
_CASES: dict[str, Msg] = {
    "row_created_bare": Msg(MessageCode.ROW_CREATED),
    "row_created_who": Msg(MessageCode.ROW_CREATED, {"who": _WHO}),
    "row_updated_bare": Msg(MessageCode.ROW_UPDATED),
    "row_updated_who": Msg(MessageCode.ROW_UPDATED, {"who": _WHO}),
    "row_deleted_bare": Msg(MessageCode.ROW_DELETED),
    "row_deleted_who": Msg(MessageCode.ROW_DELETED, {"who": _WHO}),
    "row_dryrun_bare": Msg(MessageCode.ROW_DRY_RUN),
    "row_dryrun_who": Msg(MessageCode.ROW_DRY_RUN, {"who": _WHO}),
    "row_created_no_rid": Msg(MessageCode.ROW_CREATED, {"who": _WHO, "no_record_id": True}),
    "row_created_bare_no_rid": Msg(MessageCode.ROW_CREATED, {"no_record_id": True}),
    "row_already": Msg(MessageCode.ROW_ALREADY_PROCESSED),
    "row_id_blank": Msg(MessageCode.ROW_ID_BLANK),
    "row_recordid_blank": Msg(MessageCode.ROW_RECORD_ID_BLANK),
    "row_fetch_detail": Msg(MessageCode.ROW_FETCH_DETAIL_FAILED, detail="HTTP 404"),
    "row_no_patient": Msg(MessageCode.ROW_NO_PATIENT, {"query": _Q}),
    "row_multi_match": Msg(MessageCode.ROW_MULTI_MATCH, {"count": 2, "query": _Q}),
    "row_multi_match_skip": Msg(
        MessageCode.ROW_MULTI_MATCH, {"count": 2, "query": _Q, "skipping": True}
    ),
    "row_match_no_pid": Msg(MessageCode.ROW_MATCH_NO_PATIENT_ID, {"query": _Q}),
    "coerce_cannot_parse": Msg(
        MessageCode.COERCE_CANNOT_PARSE,
        {"col": "'Tuổi'", "value": "'abc'", "type": "int"},
        detail="invalid",
    ),
    "coerce_range_warn": Msg(
        MessageCode.COERCE_RANGE, {"target": "Mạch", "value": 250, "lo": 30, "hi": 200}
    ),
    "coerce_date_before": Msg(
        MessageCode.COERCE_DATE_BEFORE, {"finish": "17/06/2026", "start": "18/06/2026"}
    ),
    "coerce_missing_required": Msg(MessageCode.COERCE_MISSING_REQUIRED, {"col": "'Mã định danh'"}),
    "file_missing_columns": Msg(
        MessageCode.FILE_MISSING_COLUMNS,
        {"name": "foo.xlsx", "missing": ["Mã hồ sơ"], "headers": ["A", "B"]},
    ),
    "file_duplicate_columns": Msg(
        MessageCode.FILE_DUPLICATE_COLUMNS, {"name": "foo.xlsx", "dups": ["X"]}
    ),
    "log_first_search": Msg(MessageCode.LOG_FIRST_SEARCH_SAVED),
    "log_retry": Msg(MessageCode.LOG_RETRY, {"delay": "2.5", "attempt": 3}),
    "log_no_record_id": Msg(MessageCode.LOG_NO_RECORD_ID, {"row": 5}),
    "log_ledger_corrupt": Msg(MessageCode.LOG_LEDGER_CORRUPT, {"n": 3}),
    "log_saved_search": Msg(
        MessageCode.LOG_SEARCH_SAVED_ROW, {"row": 5, "filename": "search_response_row_5.json"}
    ),
    "log_unmapped": Msg(MessageCode.LOG_UNMAPPED_COLUMNS, {"n": 2, "cols": "'A', 'B'"}),
    "log_token_short": Msg(MessageCode.LOG_TOKEN_SHORT, {"needed": 10, "left": 5}),
    "login_waiting": Msg(MessageCode.LOGIN_WAITING),
    "login_captured": Msg(MessageCode.LOGIN_TOKEN_CAPTURED),
}

# ROW_COERCE_ERROR is deliberately excluded from the golden cross-check: the GUI shows the raw
# passthrough detail unmodified (see test_coerce_error_shows_raw_detail_unmodified below), which
# differs from the golden's old messages.py behavior of re-parsing that detail text.

_CODES_WITHOUT_GOLDEN_CASE = {
    MessageCode.ROW_COERCE_ERROR,  # tested separately (see below)
    MessageCode.ROW_SEARCH_FAILED,  # tested separately (see below)
    MessageCode.PASSTHROUGH,  # not a real code — no template, always render_en passthrough
    MessageCode.ROW_PAYLOAD_INVALID,  # Phase 5, no pre-refactor golden — tested below
    MessageCode.LOG_DRIFT,  # Phase 5, no pre-refactor golden — tested below
    # Plan 004, no pre-refactor golden — tested in test_pipeline/test_events
    MessageCode.ROW_PENDING_VERIFY,
}


def test_every_code_has_a_golden_case_or_is_explicitly_exempt() -> None:
    covered = {m.code for m in _CASES.values()} | _CODES_WITHOUT_GOLDEN_CASE
    assert covered == set(MessageCode), f"missing coverage: {set(MessageCode) - covered}"


# For coerce_range_warn only: the golden's "⚠ " is a display prefix the old code added when
# showing the message in a *warnings* list (_tr_coerce_msgs), not part of the message template
# itself — render_validation_row (tested below) adds the same prefix contextually. Every other
# golden "⚠ " (e.g. log_token_short) is baked into that specific translation and must match as-is.
_STRIP_WARNING_MARKER = {"coerce_range_warn"}


@pytest.mark.parametrize("label", sorted(_CASES))
def test_render_matches_golden_vi_and_en(label: str) -> None:
    golden = GOLDEN["messages"][label]
    msg = _CASES[label]
    strip = label in _STRIP_WARNING_MARKER
    set_language("vi")
    expected_vi = golden["vi"].removeprefix("⚠ ") if strip else golden["vi"]
    assert render(msg) == expected_vi
    set_language("en")
    expected_en = golden["en"].removeprefix("⚠ ") if strip else golden["en"]
    assert render(msg) == expected_en


def test_coerce_error_shows_raw_detail_unmodified() -> None:
    # Unlike the old messages.py (which re-parsed the coerce detail text for fixed phrases),
    # the GUI now shows a translated prefix + the raw detail verbatim — the detail itself is
    # inherently free-form (an arbitrary exception message) and is never re-translated.
    msg = Msg(MessageCode.ROW_COERCE_ERROR, detail="'Tuổi': cannot parse 'abc' as int (bad)")
    set_language("vi")
    assert render(msg) == "Lỗi chuyển đổi: 'Tuổi': cannot parse 'abc' as int (bad)"
    set_language("en")
    assert render(msg) == "Coercion error: 'Tuổi': cannot parse 'abc' as int (bad)"


def test_payload_invalid_shows_translated_prefix_plus_raw_detail() -> None:
    # Phase 5: like ROW_COERCE_ERROR — a translated prefix followed by the verbatim pydantic detail.
    msg = Msg(MessageCode.ROW_PAYLOAD_INVALID, detail="medicalRecordInfo.symptomss: Extra inputs")
    set_language("vi")
    assert render(msg) == "Dữ liệu gửi không hợp lệ: medicalRecordInfo.symptomss: Extra inputs"
    set_language("en")
    assert render(msg) == "Payload failed validation: medicalRecordInfo.symptomss: Extra inputs"


def test_drift_formats_endpoint_in_both_languages() -> None:
    # Phase 5: a plain format template — the {endpoint} param must be substituted, not left literal.
    from hssk.events import LogEvent

    event = LogEvent(MessageCode.LOG_DRIFT, {"endpoint": "/api/v1/report/patient/search"})
    for lang in ("vi", "en"):
        set_language(lang)
        out = render(event)
        assert "/api/v1/report/patient/search" in out
        assert "{endpoint}" not in out
        assert out != "msg_LOG_DRIFT"  # key actually resolved


def test_search_failed_is_passthrough_with_prefix() -> None:
    # Mirrors render_en: "search: {detail}", never translated (raw API/exception text).
    msg = Msg(MessageCode.ROW_SEARCH_FAILED, detail="HTTP 500 server error")
    for lang in ("vi", "en"):
        set_language(lang)
        assert render(msg) == render_en(msg) == "search: HTTP 500 server error"


def test_passthrough_code_is_detail_verbatim() -> None:
    msg = Msg(MessageCode.PASSTHROUGH, detail="PatientNotFound: no match for 123")
    for lang in ("vi", "en"):
        set_language(lang)
        assert render(msg) == "PatientNotFound: no match for 123"


def test_none_code_is_detail_verbatim() -> None:
    from hssk.events import LogEvent

    event = LogEvent(code=None, detail="some raw diagnostic")
    assert render(event) == "some raw diagnostic"


# -- render_all / render_validation_row (multi-message rows) ------------------------------


def test_render_all_joins_with_semicolon() -> None:
    set_language("vi")
    msgs = [
        Msg(MessageCode.COERCE_MISSING_REQUIRED, {"col": "'X'"}),
        Msg(MessageCode.COERCE_CANNOT_PARSE, {"col": "'Tuổi'", "value": "'a'", "type": "int"}, "e"),
    ]
    assert render_all(msgs) == ("thiếu cột bắt buộc 'X'; 'Tuổi': không thể đọc 'a' thành int (e)")


def test_render_validation_row_prefixes_warnings() -> None:
    set_language("vi")
    errors = [Msg(MessageCode.COERCE_MISSING_REQUIRED, {"col": "'X'"})]
    warnings = [
        Msg(MessageCode.COERCE_RANGE, {"target": "pulse", "value": 250, "lo": 30, "hi": 220})
    ]
    out = render_validation_row(errors, warnings)
    assert out == "thiếu cột bắt buộc 'X'; ⚠ pulse=250 nằm ngoài phạm vi 30–220"


# -- UI vocabulary keys resolve in both languages ------------------------------------------

_V140_KEYS = [
    "msg_no_record_id",
    "tip_dismiss_banner",
    "a11y_error_banner",
    "filter_all_statuses",
    "btn_clear_log",
    "tip_status_filter",
    "menu_file",
    "menu_open_recent",
    "menu_recent_empty",
    "menu_open_reports_root",
    "msg_recent_missing",
    "tip_choose_excel",
    "tip_validate",
    "tip_stop",
    "tip_start_ready",
    "update_available",
    "update_link",
    "chk_check_updates",
    "tip_check_updates",
]


def test_v140_keys_resolve_in_both_languages() -> None:
    for lang in ("vi", "en"):
        set_language(lang)
        for key in _V140_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


_UI_POLISH_KEYS = [
    "counter_ok",
    "counter_skipped",
    "counter_failed",
    "counter_aborted",
    "counter_valid",
    "counter_warns",
    "counter_invalid",
    "msg_validation_done",
]


def test_ui_polish_keys_resolve_in_both_languages() -> None:
    for lang in ("vi", "en"):
        set_language(lang)
        for key in _UI_POLISH_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


_DELETE_KEYS = [
    "mode_delete",
    "btn_start_delete_live",
    "banner_production_delete",
    "msg_confirm_push_delete",
    "status_DELETED",
    "dlg_delete_needs_record_id",
    "msg_delete_needs_record_id",
]


def test_delete_keys_resolve_in_both_languages() -> None:
    for lang in ("vi", "en"):
        set_language(lang)
        for key in _DELETE_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


# -- ValidationSummary contract -------------------------------------------------------------


def test_validation_summary_not_cancelled_by_default() -> None:
    # _on_validate_finished relies on this default: a normal full pass marks the file
    # validated; only an explicitly cancelled pass leaves it unvalidated.
    assert ValidationSummary(valid=1, invalid=0, warns=0, total=1).cancelled is False
