from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hssk.errors import ConfigError
from hssk.mapping import load_mapping


def test_example_mapping_loads(mapping):
    assert mapping.identifier.column == "Mã định danh"
    assert mapping.columns["Mã định danh"].target == "medicalIdentifierCode"
    assert mapping.defaults.medicalRecordInfo["healthfacilitiesId"] == "27084"
    assert mapping.search.multi_match == "skip"
    assert mapping.computed.bmi is not None
    assert mapping.computed.bmi.source == ["weight", "height"]


def test_identifier_must_map_to_code(tmp_path: Path):
    bad = tmp_path / "m.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            identifier: { column: "ID" }
            columns:
              "ID": { target: pulse, type: int }
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_mapping(bad)
    assert "medicalIdentifierCode" in str(exc.value)


def test_identifier_must_be_required(tmp_path: Path):
    bad = tmp_path / "m.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            identifier: { column: "ID" }
            columns:
              "ID": { target: medicalIdentifierCode, type: str, required: false }
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc:
        load_mapping(bad)
    assert "required" in str(exc.value)


def test_missing_file():
    with pytest.raises(ConfigError):
        load_mapping("/no/such/mapping.yaml")
