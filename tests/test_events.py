"""events.render_en must reproduce the pre-refactor engine English byte-for-byte.

The golden file (tests/golden/vi_messages_golden.json) was captured from the old messages.py; its
``raw`` field is exactly what the engine used to emit and what the CLI/reports still print. For
each golden label we rebuild the equivalent typed Msg and assert render_en matches ``raw`` (the
range-warning golden carries a leading "⚠ " display marker that is not part of the message).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hssk.events import MessageCode, Msg, render_en

GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "vi_messages_golden.json").read_text(encoding="utf-8")
)


# label -> the typed Msg that must render to the golden's raw English.
def _cases() -> dict[str, Msg]:
    C = MessageCode
    who = "Nguyễn Thị Hoa"
    q = "'027148003240'"
    return {
        "row_created_bare": Msg(C.ROW_CREATED),
        "row_created_who": Msg(C.ROW_CREATED, {"who": who}),
        "row_updated_bare": Msg(C.ROW_UPDATED),
        "row_updated_who": Msg(C.ROW_UPDATED, {"who": who}),
        "row_deleted_bare": Msg(C.ROW_DELETED),
        "row_deleted_who": Msg(C.ROW_DELETED, {"who": who}),
        "row_dryrun_bare": Msg(C.ROW_DRY_RUN),
        "row_dryrun_who": Msg(C.ROW_DRY_RUN, {"who": who}),
        "row_created_no_rid": Msg(C.ROW_CREATED, {"who": who, "no_record_id": True}),
        "row_created_bare_no_rid": Msg(C.ROW_CREATED, {"no_record_id": True}),
        "row_already": Msg(C.ROW_ALREADY_PROCESSED),
        "row_id_blank": Msg(C.ROW_ID_BLANK),
        "row_recordid_blank": Msg(C.ROW_RECORD_ID_BLANK),
        "row_coercion_error": Msg(
            C.ROW_COERCE_ERROR, detail="'Tuổi': cannot parse 'abc' as int (bad)"
        ),
        "row_fetch_detail": Msg(C.ROW_FETCH_DETAIL_FAILED, detail="HTTP 404"),
        "row_no_patient": Msg(C.ROW_NO_PATIENT, {"query": q}),
        "row_multi_match": Msg(C.ROW_MULTI_MATCH, {"count": "2", "query": q}),
        "row_multi_match_skip": Msg(
            C.ROW_MULTI_MATCH, {"count": "2", "query": q, "skipping": True}
        ),
        "row_match_no_pid": Msg(C.ROW_MATCH_NO_PATIENT_ID, {"query": q}),
        "coerce_cannot_parse": Msg(
            C.COERCE_CANNOT_PARSE, {"col": "'Tuổi'", "value": "'abc'", "type": "int"}, "invalid"
        ),
        "coerce_range_warn": Msg(
            C.COERCE_RANGE, {"target": "Mạch", "value": "250", "lo": "30", "hi": "200"}
        ),
        "coerce_date_before": Msg(
            C.COERCE_DATE_BEFORE, {"finish": "17/06/2026", "start": "18/06/2026"}
        ),
        "coerce_missing_required": Msg(C.COERCE_MISSING_REQUIRED, {"col": "'Mã định danh'"}),
        "file_missing_columns": Msg(
            C.FILE_MISSING_COLUMNS,
            {"name": "foo.xlsx", "missing": ["Mã hồ sơ"], "headers": ["A", "B"]},
        ),
        "file_duplicate_columns": Msg(
            C.FILE_DUPLICATE_COLUMNS, {"name": "foo.xlsx", "dups": ["X"]}
        ),
        "coerce_unmapped": Msg(C.LOG_UNMAPPED_COLUMNS, {"n": "2", "cols": "'A', 'B'"}),
        "log_first_search": Msg(C.LOG_FIRST_SEARCH_SAVED),
        "log_retry": Msg(C.LOG_RETRY, {"delay": "2.5", "attempt": "3"}),
        "log_no_record_id": Msg(C.LOG_NO_RECORD_ID, {"row": "5"}),
        "log_ledger_corrupt": Msg(C.LOG_LEDGER_CORRUPT, {"n": "3"}),
        "log_saved_search": Msg(
            C.LOG_SEARCH_SAVED_ROW, {"row": "5", "filename": "search_response_row_5.json"}
        ),
        "log_unmapped": Msg(C.LOG_UNMAPPED_COLUMNS, {"n": "2", "cols": "'A', 'B'"}),
        "log_token_short": Msg(C.LOG_TOKEN_SHORT, {"needed": "10", "left": "5"}),
        "login_waiting": Msg(C.LOGIN_WAITING),
        "login_captured": Msg(C.LOGIN_TOKEN_CAPTURED),
    }


CASES = _cases()


def test_every_golden_label_has_a_case():
    assert set(CASES) == set(GOLDEN["messages"]), "events test cases drifted from the golden labels"


@pytest.mark.parametrize("label", sorted(CASES))
def test_render_en_matches_golden_raw(label: str):
    expected = GOLDEN["messages"][label]["raw"]
    expected = expected.removeprefix("⚠ ")  # the range-warning display marker is not the message
    assert render_en(CASES[label]) == expected
