from __future__ import annotations

from pathlib import Path

import httpx
import respx
from openpyxl import Workbook

from hssk.api import exams, patients
from hssk.config import Settings
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
    summary = runner.run(
        xlsx,
        mapping,
        token="t",
        dry_run=False,
        settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert summary.counts.get(Status.NO_PATIENT) == 1


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
    assert (summary.run_dir / "payloads" / "row_2.json").exists()
    assert (summary.run_dir / "results.xlsx").exists()
