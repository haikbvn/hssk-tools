"""The Results group box: progress, status/counter, filter, log pane, the per-row table, buttons.

A self-contained view widget. ``MainWindow`` owns the threads and run orchestration and pushes
outcomes here via the small method API (``reset`` / ``set_progress`` / ``add_row`` / ``append_log``
/ ``set_status`` / ``set_counter`` / ``record_run``). The panel keeps no engine logic — only display
state (row counts, the last run directory for the Open buttons).
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from hssk.pipeline.results import RowOutcome, Status

from . import theme
from .i18n import tr
from .messages import _tr_coerce_msgs, _tr_message, _tr_status
from .workers import ValidationProblem

try:  # accessibility announcements (Qt 6.8+); degrade gracefully if unavailable
    from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent

    _ANNOUNCE_OK = True
except ImportError:  # pragma: no cover - depends on Qt build
    _ANNOUNCE_OK = False

# Run statuses that count as "problems" for the problems-only filter (success/skip are hidden).
_PROBLEM_STATUSES = frozenset(
    {
        Status.INVALID,
        Status.NO_PATIENT,
        Status.MULTI_MATCH,
        Status.FAILED,
        Status.AUTH_EXPIRED,
        Status.RATE_LIMITED,
    }
)

# Qt item-data roles for our own bookkeeping on each row.
# _ROLE_TOKEN: theme token for the status cell, so rows re-colour on a Light/Dark switch.
# _ROLE_PROBLEM: bool, whether the row is a "problem" (for the problems-only filter).
_ROLE_TOKEN = Qt.ItemDataRole.UserRole
_ROLE_PROBLEM = Qt.ItemDataRole.UserRole + 1

_TABLE_COL_KEYS = [
    "col_row",
    "col_identifier",
    "col_status",
    "col_patient_id",
    "col_record_id",
    "col_message",
]


class ResultsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__(tr("group_results"))
        self._counts: dict[Status, int] = {}
        self._run_start: float = 0.0
        self._last_run_dir: Path | None = None
        self._last_results_file: Path | None = None

        lay = QVBoxLayout(self)

        prog_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setAccessibleName(tr("col_status"))
        self.status_label = QLabel("")
        self.counter_label = QLabel("—")
        self.counter_label.setAccessibleName(tr("col_status"))
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addWidget(self.status_label)
        prog_row.addWidget(self.counter_label)
        lay.addLayout(prog_row)

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setPlaceholderText(tr("ph_filter"))
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.problems_check = QCheckBox(tr("chk_problems_only"))
        self.problems_check.stateChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit, stretch=1)
        filter_row.addWidget(self.problems_check)
        lay.addLayout(filter_row)

        # Log pane and table share a resizable splitter so operators can drag the log taller
        # to read recovery guidance after a run.
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.log_pane = QPlainTextEdit()
        self.log_pane.setReadOnly(True)
        self.log_pane.setPlaceholderText(tr("log_placeholder"))
        splitter.addWidget(self.log_pane)

        self.table = QTableWidget(0, len(_TABLE_COL_KEYS))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _TABLE_COL_KEYS])
        self.table.horizontalHeader().setSectionResizeMode(
            len(_TABLE_COL_KEYS) - 1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        QShortcut(QKeySequence.StandardKey.Copy, self.table, self._copy_selection)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([80, 400])
        lay.addWidget(splitter, stretch=1)

        # Empty-state overlay centred over the table's viewport.
        self._empty_label = QLabel(tr("empty_results"), self.table.viewport())
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self.table.viewport().installEventFilter(self)
        self._refresh_empty_state()

        bottom = QHBoxLayout()
        self.export_btn = QPushButton(tr("btn_export_csv"))
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_csv)
        bottom.addWidget(self.export_btn)
        bottom.addStretch(1)
        self.open_results_btn = QPushButton(tr("btn_open_results"))
        self.open_results_btn.setEnabled(False)
        self.open_results_btn.clicked.connect(self._open_results)
        bottom.addWidget(self.open_results_btn)
        self.open_report_btn = QPushButton(tr("btn_open_report"))
        self.open_report_btn.setEnabled(False)
        self.open_report_btn.clicked.connect(self._open_report)
        bottom.addWidget(self.open_report_btn)
        lay.addLayout(bottom)

    # -- run/validate lifecycle ---------------------------------------------------------

    def reset(self, for_validation: bool = False) -> None:
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self._counts = {}
        self.counter_label.setText("—")
        self.counter_label.setStyleSheet("")
        self.status_label.setText("")
        self.log_pane.clear()
        self.open_report_btn.setEnabled(False)
        self.open_results_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        # col indices: 0=row, 1=identifier, 2=status, 3=patient_id, 4=record_id, 5=message
        self.table.setColumnHidden(3, for_validation)
        self.table.setColumnHidden(4, for_validation)
        self._run_start = time.monotonic()
        self._refresh_empty_state()

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        if done == 0:
            self.status_label.setText(tr("prog_starting").format(total=total))
        elif done >= total:
            self.status_label.setText(tr("prog_all_done").format(total=total))
        else:
            elapsed = time.monotonic() - self._run_start
            if elapsed > 0:
                rem = int((elapsed / done) * (total - done))
                if rem >= 60:
                    eta = tr("eta_min_sec").format(m=rem // 60, s=rem % 60)
                else:
                    eta = tr("eta_sec").format(s=rem)
                self.status_label.setText(tr("prog_row_of").format(done=done, total=total, eta=eta))
            else:
                self.status_label.setText(tr("prog_row_of_no_eta").format(done=done, total=total))

    def add_row(self, outcome: RowOutcome) -> None:
        self._counts[outcome.status] = self._counts.get(outcome.status, 0) + 1
        cells = [
            str(outcome.row_index),
            outcome.identifier or "",
            _tr_status(outcome.status),
            "" if outcome.patient_id is None else str(outcome.patient_id),
            "" if outcome.record_id is None else str(outcome.record_id),
            _tr_message(outcome.message),
        ]
        token = theme.STATUS_COLOR_TOKENS.get(outcome.status)
        self._append_row(cells, token, is_problem=outcome.status in _PROBLEM_STATUSES)
        self._update_counter_label()
        self.export_btn.setEnabled(True)

    def add_validation_row(self, problem: ValidationProblem) -> None:
        status_text = tr("val_status_invalid") if problem.has_errors else tr("val_status_warning")
        token = "danger" if problem.has_errors else "warning"
        cells = [
            str(problem.row_index),
            problem.identifier,
            status_text,
            "",
            "",
            _tr_coerce_msgs(problem.message),
        ]
        self._append_row(cells, token, is_problem=True)
        self.export_btn.setEnabled(True)

    def _append_row(self, cells: list[str], token: str | None, *, is_problem: bool) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        items = [QTableWidgetItem(text) for text in cells]
        if token is not None:
            items[2].setForeground(QColor(theme.color(token)))
            items[2].setData(_ROLE_TOKEN, token)
        items[0].setData(_ROLE_PROBLEM, is_problem)
        for c, item in enumerate(items):
            self.table.setItem(r, c, item)
        self._set_row_visible(r)
        self.table.scrollToBottom()
        self._refresh_empty_state()

    def _update_counter_label(self) -> None:
        created = (
            self._counts.get(Status.CREATED, 0)
            + self._counts.get(Status.UPDATED, 0)
            + self._counts.get(Status.DRY_RUN_OK, 0)
        )
        skipped = self._counts.get(Status.SKIPPED_ALREADY, 0)
        failed = sum(
            self._counts.get(s, 0)
            for s in (Status.FAILED, Status.NO_PATIENT, Status.MULTI_MATCH, Status.INVALID)
        )
        aborted = self._counts.get(Status.AUTH_EXPIRED, 0) + self._counts.get(
            Status.RATE_LIMITED, 0
        )
        text = f"✓ {created}   ↷ {skipped}   ✗ {failed}"
        if aborted:
            text += f"   ⛔ {aborted}"
        self.counter_label.setText(text)

    # -- filtering ----------------------------------------------------------------------

    def _row_matches(self, r: int) -> bool:
        if self.problems_check.isChecked():
            first = self.table.item(r, 0)
            if first is None or not first.data(_ROLE_PROBLEM):
                return False
        needle = self.filter_edit.text().strip().lower()
        if not needle:
            return True
        for c in range(self.table.columnCount()):
            if self.table.isColumnHidden(c):
                continue
            item = self.table.item(r, c)
            if item is not None and needle in item.text().lower():
                return True
        return False

    def _set_row_visible(self, r: int) -> None:
        self.table.setRowHidden(r, not self._row_matches(r))

    def _apply_filter(self) -> None:
        for r in range(self.table.rowCount()):
            self._set_row_visible(r)
        self._refresh_empty_state()

    # -- empty-state overlay ------------------------------------------------------------

    def _visible_row_count(self) -> int:
        return sum(1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r))

    def _refresh_empty_state(self) -> None:
        self._empty_label.setGeometry(self.table.viewport().rect())
        self._empty_label.setVisible(self._visible_row_count() == 0)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.table.viewport() and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self.table.viewport().rect())
        return super().eventFilter(obj, event)

    # -- copy / context menu ------------------------------------------------------------

    def _visible_cols(self) -> list[int]:
        return [c for c in range(self.table.columnCount()) if not self.table.isColumnHidden(c)]

    def _cell_text(self, r: int, c: int) -> str:
        item = self.table.item(r, c)
        return item.text() if item is not None else ""

    def _header_text(self, c: int) -> str:
        item = self.table.horizontalHeaderItem(c)
        return item.text() if item is not None else ""

    def _row_tsv(self, r: int) -> str:
        return "\t".join(self._cell_text(r, c) for c in self._visible_cols())

    def _copy_selection(self) -> None:
        rows = sorted({it.row() for it in self.table.selectedItems()})
        if rows:
            QApplication.clipboard().setText("\n".join(self._row_tsv(r) for r in rows))

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.table.itemAt(pos)
        menu = QMenu(self)
        act_cell = menu.addAction(tr("ctx_copy_cell"))
        act_row = menu.addAction(tr("ctx_copy_row"))
        act_all = menu.addAction(tr("ctx_copy_all"))
        if item is None:
            act_cell.setEnabled(False)
            act_row.setEnabled(False)
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_cell and item is not None:
            QApplication.clipboard().setText(item.text())
        elif chosen is act_row and item is not None:
            QApplication.clipboard().setText(self._row_tsv(item.row()))
        elif chosen is act_all:
            QApplication.clipboard().setText(self._all_visible_tsv())

    def _all_visible_tsv(self) -> str:
        cols = self._visible_cols()
        lines = ["\t".join(self._header_text(c) for c in cols)]
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                lines.append(self._row_tsv(r))
        return "\n".join(lines)

    # -- CSV export ---------------------------------------------------------------------

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_export_csv_title"), "results.csv", tr("filter_csv")
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        cols = self._visible_cols()
        # utf-8-sig so Excel opens Vietnamese diacritics correctly.
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow([self._header_text(c) for c in cols])
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    writer.writerow([self._cell_text(r, c) for c in cols])

    # -- small setters used by MainWindow's finished/failed handlers --------------------

    def append_log(self, message: str) -> None:
        self.log_pane.appendPlainText(message)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self._announce(text)

    def set_counter(self, text: str, color: str = "") -> None:
        self.counter_label.setText(text)
        self.counter_label.setStyleSheet(color)

    def _announce(self, text: str) -> None:
        if _ANNOUNCE_OK and text:
            QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(self.status_label, text))

    def record_run(self, run_dir: Path) -> None:
        """Remember a finished run's output dir and enable the Open buttons."""
        self._last_run_dir = run_dir
        self._last_results_file = run_dir / "results.xlsx"
        self.open_report_btn.setEnabled(True)
        self.open_results_btn.setEnabled(self._last_results_file.exists())

    # -- live re-translation / theming --------------------------------------------------

    def retranslate(self) -> None:
        self.setTitle(tr("group_results"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _TABLE_COL_KEYS])
        self.filter_edit.setPlaceholderText(tr("ph_filter"))
        self.problems_check.setText(tr("chk_problems_only"))
        self.log_pane.setPlaceholderText(tr("log_placeholder"))
        self._empty_label.setText(tr("empty_results"))
        self.export_btn.setText(tr("btn_export_csv"))
        self.open_results_btn.setText(tr("btn_open_results"))
        self.open_report_btn.setText(tr("btn_open_report"))

    def on_theme_changed(self) -> None:
        """Re-colour the status cells of existing rows after a Light/Dark switch."""
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 2)
            if item is None:
                continue
            token = item.data(_ROLE_TOKEN)
            if token:
                item.setForeground(QColor(theme.color(token)))

    # -- Open buttons -------------------------------------------------------------------

    def _open_results(self) -> None:
        if self._last_results_file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_results_file)))

    def _open_report(self) -> None:
        if self._last_run_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_run_dir)))
