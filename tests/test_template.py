from __future__ import annotations

from openpyxl import load_workbook

from hssk.excel import reader
from hssk.excel.coerce import coerce_row
from hssk.excel.template import make_template


def test_template_headers_match_mapping(mapping, tmp_path):
    out = make_template(mapping, tmp_path / "tpl.xlsx")
    assert out.exists()
    wb = load_workbook(out)
    ws = wb["Dữ liệu"]
    headers = [c.value for c in ws[1]]
    assert headers == list(mapping.columns.keys())
    assert "Hướng dẫn" in wb.sheetnames


def test_template_rows_read_and_coerce_cleanly(mapping, tmp_path):
    out = make_template(mapping, tmp_path / "tpl.xlsx", examples=True)
    rows = reader.read_rows(out, mapping)
    assert len(rows) >= 1
    for idx, raw in rows:
        result = coerce_row(raw, mapping, idx)
        assert result.ok, result.errors
        # BMI is left blank in the template and auto-calculated.
        assert result.values.get("bmi")


def test_template_without_examples_is_header_only(mapping, tmp_path):
    out = make_template(mapping, tmp_path / "tpl.xlsx", examples=False)
    rows = reader.read_rows(out, mapping)
    assert rows == []
