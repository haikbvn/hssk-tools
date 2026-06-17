from __future__ import annotations

import datetime as dt

from hssk.excel.coerce import _coerce_one, coerce_row
from hssk.mapping import ColumnSpec


def _spec(**kw) -> ColumnSpec:
    return ColumnSpec(**kw)


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
    assert any("before" in e for e in res.errors)


def test_required_missing_is_error(mapping):
    res = coerce_row({"Mã định danh": None}, mapping, row_index=4)
    assert not res.ok
    assert any("required" in e for e in res.errors)


def test_out_of_range_warns(mapping):
    raw = {"Mã định danh": "X", "Mạch": 300, **_REQ}
    res = coerce_row(raw, mapping, row_index=5)
    assert res.ok  # warning, not error
    assert any("pulse" in w for w in res.warnings)


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
