"""The Results group box: progress, status/counter, log pane, the per-row table, Open buttons.

A self-contained view widget. ``MainWindow`` owns the threads and run orchestration and pushes
outcomes here via the small method API (``reset`` / ``set_progress`` / ``add_row`` / ``append_log``
/ ``set_status`` / ``set_counter`` / ``record_run``). The panel keeps no engine logic — only display
state (row counts, the last run directory for the Open buttons).
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from hssk.pipeline.results import RowOutcome, Status

from .i18n import tr
from .messages import _tr_coerce_msgs, _tr_message, _tr_status
from .workers import ValidationProblem

_STATUS_COLORS = {
    Status.CREATED: "#1a7f37",
    Status.UPDATED: "#1a7f37",
    Status.DRY_RUN_OK: "#0969da",
    Status.SKIPPED_ALREADY: "#6e7781",
    Status.INVALID: "#bf8700",
    Status.NO_PATIENT: "#bf8700",
    Status.MULTI_MATCH: "#bf8700",
    Status.FAILED: "#cf222e",
    Status.AUTH_EXPIRED: "#cf222e",
    Status.RATE_LIMITED: "#cf222e",
}
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
        self.status_label = QLabel("")
        self.counter_label = QLabel("—")
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addWidget(self.status_label)
        prog_row.addWidget(self.counter_label)
        lay.addLayout(prog_row)

        self.log_pane = QPlainTextEdit()
        self.log_pane.setReadOnly(True)
        self.log_pane.setMaximumHeight(80)
        self.log_pane.setPlaceholderText(tr("log_placeholder"))
        lay.addWidget(self.log_pane)

        self.table = QTableWidget(0, len(_TABLE_COL_KEYS))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _TABLE_COL_KEYS])
        self.table.horizontalHeader().setSectionResizeMode(
            len(_TABLE_COL_KEYS) - 1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, stretch=1)

        bottom = QHBoxLayout()
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
        # col indices: 0=row, 1=identifier, 2=status, 3=patient_id, 4=record_id, 5=message
        self.table.setColumnHidden(3, for_validation)
        self.table.setColumnHidden(4, for_validation)
        self._run_start = time.monotonic()

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
        r = self.table.rowCount()
        self.table.insertRow(r)
        cells = [
            str(outcome.row_index),
            outcome.identifier or "",
            _tr_status(outcome.status),
            "" if outcome.patient_id is None else str(outcome.patient_id),
            "" if outcome.record_id is None else str(outcome.record_id),
            _tr_message(outcome.message),
        ]
        for c, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if c == 2:
                item.setForeground(QColor(_STATUS_COLORS.get(outcome.status, "#000000")))
            self.table.setItem(r, c, item)
        self.table.scrollToBottom()
        self._update_counter_label()

    def add_validation_row(self, problem: ValidationProblem) -> None:
        status_text = tr("val_status_invalid") if problem.has_errors else tr("val_status_warning")
        status_color = "#cf222e" if problem.has_errors else "#bf8700"
        row = self.table.rowCount()
        self.table.insertRow(row)
        cells = [
            str(problem.row_index),
            problem.identifier,
            status_text,
            "",
            "",
            _tr_coerce_msgs(problem.message),
        ]
        for c, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if c == 2:
                item.setForeground(QColor(status_color))
            self.table.setItem(row, c, item)

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

    # -- small setters used by MainWindow's finished/failed handlers --------------------

    def append_log(self, message: str) -> None:
        self.log_pane.appendPlainText(message)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_counter(self, text: str, color: str = "") -> None:
        self.counter_label.setText(text)
        self.counter_label.setStyleSheet(color)

    def record_run(self, run_dir: Path) -> None:
        """Remember a finished run's output dir and enable the Open buttons."""
        self._last_run_dir = run_dir
        self._last_results_file = run_dir / "results.xlsx"
        self.open_report_btn.setEnabled(True)
        self.open_results_btn.setEnabled(self._last_results_file.exists())

    # -- Open buttons -------------------------------------------------------------------

    def _open_results(self) -> None:
        if self._last_results_file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_results_file)))

    def _open_report(self) -> None:
        if self._last_run_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_run_dir)))
