"""Tests for save_record_defaults — engine-side, no Qt."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hssk.errors import ConfigError
from hssk.mapping import load_mapping, save_record_defaults

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "mapping.example.yaml"


def _copy(tmp_path: Path) -> Path:
    dst = tmp_path / "mapping.yaml"
    shutil.copy(EXAMPLE, dst)
    return dst


def test_save_changes_doctor_and_facility(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    orig = load_mapping(p)
    updated_rec = {
        **orig.defaults.medicalRecordInfo,
        "doctorName": "Bác sĩ Test",
        "healthfacilitiesId": "99999",
    }
    save_record_defaults(
        p,
        record_info=updated_rec,
        normal_desc_value="Bình thường",
    )
    updated = load_mapping(p)
    assert updated.defaults.medicalRecordInfo["doctorName"] == "Bác sĩ Test"
    assert updated.defaults.medicalRecordInfo["healthfacilitiesId"] == "99999"


def test_save_changes_normal_desc_value(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    save_record_defaults(
        p,
        record_info=load_mapping(p).defaults.medicalRecordInfo,
        normal_desc_value="Không đánh giá",
    )
    updated = load_mapping(p)
    assert updated.defaults.normal_desc_value == "Không đánh giá"


def test_round_trip_preserves_comments_and_columns(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    save_record_defaults(
        p,
        record_info=load_mapping(p).defaults.medicalRecordInfo,
        normal_desc_value="Bình thường",
    )
    new_text = p.read_text(encoding="utf-8")
    # Comments and the columns block should be present.
    assert "# the Excel column holding medicalIdentifierCode" in new_text
    assert "medicalIdentifierCode" in new_text
    assert "columns:" in new_text
    # The original identifier column definition must survive.
    assert "Mã định danh" in new_text


def test_columns_structure_unchanged_after_save(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    orig_mapping = load_mapping(p)
    save_record_defaults(
        p,
        record_info=orig_mapping.defaults.medicalRecordInfo,
        normal_desc_value=orig_mapping.defaults.normal_desc_value,
    )
    new_mapping = load_mapping(p)
    assert new_mapping.columns.keys() == orig_mapping.columns.keys()
    assert new_mapping.identifier.column == orig_mapping.identifier.column


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        save_record_defaults(
            tmp_path / "does_not_exist.yaml",
            record_info={},
            normal_desc_value="x",
        )
