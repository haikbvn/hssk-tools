from __future__ import annotations

import datetime as dt

import pytest

from hssk.events import render_en
from hssk.excel.coerce import _coerce_one, _parse_default_time, coerce_row
from hssk.mapping import ColumnSpec


def _spec(**kw) -> ColumnSpec:
    return ColumnSpec(**kw)


def test_parse_default_time_returns_time_and_caches():
    _parse_default_time.cache_clear()
    assert _parse_default_time("07:00:00") == dt.time(7, 0, 0)
    _parse_default_time("07:00:00")  # second call is a cache hit, not a re-parse
    assert _parse_default_time.cache_info().hits >= 1


def test_parse_default_time_reraises_bad_value_each_call():
    # lru_cache does not cache exceptions, so a malformed value keeps raising (row error path).
    for _ in range(2):
        with pytest.raises(ValueError):
            _parse_default_time("not-a-time")


# Minimal set of values that satisfies all required columns in the example mapping.
_REQ = {
    "Ngày khám": "17/06/2026",
    "Giờ kết thúc": "17/06/2026",
    "Mã hình thức khám": 100,
    "Mã đối tượng khám": 93,
    "Chẩn đoán": "0000 - Bình thường",
    "Mã kết quả khám": 3,
    "Mã tình trạng ra viện": 1,
    "Bác sĩ": "Nguyễn Thị Hoa",
}


def test_date_string_gets_default_time():
    spec = _spec(target="examinationDate", type="datetime", default_time="07:00:00")
    assert _coerce_one("17/06/2026", spec) == "17/06/2026 07:00:00"


def test_datetime_keeps_explicit_time():
    spec = _spec(target="finishExaminationDate", type="datetime", default_time="08:00:00")
    out = _coerce_one(dt.datetime(2026, 6, 17, 8, 56, 0), spec)
    assert out == "17/06/2026 08:56:00"


def test_comma_decimal_float():
    assert _coerce_one("36,8", _spec(target="temperature", type="float")) == 36.8


def test_int_rounds_float_like():
    assert _coerce_one(80.0, _spec(target="pulse", type="int")) == 80


def test_str_num_drops_trailing_zero():
    assert _coerce_one("18.0", _spec(target="weight", type="str_num")) == "18"
    assert _coerce_one(18, _spec(target="weight", type="str_num")) == "18"
    assert _coerce_one("18.5", _spec(target="weight", type="str_num")) == "18.5"


def test_bmi_autocalc(mapping):
    raw = {
        "Mã định danh": "2700020596A",
        "Cân nặng": 18,
        "Chiều cao": 140,
        "BMI": None,
        **_REQ,
    }
    res = coerce_row(raw, mapping, row_index=2)
    assert res.ok, res.errors
    assert res.values["bmi"] == "9.18"


def test_finish_before_start_is_error(mapping):
    raw = {
        "Mã định danh": "X",
        **_REQ,
        "Ngày khám": dt.datetime(2026, 6, 17, 8, 0, 0),
        "Giờ kết thúc": dt.datetime(2026, 6, 17, 7, 0, 0),
    }
    res = coerce_row(raw, mapping, row_index=3)
    assert not res.ok
    assert any("before" in render_en(e) for e in res.errors)


def _with_custom_date_format(mapping, out_format: str):
    """Deep-copy `mapping` with a custom out_format on both datetime columns.

    Regression coverage for _check_dates: it must honor each column's real out_format instead
    of a hardcoded one, or the finish-before-start check silently disappears when an operator
    customizes the mapping.
    """
    columns = dict(mapping.columns)
    for header, spec in mapping.columns.items():
        if spec.type == "datetime":
            columns[header] = spec.model_copy(update={"out_format": out_format})
    return mapping.model_copy(update={"columns": columns}, deep=True)


def test_finish_before_start_is_error_with_custom_out_format(mapping):
    """Regression: before the fix, a custom out_format made _check_dates silently no-op."""
    custom_mapping = _with_custom_date_format(mapping, "%d/%m/%Y %H:%M")
    raw = {
        "Mã định danh": "X",
        **_REQ,
        "Ngày khám": dt.datetime(2026, 6, 17, 8, 0, 0),
        "Giờ kết thúc": dt.datetime(2026, 6, 17, 7, 0, 0),
    }
    res = coerce_row(raw, custom_mapping, row_index=9)
    assert not res.ok
    assert any("before" in render_en(e) for e in res.errors)


def test_finish_after_start_with_custom_out_format_is_ok(mapping):
    custom_mapping = _with_custom_date_format(mapping, "%d/%m/%Y %H:%M")
    raw = {
        "Mã định danh": "X",
        **_REQ,
        "Ngày khám": dt.datetime(2026, 6, 17, 7, 0, 0),
        "Giờ kết thúc": dt.datetime(2026, 6, 17, 8, 0, 0),
    }
    res = coerce_row(raw, custom_mapping, row_index=10)
    assert res.ok, res.errors


def test_required_missing_is_error(mapping):
    res = coerce_row({"Mã định danh": None}, mapping, row_index=4)
    assert not res.ok
    assert any("required" in render_en(e) for e in res.errors)


def test_out_of_range_warns(mapping):
    raw = {"Mã định danh": "X", "Mạch": 300, **_REQ}
    res = coerce_row(raw, mapping, row_index=5)
    assert res.ok  # warning, not error
    assert any("pulse" in render_en(w) for w in res.warnings)


def test_list_semicolon_split():
    spec = _spec(target="diagnosesDischargeList", type="list")
    assert _coerce_one("a; b; c", spec) == ["a", "b", "c"]


def test_list_newline_split():
    spec = _spec(target="diagnosesDischargeList", type="list")
    assert _coerce_one("0000 - Bình thường\nJ00 - Cảm lạnh", spec) == [
        "0000 - Bình thường",
        "J00 - Cảm lạnh",
    ]


def test_list_single_value():
    spec = _spec(target="diagnosesDischargeList", type="list")
    assert _coerce_one("0000 - Bình thường", spec) == ["0000 - Bình thường"]


def test_list_blank_is_skipped(mapping):
    raw = {"Mã định danh": "X", "Bệnh kèm theo": None, **_REQ}
    res = coerce_row(raw, mapping, row_index=6)
    assert res.ok
    assert "diagnosesDischargeList" not in res.values


def test_non_finite_value_is_per_cell_error(mapping):
    """A non-finite numeric cell ('inf') becomes a precise per-cell error, never a crash."""
    raw = {"Mã định danh": "X", "Cân nặng": "inf", **_REQ}
    res = coerce_row(raw, mapping, row_index=7)
    assert not res.ok
    assert any("Cân nặng" in render_en(e) for e in res.errors)
    assert "bmi" not in res.values


def test_overflow_to_infinity_is_per_cell_error(mapping):
    """A value that overflows float to infinity ('1e400') is handled like any bad cell."""
    raw = {"Mã định danh": "X", "Cân nặng": "1e400", **_REQ}
    res = coerce_row(raw, mapping, row_index=8)
    assert not res.ok
    assert any("Cân nặng" in render_en(e) for e in res.errors)
