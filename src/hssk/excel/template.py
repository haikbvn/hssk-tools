"""Generate a fill-in Excel template whose headers exactly match a mapping."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..mapping import MappingConfig

_TYPE_HINT = {
    "str": "Chữ",
    "int": "Số nguyên",
    "float": "Số thập phân",
    "str_num": "Số",
    "datetime": "Ngày dd/mm/yyyy",
}

# Per-field Vietnamese hints, keyed by API target.
_FIELD_HINT = {
    "medicalIdentifierCode": "Mã tra cứu bệnh nhân: CCCD / số thẻ BHYT / mã định danh "
    "(giống ô tìm kiếm trên web).",
    "examinationDate": "Ngày khám. Bỏ trống giờ sẽ dùng giờ mặc định trong cấu hình.",
    "finishExaminationDate": "Ngày/giờ kết thúc khám. Phải sau 'Ngày khám'.",
    "pulse": "Mạch (lần/phút), ví dụ 80.",
    "temperature": "Nhiệt độ °C, ví dụ 36.8.",
    "bloodPressureMax": "Huyết áp tối đa (tâm thu), ví dụ 110.",
    "bloodPressureMin": "Huyết áp tối thiểu (tâm trương), ví dụ 70.",
    "breath": "Nhịp thở (lần/phút), ví dụ 20.",
    "weight": "Cân nặng (kg).",
    "height": "Chiều cao (cm).",
    "bmi": "ĐỂ TRỐNG để tự tính từ cân nặng & chiều cao.",
    "waistCircumference": "Vòng bụng (cm).",
    "chestCircumference": "Vòng ngực (cm).",
    "leftEyeGlasses": "Thị lực mắt trái (có kính).",
    "leftEyeNoGlasses": "Thị lực mắt trái (không kính).",
    "rightEyeGlasses": "Thị lực mắt phải (có kính).",
    "rightEyeNoGlasses": "Thị lực mắt phải (không kính).",
}

# Example values keyed by API target (used to fill demo rows).
_EXAMPLE = {
    "medicalIdentifierCode": ["027148003240", "2720551044"],
    "examinationDate": [dt.datetime(2026, 6, 17, 7, 0), dt.datetime(2026, 6, 17, 7, 30)],
    "finishExaminationDate": [dt.datetime(2026, 6, 17, 8, 30), dt.datetime(2026, 6, 17, 9, 0)],
    "pulse": [80, 78],
    "temperature": [36.8, 37.0],
    "bloodPressureMax": [110, 120],
    "bloodPressureMin": [70, 80],
    "breath": [20, 19],
    "weight": [18, 55],
    "height": [140, 160],
    "bmi": [None, None],
    "waistCircumference": [60, 72],
    "chestCircumference": [60, 80],
    "leftEyeGlasses": [10, 10],
    "leftEyeNoGlasses": [10, 8],
    "rightEyeGlasses": [10, 10],
    "rightEyeNoGlasses": [10, 9],
}

_GUIDE = [
    "HƯỚNG DẪN",
    "",
    "• Mỗi dòng = 1 bệnh nhân (1 lần khám sức khoẻ).",
    "• KHÔNG đổi tên các cột ở dòng tiêu đề — ứng dụng dựa vào đó để đọc dữ liệu.",
    "• Cột 'Mã định danh': nhập CCCD hoặc số thẻ BHYT để tìm bệnh nhân (giống ô tìm "
    "kiếm trên web). Không cần là mã định danh y tế.",
    "• Ngày: định dạng dd/mm/yyyy, có thể kèm giờ. Để trống giờ sẽ dùng giờ mặc định.",
    "• Cột 'BMI': để TRỐNG, ứng dụng tự tính từ cân nặng và chiều cao.",
    "• XOÁ các dòng ví dụ (in nghiêng) trước khi chạy thật.",
    "• Di chuột vào ô tiêu đề để xem chú thích từng cột.",
    "",
    "Quy trình: Mở app → Đăng nhập → Chọn Excel → Validate → Dry-run (xem trước) → bỏ "
    "Dry-run, Limit=1 để thử 1 bệnh nhân → kiểm tra trên web → chạy toàn bộ.",
]


def make_template(
    mapping: MappingConfig, out_path: str | Path, *, examples: bool = True
) -> Path:
    """Write an .xlsx template with one column per mapped Excel header, plus a guide sheet."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Dữ liệu"

    headers = list(mapping.columns.keys())
    id_col = mapping.identifier.column
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5496")
    id_fill = PatternFill("solid", fgColor="C55A11")  # highlight the search-key column

    for c, header in enumerate(headers, start=1):
        spec = mapping.columns[header]
        cell = ws.cell(row=1, column=c, value=header)
        cell.font = header_font
        cell.fill = id_fill if header == id_col else header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        note = f"Trường API: {spec.target}\nKiểu: {_TYPE_HINT.get(spec.type, spec.type)}"
        if spec.required or header == id_col:
            note += "\n(Bắt buộc)"
        hint = _FIELD_HINT.get(spec.target)
        if hint:
            note += f"\n{hint}"
        cell.comment = Comment(note, "hssk-tools")
        ws.column_dimensions[get_column_letter(c)].width = max(12, min(30, len(header) + 4))

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

    if examples:
        italic = Font(italic=True, color="808080")
        n = len(next(iter(_EXAMPLE.values())))
        for i in range(n):
            row_idx = ws.max_row + 1
            for c, header in enumerate(headers, start=1):
                target = mapping.columns[header].target
                value = _EXAMPLE.get(target, [None] * n)[i]
                cell = ws.cell(row=row_idx, column=c, value=value)
                cell.font = italic
                if isinstance(value, dt.datetime):
                    cell.number_format = "dd/mm/yyyy hh:mm"

    # Guide sheet
    guide = wb.create_sheet("Hướng dẫn")
    guide.column_dimensions["A"].width = 100
    for r, line in enumerate(_GUIDE, start=1):
        cell = guide.cell(row=r, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if r == 1:
            cell.font = Font(bold=True, size=14)

    wb.save(out)
    return out
