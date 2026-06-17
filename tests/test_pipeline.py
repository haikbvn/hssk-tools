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


def _two_row_xlsx(tmp: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    headers = [
        "Mã định danh", "Ngày khám", "Giờ kết thúc", "Mạch", "Nhiệt độ",
        "HA tối đa", "HA tối thiểu", "Nhịp thở", "Cân nặng", "Chiều cao", "BMI",
        "Vòng bụng", "Vòng ngực", "Mắt trái (kính)", "Mắt trái (không kính)",
        "Mắt phải (kính)", "Mắt phải (không kính)",
    ]
    ws.append(headers)
    ws.append(["2700020596A", "17/06/2026", "17/06/2026", 80, 36.8, 110, 70, 20,
               18, 140, None, 60, 60, 10, 10, 10, 10])
    ws.append([None, "17/06/2026", "17/06/2026", 80, 36.8, 110, 70, 20,  # missing identifier
               18, 140, None, 60, 60, 10, 10, 10, 10])
    path = tmp / "in.xlsx"
    wb.save(path)
    return path


def _mock_search(found: bool):
    content = (
        [{"patientId": 372954970, "medicalIdentifierCode": "2700020596A"}] if found else []
    )
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
        xlsx, mapping, token="t", dry_run=False, settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert summary.counts.get(Status.NO_PATIENT) == 1


@respx.mock
def test_dry_run_writes_payload_and_does_not_create(mapping, tmp_path):
    _mock_search(found=True)
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )
    xlsx = _two_row_xlsx(tmp_path)
    s = _settings(tmp_path)
    summary = runner.run(
        xlsx, mapping, token="t", dry_run=True, settings=s,
        ledger=Ledger(tmp_path / "l.jsonl"),
    )
    assert summary.counts.get(Status.DRY_RUN_OK) == 1
    assert create_route.call_count == 0
    assert (summary.run_dir / "payloads" / "row_2.json").exists()
    assert (summary.run_dir / "results.xlsx").exists()
