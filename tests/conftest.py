from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from openpyxl import Workbook

from hssk.mapping import MappingConfig, load_mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MAPPING = REPO_ROOT / "config" / "mapping.example.yaml"


@pytest.fixture
def mapping() -> MappingConfig:
    return load_mapping(EXAMPLE_MAPPING)


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    """A tiny workbook matching the example mapping's headers."""
    wb = Workbook()
    ws = wb.active
    headers = [
        "Mã định danh",
        "Ngày khám",
        "Giờ kết thúc",
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
    ws.append(headers)
    ws.append(
        [
            "2700020596A",
            dt.datetime(2026, 6, 17),
            dt.datetime(2026, 6, 17, 8, 56, 0),
            80,
            36.8,
            110,
            70,
            20,
            18,
            140,
            None,  # BMI blank -> auto-calc
            60,
            60,
            10,
            10,
            10,
            10,
        ]
    )
    path = tmp_path / "sample.xlsx"
    wb.save(path)
    return path
