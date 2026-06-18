"""Single-window GUI: login, pick Excel, validate, dry-run/push with live progress."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hssk.auth.profile import load_profile
from hssk.auth.token_store import load_token
from hssk.config import ensure_mapping_file
from hssk.config import settings as engine_settings
from hssk.errors import ConfigError, HsskError
from hssk.excel import reader
from hssk.excel.coerce import coerce_row
from hssk.mapping import load_mapping
from hssk.pipeline.runner import RowOutcome, RunSummary, Status

from .preferences_dialog import PreferencesDialog
from .settings import UiSettings
from .workers import LoginWorker, RunWorker

_STATUS_COLORS = {
    Status.CREATED: "#1a7f37",
    Status.DRY_RUN_OK: "#0969da",
    Status.SKIPPED_ALREADY: "#6e7781",
    Status.INVALID: "#bf8700",
    Status.NO_PATIENT: "#bf8700",
    Status.MULTI_MATCH: "#bf8700",
    Status.FAILED: "#cf222e",
    Status.AUTH_EXPIRED: "#cf222e",
    Status.RATE_LIMITED: "#cf222e",
}
_TABLE_COLS = ["Row", "Identifier", "Status", "PatientId", "RecordId", "Message"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HSSK Tools — Health checkup uploader")
        self.resize(960, 720)

        self._ui = UiSettings()
        self._token: str | None = None
        self._excel_path: Path | None = None
        self._last_run_dir: Path | None = None
        self._last_results_file: Path | None = None
        self._run_start: float = 0.0
        self._counts: dict[Status, int] = {}

        # thread/worker handles (kept alive while running)
        self._login_thread: QThread | None = None
        self._login_worker: LoginWorker | None = None
        self._run_thread: QThread | None = None
        self._run_worker: RunWorker | None = None

        self._build_ui()
        self._restore_prefs()
        self._refresh_token_status()
        self._update_start_enabled()

    # -- UI construction ----------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(self._build_login_box())
        root.addWidget(self._build_data_box())
        root.addWidget(self._build_run_box())
        root.addWidget(self._build_results_box(), stretch=1)
        self.setCentralWidget(central)
        self._build_menu()

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("Settings")
        prefs_action = QAction("Settings…", self)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.triggered.connect(self._show_preferences)
        settings_menu.addAction(prefs_action)

    def _build_login_box(self) -> QGroupBox:
        box = QGroupBox("1 · Login")
        lay = QHBoxLayout(box)
        self.login_btn = QPushButton("Open website && log in")
        self.login_btn.clicked.connect(self._do_login)
        self.token_label = QLabel("Not logged in")
        lay.addWidget(self.login_btn)
        lay.addWidget(self.token_label, stretch=1)
        return box

    def _build_data_box(self) -> QGroupBox:
        box = QGroupBox("2 · Data")
        lay = QHBoxLayout(box)
        self.choose_btn = QPushButton("Choose Excel…")
        self.choose_btn.clicked.connect(self._choose_excel)
        self.file_label = QLabel("No file selected")
        self.template_btn = QPushButton("Template…")
        self.template_btn.clicked.connect(self._make_template)
        self.mapping_btn = QPushButton("Open mapping")
        self.mapping_btn.clicked.connect(self._open_mapping)
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self._validate)
        lay.addWidget(self.choose_btn)
        lay.addWidget(self.file_label, stretch=1)
        lay.addWidget(self.template_btn)
        lay.addWidget(self.mapping_btn)
        lay.addWidget(self.validate_btn)
        return box

    def _build_run_box(self) -> QGroupBox:
        box = QGroupBox("3 · Run")
        outer = QVBoxLayout(box)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Delay (s):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.2, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(1.0)
        controls.addWidget(self.delay_spin)

        controls.addWidget(QLabel("Limit (0 = all):"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        self.limit_spin.setValue(0)
        controls.addWidget(self.limit_spin)

        self.dryrun_check = QCheckBox("Dry-run (don't send)")
        self.dryrun_check.setChecked(True)
        self.dryrun_check.stateChanged.connect(self._on_dryrun_toggled)
        controls.addWidget(self.dryrun_check)
        controls.addStretch(1)

        self.start_btn = QPushButton("Start dry-run")
        self.start_btn.clicked.connect(self._start_run)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_run)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        outer.addLayout(controls)

        self.banner = QLabel("⚠️  PRODUCTION — this sends LIVE medical records")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setStyleSheet(
            "background:#cf222e; color:white; font-weight:bold; padding:4px; border-radius:4px;"
        )
        self.banner.setVisible(False)
        outer.addWidget(self.banner)
        return box

    def _build_results_box(self) -> QGroupBox:
        box = QGroupBox("Results")
        lay = QVBoxLayout(box)

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
        self.log_pane.setPlaceholderText("Engine log…")
        lay.addWidget(self.log_pane)

        self.table = QTableWidget(0, len(_TABLE_COLS))
        self.table.setHorizontalHeaderLabels(_TABLE_COLS)
        self.table.horizontalHeader().setSectionResizeMode(
            len(_TABLE_COLS) - 1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.open_results_btn = QPushButton("Open results spreadsheet")
        self.open_results_btn.setEnabled(False)
        self.open_results_btn.clicked.connect(self._open_results)
        bottom.addWidget(self.open_results_btn)
        self.open_report_btn = QPushButton("Open report folder")
        self.open_report_btn.setEnabled(False)
        self.open_report_btn.clicked.connect(self._open_report)
        bottom.addWidget(self.open_report_btn)
        lay.addLayout(bottom)
        return box

    # -- preferences --------------------------------------------------------------------

    def _restore_prefs(self) -> None:
        if self._ui.last_file and Path(self._ui.last_file).exists():
            self._set_excel(Path(self._ui.last_file))
        self.delay_spin.setValue(self._ui.delay)
        self.limit_spin.setValue(self._ui.limit)
        self.dryrun_check.setChecked(self._ui.dry_run)

    def _show_preferences(self) -> None:
        dlg = PreferencesDialog(self)
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self.delay_spin.setValue(self._ui.delay)
            self.limit_spin.setValue(self._ui.limit)
            self.dryrun_check.setChecked(self._ui.dry_run)

    # -- login --------------------------------------------------------------------------

    def _refresh_token_status(self) -> None:
        data = load_token()
        if data is None:
            self._token = None
            self._set_token_label("Not logged in", "#cf222e")
            return
        rem = data.seconds_remaining()
        if not data.is_valid():
            self._token = None
            self._set_token_label("Token expired — please log in again", "#cf222e")
            return
        self._token = data.token
        profile = load_profile()
        identity = f"  —  {profile.identity_label()}" if profile else ""
        if rem is None:
            self._set_token_label(f"Logged in ✓{identity}", "#1a7f37")
        else:
            self._set_token_label(
                f"Logged in ✓{identity}  (valid ~{rem // 60}m {rem % 60}s)", "#1a7f37"
            )

    def _set_token_label(self, text: str, color: str) -> None:
        self.token_label.setText(text)
        self.token_label.setStyleSheet(f"color:{color}; font-weight:bold;")

    def _do_login(self) -> None:
        self.login_btn.setEnabled(False)
        self._set_token_label("Opening browser… log in in the window that appears.", "#0969da")
        self._login_thread = QThread()
        self._login_worker = LoginWorker()
        self._login_worker.moveToThread(self._login_thread)
        self._login_thread.started.connect(self._login_worker.run)
        self._login_worker.status.connect(lambda m: self._set_token_label(m, "#0969da"))
        # Stop the thread first, then update UI; only drop our references once the thread has
        # fully finished (dropping a running QThread is a fatal crash).
        self._login_worker.finished.connect(self._login_thread.quit)
        self._login_worker.failed.connect(self._login_thread.quit)
        self._login_worker.finished.connect(self._on_login_finished)
        self._login_worker.failed.connect(self._on_login_failed)
        self._login_thread.finished.connect(self._login_worker.deleteLater)
        self._login_thread.finished.connect(self._login_thread.deleteLater)
        self._login_thread.finished.connect(self._on_login_thread_finished)
        self._login_thread.start()

    def _on_login_finished(self, _data: object) -> None:
        self.login_btn.setEnabled(True)
        self._refresh_token_status()
        self._update_start_enabled()

    def _on_login_failed(self, message: str) -> None:
        self.login_btn.setEnabled(True)
        self._refresh_token_status()
        QMessageBox.warning(self, "Login failed", message)

    def _on_login_thread_finished(self) -> None:
        self._login_thread = None
        self._login_worker = None

    # -- data ---------------------------------------------------------------------------

    def _choose_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Excel file", self._ui.last_file or "", "Excel files (*.xlsx *.xlsm)"
        )
        if path:
            self._set_excel(Path(path))

    def _set_excel(self, path: Path) -> None:
        self._excel_path = path
        self.file_label.setText(str(path))
        self._ui.last_file = str(path)
        self._update_start_enabled()

    def _make_template(self) -> None:
        from hssk.excel.template import make_template

        default = "hssk_template.xlsx"
        if self._ui.last_file:
            default = str(Path(self._ui.last_file).with_name("hssk_template.xlsx"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel template", default, "Excel files (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            out = make_template(self._load_mapping(), path)
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, "Template error", str(exc))
            return
        QMessageBox.information(self, "Template created", f"Saved to:\n{out}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))

    def _open_mapping(self) -> None:
        path = ensure_mapping_file()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _load_mapping(self):
        return load_mapping(ensure_mapping_file())

    def _validate(self) -> None:
        if self._excel_path is None:
            return
        try:
            mapping = self._load_mapping()
            rows = reader.read_rows(self._excel_path, mapping)
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, "Validation error", str(exc))
            return
        valid = invalid = warns = 0
        lines: list[str] = []
        for idx, raw in rows:
            r = coerce_row(raw, mapping, idx)
            if r.ok:
                valid += 1
            else:
                invalid += 1
                lines.append(f"row {idx}: {'; '.join(r.errors)}")
            for w in r.warnings:
                warns += 1
                lines.append(f"row {idx}: ⚠ {w}")
        summary = f"{valid} valid, {invalid} invalid, {warns} warnings ({len(rows)} rows)."
        detail = "\n".join(lines[:200]) if lines else "No issues found."
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Icon.Information if invalid == 0 else QMessageBox.Icon.Warning)
        dlg.setWindowTitle("Validation")
        dlg.setText(summary)
        dlg.setDetailedText(detail)
        dlg.exec()

    # -- run ----------------------------------------------------------------------------

    def _on_dryrun_toggled(self) -> None:
        dry = self.dryrun_check.isChecked()
        self.banner.setVisible(not dry)
        self.start_btn.setText("Start dry-run" if dry else "PUSH live records")
        self.start_btn.setStyleSheet(
            "" if dry else "background:#cf222e; color:white; font-weight:bold;"
        )

    def _update_start_enabled(self) -> None:
        ready = self._excel_path is not None and self._token is not None
        self.start_btn.setEnabled(ready and self._run_thread is None)

    def _start_run(self) -> None:
        if self._excel_path is None or self._token is None:
            return
        dry_run = self.dryrun_check.isChecked()
        if not dry_run:
            confirm = QMessageBox.question(
                self,
                "Confirm PRODUCTION push",
                "This will create LIVE medical records on hososuckhoe.com.vn.\n\nProceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            mapping = self._load_mapping()
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, "Mapping error", str(exc))
            return

        # persist prefs
        self._ui.delay = self.delay_spin.value()
        self._ui.limit = self.limit_spin.value()
        self._ui.dry_run = dry_run

        settings = engine_settings().model_copy(update={"request_delay": self.delay_spin.value()})
        limit = self.limit_spin.value() or None

        self._reset_results()
        self._run_start = time.monotonic()
        self._run_thread = QThread()
        self._run_worker = RunWorker(
            self._excel_path,
            mapping,
            self._token,
            dry_run=dry_run,
            limit=limit,
            settings=settings,
        )
        self._run_worker.moveToThread(self._run_thread)
        self._run_thread.started.connect(self._run_worker.run)
        self._run_worker.progress.connect(self._on_progress)
        self._run_worker.row.connect(self._on_row)
        self._run_worker.log.connect(self._on_log)
        # Stop the thread first, then run the UI handlers; drop references only after the thread
        # has fully finished — destroying a running QThread aborts the process.
        self._run_worker.finished.connect(self._run_thread.quit)
        self._run_worker.failed.connect(self._run_thread.quit)
        self._run_worker.finished.connect(self._on_run_finished)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_thread.finished.connect(self._run_worker.deleteLater)
        self._run_thread.finished.connect(self._run_thread.deleteLater)
        self._run_thread.finished.connect(self._on_run_thread_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._run_thread.start()

    def _stop_run(self) -> None:
        if self._run_worker is not None:
            self._run_worker.cancel()
            self.stop_btn.setEnabled(False)

    def _reset_results(self) -> None:
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self._counts = {}
        self.counter_label.setText("—")
        self.status_label.setText("")
        self.log_pane.clear()
        self.open_report_btn.setEnabled(False)
        self.open_results_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        if done == 0:
            self.status_label.setText(f"Starting… ({total} rows)")
        elif done >= total:
            self.status_label.setText(f"All {total} rows processed")
        else:
            elapsed = time.monotonic() - self._run_start
            if elapsed > 0:
                rem = int((elapsed / done) * (total - done))
                eta = f"~{rem // 60}m {rem % 60}s left" if rem >= 60 else f"~{rem}s left"
                self.status_label.setText(f"Row {done} of {total}   {eta}")
            else:
                self.status_label.setText(f"Row {done} of {total}")

    def _on_row(self, outcome: RowOutcome) -> None:
        self._counts[outcome.status] = self._counts.get(outcome.status, 0) + 1
        r = self.table.rowCount()
        self.table.insertRow(r)
        cells = [
            str(outcome.row_index),
            outcome.identifier or "",
            outcome.status.value,
            "" if outcome.patient_id is None else str(outcome.patient_id),
            "" if outcome.record_id is None else str(outcome.record_id),
            outcome.message,
        ]
        for c, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if c == 2:
                item.setForeground(QColor(_STATUS_COLORS.get(outcome.status, "#000000")))
            self.table.setItem(r, c, item)
        self.table.scrollToBottom()
        self._update_counter_label()

    def _update_counter_label(self) -> None:
        created = self._counts.get(Status.CREATED, 0) + self._counts.get(Status.DRY_RUN_OK, 0)
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

    def _on_log(self, message: str) -> None:
        self.log_pane.appendPlainText(message)

    def _on_run_finished(self, summary: RunSummary) -> None:
        self._last_run_dir = summary.run_dir
        self._last_results_file = summary.run_dir / "results.xlsx"
        self.open_report_btn.setEnabled(True)
        self.open_results_btn.setEnabled(self._last_results_file.exists())
        self._refresh_token_status()

        processed = len(summary.outcomes)
        skipped = summary.counts.get(Status.SKIPPED_ALREADY, 0)
        parts: list[str] = []

        if summary.aborted:
            if summary.counts.get(Status.AUTH_EXPIRED, 0):
                parts.append(
                    "Your login token expired.\n\n"
                    "Click 'Open website & log in', then press Start again — "
                    "rows already sent will be skipped automatically."
                )
                self.status_label.setText("Aborted — token expired.")
            elif summary.counts.get(Status.RATE_LIMITED, 0):
                parts.append(
                    "The server is busy or temporarily unreachable.\n\n"
                    "Wait a few minutes and press Start again — "
                    "rows already sent will be skipped automatically."
                )
                self.status_label.setText("Aborted — server error.")
            else:
                parts.append("Run cancelled.")
                self.status_label.setText("Cancelled.")
            parts.append(f"Processed {processed} of {summary.total} rows before stopping.")
        else:
            parts.append(f"Done — {processed} rows processed.")
            self.status_label.setText(f"Finished ({processed} rows).")

        if skipped > 0:
            parts.append(
                f"\n{skipped} already-sent row(s) were skipped — safe to re-run, "
                "previously sent rows are always skipped."
            )
        parts.append(f"\nReport: {summary.run_dir}")
        QMessageBox.information(self, "Run complete", "\n".join(parts))

    def _on_run_failed(self, message: str) -> None:
        self.status_label.setText("Error.")
        QMessageBox.critical(self, "Run failed", message)

    def _on_run_thread_finished(self) -> None:
        # Thread has fully stopped — now it is safe to drop references and re-enable Start.
        self._run_thread = None
        self._run_worker = None
        self.stop_btn.setEnabled(False)
        self._update_start_enabled()

    def _open_results(self) -> None:
        if self._last_results_file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_results_file)))

    def _open_report(self) -> None:
        if self._last_run_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_run_dir)))

    def closeEvent(self, event: QCloseEvent) -> None:
        # Never let the window (and its QThreads) be torn down while a worker is still running.
        # If a thread doesn't stop within the timeout, refuse the close rather than risk SIGABRT.
        still_running = False
        for worker, thread in (
            (self._run_worker, self._run_thread),
            (self._login_worker, self._login_thread),
        ):
            if worker is not None:
                worker.cancel()
            if thread is not None and thread.isRunning():
                thread.quit()
                if not thread.wait(10000):
                    still_running = True

        if still_running:
            event.ignore()
            QMessageBox.warning(
                self,
                "Operation still stopping",
                "An operation is still stopping — please wait a moment and try again.",
            )
            return
        event.accept()
