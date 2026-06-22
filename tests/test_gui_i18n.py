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
from hssk_gui.messages import _tr_coerce_msg, _tr_coerce_msgs, _tr_message, _tr_status
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
    assert _tr_message("payload built (not sent) — Le C") == "Đã dựng dữ liệu (chưa gửi) — Le C"


def test_message_coercion_prefix() -> None:
    set_language("vi")
    out = _tr_message("coercion error: missing required column 'Ngày khám'")
    assert out == "Lỗi chuyển đổi: thiếu cột bắt buộc 'Ngày khám'"


def test_message_bare_compound_coerce_errors() -> None:
    # The runner joins coerced.errors with "; " and emits them with no prefix.
    set_language("vi")
    out = _tr_message("missing required column 'X'; 'Tuổi': cannot parse 'a' as int")
    assert out == "thiếu cột bắt buộc 'X'; 'Tuổi': không thể đọc 'a' thành int"


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


# -- ValidationSummary contract ---------------------------------------------------------


def test_validation_summary_not_cancelled_by_default() -> None:
    # _on_validate_finished relies on this default: a normal full pass marks the file
    # validated; only an explicitly cancelled pass leaves it unvalidated.
    assert ValidationSummary(valid=1, invalid=0, warns=0, total=1).cancelled is False
