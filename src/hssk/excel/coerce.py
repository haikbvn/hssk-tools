"""Per-row type coercion and validation: Excel cells → API-ready values.

Handles Vietnamese-locale quirks (comma decimals), Excel serial/`datetime` dates formatted to
``dd/MM/yyyy HH:mm:ss``, weight/height/bmi kept as numeric strings (as the API expects), BMI
auto-calculation, and soft out-of-range warnings. One bad cell becomes a row error, never an
exception that kills the batch.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from dateutil import parser as date_parser

from ..mapping import ColumnSpec, MappingConfig

# Soft sanity ranges (warn, don't block) keyed by target field.
_RANGES: dict[str, tuple[float, float]] = {
    "pulse": (30, 220),
    "temperature": (34, 43),
    "bloodPressureMax": (60, 260),
    "bloodPressureMin": (30, 160),
    "breath": (8, 60),
    "weight": (1, 300),
    "height": (30, 230),
}

_EXCEL_EPOCH = dt.datetime(1899, 12, 30)


@dataclass
class RowResult:
    row_index: int  # 1-based Excel row number
    raw: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)  # target -> coerced value
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def identifier(self) -> str | None:
        v = self.values.get("medicalIdentifierCode")
        return str(v) if v is not None else None

    @property
    def exam_date(self) -> str | None:
        v = self.values.get("examinationDate")
        return str(v) if v is not None else None


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _parse_number(value: Any) -> float:
    """Parse a number from an int/float or a (possibly VN-formatted) string."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "")
    if "," in s and "." in s:
        # assume '.' thousands, ',' decimal -> "1.234,5" => "1234.5"
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def _format_number_str(value: Any) -> str:
    """Numeric string as the API sends it: drop a trailing .0 but keep real decimals."""
    n = _parse_number(value)
    if n == int(n):
        return str(int(n))
    return repr(n).rstrip("0").rstrip(".") if "." in repr(n) else str(n)


def _to_datetime(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _EXCEL_EPOCH + dt.timedelta(days=float(value))
    return date_parser.parse(str(value).strip(), dayfirst=True)


def _coerce_one(value: Any, spec: ColumnSpec) -> Any:
    t = spec.type
    if t == "str":
        return str(value).strip()
    if t == "int":
        return int(round(_parse_number(value)))
    if t == "float":
        return _parse_number(value)
    if t == "str_num":
        return _format_number_str(value)
    if t == "datetime":
        d = _to_datetime(value)
        if spec.default_time and d.time() == dt.time(0, 0, 0):
            ht = dt.datetime.strptime(spec.default_time, "%H:%M:%S").time()
            d = d.replace(hour=ht.hour, minute=ht.minute, second=ht.second)
        return d.strftime(spec.out_format)
    if t == "list":
        import re

        parts = re.split(r"[;\n]+", str(value))
        return [p.strip() for p in parts if p.strip()]
    raise ValueError(f"unknown column type {t!r}")


def coerce_row(raw: dict[str, Any], mapping: MappingConfig, row_index: int) -> RowResult:
    result = RowResult(row_index=row_index, raw=dict(raw))

    for column, spec in mapping.columns.items():
        value = raw.get(column)
        if _is_blank(value):
            if spec.required:
                result.errors.append(f"missing required column {column!r}")
            continue
        try:
            coerced = _coerce_one(value, spec)
        except (ValueError, TypeError) as exc:
            result.errors.append(f"{column!r}: cannot parse {value!r} as {spec.type} ({exc})")
            continue
        result.values[spec.target] = coerced
        _range_check(spec.target, coerced, result)

    _compute_bmi(mapping, result)
    _check_dates(result)
    return result


def _range_check(target: str, value: Any, result: RowResult) -> None:
    lo_hi = _RANGES.get(target)
    if lo_hi is None:
        return
    try:
        n = _parse_number(value)
    except (ValueError, TypeError):
        return
    lo, hi = lo_hi
    if not (lo <= n <= hi):
        result.warnings.append(f"{target}={value} outside expected range {lo}–{hi}")


def _compute_bmi(mapping: MappingConfig, result: RowResult) -> None:
    cfg = mapping.computed.bmi
    if cfg is None:
        return
    has_bmi = "bmi" in result.values and not _is_blank(result.values.get("bmi"))
    if has_bmi and cfg.only_if_missing:
        return
    w = result.values.get(cfg.source[0])
    h = result.values.get(cfg.source[1])
    if _is_blank(w) or _is_blank(h):
        return
    try:
        weight_kg = _parse_number(w)
        height_m = _parse_number(h) / 100.0
        if height_m <= 0:
            return
        bmi = round(weight_kg / (height_m * height_m), cfg.round)
    except (ValueError, TypeError, ZeroDivisionError):
        return
    result.values["bmi"] = _format_number_str(bmi)


def _check_dates(result: RowResult) -> None:
    start = result.values.get("examinationDate")
    finish = result.values.get("finishExaminationDate")
    if not start or not finish:
        return
    try:
        s = dt.datetime.strptime(start, "%d/%m/%Y %H:%M:%S")
        f = dt.datetime.strptime(finish, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return
    if f < s:
        result.errors.append(
            f"finishExaminationDate ({finish}) is before examinationDate ({start})"
        )
