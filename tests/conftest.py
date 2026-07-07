from __future__ import annotations

import os

# Must be set before any PySide6 import (conftest.py loads before test collection, so this is
# the earliest safe point) — lets pytest-qt's qapp/qtbot fixtures create a QApplication without
# a real display, on every machine including CI. A pre-existing QT_QPA_PLATFORM (e.g. a developer
# running tests against a real display on purpose) is left alone.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import datetime as dt
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend
from openpyxl import Workbook

from hssk.mapping import MappingConfig, load_mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MAPPING = REPO_ROOT / "config" / "mapping.example.yaml"


class _InMemoryKeyring(KeyringBackend):
    """A throwaway keychain backend so tests never touch (or prompt) the real OS keychain."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def _fake_keyring() -> object:
    """Swap in an empty in-memory keychain for every test (restored afterwards)."""
    prev = keyring.get_keyring()
    keyring.set_keyring(_InMemoryKeyring())
    try:
        yield
    finally:
        keyring.set_keyring(prev)


@pytest.fixture
def mapping() -> MappingConfig:
    return load_mapping(EXAMPLE_MAPPING)


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    """A tiny workbook matching the example mapping's headers."""
    wb = Workbook()
    ws = wb.active
    headers = [
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
    ws.append(headers)
    ws.append(
        [
            # key + dates
            "2700020596A",
            dt.datetime(2026, 6, 17),
            dt.datetime(2026, 6, 17, 8, 56, 0),
            # exam meta
            100,
            93,
            "Khám sức khoẻ",
            "Không",
            # organ descriptions (all normal)
            "Bình thường",  # bodySkinDesc
            "Bình thường",  # bodyOtherDesc
            "Bình thường",  # heartDesc
            "Bình thường",  # respiratoryDesc
            "Bình thường",  # digestDesc
            "Bình thường",  # urologyDesc
            "Bình thường",  # nerveDesc
            "Bình thường",  # osteoarthritisDesc
            "Bình thường",  # endocrineDesc
            "Bình thường",  # bloodDesc
            "Bình thường",  # surgeryDesc
            "Bình thường",  # maternityDesc
            "Bình thường",  # earNoseThroatDesc
            "Bình thường",  # toothDesc
            "Bình thường",  # eyeDesc
            "Bình thường",  # dermatologyDesc
            "Bình thường",  # nutritionDesc
            "Bình thường",  # motionDesc
            "Bình thường",  # physicalDesc
            "Bình thường",  # organsOtherDesc
            # diagnosis / treatment
            "0000 - Bình thường",  # diagnosesDischarge
            "0000 - Bình thường",  # diagnosesDischargeList
            "Không",  # noteDisease
            "Bình thường",  # treatmentDirection
            3,  # treatmentResultId
            1,  # dischargeStatusId
            # doctor
            "Nguyễn Thị Hoa",
            # vitals
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
