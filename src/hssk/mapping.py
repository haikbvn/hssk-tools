"""Load and validate ``mapping.yaml`` — the Excel-column → API-field map plus constants."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .errors import ConfigError

ColumnType = Literal["str", "int", "float", "str_num", "datetime"]


class ColumnSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    type: ColumnType = "str"
    required: bool = False
    out_format: str = "%d/%m/%Y %H:%M:%S"  # for datetime targets
    default_time: str | None = None  # "HH:MM:SS" applied when the cell holds only a date


class IdentifierSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str


class ComputedBmi(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: list[str] = Field(default_factory=lambda: ["weight", "height"], alias="from")
    only_if_missing: bool = True
    round: int = 2


class ComputedSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bmi: ComputedBmi | None = None


class SearchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profileStatus: str = "1"
    page: int = 1
    size: int = 20
    multi_match: Literal["skip", "first", "error"] = "skip"


class DefaultsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medicalRecordInfo: dict[str, Any] = Field(default_factory=dict)
    medicalPatientDetailInfo: dict[str, Any] = Field(default_factory=dict)
    normal_desc_value: str = "Bình thường"


class MappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: str | None = None
    header_row: int = 1
    identifier: IdentifierSpec
    columns: dict[str, ColumnSpec]
    computed: ComputedSpec = Field(default_factory=ComputedSpec)
    search: SearchSpec = Field(default_factory=SearchSpec)
    defaults: DefaultsSpec = Field(default_factory=DefaultsSpec)

    @model_validator(mode="after")
    def _check_identifier(self) -> MappingConfig:
        col = self.identifier.column
        spec = self.columns.get(col)
        if spec is None:
            raise ValueError(
                f"identifier.column {col!r} is not defined under columns:"
            )
        if spec.target != "medicalIdentifierCode":
            raise ValueError(
                f"identifier column {col!r} must map to target 'medicalIdentifierCode', "
                f"got {spec.target!r}"
            )
        return self

    def target_by_column(self) -> dict[str, ColumnSpec]:
        return dict(self.columns)


def load_mapping(path: str | Path) -> MappingConfig:
    """Read and validate a mapping YAML file, raising ConfigError with a readable message."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Mapping file not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse YAML in {p}: {exc}") from exc
    try:
        return MappingConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid mapping in {p}:\n{exc}") from exc
