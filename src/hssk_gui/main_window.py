"""Single-window GUI: login, pick Excel, validate, dry-run/push with live progress."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from hssk.auth.profile import load_profile
from hssk.auth.token_store import TokenData, load_token
from hssk.config import ensure_mapping_file, ensure_update_overlay_file, output_dir
from hssk.config import settings as engine_settings
from hssk.errors import ConfigError, HsskError
from hssk.mapping import load_mapping
from hssk.pipeline.results import RunSummary, Status

from . import theme
from .banner import NoticeBanner
from .i18n import tr
from .messages import _tr_log, _tr_login_status
from .preferences_dialog import PreferencesDialog
from .results_panel import ResultsPanel
from .settings import UiSettings
from .update_check import is_newer
from .workers import (
    LoginWorker,
    RunWorker,
    UpdateCheckWorker,
    ValidateWorker,
    ValidationSummary,
)


def _with_shortcut(text: str, button: QPushButton) -> str:
    """Append the button's shortcut to a tooltip, rendered natively (⌘O on macOS, Ctrl+O
    elsewhere) so no chord ever needs hardcoding in a translatable string."""
    rendered = button.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return f"{text} ({rendered})" if rendered else text


class _ElidingLabel(QLabel):
    """QLabel that middle-elides its text instead of forcing the window wider.

    The full text is available via tooltip when truncation occurs.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        # Ignored horizontal policy: text width contributes no minimum, so it
        # can never force the parent window to grow.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._apply_elision()

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text
        self._apply_elision()

    def text(self) -> str:  # noqa: N802
        return self._full_text

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, self.width())
        super().setText(elided)
        self.setToolTip(self._full_text if elided != self._full_text else "")


class _DropArea(QWidget):
    """Central widget that paints its own dashed drop-target border.

    We draw the highlight in ``paintEvent`` rather than via a Qt Style Sheet ``border`` rule:
    under the native macOS style a plain ``QWidget`` ignores a QSS box border, so the stylesheet
    approach never showed. Manual painting is style-independent and works everywhere.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drop_active = False

    def set_drop_active(self, on: bool) -> None:
        if on != self._drop_active:
            self._drop_active = on
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._drop_active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme.color("info")), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        # Inset by the pen half-width so the 2px stroke stays inside the widget bounds.
        rect = self.rect().adjusted(1, 1, -2, -2)
        painter.drawRoundedRect(rect, 6, 6)


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

        # thread/worker handles (kept alive while running)
        self._login_thread: QThread | None = None
        self._login_worker: LoginWorker | None = None
        self._validate_thread: QThread | None = None
        self._validate_worker: ValidateWorker | None = None
        self._run_thread: QThread | None = None
        self._run_worker: RunWorker | None = None
        self._update_thread: QThread | None = None
        self._update_worker: UpdateCheckWorker | None = None

        self._build_ui()
        self.results.restore_splitter(self._ui.results_splitter)
        self.setAcceptDrops(True)
        self._restore_prefs()
        self._refresh_token_status()
        self._update_start_enabled()

        self._token_timer = QTimer(self)
        self._token_timer.setInterval(1000)
        self._token_timer.timeout.connect(self._tick_token)
        self._token_timer.start()

        if self._ui.check_updates:
            self._start_update_check()

    # -- UI construction ----------------------------------------------------------------

    def _build_ui(self) -> None:
        self._central = _DropArea()
        root = QVBoxLayout(self._central)
        root.setSpacing(10)
        root.setContentsMargins(12, 10, 12, 6)
        # Inline error surface — errors show here instead of modal popups so the log pane
        # underneath stays readable. Distinct from self.banner (the production warning).
        self.error_banner = NoticeBanner()
        root.addWidget(self.error_banner)
        # Separate instance for the newer-version hint so an error never overwrites it.
        self.update_banner = NoticeBanner()
        root.addWidget(self.update_banner)
        root.addWidget(self._build_login_box())
        root.addWidget(self._build_data_box())
        root.addWidget(self._build_run_box())
        self.results = ResultsPanel()
        root.addWidget(self.results, stretch=1)
        root.addWidget(self._build_footer())
        self.setCentralWidget(self._central)
        self._build_menu()

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(0, 0, 4, 2)
        self._footer_link = QLabel()
        self._footer_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._footer_link.setTextFormat(Qt.TextFormat.RichText)
        self._footer_link.linkActivated.connect(lambda _: self._show_sponsor())
        self._render_footer_link()
        lay.addWidget(self._footer_link)
        return footer

    def _render_footer_link(self) -> None:
        self._footer_link.setText(
            f'<a href="#sponsor" style="color: grey; font-size: small; text-decoration: none;">'
            f'{tr("footer_sponsor")} <span style="color: #e05050;">♥</span></a>'
        )

    def _build_menu(self) -> None:
        # No Ctrl+O on any action here: choose_btn already owns it, and a duplicate
        # QKeySequence makes the shortcut ambiguous (Qt then fires neither).
        file_menu = self.menuBar().addMenu(tr("menu_file"))
        self._recent_menu = file_menu.addMenu(tr("menu_open_recent"))
        self._populate_recent_menu()
        file_menu.addSeparator()
        reports_action = QAction(tr("menu_open_reports_root"), self)
        reports_action.setMenuRole(QAction.MenuRole.NoRole)
        reports_action.triggered.connect(self._open_reports_root)
        file_menu.addAction(reports_action)

        settings_menu = self.menuBar().addMenu(tr("menu_settings"))
        prefs_action = QAction(tr("menu_settings_action"), self)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.triggered.connect(self._show_preferences)
        settings_menu.addAction(prefs_action)

        help_menu = self.menuBar().addMenu(tr("menu_help"))

        guide_action = QAction(tr("menu_user_guide"), self)
        guide_action.setMenuRole(QAction.MenuRole.NoRole)
        guide_action.triggered.connect(self._show_guide)
        help_menu.addAction(guide_action)
        help_menu.addSeparator()

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

        sponsor_action = QAction(tr("menu_sponsor"), self)
        sponsor_action.setMenuRole(QAction.MenuRole.NoRole)
        sponsor_action.triggered.connect(self._show_sponsor)
        help_menu.addAction(sponsor_action)

        help_menu.addSeparator()

        about_action = QAction(tr("menu_about"), self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _populate_recent_menu(self) -> None:
        """(Re)fill the Open-recent submenu; callable on its own so _set_excel can refresh it."""
        self._recent_menu.clear()
        recent = self._ui.recent_files
        if not recent:
            empty = QAction(tr("menu_recent_empty"), self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for p in recent:
            act = QAction(p, self)
            act.setMenuRole(QAction.MenuRole.NoRole)
            act.triggered.connect(lambda _checked=False, p=p: self._open_recent(p))
            self._recent_menu.addAction(act)

    def _open_recent(self, path_str: str) -> None:
        p = Path(path_str)
        if p.exists():
            self._set_excel(p)
            return
        self.error_banner.show_message(tr("msg_recent_missing").format(path=path_str))
        self._ui.recent_files = [x for x in self._ui.recent_files if x != path_str]
        self._populate_recent_menu()

    def _open_reports_root(self) -> None:
        # Same root the runner writes into (runner.py _run_batch out_base) — the panel's
        # buttons cover the current run; this reaches every past run.
        s = engine_settings()
        base = (s.data_dir / "output") if s.data_dir else output_dir()
        base.mkdir(parents=True, exist_ok=True)  # openUrl fails silently on a missing path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(base)))

    def _show_guide(self) -> None:
        from .guide_dialog import GuideDialog

        GuideDialog(self).exec()

    def _show_legal(self, tab: int) -> None:
        from .legal_dialog import LegalDialog

        LegalDialog(self, tab=tab).exec()

    def _show_sponsor(self) -> None:
        from .sponsor_dialog import SponsorDialog

        SponsorDialog(self).exec()

    def _show_about(self) -> None:
        from hssk import __version__

        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_body").format(version=__version__),
        )

    def _build_login_box(self) -> QGroupBox:
        self._login_box = QGroupBox(tr("group_login"))
        lay = QHBoxLayout(self._login_box)
        self.login_btn = QPushButton(tr("btn_login"))
        self.login_btn.clicked.connect(self._do_login)
        self.token_label = QLabel(tr("lbl_not_logged_in"))
        self.token_label.setAccessibleName(tr("a11y_token_status"))
        lay.addWidget(self.login_btn)
        lay.addWidget(self.token_label, stretch=1)
        return self._login_box

    def _build_data_box(self) -> QGroupBox:
        self._data_box = QGroupBox(tr("group_data"))
        lay = QHBoxLayout(self._data_box)
        self.choose_btn = QPushButton(tr("btn_choose_excel"))
        self.choose_btn.setShortcut(QKeySequence.StandardKey.Open)  # Ctrl/Cmd+O
        self.choose_btn.clicked.connect(self._choose_excel)
        self.file_label = _ElidingLabel(tr("lbl_no_file"))
        self.file_label.setAccessibleName(tr("a11y_file_status"))
        # Muted so the (long) path doesn't visually dominate its row; re-applied on
        # theme change because the token value differs between light and dark.
        self.file_label.setStyleSheet(f"color: {theme.color('muted')};")
        self.template_btn = QPushButton(tr("btn_template"))
        self.template_btn.clicked.connect(self._make_template)
        self.mapping_btn = QPushButton(tr("btn_open_mapping"))
        self.mapping_btn.clicked.connect(self._open_mapping)
        self.validate_btn = QPushButton(tr("btn_validate"))
        self.validate_btn.setShortcut(QKeySequence("Ctrl+L"))
        self.validate_btn.clicked.connect(self._validate)
        lay.addWidget(self.choose_btn)
        lay.addWidget(self.file_label, stretch=1)
        lay.addWidget(self.template_btn)
        lay.addWidget(self.mapping_btn)
        lay.addWidget(self.validate_btn)
        return self._data_box

    def _build_run_box(self) -> QGroupBox:
        self._run_box = QGroupBox(tr("group_run"))
        outer = QVBoxLayout(self._run_box)

        controls = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("mode_create"))
        self.mode_combo.addItem(tr("mode_update"))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_lbl = QLabel(tr("lbl_mode"))
        self._mode_lbl.setBuddy(self.mode_combo)
        controls.addWidget(self._mode_lbl)
        controls.addWidget(self.mode_combo)
        controls.addSpacing(12)

        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.2, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(1.0)
        self._delay_lbl = QLabel(tr("lbl_delay"))
        # self._delay_lbl.setBuddy(self.delay_spin)
        controls.addWidget(self._delay_lbl)
        controls.addWidget(self.delay_spin)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 1_000_000)
        self.limit_spin.setValue(0)
        self._limit_lbl = QLabel(tr("lbl_limit"))
        self._limit_lbl.setBuddy(self.limit_spin)
        controls.addWidget(self._limit_lbl)
        controls.addWidget(self.limit_spin)

        self.dryrun_check = QCheckBox(tr("chk_dryrun"))
        self.dryrun_check.setChecked(True)
        self.dryrun_check.stateChanged.connect(self._on_dryrun_toggled)
        controls.addWidget(self.dryrun_check)
        controls.addStretch(1)

        self.start_btn = QPushButton(tr("btn_start_dryrun"))
        self.start_btn.setShortcut(QKeySequence("Ctrl+R"))
        self.start_btn.clicked.connect(self._start_run)
        self.stop_btn = QPushButton(tr("btn_stop"))
        self.stop_btn.setShortcut(QKeySequence("Ctrl+."))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_run)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        outer.addLayout(controls)

        self.banner = QLabel(tr("banner_production"))
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setStyleSheet(theme.banner_qss())
        self.banner.setVisible(False)
        outer.addWidget(self.banner)
        self._apply_control_tooltips()
        return self._run_box

    def _apply_control_tooltips(self) -> None:
        self.mode_combo.setToolTip(tr("tip_mode"))
        self.delay_spin.setToolTip(tr("tip_delay"))
        self.limit_spin.setToolTip(tr("tip_limit"))
        self.dryrun_check.setToolTip(tr("tip_dryrun"))
        self.choose_btn.setToolTip(_with_shortcut(tr("tip_choose_excel"), self.choose_btn))
        self.validate_btn.setToolTip(_with_shortcut(tr("tip_validate"), self.validate_btn))
        self.stop_btn.setToolTip(_with_shortcut(tr("tip_stop"), self.stop_btn))

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
        dlg.applied.connect(self._on_prefs_applied)
        dlg.exec()

    def _on_prefs_applied(self, language_changed: bool) -> None:
        # Fires on each Apply (and on OK), so the main window tracks live rather than only
        # syncing once on accept.
        self.delay_spin.setValue(self._ui.delay)
        self.limit_spin.setValue(self._ui.limit)
        self.dryrun_check.setChecked(self._ui.dry_run)
        if language_changed:
            self.retranslate()

    # -- live re-translation / theming --------------------------------------------------

    def retranslate(self) -> None:
        """Re-apply ``tr()`` to all persistent chrome so a language switch takes effect live.

        On-demand dialogs are rebuilt each time they open, so only the always-present main
        window needs this. Transient run/validation status text is left as-is; it is refreshed
        on the next run.
        """
        from hssk import __version__

        self.setWindowTitle(tr("window_title").format(version=__version__))
        self._login_box.setTitle(tr("group_login"))
        self._data_box.setTitle(tr("group_data"))
        self._run_box.setTitle(tr("group_run"))
        self.login_btn.setText(tr("btn_login"))
        self.choose_btn.setText(tr("btn_choose_excel"))
        self.template_btn.setText(tr("btn_template"))
        self.mapping_btn.setText(tr("btn_open_mapping"))
        self.validate_btn.setText(tr("btn_validate"))
        self._mode_lbl.setText(tr("lbl_mode"))
        self.mode_combo.setItemText(0, tr("mode_create"))
        self.mode_combo.setItemText(1, tr("mode_update"))
        self._delay_lbl.setText(tr("lbl_delay"))
        self._limit_lbl.setText(tr("lbl_limit"))
        self.dryrun_check.setText(tr("chk_dryrun"))
        self.stop_btn.setText(tr("btn_stop"))
        self.token_label.setAccessibleName(tr("a11y_token_status"))
        self.file_label.setAccessibleName(tr("a11y_file_status"))
        if self._excel_path is None:
            self.file_label.setText(tr("lbl_no_file"))
        self._apply_control_tooltips()
        self._render_footer_link()
        self.error_banner.retranslate()
        self.update_banner.retranslate()
        self.menuBar().clear()
        self._build_menu()
        self.results.retranslate()
        self._refresh_run_controls()  # start button + banner text
        self._render_token_label()  # token label text
        self._update_start_enabled()  # disabled-reason tooltip

    def on_theme_changed(self) -> None:
        """Re-colour the programmatically-styled chrome after a Light/Dark switch."""
        self._refresh_run_controls()
        self._render_token_label()
        self.file_label.setStyleSheet(f"color: {theme.color('muted')};")
        self.error_banner.refresh_theme()
        self.update_banner.refresh_theme()
        self.results.on_theme_changed()

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
            self._set_token_label(tr("lbl_not_logged_in"), "danger")
            return
        if not data.is_valid():
            self._token = None
            self._set_token_label(tr("lbl_token_expired"), "danger")
            return
        self._token = data.token
        rem = data.seconds_remaining()
        identity = self._token_identity
        if rem is None:
            self._set_token_label(tr("lbl_logged_in").format(identity=identity), "success")
        else:
            token = "warning" if rem < 300 else "success"
            text = tr("lbl_logged_in_ttl").format(identity=identity, m=rem // 60, s=rem % 60)
            self._set_token_label(text, token)

    def _tick_token(self) -> None:
        data = self._token_data
        if data is None:
            return
        if not data.is_valid():
            was_logged_in = self._token is not None
            self._render_token_label()  # flips to "expired" and clears self._token
            if was_logged_in:
                self.results.append_log(tr("log_token_expired"))
                self._update_start_enabled()
            return
        rem = data.seconds_remaining()
        if rem is not None and rem < 300 and not self._token_low_warned:
            self._token_low_warned = True
            self.results.append_log(tr("log_token_low"))
        self._render_token_label()

    def _set_token_label(self, text: str, token: str) -> None:
        self.token_label.setText(text)
        self.token_label.setStyleSheet(theme.label_qss(token))

    def _do_login(self) -> None:
        self.error_banner.clear()
        self.login_btn.setEnabled(False)
        self._set_token_label(tr("lbl_opening_browser"), "info")
        self._login_thread = QThread()
        self._login_worker = LoginWorker()
        self._login_worker.moveToThread(self._login_thread)
        self._login_thread.started.connect(self._login_worker.run)
        self._login_worker.status.connect(
            lambda m: self._set_token_label(_tr_login_status(m), "info")
        )
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
        self.error_banner.show_message(f"{tr('dlg_login_failed')}: {message}")

    def _on_login_thread_finished(self) -> None:
        self._login_thread = None
        self._login_worker = None

    # -- update notification --------------------------------------------------------------

    def _start_update_check(self) -> None:
        self._update_thread = QThread()
        self._update_worker = UpdateCheckWorker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        # Same lifecycle as the login worker: quit first, then UI handler, deleteLater and
        # reference drops only once the thread has fully finished.
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_worker.failed.connect(self._update_thread.quit)
        self._update_worker.finished.connect(self._on_update_check_finished)
        self._update_thread.finished.connect(self._update_worker.deleteLater)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.finished.connect(self._on_update_thread_finished)
        self._update_thread.start()

    def _on_update_check_finished(self, result: object) -> None:
        from hssk import __version__

        if not (isinstance(result, tuple) and len(result) == 2):
            return  # network failure / rate limit / malformed payload / cancelled → silent
        tag, url = result
        if is_newer(tag, __version__):
            self.update_banner.show_message(
                tr("update_available").format(version=tag.lstrip("vV")),
                severity="info",
                link_text=tr("update_link"),
                link_url=url,
            )

    def _on_update_thread_finished(self) -> None:
        self._update_thread = None
        self._update_worker = None

    # -- data ---------------------------------------------------------------------------

    def _choose_excel(self) -> None:
        start = self._ui.last_file or ""
        if start and not Path(start).exists():
            # The last file was moved/deleted — at least open its folder if that survives.
            parent = Path(start).parent
            start = str(parent) if parent.exists() else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dlg_choose_excel_title"),
            start,
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
        self._ui.add_recent_file(str(path))
        self._populate_recent_menu()
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
            out = make_template(self._load_mapping(update=self._is_update_mode()), path)
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

    def _load_mapping(self, *, update: bool = False):
        overlay = ensure_update_overlay_file() if update else None
        return load_mapping(ensure_mapping_file(), overlay_path=overlay)

    def _is_update_mode(self) -> bool:
        return self.mode_combo.currentIndex() == 1

    def _validate(self) -> None:
        if self._excel_path is None:
            return
        self.error_banner.clear()
        try:
            mapping = self._load_mapping(update=self._is_update_mode())
        except (ConfigError, HsskError) as exc:
            self.error_banner.show_message(f"{tr('dlg_validation')}: {exc}")
            return
        from hssk.payload import builder  # deferred: loads openpyxl/API stack on first use

        bad_targets = builder.validate_targets(mapping)
        if bad_targets:
            self.error_banner.show_message(
                f"{tr('dlg_validation')}: {tr('msg_bad_targets').format(targets=bad_targets)}"
            )
            return
        # Re-validating: the old verdict is stale (file may have changed on disk). Drop it
        # so a stopped/failed pass leaves the file marked unvalidated.
        self._validated_path = None
        self._validated_invalid = 0
        self.results.reset(for_validation=True)
        self._validate_thread = QThread()
        self._validate_worker = ValidateWorker(self._excel_path, mapping)
        self._validate_worker.moveToThread(self._validate_thread)
        self._validate_thread.started.connect(self._validate_worker.run)
        self._validate_worker.progress.connect(self.results.set_progress)
        self._validate_worker.problem.connect(self.results.add_validation_row)
        self._validate_worker.finished.connect(self._validate_thread.quit)
        self._validate_worker.failed.connect(self._validate_thread.quit)
        self._validate_worker.finished.connect(self._on_validate_finished)
        self._validate_worker.failed.connect(self._on_validate_failed)
        self._validate_thread.finished.connect(self._validate_worker.deleteLater)
        self._validate_thread.finished.connect(self._validate_thread.deleteLater)
        self._validate_thread.finished.connect(self._on_validate_thread_finished)
        self.stop_btn.setEnabled(True)
        self._update_start_enabled()  # _validate_thread is set, so this disables Start/Validate
        self._validate_thread.start()

    def _on_validate_finished(self, summary: ValidationSummary) -> None:
        self.results.flush_now()  # ensure every buffered row is in the table before summarising
        if summary.invalid == 0 and summary.warns == 0:
            self.results.set_status(tr("msg_no_issues"))
        else:
            # Just the phase + row total — the per-kind numbers live in the colored
            # counter right beside this label, so repeating them here reads as a duplicate.
            self.results.set_status(tr("msg_validation_done").format(total=summary.total))
        self.results.set_counts(
            [
                (tr("counter_valid"), summary.valid, "success"),
                (tr("counter_warns"), summary.warns, "warning"),
                (tr("counter_invalid"), summary.invalid, "danger"),
            ]
        )
        # Only a pass that checked every row counts as validated. A stopped pass reports
        # partial counts (invalid may be 0 simply because the bad rows weren't reached),
        # so leave the file unvalidated to keep the "not validated yet" nudge honest.
        if not summary.cancelled:
            self._validated_path = self._excel_path
            self._validated_invalid = summary.invalid

    def _on_validate_failed(self, message: str) -> None:
        self.results.flush_now()
        self.results.set_status(tr("lbl_error"))
        self.error_banner.show_message(f"{tr('dlg_validation')}: {message}")

    def _on_validate_thread_finished(self) -> None:
        self._validate_thread = None
        self._validate_worker = None
        self.stop_btn.setEnabled(self._run_thread is not None)
        self._update_start_enabled()  # re-enables Validate/Start now that idle is true

    # -- run ----------------------------------------------------------------------------

    def _refresh_run_controls(self) -> None:
        dry = self.dryrun_check.isChecked()
        update_mode = self.mode_combo.currentIndex() == 1
        self.banner.setVisible(not dry)
        self.banner.setStyleSheet(theme.banner_qss())
        if not dry:
            self.banner.setText(
                tr("banner_production_update") if update_mode else tr("banner_production")
            )
        if dry:
            self.start_btn.setText(tr("btn_start_dryrun"))
            self.start_btn.setStyleSheet("")
        else:
            self.start_btn.setText(
                tr("btn_start_update_live") if update_mode else tr("btn_start_live")
            )
            self.start_btn.setStyleSheet(theme.danger_button_qss())

    def _on_dryrun_toggled(self) -> None:
        self._refresh_run_controls()

    def _on_mode_changed(self) -> None:
        self._refresh_run_controls()

    def _update_start_enabled(self) -> None:
        ready = self._excel_path is not None and self._token is not None
        idle = self._run_thread is None and self._validate_thread is None
        self.start_btn.setEnabled(ready and idle)
        self.mode_combo.setEnabled(idle)
        # Validate shares the table/progress with a run, so keep it mutually exclusive: only
        # offer it when a file is loaded and nothing else is running.
        self.validate_btn.setEnabled(self._excel_path is not None and idle)
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
        return _with_shortcut(tr("tip_start_ready"), self.start_btn)  # enabled

    def _start_run(self) -> None:
        if self._excel_path is None or self._token is None:
            return
        self.error_banner.clear()
        dry_run = self.dryrun_check.isChecked()
        update_mode = self.mode_combo.currentIndex() == 1
        if not dry_run:
            msg = tr("msg_confirm_push_update") if update_mode else tr("msg_confirm_push")
            if self._validated_path != self._excel_path:
                msg = tr("msg_not_validated_warn") + msg
            elif self._validated_invalid > 0:
                msg = tr("msg_validation_had_errors").format(n=self._validated_invalid) + msg
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("dlg_confirm_push"))
            box.setText(msg)
            yes_btn = box.addButton(tr("btn_yes"), QMessageBox.ButtonRole.YesRole)
            no_btn = box.addButton(tr("btn_no"), QMessageBox.ButtonRole.NoRole)
            box.setDefaultButton(no_btn)
            box.exec()
            if box.clickedButton() is not yes_btn:
                return

        try:
            mapping = self._load_mapping(update=update_mode)
        except (ConfigError, HsskError) as exc:
            self.error_banner.show_message(f"{tr('dlg_mapping_error')}: {exc}")
            return

        if update_mode and not any(
            spec.target == "medicalRecordId" and spec.required for spec in mapping.columns.values()
        ):
            self.error_banner.show_message(
                f"{tr('dlg_update_needs_record_id')}: {tr('msg_update_needs_record_id')}"
            )
            return

        # persist prefs
        self._ui.delay = self.delay_spin.value()
        self._ui.limit = self.limit_spin.value()
        self._ui.dry_run = dry_run
        self._ui.update_mode = update_mode

        settings = engine_settings().model_copy(update={"request_delay": self.delay_spin.value()})
        limit = self.limit_spin.value() or None

        self.results.reset()
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
        self._run_worker.progress.connect(self.results.set_progress)
        self._run_worker.row.connect(self.results.add_row)
        self._run_worker.log.connect(self._on_run_log)
        # Stop the thread first, then run the UI handlers; drop references only after the thread
        # has fully finished — destroying a running QThread aborts the process.
        self._run_worker.finished.connect(self._run_thread.quit)
        self._run_worker.failed.connect(self._run_thread.quit)
        self._run_worker.finished.connect(self._on_run_finished)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_thread.finished.connect(self._run_worker.deleteLater)
        self._run_thread.finished.connect(self._run_thread.deleteLater)
        self._run_thread.finished.connect(self._on_run_thread_finished)

        self.stop_btn.setEnabled(True)
        self._update_start_enabled()  # _run_thread is set, so this also disables Start/Validate
        self._run_thread.start()

    def _on_run_log(self, msg: str) -> None:
        self.results.append_log(_tr_log(msg))
        # The engine's pre-run token-lifetime estimate is easy to miss in the log pane —
        # mirror it in the banner (wording matched in hssk_gui/messages.py).
        if msg.startswith("token may expire before this batch finishes"):
            self.error_banner.show_message(_tr_log(msg), severity="warning")

    def _stop_run(self) -> None:
        if self._run_worker is not None:
            self._run_worker.cancel()
        if self._validate_worker is not None:
            self._validate_worker.cancel()
        self.stop_btn.setEnabled(False)

    def _on_run_finished(self, summary: RunSummary) -> None:
        self.results.flush_now()  # ensure every buffered row is in the table before summarising
        self.results.record_run(summary.run_dir)
        self._refresh_token_status()

        processed = len(summary.outcomes)
        skipped = summary.counts.get(Status.SKIPPED_ALREADY, 0)
        parts: list[str] = []

        if summary.aborted:
            if summary.counts.get(Status.AUTH_EXPIRED, 0):
                parts.append(tr("msg_token_expired_abort"))
                self.results.set_status(tr("lbl_aborted_token"))
            elif summary.counts.get(Status.RATE_LIMITED, 0):
                parts.append(tr("msg_rate_limited_abort"))
                self.results.set_status(tr("lbl_aborted_server"))
            else:
                parts.append(tr("msg_run_cancelled"))
                self.results.set_status(tr("lbl_cancelled"))
            parts.append(tr("msg_processed_of").format(done=processed, total=summary.total))
        else:
            parts.append(tr("msg_done").format(done=processed))
            self.results.set_status(tr("lbl_finished").format(done=processed))

        if skipped > 0:
            parts.append(tr("msg_skipped_rows").format(skipped=skipped))
        parts.append(tr("msg_report_path").format(path=summary.run_dir))
        # Inline, no modal: headline is in status_label, tally in counter_label, the Open
        # buttons are enabled above — surface the detail + recovery guidance in the log pane.
        self.results.append_log("\n" + "\n".join(parts))

    def _on_run_failed(self, message: str) -> None:
        self.results.flush_now()
        self.results.set_status(tr("lbl_error"))
        self.error_banner.show_message(f"{tr('dlg_run_failed')}: {message}")

    def _on_run_thread_finished(self) -> None:
        # Thread has fully stopped — now it is safe to drop references and re-enable Start.
        self._run_thread = None
        self._run_worker = None
        self.stop_btn.setEnabled(False)
        self._update_start_enabled()

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

    def _set_drop_highlight(self, on: bool) -> None:
        self._central.set_drop_active(on)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        idle = self._run_thread is None and self._validate_thread is None
        if idle and self._excel_from_mime(event) is not None:
            self._set_drop_highlight(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_drop_highlight(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drop_highlight(False)
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
            (self._update_worker, self._update_thread),
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
        self._ui.results_splitter = self.results.save_splitter()
        event.accept()
