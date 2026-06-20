"""Single-window GUI: login, pick Excel, validate, dry-run/push with live progress."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from hssk.auth.token_store import TokenData, load_token
from hssk.config import ensure_mapping_file
from hssk.config import settings as engine_settings
from hssk.errors import ConfigError, HsskError
from hssk.mapping import load_mapping
from hssk.pipeline.results import RowOutcome, RunSummary, Status

from .i18n import tr
from .preferences_dialog import PreferencesDialog
from .settings import UiSettings
from .workers import LoginWorker, RunWorker, ValidateWorker, ValidationProblem, ValidationSummary

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


def _tr_status(status: Status) -> str:
    """Localized label for a run-result Status (falls back to the raw enum value)."""
    key = f"status_{status.value}"
    text = tr(key)
    return status.value if text == key else text


# Engine-authored row messages from hssk/pipeline/runner.py. Anything not matched here
# (raw API/exception text, per-cell coercion detail) is shown as-is — it is server or
# diagnostic content we don't control. Keep these prefixes in sync with the runner.
_MSG_EXACT = {
    "already processed": "msg_row_already",
    "identifier is blank": "msg_row_id_blank",
    "medicalRecordId is blank": "msg_row_recordid_blank",
}
_MSG_HEADS = [  # "<head>" or "<head> — <name>"
    ("created", "msg_row_created"),
    ("updated", "msg_row_updated"),
    ("payload built (not sent)", "msg_row_dryrun"),
]


def _tr_coerce_msg(msg: str) -> str:
    """Translate a single coerce error/warning line from the engine (no ⚠ prefix)."""
    if msg.startswith("missing required column "):
        return tr("msg_coerce_missing_col") + msg[len("missing required column ") :]
    if ": cannot parse " in msg:
        # "'COL': cannot parse 'VAL' as TYPE (detail)" — translate the two fixed phrases
        msg = msg.replace(": cannot parse ", tr("msg_coerce_cannot_parse"), 1)
        msg = msg.replace(" as ", tr("msg_coerce_as_type"), 1)
        return msg
    if " outside expected range " in msg:
        return msg.replace(" outside expected range ", tr("msg_coerce_range"), 1)
    if " is before " in msg:
        return msg.replace(" is before ", tr("msg_coerce_date_before"), 1)
    return msg


def _tr_coerce_msgs(compound: str) -> str:
    """Translate a semicolon-joined string of coerce errors/warnings (validation path)."""
    parts = compound.split("; ")
    result = []
    for part in parts:
        if part.startswith("⚠ "):
            result.append("⚠ " + _tr_coerce_msg(part[2:]))
        else:
            result.append(_tr_coerce_msg(part))
    return "; ".join(result)


def _tr_message(message: str) -> str:
    """Localize engine-authored row messages; pass diagnostic detail through unchanged."""
    if not message:
        return ""
    exact = _MSG_EXACT.get(message)
    if exact is not None:
        return tr(exact)
    for head, key in _MSG_HEADS:
        if message == head:
            return tr(key)
        if message.startswith(f"{head} — "):
            return f"{tr(key)} — {message[len(head) + 3 :]}"
    # "coercion error: <coerce detail>" — translate prefix and coerce detail
    if message.startswith("coercion error: "):
        return tr("msg_row_coercion") + _tr_coerce_msg(message[len("coercion error: ") :])
    # "fetch detail: <diagnostic tail>" — translate prefix, diagnostic passes through
    if message.startswith("fetch detail: "):
        return tr("msg_row_fetch") + message[len("fetch detail: ") :]
    # Bare/compound coerce errors (runner joins coerced.errors with "; " — no prefix).
    # _tr_coerce_msgs only substitutes a few distinctive fixed phrases, so raw API/exception
    # text is left intact in practice (a server string containing e.g. " is before " could
    # in theory be partially rewritten, but those phrases are specific enough to be safe).
    return _tr_coerce_msgs(message)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        from hssk import __version__

        self.setWindowTitle(tr("window_title").format(version=__version__))

        self._ui = UiSettings()
        geo = self._ui.geometry
        if not geo.isEmpty():
            self.restoreGeometry(geo)
        else:
            self.resize(960, 720)
        self._token: str | None = None
        self._token_data: TokenData | None = None
        self._token_identity = ""
        self._token_low_warned = False
        self._excel_path: Path | None = None
        self._validated_path: Path | None = None  # last file a validation pass completed on
        self._validated_invalid = 0  # invalid-row count from that pass
        self._last_run_dir: Path | None = None
        self._last_results_file: Path | None = None
        self._run_start: float = 0.0
        self._counts: dict[Status, int] = {}

        # thread/worker handles (kept alive while running)
        self._login_thread: QThread | None = None
        self._login_worker: LoginWorker | None = None
        self._validate_thread: QThread | None = None
        self._validate_worker: ValidateWorker | None = None
        self._run_thread: QThread | None = None
        self._run_worker: RunWorker | None = None

        self._build_ui()
        self.setAcceptDrops(True)
        self._restore_prefs()
        self._refresh_token_status()
        self._update_start_enabled()

        self._token_timer = QTimer(self)
        self._token_timer.setInterval(1000)
        self._token_timer.timeout.connect(self._tick_token)
        self._token_timer.start()

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
        settings_menu = self.menuBar().addMenu(tr("menu_settings"))
        prefs_action = QAction(tr("menu_settings_action"), self)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.triggered.connect(self._show_preferences)
        settings_menu.addAction(prefs_action)

        help_menu = self.menuBar().addMenu(tr("menu_help"))

        terms_action = QAction(tr("menu_terms"), self)
        terms_action.setMenuRole(QAction.MenuRole.NoRole)
        terms_action.triggered.connect(lambda: self._show_legal(0))
        help_menu.addAction(terms_action)

        privacy_action = QAction(tr("menu_privacy"), self)
        privacy_action.setMenuRole(QAction.MenuRole.NoRole)
        privacy_action.triggered.connect(lambda: self._show_legal(1))
        help_menu.addAction(privacy_action)

        security_action = QAction(tr("menu_security"), self)
        security_action.setMenuRole(QAction.MenuRole.NoRole)
        security_action.triggered.connect(lambda: self._show_legal(2))
        help_menu.addAction(security_action)

        help_menu.addSeparator()

        about_action = QAction(tr("menu_about"), self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_legal(self, tab: int) -> None:
        from .legal_dialog import LegalDialog

        LegalDialog(self, tab=tab).exec()

    def _show_about(self) -> None:
        from hssk import __version__

        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_body").format(version=__version__),
        )

    def _build_login_box(self) -> QGroupBox:
        box = QGroupBox(tr("group_login"))
        lay = QHBoxLayout(box)
        self.login_btn = QPushButton(tr("btn_login"))
        self.login_btn.clicked.connect(self._do_login)
        self.token_label = QLabel(tr("lbl_not_logged_in"))
        lay.addWidget(self.login_btn)
        lay.addWidget(self.token_label, stretch=1)
        return box

    def _build_data_box(self) -> QGroupBox:
        box = QGroupBox(tr("group_data"))
        lay = QHBoxLayout(box)
        self.choose_btn = QPushButton(tr("btn_choose_excel"))
        self.choose_btn.clicked.connect(self._choose_excel)
        self.file_label = QLabel(tr("lbl_no_file"))
        self.template_btn = QPushButton(tr("btn_template"))
        self.template_btn.clicked.connect(self._make_template)
        self.mapping_btn = QPushButton(tr("btn_open_mapping"))
        self.mapping_btn.clicked.connect(self._open_mapping)
        self.validate_btn = QPushButton(tr("btn_validate"))
        self.validate_btn.clicked.connect(self._validate)
        lay.addWidget(self.choose_btn)
        lay.addWidget(self.file_label, stretch=1)
        lay.addWidget(self.template_btn)
        lay.addWidget(self.mapping_btn)
        lay.addWidget(self.validate_btn)
        return box

    def _build_run_box(self) -> QGroupBox:
        box = QGroupBox(tr("group_run"))
        outer = QVBoxLayout(box)

        controls = QHBoxLayout()
        controls.addWidget(QLabel(tr("lbl_mode")))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("mode_create"))
        self.mode_combo.addItem(tr("mode_update"))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        controls.addWidget(self.mode_combo)
        controls.addSpacing(12)

        controls.addWidget(QLabel(tr("lbl_delay")))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.2, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(1.0)
        controls.addWidget(self.delay_spin)

        controls.addWidget(QLabel(tr("lbl_limit")))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        self.limit_spin.setValue(0)
        controls.addWidget(self.limit_spin)

        self.dryrun_check = QCheckBox(tr("chk_dryrun"))
        self.dryrun_check.setChecked(True)
        self.dryrun_check.stateChanged.connect(self._on_dryrun_toggled)
        controls.addWidget(self.dryrun_check)
        controls.addStretch(1)

        self.start_btn = QPushButton(tr("btn_start_dryrun"))
        self.start_btn.clicked.connect(self._start_run)
        self.stop_btn = QPushButton(tr("btn_stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_run)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        outer.addLayout(controls)

        self.banner = QLabel(tr("banner_production"))
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setStyleSheet(
            "background:#cf222e; color:white; font-weight:bold; padding:4px; border-radius:4px;"
        )
        self.banner.setVisible(False)
        outer.addWidget(self.banner)
        return box

    def _build_results_box(self) -> QGroupBox:
        box = QGroupBox(tr("group_results"))
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
        return box

    # -- preferences --------------------------------------------------------------------

    def _restore_prefs(self) -> None:
        if self._ui.last_file and Path(self._ui.last_file).exists():
            self._set_excel(Path(self._ui.last_file))
        self.delay_spin.setValue(self._ui.delay)
        self.limit_spin.setValue(self._ui.limit)
        self.mode_combo.setCurrentIndex(1 if self._ui.update_mode else 0)
        self.dryrun_check.setChecked(self._ui.dry_run)
        self._refresh_run_controls()

    def _show_preferences(self) -> None:
        dlg = PreferencesDialog(self)
        if dlg.exec() == PreferencesDialog.DialogCode.Accepted:
            self.delay_spin.setValue(self._ui.delay)
            self.limit_spin.setValue(self._ui.limit)
            self.dryrun_check.setChecked(self._ui.dry_run)

    # -- login --------------------------------------------------------------------------

    def _refresh_token_status(self) -> None:
        # Disk reads happen here only (login / run-finished); the per-second tick reuses
        # the cached TokenData so it never touches disk.
        self._token_data = load_token()
        self._token_low_warned = False
        if self._token_data is not None and self._token_data.is_valid():
            profile = load_profile()
            self._token_identity = f"  —  {profile.identity_label()}" if profile else ""
        else:
            self._token_identity = ""
        self._render_token_label()

    def _render_token_label(self) -> None:
        data = self._token_data
        if data is None:
            self._token = None
            self._set_token_label(tr("lbl_not_logged_in"), "#cf222e")
            return
        if not data.is_valid():
            self._token = None
            self._set_token_label(tr("lbl_token_expired"), "#cf222e")
            return
        self._token = data.token
        rem = data.seconds_remaining()
        identity = self._token_identity
        if rem is None:
            self._set_token_label(tr("lbl_logged_in").format(identity=identity), "#1a7f37")
        else:
            color = "#bf8700" if rem < 300 else "#1a7f37"
            text = tr("lbl_logged_in_ttl").format(identity=identity, m=rem // 60, s=rem % 60)
            self._set_token_label(text, color)

    def _tick_token(self) -> None:
        data = self._token_data
        if data is None:
            return
        if not data.is_valid():
            was_logged_in = self._token is not None
            self._render_token_label()  # flips to "expired" and clears self._token
            if was_logged_in:
                self._on_log(tr("log_token_expired"))
                self._update_start_enabled()
            return
        rem = data.seconds_remaining()
        if rem is not None and rem < 300 and not self._token_low_warned:
            self._token_low_warned = True
            self._on_log(tr("log_token_low"))
        self._render_token_label()

    def _set_token_label(self, text: str, color: str) -> None:
        self.token_label.setText(text)
        self.token_label.setStyleSheet(f"color:{color}; font-weight:bold;")

    def _do_login(self) -> None:
        self.login_btn.setEnabled(False)
        self._set_token_label(tr("lbl_opening_browser"), "#0969da")
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
        QMessageBox.warning(self, tr("dlg_login_failed"), message)

    def _on_login_thread_finished(self) -> None:
        self._login_thread = None
        self._login_worker = None

    # -- data ---------------------------------------------------------------------------

    def _choose_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dlg_choose_excel_title"),
            self._ui.last_file or "",
            tr("filter_excel_multi"),
        )
        if path:
            self._set_excel(Path(path))

    def _set_excel(self, path: Path) -> None:
        self._excel_path = path
        self._validated_path = None  # a newly chosen file is unvalidated
        self._validated_invalid = 0
        self.file_label.setText(str(path))
        self._ui.last_file = str(path)
        self._update_start_enabled()

    def _make_template(self) -> None:
        from hssk.excel.template import make_template

        default = "hssk_template.xlsx"
        if self._ui.last_file:
            default = str(Path(self._ui.last_file).with_name("hssk_template.xlsx"))
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dlg_save_template_title"),
            default,
            tr("filter_excel_xlsx"),
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            out = make_template(self._load_mapping(), path)
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, tr("dlg_template_error"), str(exc))
            return
        QMessageBox.information(
            self,
            tr("dlg_template_created"),
            tr("msg_saved_to").format(path=out),
        )
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
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, tr("dlg_validation"), str(exc))
            return
        from hssk.payload import builder  # deferred: loads openpyxl/API stack on first use

        bad_targets = builder.validate_targets(mapping)
        if bad_targets:
            QMessageBox.critical(
                self,
                tr("dlg_validation"),
                tr("msg_bad_targets").format(targets=bad_targets),
            )
            return
        # Re-validating: the old verdict is stale (file may have changed on disk). Drop it
        # so a stopped/failed pass leaves the file marked unvalidated.
        self._validated_path = None
        self._validated_invalid = 0
        self._reset_results(for_validation=True)
        self._run_start = time.monotonic()
        self._validate_thread = QThread()
        self._validate_worker = ValidateWorker(self._excel_path, mapping)
        self._validate_worker.moveToThread(self._validate_thread)
        self._validate_thread.started.connect(self._validate_worker.run)
        self._validate_worker.progress.connect(self._on_progress)
        self._validate_worker.problem.connect(self._on_validate_problem)
        self._validate_worker.finished.connect(self._validate_thread.quit)
        self._validate_worker.failed.connect(self._validate_thread.quit)
        self._validate_worker.finished.connect(self._on_validate_finished)
        self._validate_worker.failed.connect(self._on_validate_failed)
        self._validate_thread.finished.connect(self._validate_worker.deleteLater)
        self._validate_thread.finished.connect(self._validate_thread.deleteLater)
        self._validate_thread.finished.connect(self._on_validate_thread_finished)
        self.validate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._validate_thread.start()

    def _on_validate_problem(self, problem: ValidationProblem) -> None:
        self._append_validation_row(
            problem.row_index, problem.identifier, problem.has_errors, problem.message
        )

    def _on_validate_finished(self, summary: ValidationSummary) -> None:
        if summary.invalid == 0 and summary.warns == 0:
            self.status_label.setText(tr("msg_no_issues"))
            self.counter_label.setStyleSheet("color:#1a7f37; font-weight:bold;")
        else:
            self.status_label.setText(
                tr("msg_validation_summary").format(
                    valid=summary.valid,
                    invalid=summary.invalid,
                    warns=summary.warns,
                    total=summary.total,
                )
            )
            self.counter_label.setStyleSheet("")
        self.counter_label.setText(f"✓ {summary.valid}   ⚠ {summary.warns}   ✗ {summary.invalid}")
        # Only a pass that checked every row counts as validated. A stopped pass reports
        # partial counts (invalid may be 0 simply because the bad rows weren't reached),
        # so leave the file unvalidated to keep the "not validated yet" nudge honest.
        if not summary.cancelled:
            self._validated_path = self._excel_path
            self._validated_invalid = summary.invalid

    def _on_validate_failed(self, message: str) -> None:
        self.status_label.setText(tr("lbl_error"))
        QMessageBox.critical(self, tr("dlg_validation"), message)

    def _on_validate_thread_finished(self) -> None:
        self._validate_thread = None
        self._validate_worker = None
        self.validate_btn.setEnabled(self._excel_path is not None)
        self.stop_btn.setEnabled(self._run_thread is not None)
        self._update_start_enabled()

    def _append_validation_row(
        self, idx: int, identifier: str, has_errors: bool, message: str
    ) -> None:
        status_text = tr("val_status_invalid") if has_errors else tr("val_status_warning")
        status_color = "#cf222e" if has_errors else "#bf8700"
        row = self.table.rowCount()
        self.table.insertRow(row)
        cells = [str(idx), identifier, status_text, "", "", _tr_coerce_msgs(message)]
        for c, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if c == 2:
                item.setForeground(QColor(status_color))
            self.table.setItem(row, c, item)

    # -- run ----------------------------------------------------------------------------

    def _refresh_run_controls(self) -> None:
        dry = self.dryrun_check.isChecked()
        update_mode = self.mode_combo.currentIndex() == 1
        self.banner.setVisible(not dry)
        if not dry:
            self.banner.setText(
                tr("banner_production_update") if update_mode else tr("banner_production")
            )
        if dry:
            self.start_btn.setText(tr("btn_start_dryrun"))
            self.start_btn.setStyleSheet("")
        elif update_mode:
            self.start_btn.setText(tr("btn_start_update_live"))
            self.start_btn.setStyleSheet("background:#cf222e; color:white; font-weight:bold;")
        else:
            self.start_btn.setText(tr("btn_start_live"))
            self.start_btn.setStyleSheet("background:#cf222e; color:white; font-weight:bold;")

    def _on_dryrun_toggled(self) -> None:
        self._refresh_run_controls()

    def _on_mode_changed(self) -> None:
        self._refresh_run_controls()

    def _update_start_enabled(self) -> None:
        ready = self._excel_path is not None and self._token is not None
        idle = self._run_thread is None and self._validate_thread is None
        self.start_btn.setEnabled(ready and idle)
        self.mode_combo.setEnabled(idle)
        self.start_btn.setToolTip(self._start_disabled_reason(ready, idle))

    def _start_disabled_reason(self, ready: bool, idle: bool) -> str:
        if not idle:
            return tr("tip_start_busy")
        need_login = self._token is None
        need_file = self._excel_path is None
        if need_login and need_file:
            return tr("tip_start_need_both")
        if need_login:
            return tr("tip_start_need_login")
        if need_file:
            return tr("tip_start_need_file")
        return ""  # enabled — no tooltip

    def _start_run(self) -> None:
        if self._excel_path is None or self._token is None:
            return
        dry_run = self.dryrun_check.isChecked()
        update_mode = self.mode_combo.currentIndex() == 1
        if not dry_run:
            msg = tr("msg_confirm_push_update") if update_mode else tr("msg_confirm_push")
            if self._validated_path != self._excel_path:
                msg = tr("msg_not_validated_warn") + msg
            elif self._validated_invalid > 0:
                msg = tr("msg_validation_had_errors").format(n=self._validated_invalid) + msg
            confirm = QMessageBox.question(
                self,
                tr("dlg_confirm_push"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            mapping = self._load_mapping()
        except (ConfigError, HsskError) as exc:
            QMessageBox.critical(self, tr("dlg_mapping_error"), str(exc))
            return

        if update_mode and not any(
            spec.target == "medicalRecordId" and spec.required for spec in mapping.columns.values()
        ):
            QMessageBox.critical(
                self,
                tr("dlg_update_needs_record_id"),
                tr("msg_update_needs_record_id"),
            )
            return

        # persist prefs
        self._ui.delay = self.delay_spin.value()
        self._ui.limit = self.limit_spin.value()
        self._ui.dry_run = dry_run
        self._ui.update_mode = update_mode

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
            update_mode=update_mode,
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
        if self._validate_worker is not None:
            self._validate_worker.cancel()
        self.stop_btn.setEnabled(False)

    def _reset_results(self, for_validation: bool = False) -> None:
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

    def _on_progress(self, done: int, total: int) -> None:
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

    def _on_row(self, outcome: RowOutcome) -> None:
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
                parts.append(tr("msg_token_expired_abort"))
                self.status_label.setText(tr("lbl_aborted_token"))
            elif summary.counts.get(Status.RATE_LIMITED, 0):
                parts.append(tr("msg_rate_limited_abort"))
                self.status_label.setText(tr("lbl_aborted_server"))
            else:
                parts.append(tr("msg_run_cancelled"))
                self.status_label.setText(tr("lbl_cancelled"))
            parts.append(tr("msg_processed_of").format(done=processed, total=summary.total))
        else:
            parts.append(tr("msg_done").format(done=processed))
            self.status_label.setText(tr("lbl_finished").format(done=processed))

        if skipped > 0:
            parts.append(tr("msg_skipped_rows").format(skipped=skipped))
        parts.append(tr("msg_report_path").format(path=summary.run_dir))
        # Inline, no modal: headline is in status_label, tally in counter_label, the Open
        # buttons are enabled above — surface the detail + recovery guidance in the log pane.
        self.log_pane.appendPlainText("\n" + "\n".join(parts))

    def _on_run_failed(self, message: str) -> None:
        self.status_label.setText(tr("lbl_error"))
        QMessageBox.critical(self, tr("dlg_run_failed"), message)

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

    @staticmethod
    def _excel_from_mime(event: QDragEnterEvent | QDropEvent) -> Path | None:
        md = event.mimeData()
        if not md.hasUrls():
            return None
        for url in md.urls():
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in (".xlsx", ".xlsm"):
                    return p
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        idle = self._run_thread is None and self._validate_thread is None
        if idle and self._excel_from_mime(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._excel_from_mime(event)
        if path is not None:
            self._set_excel(path)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Never let the window (and its QThreads) be torn down while a worker is still running.
        # If a thread doesn't stop within the timeout, refuse the close rather than risk SIGABRT.
        still_running = False
        for worker, thread in (
            (self._run_worker, self._run_thread),
            (self._validate_worker, self._validate_thread),
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
                tr("dlg_still_stopping"),
                tr("msg_still_stopping"),
            )
            return
        self._token_timer.stop()
        self._ui.geometry = self.saveGeometry()
        event.accept()
