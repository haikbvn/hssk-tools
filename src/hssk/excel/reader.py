"""Read an Excel workbook into raw ``{header: value}`` rows using openpyxl."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from ..errors import ConfigError
from ..mapping import MappingConfig


def _clean_header(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def read_rows(path: str | Path, mapping: MappingConfig) -> list[tuple[int, dict[str, Any]]]:
    """Return ``[(excel_row_number, {header: value})]`` for every non-empty data row."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Excel file not found: {p}")
    wb = load_workbook(filename=str(p), read_only=True, data_only=True)
    try:
        ws = wb[mapping.sheet] if mapping.sheet else wb[wb.sheetnames[0]]
    except KeyError as exc:
        raise ConfigError(f"Sheet {mapping.sheet!r} not found. Available: {wb.sheetnames}") from exc

    headers: list[str] = []
    rows: list[tuple[int, dict[str, Any]]] = []
    try:
        for r_idx, values in enumerate(ws.iter_rows(values_only=True), start=1):
            if r_idx < mapping.header_row:
                continue
            if r_idx == mapping.header_row:
                headers = [_clean_header(v) for v in values]
                continue
            if all(_is_blank(v) for v in values):
                continue
            raw = {h: v for h, v in zip(headers, values, strict=False) if h}
            rows.append((r_idx, raw))
    finally:
        wb.close()

    if not headers:
        raise ConfigError(f"No header row found at row {mapping.header_row} in {p}")
    _check_columns(headers, mapping, p)
    return rows


def _check_columns(headers: list[str], mapping: MappingConfig, path: Path) -> None:
    present = set(headers)
    missing = [c for c in mapping.columns if c not in present]
    if missing:
        raise ConfigError(
            f"Excel {path.name} is missing mapped column(s): {missing}. Found headers: {headers}"
        )
