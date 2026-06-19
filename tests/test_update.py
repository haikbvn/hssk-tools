from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from openpyxl import Workbook

from hssk.api import exams, records
from hssk.config import Settings
from hssk.errors import ConfigError
from hssk.mapping import load_mapping
from hssk.pipeline import runner
from hssk.pipeline.runner import Status

BASE = "https://api.test"


def _settings(tmp: Path) -> Settings:
    return Settings(base_url=BASE, request_delay=0.0, jitter=0.0, data_dir=tmp)


def _make_update_mapping(tmp: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    base = yaml.safe_load((repo / "config" / "mapping.example.yaml").read_text(encoding="utf-8"))
    base["columns"]["Mã hồ sơ"] = {"target": "medicalRecordId", "type": "int", "required": True}
    p = tmp / "mapping_update.yaml"
    p.write_text(yaml.dump(base, allow_unicode=True), encoding="utf-8")
    return p


def _make_xlsx(tmp: Path, record_id: int = 388261169) -> Path:
    wb = Workbook()
    ws = wb.active
    headers = [
        "Mã định danh",
        "Ngày khám",
        "Giờ kết thúc",
        "Mã hình thức khám",
        "Mã đối tượng khám",
        "Lý do khám",
        "Bệnh sử",
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
        "Chẩn đoán",
        "Bệnh kèm theo",
        "Bệnh theo dõi",
        "Tư vấn điều trị",
        "Mã kết quả khám",
        "Mã tình trạng ra viện",
        "Bác sĩ",
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
        "Mã hồ sơ",
    ]
    ws.append(headers)
    ws.append(
        [
            "2700020596A",
            "17/06/2026",
            "17/06/2026",
            100,
            93,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "0000 - Bình thường",
            None,
            None,
            None,
            3,
            1,
            "Nguyễn Thị Hoa",
            75,
            37.0,
            120,
            80,
            18,
            60,
            165,
            None,
            72,
            None,
            None,
            None,
            None,
            None,
            record_id,
        ]
    )
    p = tmp / "in.xlsx"
    wb.save(p)
    return p


# Flat shape matching the real /health-examination/get-detail response.
_DETAIL_RESPONSE = {
    "medicalRecordInfo": {
        "medicalRecordId": 388261169,
        "patientId": 372954970,
        "medicalIdentifierCode": "2700020596A",
        "examinationDate": "02/12/2024 15:31:00",
        "treatmentDirection": "Không",
        "healthfacilitiesId": "27084",
        "doctorName": "Nguyễn Thị Hoa",
        "noteDisease": "Không",
    },
    "medicalPatientDetailInfo": {
        "patientDetailId": None,
        "pulse": 80,
        "temperature": 36.8,
        "bloodPressureMax": None,
        "bloodPressureMin": None,
        "breath": 20,
        "weight": 60,
        "height": 165,
        "bmi": None,
        "waistCircumference": None,
        "chestCircumference": None,
        "leftEyeGlasses": None,
        "leftEyeNoGlasses": None,
        "rightEyeGlasses": None,
        "rightEyeNoGlasses": None,
    },
    "serviceList": [],
    "drugList": [],
    "deletedServiceIds": [],
    "deletedDrugIds": [],
}


@respx.mock
def test_dry_run_writes_payload_no_post(tmp_path):
    mapping = load_mapping(_make_update_mapping(tmp_path))
    respx.get(f"{BASE}{records.DETAIL_PATH}/388261169").mock(
        return_value=httpx.Response(200, json=_DETAIL_RESPONSE)
    )
    update_route = respx.post(f"{BASE}{records.UPDATE_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )
    xlsx = _make_xlsx(tmp_path)

    summary = runner.run_update(
        xlsx, mapping, token="t", dry_run=True, settings=_settings(tmp_path)
    )

    assert summary.counts.get(Status.DRY_RUN_OK) == 1
    assert update_route.call_count == 0
    assert (summary.run_dir / "payloads" / "row_2.json").exists()
    assert (summary.run_dir / "results.xlsx").exists()


@respx.mock
def test_commit_calls_update_not_create(tmp_path):
    mapping = load_mapping(_make_update_mapping(tmp_path))
    respx.get(f"{BASE}{records.DETAIL_PATH}/388261169").mock(
        return_value=httpx.Response(200, json=_DETAIL_RESPONSE)
    )
    update_route = respx.post(f"{BASE}{records.UPDATE_PATH}").mock(
        return_value=httpx.Response(200, json={"data": {"medicalRecordId": 388261169}})
    )
    create_route = respx.post(f"{BASE}{exams.CREATE_PATH}").mock(
        return_value=httpx.Response(200, json={})
    )
    xlsx = _make_xlsx(tmp_path)

    summary = runner.run_update(
        xlsx, mapping, token="t", dry_run=False, settings=_settings(tmp_path)
    )

    assert summary.counts.get(Status.UPDATED) == 1
    assert update_route.call_count == 1
    assert create_route.call_count == 0
    assert summary.outcomes[0].record_id == 388261169


@respx.mock
def test_detail_fetch_failure_is_per_row_not_batch_abort(tmp_path):
    mapping = load_mapping(_make_update_mapping(tmp_path))
    respx.get(f"{BASE}{records.DETAIL_PATH}/388261169").mock(
        return_value=httpx.Response(404, text="not found")
    )
    xlsx = _make_xlsx(tmp_path)

    summary = runner.run_update(
        xlsx, mapping, token="t", dry_run=False, settings=_settings(tmp_path)
    )

    assert not summary.aborted
    assert summary.counts.get(Status.FAILED) == 1


@respx.mock
def test_auth_expired_on_detail_aborts_batch(tmp_path):
    mapping = load_mapping(_make_update_mapping(tmp_path))
    respx.get(f"{BASE}{records.DETAIL_PATH}/388261169").mock(return_value=httpx.Response(401))
    xlsx = _make_xlsx(tmp_path)

    summary = runner.run_update(
        xlsx, mapping, token="t", dry_run=False, settings=_settings(tmp_path)
    )

    assert summary.aborted
    assert summary.counts.get(Status.AUTH_EXPIRED) == 1


def test_missing_record_id_column_raises_config_error(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    mapping = load_mapping(repo / "config" / "mapping.example.yaml")

    with pytest.raises(ConfigError, match="medicalRecordId"):
        runner.run_update("nonexistent.xlsx", mapping, token="t", settings=_settings(tmp_path))


@respx.mock
def test_vitals_and_record_id_in_posted_payload(tmp_path):
    """The posted update body must carry the Excel row's vitals and the stamped medicalRecordId."""
    mapping = load_mapping(_make_update_mapping(tmp_path))
    respx.get(f"{BASE}{records.DETAIL_PATH}/388261169").mock(
        return_value=httpx.Response(200, json=_DETAIL_RESPONSE)
    )
    captured: list[dict] = []

    def _capture(request, route):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"medicalRecordId": 388261169}})

    respx.post(f"{BASE}{records.UPDATE_PATH}").mock(side_effect=_capture)
    xlsx = _make_xlsx(tmp_path)

    runner.run_update(xlsx, mapping, token="t", dry_run=False, settings=_settings(tmp_path))

    assert len(captured) == 1
    payload = captured[0]
    detail = payload["medicalPatientDetailInfo"]
    assert detail["pulse"] == 75  # Excel row value, not the fetched 80
    assert detail["temperature"] == 37.0  # Excel row value, not the fetched 36.8
    assert payload["medicalRecordInfo"]["medicalRecordId"] == 388261169
    assert payload["deletedServiceIds"] == []
    assert payload["deletedDrugIds"] == []
