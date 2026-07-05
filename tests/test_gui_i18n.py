"""Translation of engine-authored result/validation messages in the GUI layer.

These helpers encode a contract with the runner and coerce modules: they translate a
small set of fixed English phrases and pass all other (diagnostic / API) text through
untouched. If the runner's wording drifts, these tests should catch it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk.pipeline.results import Status
from hssk_gui.i18n import set_language
from hssk_gui.messages import (
    _tr_coerce_msg,
    _tr_coerce_msgs,
    _tr_file_error,
    _tr_log,
    _tr_login_status,
    _tr_message,
    _tr_status,
)
from hssk_gui.workers import ValidationSummary


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    # Every test sets the language it needs; restore the default afterwards so a stray
    # language never leaks into another test.
    yield
    set_language("vi")


# -- _tr_status -------------------------------------------------------------------------


def test_status_every_enum_value_translates() -> None:
    set_language("vi")
    for status in Status:
        out = _tr_status(status)
        # A real translation never equals the bare key form ("status_<VALUE>") and is
        # non-empty; the raw enum value would only show through on a missing key.
        assert out
        assert not out.startswith("status_")


def test_status_specific_labels() -> None:
    set_language("en")
    assert _tr_status(Status.CREATED) == "Created"
    assert _tr_status(Status.SKIPPED_ALREADY) == "Skipped (already sent)"
    set_language("vi")
    assert _tr_status(Status.CREATED) == "Đã tạo"


# -- _tr_message: engine-authored row messages ------------------------------------------


def test_message_exact_phrases() -> None:
    set_language("vi")
    assert _tr_message("already processed") == "Đã xử lý trước đó"
    assert _tr_message("identifier is blank") == "Mã định danh trống"


def test_message_head_with_name_keeps_detail() -> None:
    set_language("vi")
    assert _tr_message("created — Nguyễn Văn A") == "Đã tạo — Nguyễn Văn A"
    assert _tr_message("deleted — Nguyễn Văn A") == "Đã xoá — Nguyễn Văn A"
    assert _tr_message("payload built (not sent) — Le C") == "Đã dựng dữ liệu (chưa gửi) — Le C"


def test_message_deleted_head() -> None:
    set_language("vi")
    assert _tr_message("deleted") == "Đã xoá"
    set_language("en")
    assert _tr_message("deleted — A") == "Deleted — A"


def test_message_no_record_id_suffix() -> None:
    set_language("vi")
    assert _tr_message("created — Nguyễn A (no record id returned)") == (
        "Đã tạo — Nguyễn A (không nhận được mã hồ sơ)"
    )
    # who-less variant: the suffix must be stripped before head matching
    assert _tr_message("created (no record id returned)") == ("Đã tạo (không nhận được mã hồ sơ)")
    set_language("en")
    assert _tr_message("created — A (no record id returned)") == (
        "Created — A (no record id returned)"
    )


def test_message_coercion_prefix() -> None:
    set_language("vi")
    out = _tr_message("coercion error: missing required column 'Ngày khám'")
    assert out == "Lỗi chuyển đổi: thiếu cột bắt buộc 'Ngày khám'"


def test_message_bare_compound_coerce_errors() -> None:
    # The runner joins coerced.errors with "; " and emits them with no prefix.
    set_language("vi")
    out = _tr_message("missing required column 'X'; 'Tuổi': cannot parse 'a' as int")
    assert out == "thiếu cột bắt buộc 'X'; 'Tuổi': không thể đọc 'a' thành int"


def test_message_no_patient_found() -> None:
    set_language("vi")
    assert _tr_message("no patient found for '027xxx'") == ("không tìm thấy bệnh nhân với '027xxx'")


def test_message_no_patient_id_field() -> None:
    set_language("vi")
    assert _tr_message("match for '027xxx' has no patientId field") == (
        "khớp với '027xxx' không có trường patientId"
    )


def test_message_multi_match() -> None:
    set_language("vi")
    assert _tr_message("3 patients match '027xxx'") == "3 bệnh nhân khớp với '027xxx'"
    assert _tr_message("3 patients match '027xxx'; skipping") == (
        "3 bệnh nhân khớp với '027xxx'; bỏ qua"
    )


def test_message_patient_english_passthrough() -> None:
    set_language("en")
    assert _tr_message("no patient found for '027xxx'") == "no patient found for '027xxx'"
    assert _tr_message("3 patients match '027xxx'") == "3 patients match '027xxx'"


def test_message_raw_text_passes_through() -> None:
    set_language("vi")
    raw = "PatientNotFound: no match for 123"
    assert _tr_message(raw) == raw
    fetch = _tr_message("fetch detail: HTTP 500 server error")
    assert fetch == "Lỗi lấy chi tiết: HTTP 500 server error"


def test_message_empty() -> None:
    assert _tr_message("") == ""


def test_message_english_is_passthrough() -> None:
    set_language("en")
    assert _tr_message("missing required column 'X'") == "missing required column 'X'"
    assert _tr_message("created — A") == "Created — A"


# -- _tr_coerce_msg: the four coerce patterns -------------------------------------------


@pytest.mark.parametrize(
    ("english", "vietnamese"),
    [
        ("missing required column 'Ngày khám'", "thiếu cột bắt buộc 'Ngày khám'"),
        (
            "'Tuổi': cannot parse 'x' as int (bad literal)",
            "'Tuổi': không thể đọc 'x' thành int (bad literal)",
        ),
        ("pulse=200 outside expected range 30–220", "pulse=200 nằm ngoài phạm vi 30–220"),
        (
            "finishExaminationDate (a) is before examinationDate (b)",
            "finishExaminationDate (a) trước examinationDate (b)",
        ),
    ],
)
def test_coerce_msg_patterns(english: str, vietnamese: str) -> None:
    set_language("vi")
    assert _tr_coerce_msg(english) == vietnamese
    set_language("en")
    assert _tr_coerce_msg(english) == english


def test_coerce_msgs_preserves_warning_marker() -> None:
    set_language("vi")
    out = _tr_coerce_msgs("⚠ pulse=200 outside expected range 30–220")
    assert out == "⚠ pulse=200 nằm ngoài phạm vi 30–220"


def test_coerce_msgs_mixed_error_and_warning() -> None:
    set_language("vi")
    out = _tr_coerce_msgs("missing required column 'X'; ⚠ pulse=200 outside expected range 30–220")
    assert out == "thiếu cột bắt buộc 'X'; ⚠ pulse=200 nằm ngoài phạm vi 30–220"


# -- _tr_log: engine on_log strings ----------------------------------------------------


def test_log_first_search_response() -> None:
    set_language("vi")
    assert _tr_log("Logged first search response for inspection.") == (
        "Đã ghi phản hồi tìm kiếm đầu tiên để kiểm tra."
    )
    set_language("en")
    assert _tr_log("Logged first search response for inspection.") == (
        "Logged first search response for inspection."
    )


def test_log_retry_translated() -> None:
    set_language("vi")
    assert _tr_log("retry in 2.5s (attempt 3)") == "thử lại sau 2.5s (lần 3)"


def test_log_retry_english_passthrough() -> None:
    set_language("en")
    assert _tr_log("retry in 1.0s (attempt 2)") == "retry in 1.0s (attempt 2)"


# -- unmapped-columns warning (reader → validate table + run log) ----------------------

_UNMAPPED_EN = "ignoring 2 unmapped Excel column(s): 'A', 'B'"
_UNMAPPED_VI = "bỏ qua 2 cột Excel không có trong file mapping: 'A', 'B'"


def test_unmapped_columns_via_coerce_msg() -> None:
    set_language("vi")
    assert _tr_coerce_msg(_UNMAPPED_EN) == _UNMAPPED_VI
    set_language("en")
    assert _tr_coerce_msg(_UNMAPPED_EN) == _UNMAPPED_EN


def test_unmapped_columns_via_log() -> None:
    set_language("vi")
    assert _tr_log(_UNMAPPED_EN) == _UNMAPPED_VI
    set_language("en")
    assert _tr_log(_UNMAPPED_EN) == _UNMAPPED_EN


# -- file-level ConfigError shapes (missing / duplicate mapped columns) -----------------

# Exact shapes raised by excel/reader.py:_check_columns, including the long Found-headers dump.
_MISSING_RAW = (
    "Excel hssk_import.xlsx is missing mapped column(s): ['Mã hồ sơ']. "
    "Found headers: ['Mã định danh', 'Ngày khám', 'Bác sĩ']"
)
_DUP_RAW = (
    "Excel hssk_import.xlsx has duplicate mapped column header(s): ['Mã hồ sơ']. "
    "Only the right-most copy would be read — rename or remove the duplicates."
)


def test_file_error_missing_columns_condensed_and_localized() -> None:
    set_language("vi")
    out = _tr_coerce_msg(_MISSING_RAW)
    assert "Found headers" not in out  # the raw header dump is dropped
    assert "['Mã hồ sơ']" not in out and "'Mã hồ sơ'" in out  # brackets stripped
    assert out.startswith("File hssk_import.xlsx thiếu cột bắt buộc: 'Mã hồ sơ'")
    set_language("en")
    out_en = _tr_coerce_msg(_MISSING_RAW)
    assert "Found headers" not in out_en
    assert out_en.startswith("Excel hssk_import.xlsx is missing required column(s): 'Mã hồ sơ'")
    assert "Template button" in out_en


def test_file_error_duplicate_columns_localized() -> None:
    set_language("vi")
    out = _tr_coerce_msg(_DUP_RAW)
    assert out.startswith("File hssk_import.xlsx có tiêu đề cột bị trùng: 'Mã hồ sơ'")
    set_language("en")
    out_en = _tr_coerce_msg(_DUP_RAW)
    assert out_en.startswith("Excel hssk_import.xlsx has duplicate column header(s): 'Mã hồ sơ'")


def test_file_error_unknown_shape_passes_through() -> None:
    set_language("vi")
    assert _tr_file_error("Excel foo.xlsx something else entirely") is None
    assert _tr_file_error("some raw API diagnostic") is None
    # via the coerce path, an unmatched message is returned unchanged
    assert _tr_coerce_msg("Excel foo.xlsx something else entirely") == (
        "Excel foo.xlsx something else entirely"
    )


def test_log_no_record_id() -> None:
    set_language("vi")
    assert _tr_log("row 5: no record id in server response") == (
        "dòng 5: máy chủ không trả về mã hồ sơ"
    )
    set_language("en")
    assert _tr_log("row 5: no record id in server response") == (
        "row 5: no record id in server response"
    )


def test_log_ledger_corrupt() -> None:
    set_language("vi")
    assert _tr_log("2 unreadable ledger line(s) — those rows may be re-sent") == (
        "2 dòng nhật ký gửi (ledger) không đọc được — các hàng đó có thể bị gửi lại"
    )
    set_language("en")
    assert _tr_log("2 unreadable ledger line(s) — those rows may be re-sent") == (
        "2 unreadable ledger line(s) — those rows may be re-sent"
    )


def test_log_saved_search_response() -> None:
    set_language("vi")
    assert _tr_log("saved search response for row 3 (search_response_row_3.json)") == (
        "đã lưu phản hồi tìm kiếm cho dòng 3 (search_response_row_3.json)"
    )
    set_language("en")
    assert _tr_log("saved search response for row 3 (search_response_row_3.json)") == (
        "saved search response for row 3 (search_response_row_3.json)"
    )


def test_log_token_short_for_batch() -> None:
    msg = (
        "token may expire before this batch finishes "
        "(~7 min needed, ~2 min left) — consider logging in again first"
    )
    set_language("vi")
    assert _tr_log(msg) == (
        "⚠ Token có thể hết hạn trước khi chạy xong lô này "
        "(cần ~7 phút, còn ~2 phút) — nên đăng nhập lại trước khi chạy"
    )
    set_language("en")
    assert _tr_log(msg) == msg


def test_log_unknown_passes_through() -> None:
    set_language("vi")
    raw = "some raw API diagnostic"
    assert _tr_log(raw) == raw


# -- _tr_login_status: browser-login progress strings -----------------------------------


def test_login_status_known_strings() -> None:
    set_language("vi")
    assert _tr_login_status("Please log in in the browser window…") == (
        "Vui lòng đăng nhập trong cửa sổ trình duyệt…"
    )
    assert _tr_login_status("Token captured.") == "Đã lấy token."


def test_login_status_english_passthrough() -> None:
    set_language("en")
    assert _tr_login_status("Please log in in the browser window…") == (
        "Please log in in the browser window…"
    )
    assert _tr_login_status("Token captured.") == "Token captured."


def test_login_status_unknown_passes_through() -> None:
    set_language("vi")
    raw = "Some unexpected engine message"
    assert _tr_login_status(raw) == raw


# -- v1.4.0 keys resolve in both languages ----------------------------------------------

_V140_KEYS = [
    "msg_no_record_id",
    "log_no_record_id",
    "log_ledger_corrupt",
    "log_saved_search_response",
    "log_token_short_for_batch",
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
    from hssk_gui.i18n import tr

    for lang in ("vi", "en"):
        set_language(lang)
        for key in _V140_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


# -- UI-polish round: labeled counter keys ------------------------------------------------

_UI_POLISH_KEYS = [
    "counter_ok",
    "counter_skipped",
    "counter_failed",
    "counter_aborted",
    "counter_valid",
    "counter_warns",
    "counter_invalid",
    "msg_validation_done",
    "msg_missing_columns",
    "msg_duplicate_columns",
]


def test_ui_polish_keys_resolve_in_both_languages() -> None:
    from hssk_gui.i18n import tr

    for lang in ("vi", "en"):
        set_language(lang)
        for key in _UI_POLISH_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


# -- delete-mode keys resolve in both languages -----------------------------------------

_DELETE_KEYS = [
    "mode_delete",
    "btn_start_delete_live",
    "banner_production_delete",
    "msg_confirm_push_delete",
    "status_DELETED",
    "msg_row_deleted",
    "dlg_delete_needs_record_id",
    "msg_delete_needs_record_id",
]


def test_delete_keys_resolve_in_both_languages() -> None:
    from hssk_gui.i18n import tr

    for lang in ("vi", "en"):
        set_language(lang)
        for key in _DELETE_KEYS:
            assert tr(key) != key, f"missing {lang} entry for {key}"


# -- ValidationSummary contract ---------------------------------------------------------


def test_validation_summary_not_cancelled_by_default() -> None:
    # _on_validate_finished relies on this default: a normal full pass marks the file
    # validated; only an explicitly cancelled pass leaves it unvalidated.
    assert ValidationSummary(valid=1, invalid=0, warns=0, total=1).cancelled is False
