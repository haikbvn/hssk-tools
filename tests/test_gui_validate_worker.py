"""ValidateWorker surfaces a file-level ConfigError as a synthetic results-table row.

When the reader rejects the file up front (a required mapped column is absent), the worker must
both emit a ``problem`` (so the operator sees it in the results table) and ``failed`` (so the
existing banner/lifecycle still runs) — and must not emit ``finished``.

``run()`` is called directly (no thread) so its signals fire synchronously.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from hssk.events import render_en
from hssk.mapping import filter_for_delete, load_mapping
from hssk_gui.workers import ValidateWorker, ValidationProblem

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MAPPING = REPO_ROOT / "config" / "mapping.example.yaml"
EXAMPLE_OVERLAY = REPO_ROOT / "config" / "mapping.update.example.yaml"

# A full QApplication (not just QCoreApplication): pytest-qt's qapp/qtbot fixtures need one, and
# a bare QCoreApplication singleton can't be upgraded after the fact — created once per process,
# reused by pytest-qt's own fixture if this module collects first.
_app = QApplication.instance() or QApplication([])


def _delete_mapping():
    """The slim 2-column (identifier + Mã hồ sơ) mapping used by delete mode."""
    return filter_for_delete(load_mapping(EXAMPLE_MAPPING, overlay_path=EXAMPLE_OVERLAY))


def _xlsx_without_record_id(tmp_path: Path) -> Path:
    """A file that has the identifier column but is missing the required 'Mã hồ sơ'."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Mã định danh", "Ngày khám"])
    ws.append(["2700020596A", "17/06/2026"])
    p = tmp_path / "no_record_id.xlsx"
    wb.save(p)
    return p


def test_missing_column_emits_synthetic_row_and_fails(tmp_path: Path) -> None:
    mapping = _delete_mapping()
    xlsx = _xlsx_without_record_id(tmp_path)

    problems: list[ValidationProblem] = []
    failures: list[tuple[str, object]] = []
    finishes: list[object] = []

    worker = ValidateWorker(xlsx, mapping)
    worker.problem.connect(problems.append)
    worker.failed.connect(lambda message, msg: failures.append((message, msg)))
    worker.finished.connect(finishes.append)

    worker.run()

    assert len(problems) == 1
    p = problems[0]
    assert isinstance(p, ValidationProblem)
    assert p.has_errors is True
    assert p.row_index == mapping.header_row
    error_text = render_en(p.errors[0])
    assert "is missing mapped column(s)" in error_text  # raw engine shape, localized downstream
    assert "Mã hồ sơ" in error_text
    assert len(failures) == 1
    assert finishes == []  # a structural failure never reports a normal summary
