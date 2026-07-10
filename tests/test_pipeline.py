from __future__ import annotations

from pathlib import Path

import httpx
import respx
from openpyxl import Workbook

from hssk.api import exams, patients
from hssk.config import Settings
from hssk.events import MessageCode, render_en
from hssk.pipeline import runner
from hssk.pipeline.ledger import Ledger
from hssk.pipeline.runner import Status

BASE = "https://api.test"


def _settings(tmp: Path) -> Settings:
    return Settings(base_url=BASE, request_delay=0.0, jitter=0.0, data_dir=tmp)


_ALL_HEADERS = [
    # key + dates
    "Mã định danh",
    "Ngày khám",
    "Giờ kết thúc",
    # exam meta
    "Mã hình thức khám",
    "Mã đối tượng khám",
    "Lý do khám",
    "Bệnh sử",
    # organ descriptions
    "Da niêm mạc",
    "Toàn thân khác",
    "Tim mạch",
    "Hô hấp",
    "Tiêu hoá",
    "Thận, tiết niệu",
    "Tâm thần - Thần kinh",
    "Cơ xương khớp",
    "Nội tiết",
    "Bệnh máu",
    "Ngoại khoa",
    "Sản phụ khoa",
    "Tai mũi họng",
    "Răng hàm mặt",
    "Mắt",
    "Da liễu",
    "Dinh dưỡng",
    "Vận động",
    "Đánh giá phát triển thể chất",
    "Cơ quan khác",
    # diagnosis / treatment
    "Chẩn đoán",
    "Bệnh kèm theo",
    "Bệnh theo dõi",
    "Tư vấn điều trị",
    "Mã kết quả khám",
    "Mã tình trạng ra viện",
    # doctor
    "Bác sĩ",
    # vitals
    "Mạch",
    "Nhiệt độ",
    "HA tối đa",
    "HA tối thiểu",
    "Nhịp thở",
    "Cân nặng",
    "Chiều cao",
    "BMI",
    "Vòng bụng",
    "Vòng ngực",
    "Mắt trái (kính)",
    "Mắt trái (không kính)",
    "Mắt phải (kính)",
    "Mắt phải (không kính)",
]


# Row values aligned with _ALL_HEADERS — None for unused optional cells.
def _make_row(identifier, exam_date="17/06/2026", finish="17/06/2026"):
    return [
        identifier,
        exam_date,
        finish,
        100,
        93,
        None,
        None,  # exam meta (required: typeOfExamination, reasonCode)
        None,
        None,
        None,
        None,
        None,  # organ descs 1–5
        None,
        None,
        None,
        None,
        None,  # organ descs 6–10
        None,
        None,
        None,
        None,
        None,  # organ descs 11–15
        None,
        None,
        None,
        None,
        None,  # organ descs 16–20
        "0000 - Bình thường",
        None,
        None,
        None,  # diagnosesDischarge (req), list, notes, direction
        3,
        1,  # treatmentResultId, dischargeStatusId (required)
        "Nguyễn Thị Hoa",  # doctorName (required)
        80,
        36.8,
        110,
        70,
        20,
        18,
        140,
        None,  # weight / height / BMI (auto-calc)
        60,
        60,
        10,
        10,
        10,
        10,
    ]


def _two_row_xlsx(tmp: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(_ALL_HEADERS)
    ws.append(_make_row("2700020596A"))
    ws.append(_make_row(None))  # missing identifier → INVALID
    path = tmp / "in.xlsx"
    wb.save(path)
    return path


def _two_valid_row_xlsx(tmp: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(_ALL_HEADERS)
    ws.append(_make_row("2700020596A"))
    ws.append(_make_row("2700020597B"))
    path = tmp / "in_valid.xlsx"
    wb.save(path)
    return path


def _mock_search(found: bool):
    content = [{"patientId": 372954970, "medicalIdentifierCode": "2700020596A"}] if found else []
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"content": content}})
    )


@respx.mock
def test_create_then_skip_on_rerun(mapping, tmp_path):
    _mock_search(found=True)
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 555}})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    led = Ledger(tmp_path / "ledger.jsonl")

    summary = runner.run(xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led)
    assert summary.created == 1
    assert summary.counts.get(Status.INVALID) == 1  # the blank-identifier row
    assert (tmp_path / "ledger.jsonl").exists()

    # Re-run with a freshly loaded ledger -> the created row is now skipped.
    led2 = Ledger.load(tmp_path / "ledger.jsonl")
    summary2 = runner.run(xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led2)
    assert summary2.counts.get(Status.SKIPPED_ALREADY) == 1
    assert summary2.created == 0


@respx.mock
def test_no_patient(mapping, tmp_path):
    _mock_search(found=False)
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    logs: list[str] = []
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=False,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
        callbacks=runner.Callbacks(on_log=lambda e: logs.append(render_en(e))),
    )
    assert summary.counts.get(Status.NO_PATIENT) == 1
    # The failed lookup's exact server response is kept for debugging.
    assert (summary.run_dir / "search_response_row_2.json").exists()
    assert any(m.startswith("saved search response for row 2") for m in logs)


@respx.mock
def test_multi_match_response_is_dumped(mapping, tmp_path):
    content = [
        {"patientId": 1, "medicalIdentifierCode": "A"},
        {"patientId": 2, "medicalIdentifierCode": "B"},
    ]
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"content": content}})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert summary.counts.get(Status.MULTI_MATCH) == 1
    assert (summary.run_dir / "search_response_row_2.json").exists()


@respx.mock
def test_api_error_during_search_is_recorded_not_aborted(mapping, tmp_path):
    """A non-retryable 4xx from the search endpoint becomes FAILED, not a batch crash."""
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(400, json={"message": "bad request"})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=False,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert not summary.aborted
    assert summary.counts.get(Status.FAILED) == 1
    assert summary.counts.get(Status.INVALID) == 1  # the blank-identifier row


def test_unexpected_coercion_error_yields_invalid_not_crash(mapping, tmp_path, monkeypatch):
    """An exception from coerce_row must produce Status.INVALID, not abort the batch."""
    from hssk.pipeline import runner as runner_mod

    def _boom(raw, m, idx):
        raise RuntimeError("simulated unexpected error")

    monkeypatch.setattr(runner_mod, "coerce_row", _boom)

    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    # Both rows become INVALID; the batch does not crash.
    assert not summary.aborted
    assert summary.counts.get(Status.INVALID, 0) == 2


@respx.mock
def test_corrupt_ledger_line_warns_on_run(mapping, tmp_path):
    """A truncated/corrupt ledger line surfaces a warning — those rows may be re-sent."""
    _mock_search(found=True)
    ledger_file = tmp_path / "ledger.jsonl"
    ledger_file.write_text('{"key": "truncated by a crash', encoding="utf-8")
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    logs: list[str] = []
    runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger.load(ledger_file),
        callbacks=runner.Callbacks(on_log=lambda e: logs.append(render_en(e))),
    )
    assert any("1 unreadable ledger line(s)" in m for m in logs)


@respx.mock
def test_create_without_record_id_still_created_but_warns(mapping, tmp_path):
    """A create response with no recognisable id succeeds but flags the missing id."""
    _mock_search(found=True)
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(return_value=httpx.Response(200, json={}))
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    logs: list[str] = []
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=False,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
        callbacks=runner.Callbacks(on_log=lambda e: logs.append(render_en(e))),
    )
    assert summary.created == 1
    outcome = next(o for o in summary.outcomes if o.status is Status.CREATED)
    assert outcome.record_id is None
    assert outcome.message.endswith(" (no record id returned)")
    assert any("no record id in server response" in m for m in logs)


@respx.mock
def test_bad_default_key_yields_invalid_via_gate(mapping, tmp_path):
    """A typo in the mapping's `defaults` block (which validate_targets never checks) is caught by
    the pydantic gate: the row becomes INVALID with ROW_PAYLOAD_INVALID, not a silent bad send."""
    _mock_search(found=True)
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 1}})
    )
    bad = mapping.model_copy(deep=True)
    bad.defaults.medicalRecordInfo["symptomss"] = "typo"  # unknown field
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx, bad, token="t", dry_run=True, settings=s, ledger=Ledger(tmp_path / "l.jsonl")
    )
    # The valid row is INVALID (gate); the blank-identifier row is INVALID too → 2 total, 0 ok.
    assert summary.counts.get(Status.INVALID) == 2
    assert summary.counts.get(Status.DRY_RUN_OK) is None
    assert create_route.call_count == 0
    invalid = next(
        o for o in summary.outcomes if o.status is Status.INVALID and o.identifier == "2700020596A"
    )
    assert invalid.msgs[0].code == MessageCode.ROW_PAYLOAD_INVALID
    assert "symptomss" in (invalid.msgs[0].detail or "")


@respx.mock
def test_drifted_search_shape_emits_one_drift_log(mapping, tmp_path):
    """An unrecognised search-response shape emits exactly one LOG_DRIFT for the endpoint (deduped
    across rows) and the rows fall through as NO_PATIENT."""
    respx.post(f"{BASE}{patients.SEARCH_PATH}").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    xlsx = _two_valid_row_xlsx(tmp_path)  # two rows both hit search
    s = _settings(tmp_path)
    events: list = []
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
        callbacks=runner.Callbacks(on_log=lambda e: events.append(e)),
    )
    drift = [e for e in events if e.code == MessageCode.LOG_DRIFT]
    assert len(drift) == 1  # deduped: two drifting rows, one warning
    assert drift[0].params["endpoint"] == patients.SEARCH_PATH
    assert drift[0].level == "warning"
    assert summary.counts.get(Status.NO_PATIENT) == 2


@respx.mock
def test_no_drift_on_legitimate_empty_search(mapping, tmp_path):
    """A well-formed but empty search response is a normal no-match — never a drift warning."""
    _mock_search(found=False)  # {"data": {"content": []}} — located but empty
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    events: list = []
    runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
        callbacks=runner.Callbacks(on_log=lambda e: events.append(e)),
    )
    assert not [e for e in events if e.code == MessageCode.LOG_DRIFT]


@respx.mock
def test_dry_run_writes_payload_and_does_not_create(mapping, tmp_path):
    _mock_search(found=True)
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=True,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert summary.counts.get(Status.DRY_RUN_OK) == 1
    assert create_route.call_count == 0
    # Every emitted outcome carries a parseable recording timestamp.
    from datetime import datetime

    for o in summary.outcomes:
        assert o.timestamp
        datetime.fromisoformat(o.timestamp)
    assert (summary.run_dir / "payloads" / "row_2.json").exists()
    assert (summary.run_dir / "results.xlsx").exists()
    # No failed lookups → no per-row search-response dumps.
    assert not list(summary.run_dir.glob("search_response_row_*.json"))


# -- Plan 004: write-ahead "pending" ledger marker closes the duplicate-create window --


@respx.mock
def test_interrupted_send_leaves_pending_marker_and_second_run_makes_no_create_call(
    mapping, tmp_path
):
    """THE REGRESSION CASE. If the create request is sent but the response never arrives (here
    simulated as an ApiError from the send call), the write-ahead marker written just before the
    send must survive in the ledger. A later run must NOT silently re-create the row — it must
    surface PENDING_VERIFY and, critically, must not call the create endpoint again."""
    _mock_search(found=True)
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(400, json={"message": "simulated interrupted send"})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    ledger_file = tmp_path / "ledger.jsonl"

    summary1 = runner.run(
        xlsx, mapping, token="t", dry_run=False, settings=s, ledger=Ledger(ledger_file)
    )
    assert summary1.counts.get(Status.FAILED) == 1
    assert create_route.call_count == 1
    assert ledger_file.exists()
    lines = ledger_file.read_text(encoding="utf-8").splitlines()
    assert any('"pending": true' in ln for ln in lines)

    led2 = Ledger.load(ledger_file)
    summary2 = runner.run(xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led2)
    assert summary2.counts.get(Status.PENDING_VERIFY) == 1
    assert summary2.created == 0
    # The whole point: no second create call was made for the pending row.
    assert create_route.call_count == 1


@respx.mock
def test_retry_pending_resends_and_upgrades_ledger_then_third_run_skips(mapping, tmp_path):
    _mock_search(found=True)
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        side_effect=[
            httpx.Response(400, json={"message": "simulated interrupted send"}),
            httpx.Response(200, json={"data": {"medicalRecordId": 555}}),
        ]
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    ledger_file = tmp_path / "ledger.jsonl"

    summary1 = runner.run(
        xlsx, mapping, token="t", dry_run=False, settings=s, ledger=Ledger(ledger_file)
    )
    assert summary1.counts.get(Status.FAILED) == 1

    led2 = Ledger.load(ledger_file)
    summary2 = runner.run(
        xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led2, retry_pending=True
    )
    assert summary2.created == 1
    assert create_route.call_count == 2

    led3 = Ledger.load(ledger_file)
    summary3 = runner.run(xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led3)
    assert summary3.counts.get(Status.SKIPPED_ALREADY) == 1
    assert summary3.created == 0
    assert create_route.call_count == 2  # third run makes no new create call either


@respx.mock
def test_successful_commit_writes_pending_then_done_and_reruns_skip(mapping, tmp_path):
    _mock_search(found=True)
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 555}})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    ledger_file = tmp_path / "ledger.jsonl"

    summary = runner.run(
        xlsx, mapping, token="t", dry_run=False, settings=s, ledger=Ledger(ledger_file)
    )
    assert summary.created == 1

    lines = ledger_file.read_text(encoding="utf-8").splitlines()
    assert any('"pending": true' in ln for ln in lines)
    assert any('"recordId"' in ln for ln in lines)

    # Upgrade path: the key is done (not pending) once reloaded, so a re-run skips it.
    led2 = Ledger.load(ledger_file)
    summary2 = runner.run(xlsx, mapping, token="t", dry_run=False, settings=s, ledger=led2)
    assert summary2.counts.get(Status.SKIPPED_ALREADY) == 1
    assert summary2.created == 0


@respx.mock
def test_dry_run_writes_zero_ledger_lines(mapping, tmp_path):
    _mock_search(found=True)
    respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 555}})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    ledger_file = tmp_path / "ledger.jsonl"

    summary = runner.run(
        xlsx, mapping, token="t", dry_run=True, settings=s, ledger=Ledger(ledger_file)
    )
    assert summary.counts.get(Status.DRY_RUN_OK) == 1
    assert not ledger_file.exists()
