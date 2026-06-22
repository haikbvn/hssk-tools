from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hssk.errors import ConfigError
from hssk.mapping import load_mapping


def test_example_mapping_loads(mapping):
    assert mapping.identifier.column == "Mã định danh"
    assert mapping.columns["Mã định danh"].target == "medicalIdentifierCode"
    assert "healthfacilitiesId" not in mapping.defaults.medicalRecordInfo
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


# -- update overlay merge --------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MAPPING = REPO_ROOT / "config" / "mapping.example.yaml"
EXAMPLE_OVERLAY = REPO_ROOT / "config" / "mapping.update.example.yaml"


def test_create_mapping_has_no_record_id_column():
    """The base example must not map medicalRecordId — create payloads keep it null."""
    m = load_mapping(EXAMPLE_MAPPING)
    assert not any(spec.target == "medicalRecordId" for spec in m.columns.values())


def test_bundled_overlay_adds_required_record_id():
    """Loading the base with the bundled overlay yields a required medicalRecordId column."""
    m = load_mapping(EXAMPLE_MAPPING, overlay_path=EXAMPLE_OVERLAY)
    assert any(spec.target == "medicalRecordId" and spec.required for spec in m.columns.values())


def test_overlay_missing_is_noop(tmp_path: Path):
    """A non-existent overlay path loads the base unchanged (no error)."""
    m = load_mapping(EXAMPLE_MAPPING, overlay_path=tmp_path / "nope.yaml")
    assert not any(spec.target == "medicalRecordId" for spec in m.columns.values())


def test_overlay_base_wins_on_collision(tmp_path: Path):
    """If the base already maps the overlay's column key, the base spec is kept."""
    base = tmp_path / "base.yaml"
    base.write_text(
        textwrap.dedent(
            """
            identifier: { column: "Mã định danh" }
            columns:
              "Mã định danh": { target: medicalIdentifierCode, type: str, required: true }
              "Mã hồ sơ": { target: medicalRecordId, type: int, required: true }
            """
        ),
        encoding="utf-8",
    )
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        'columns:\n  "Mã hồ sơ": { target: pulse, type: int }\n',
        encoding="utf-8",
    )
    m = load_mapping(base, overlay_path=overlay)
    assert m.columns["Mã hồ sơ"].target == "medicalRecordId"
    assert m.columns["Mã hồ sơ"].required is True


def test_overlay_result_is_validated_as_whole(tmp_path: Path):
    """A structurally bad column introduced only via the overlay still fails validation."""
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        'columns:\n  "Mã hồ sơ": { target: medicalRecordId, type: bogus }\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_mapping(EXAMPLE_MAPPING, overlay_path=overlay)
