"""Preferences dialog: General (run + application) + Record defaults (medicalRecordInfo)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hssk.auth.profile import load_profile
from hssk.config import ensure_mapping_file, example_mapping_path
from hssk.config import settings as engine_settings
from hssk.errors import ConfigError, HsskError
from hssk.mapping import MappingConfig, load_mapping, save_record_defaults

from . import theme
from .banner import NoticeBanner
from .i18n import set_language, tr
from .settings import UiSettings

# Maps medicalRecordInfo default keys to their i18n label strings.
_LABEL_KEYS: dict[str, str] = {
    "normal_desc_value": "rec_normal_desc_value",
    "doctorName": "rec_doctorName",
    "healthfacilitiesId": "rec_healthfacilitiesId",
    "typeOfExamination": "rec_typeOfExamination",
    "reasonCode": "rec_reasonCode",
    "reasonsMedicalexamination": "rec_reasonsMedicalexamination",
    "symptoms": "rec_symptoms",
    "treatmentDayNumber": "rec_treatmentDayNumber",
    "diagnosesDischarge": "rec_diagnosesDischarge",
    "diagnosesDischargeList": "rec_diagnosesDischargeList",
    "noteDisease": "rec_noteDisease",
    "treatmentDirection": "rec_treatmentDirection",
    "treatmentResultId": "rec_treatmentResultId",
    "dischargeStatusId": "rec_dischargeStatusId",
}


def _label(key: str) -> str:
    """Translated label for a record-default field, falling back to the raw key."""
    i18n_key = _LABEL_KEYS.get(key)
    return tr(i18n_key) if i18n_key else key


def split_list_text(text: str) -> list[str]:
    """Comma-separated widget text -> trimmed, non-empty list (the mapping list format)."""
    return [s.strip() for s in text.split(",") if s.strip()]


def coerce_record_values(record_info: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Widget-space record values -> save-space.

    Comma-joined text is split back into a list for every key that is a list in
    ``reference`` (the loaded mapping's ``medicalRecordInfo``). Returns a new dict; the input
    is not mutated.
    """
    out: dict[str, Any] = {}
    for key, val in record_info.items():
        if isinstance(val, str) and isinstance(reference.get(key), list):
            out[key] = split_list_text(val)
        else:
            out[key] = val
    return out


class PreferencesDialog(QDialog):
    # Emitted after every successful apply; payload = whether the language changed.
    applied = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_prefs_title"))
        self.setMinimumWidth(520)

        self._ui = UiSettings()
        self._widgets: dict[str, QWidget] = {}
        # Tracks which mapping the current Record widgets reflect; None when load failed.
        self._mapping: MappingConfig | None = None
        self._mapping_error: str | None = None
        # Values as of the last apply; dirty state is "widgets now" vs these snapshots.
        self._run_snapshot: dict[str, Any] = {}
        self._record_snapshot: dict[str, Any] | None = None
        # Re-entrancy guard: reverting the checkbox in _on_auto_purge_toggled calls
        # setChecked(False), which re-emits toggled — this flag makes that re-entry a no-op.
        self._auto_purge_reverting = False

        # Build the button box first, so a dirty-UI refresh fired while the tabs are being
        # populated has an Apply button to toggle.
        self._buttons = QDialogButtonBox()
        self._ok_btn = self._buttons.addButton(tr("btn_ok"), QDialogButtonBox.ButtonRole.AcceptRole)
        self._cancel_btn = self._buttons.addButton(
            tr("btn_cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self._apply_btn = self._buttons.addButton(
            tr("btn_apply"), QDialogButtonBox.ButtonRole.ApplyRole
        )
        self._restore_btn = self._buttons.addButton(
            tr("btn_restore_run_defaults"), QDialogButtonBox.ButtonRole.ResetRole
        )
        self._buttons.accepted.connect(self._on_ok)
        self._buttons.rejected.connect(self.reject)
        self._apply_btn.clicked.connect(self._on_apply)
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        self._ok_btn.setDefault(True)

        # Inline, non-modal feedback surface (success toast / save-error banner).
        self._banner = NoticeBanner()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(4000)
        self._toast_timer.timeout.connect(self._banner.clear)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), tr("tab_general"))
        self._run_snapshot = self._run_values()
        self._connect_run_watchers()
        self._tabs.addTab(self._build_record_tab(), tr("tab_record_defaults"))
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._banner)
        layout.addWidget(self._buttons)

        self._on_tab_changed(self._tabs.currentIndex())
        self._refresh_dirty_ui()

    # -- tab builders -------------------------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        self._run_grp = QGroupBox(tr("grp_run_defaults"))
        run_form = QFormLayout(self._run_grp)

        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.2, 10.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setToolTip(tr("tip_delay"))
        self._delay_spin.setValue(self._ui.delay)
        self._delay_lbl = QLabel(tr("lbl_delay_rows"))
        run_form.addRow(self._delay_lbl, self._delay_spin)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 1_000_000)
        self._limit_spin.setSpecialValueText(tr("spin_all_rows"))
        self._limit_spin.setToolTip(tr("tip_limit"))
        self._limit_spin.setValue(self._ui.limit)
        self._limit_lbl = QLabel(tr("lbl_row_limit"))
        run_form.addRow(self._limit_lbl, self._limit_spin)

        self._dryrun_check = QCheckBox(tr("chk_dryrun_default"))
        self._dryrun_check.setToolTip(tr("tip_dryrun"))
        self._dryrun_check.setChecked(self._ui.dry_run)
        run_form.addRow("", self._dryrun_check)

        self._app_grp = QGroupBox(tr("grp_app_settings"))
        app_form = QFormLayout(self._app_grp)

        self._updates_check = QCheckBox(tr("chk_check_updates"))
        self._updates_check.setToolTip(tr("tip_check_updates"))
        self._updates_check.setChecked(self._ui.check_updates)
        app_form.addRow("", self._updates_check)

        self._auto_purge_check = QCheckBox(tr("chk_auto_purge"))
        self._auto_purge_check.setToolTip(tr("tip_auto_purge"))
        self._auto_purge_check.setChecked(self._ui.auto_purge)
        self._auto_purge_check.toggled.connect(self._on_auto_purge_toggled)
        app_form.addRow("", self._auto_purge_check)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Tiếng Việt", "vi")
        self._lang_combo.addItem("English", "en")
        self._lang_combo.setToolTip(tr("tip_language"))
        idx = self._lang_combo.findData(self._ui.language)
        self._lang_combo.setCurrentIndex(max(idx, 0))
        self._lang_lbl = QLabel(tr("lbl_language"))
        app_form.addRow(self._lang_lbl, self._lang_combo)

        lay.addWidget(self._run_grp)
        lay.addWidget(self._app_grp)
        lay.addStretch(1)
        return w

    def _build_record_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        self._record_note = QLabel(tr("note_record_defaults"))
        self._record_note.setWordWrap(True)
        lay.addWidget(self._record_note)

        self._record_grp = QGroupBox(tr("grp_record_defaults"))
        form = QFormLayout(self._record_grp)
        lay.addWidget(self._record_grp)
        lay.addStretch(1)

        self._record_form = form
        self._load_record_widgets(ensure_mapping_file(), reset_snapshot=True)
        return w

    def _load_record_widgets(self, mapping_path: Any, *, reset_snapshot: bool) -> None:
        form = self._record_form
        # Clear existing rows
        while form.rowCount():
            form.removeRow(0)
        self._widgets.clear()

        try:
            mapping: MappingConfig | None = load_mapping(mapping_path)
        except (ConfigError, HsskError) as exc:
            mapping = None
            self._mapping_error = str(exc)
            error_label = QLabel(tr("msg_mapping_error_prefs").format(exc=exc))
            error_label.setWordWrap(True)
            form.addRow(error_label)

        self._mapping = mapping
        if mapping is None:
            if reset_snapshot:
                self._record_snapshot = None
            return

        self._mapping_error = None
        profile = load_profile()

        # Read-only facility ID row (locked to the logged-in account).
        facility_text = (profile.identity_label() if profile else None) or tr("ph_not_logged_in")
        facility_label = QLabel(facility_text)
        facility_label.setStyleSheet(f"color: {theme.color('muted')};")
        facility_label.setToolTip(tr("tip_facility_locked"))
        form.addRow(_label("healthfacilitiesId") + ":", facility_label)

        # normal_desc_value comes first among editable fields
        nv = mapping.defaults.normal_desc_value
        w_nv = QLineEdit(str(nv))
        form.addRow(_label("normal_desc_value") + ":", w_nv)
        self._widgets["normal_desc_value"] = w_nv
        self._watch(w_nv)

        # rest of medicalRecordInfo (skip healthfacilitiesId — read-only above)
        rec: dict[str, Any] = mapping.defaults.medicalRecordInfo
        for key, val in rec.items():
            if key == "healthfacilitiesId":
                continue
            label = _label(key)
            widget: QWidget
            if isinstance(val, list):
                widget = QLineEdit(", ".join(str(x) for x in val))
            elif isinstance(val, bool):
                widget = QCheckBox()
                widget.setChecked(bool(val))  # type: ignore[arg-type]
            elif isinstance(val, int):
                widget = QSpinBox()
                widget.setRange(-2_147_483_648, 2_147_483_647)  # type: ignore[attr-defined]
                widget.setValue(val)  # type: ignore[attr-defined]
            elif isinstance(val, float):
                widget = QDoubleSpinBox()
                widget.setRange(-1e9, 1e9)  # type: ignore[attr-defined]
                widget.setValue(val)  # type: ignore[attr-defined]
            else:
                text = str(val) if val is not None else ""
                if not text and profile and key == "doctorName" and profile.display_name:
                    text = profile.display_name
                widget = QLineEdit(text)
            if profile and isinstance(widget, QLineEdit) and key == "doctorName":
                widget.setPlaceholderText(tr("ph_from_account").format(name=profile.display_name))
            form.addRow(label + ":", widget)
            self._widgets[key] = widget
            self._watch(widget)

        if reset_snapshot:
            self._record_snapshot = self._record_values()

    # -- dirty tracking -----------------------------------------------------------------

    def _connect_run_watchers(self) -> None:
        self._delay_spin.valueChanged.connect(self._refresh_dirty_ui)
        self._limit_spin.valueChanged.connect(self._refresh_dirty_ui)
        self._dryrun_check.toggled.connect(self._refresh_dirty_ui)
        self._updates_check.toggled.connect(self._refresh_dirty_ui)
        self._auto_purge_check.toggled.connect(self._refresh_dirty_ui)
        self._lang_combo.currentIndexChanged.connect(self._refresh_dirty_ui)

    def _on_auto_purge_toggled(self, checked: bool) -> None:
        """Enable-time confirmation: ticking the box ON pops a one-time explainer; declining
        reverts it. ``setChecked(False)`` always re-emits ``toggled`` even for a no-op change of
        an already-connected signal, which would recurse back into this handler — guarded two
        ways: ``_auto_purge_reverting`` short-circuits any re-entrant call immediately, and the
        revert itself is wrapped in ``QSignalBlocker`` so the nested emission never happens in the
        first place. ``_refresh_dirty_ui`` is called explicitly afterward so dirty-tracking still
        resyncs to the reverted (unchanged) state.
        """
        if self._auto_purge_reverting:
            return
        if not checked:
            return
        days = engine_settings().output_retention_days
        confirmed = QMessageBox.question(
            self,
            tr("dlg_auto_purge_enable_title"),
            tr("msg_auto_purge_enable_confirm").format(days=days),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            self._auto_purge_reverting = True
            try:
                with QSignalBlocker(self._auto_purge_check):
                    self._auto_purge_check.setChecked(False)
            finally:
                self._auto_purge_reverting = False
            self._refresh_dirty_ui()

    def _watch(self, w: QWidget) -> None:
        """Connect the appropriate change signal of a record widget to the dirty refresh."""
        if isinstance(w, QCheckBox):
            w.toggled.connect(self._refresh_dirty_ui)
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.valueChanged.connect(self._refresh_dirty_ui)
        elif isinstance(w, QLineEdit):
            w.textChanged.connect(self._refresh_dirty_ui)

    def _run_values(self) -> dict[str, Any]:
        return {
            "delay": self._delay_spin.value(),
            "limit": self._limit_spin.value(),
            "dry_run": self._dryrun_check.isChecked(),
            "check_updates": self._updates_check.isChecked(),
            "auto_purge": self._auto_purge_check.isChecked(),
            "language": self._lang_combo.currentData(),
        }

    def _record_values(self) -> dict[str, Any]:
        record_info, normal_desc_value = self._read_record_values()
        return {"normal_desc_value": normal_desc_value, **record_info}

    def _run_dirty(self) -> bool:
        return self._run_values() != self._run_snapshot

    def _record_dirty(self) -> bool:
        if self._mapping is None:
            return False  # nothing editable, nothing to write
        if self._record_snapshot is None:
            return True  # example loaded over a broken file — must write
        return self._record_values() != self._record_snapshot

    def _is_dirty(self) -> bool:
        return self._run_dirty() or self._record_dirty()

    def _refresh_dirty_ui(self) -> None:
        self._apply_btn.setEnabled(self._is_dirty())

    def _mark_clean(self) -> None:
        self._run_snapshot = self._run_values()
        if self._mapping is not None:
            self._record_snapshot = self._record_values()
        self._refresh_dirty_ui()

    def _read_record_values(self) -> tuple[dict[str, Any], str]:
        """Extract current widget values; return (record_info_dict, normal_desc_value)."""
        normal_desc_value = ""
        record_info: dict[str, Any] = {}
        for key, widget in self._widgets.items():
            if key == "normal_desc_value":
                normal_desc_value = widget.text().strip() if isinstance(widget, QLineEdit) else ""  # type: ignore[union-attr]
                continue
            if isinstance(widget, QCheckBox):
                val: Any = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                val = widget.value()
            elif isinstance(widget, QSpinBox):
                val = widget.value()
            else:
                raw = widget.text().strip() if isinstance(widget, QLineEdit) else ""  # type: ignore[union-attr]
                val = raw
            record_info[key] = val
        return record_info, normal_desc_value

    # -- apply / ok / cancel ------------------------------------------------------------

    def _on_apply(self) -> None:
        self._apply_changes()

    def _on_ok(self) -> None:
        if self._apply_changes():
            self.accept()

    def _apply_changes(self) -> bool:
        """Persist the dirty tabs. Returns False iff the mapping write failed (banner shown,
        nothing else applied, dialog stays open for retry/cancel)."""
        run_dirty = self._run_dirty()
        record_dirty = self._record_dirty()
        if not run_dirty and not record_dirty:
            return True  # nothing to do; OK just closes, mapping.yaml untouched

        # The fallible mapping write goes first: on failure nothing else is touched, so the
        # "nothing was applied" the error copy promises actually holds.
        if record_dirty and not self._save_record_defaults():
            return False

        lang_changed = self._save_run_defaults() if run_dirty else False
        self._mark_clean()
        if lang_changed:
            self.retranslate()
        self._show_toast(tr("msg_prefs_applied"))
        self.applied.emit(lang_changed)
        return True

    def _save_record_defaults(self) -> bool:
        assert self._mapping is not None  # guarded: record_dirty is False when mapping is None
        record_info, normal_desc_value = self._read_record_values()
        record_info = coerce_record_values(record_info, self._mapping.defaults.medicalRecordInfo)
        try:
            save_record_defaults(
                ensure_mapping_file(),
                record_info=record_info,
                normal_desc_value=normal_desc_value,
            )
        except (ConfigError, HsskError, RuntimeError) as exc:
            self._toast_timer.stop()  # don't let a pending toast-clear wipe the error
            self._banner.show_message(
                tr("msg_prefs_save_failed").format(exc=exc), severity="danger"
            )
            return False
        return True

    def _save_run_defaults(self) -> bool:
        """Write only the changed QSettings keys. Returns whether the language changed."""
        snap = self._run_snapshot
        cur = self._run_values()
        if cur["delay"] != snap.get("delay"):
            self._ui.delay = cur["delay"]
        if cur["limit"] != snap.get("limit"):
            self._ui.limit = cur["limit"]
        if cur["dry_run"] != snap.get("dry_run"):
            self._ui.dry_run = cur["dry_run"]
        if cur["check_updates"] != snap.get("check_updates"):
            self._ui.check_updates = cur["check_updates"]
        if cur["auto_purge"] != snap.get("auto_purge"):
            self._ui.auto_purge = cur["auto_purge"]
        language_changed = cur["language"] != snap.get("language")
        if language_changed:
            self._ui.language = cur["language"]
            set_language(cur["language"])
        return language_changed

    def _show_toast(self, text: str) -> None:
        self._banner.show_message(text, severity="success")
        self._toast_timer.start()

    # -- reset (per visible tab) --------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._restore_btn.setText(tr("btn_restore_record_defaults"))
            self._restore_btn.setToolTip(tr("tip_restore_record"))
        else:
            self._restore_btn.setText(tr("btn_restore_run_defaults"))
            self._restore_btn.setToolTip(tr("tip_restore_run"))

    def _on_restore_clicked(self) -> None:
        if self._tabs.currentIndex() == 1:
            self._restore_record_defaults()
        else:
            self._restore_run_defaults()

    def _restore_run_defaults(self) -> None:
        # Stage factory values only; nothing is saved until Apply/OK.
        self._delay_spin.setValue(UiSettings.DELAY_DEFAULT)
        self._limit_spin.setValue(UiSettings.LIMIT_DEFAULT)
        self._dryrun_check.setChecked(UiSettings.DRY_RUN_DEFAULT)
        self._updates_check.setChecked(UiSettings.CHECK_UPDATES_DEFAULT)
        # Restoring to the (off) factory default never needs the enable-time confirmation —
        # block the toggled signal so _on_auto_purge_toggled doesn't re-fire for a no-op/OFF set.
        with QSignalBlocker(self._auto_purge_check):
            self._auto_purge_check.setChecked(UiSettings.AUTO_PURGE_DEFAULT)
        # Language is an identity/environment choice, not a run default — leave it unchanged.
        self._refresh_dirty_ui()

    def _restore_record_defaults(self) -> None:
        example = example_mapping_path()
        if example.exists():
            # Stage the example values; snapshot is deliberately not reset, so this shows
            # dirty and Apply knows to write.
            self._load_record_widgets(example, reset_snapshot=False)
            self._refresh_dirty_ui()

    # -- cancel / close -----------------------------------------------------------------

    def reject(self) -> None:
        """Esc, Cancel and the window close button all funnel here — prompt when dirty."""
        if self._is_dirty():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("dlg_discard_title"))
            box.setText(tr("msg_discard_changes"))
            discard = box.addButton(tr("btn_discard"), QMessageBox.ButtonRole.DestructiveRole)
            keep = box.addButton(tr("btn_keep_editing"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(keep)
            box.exec()
            if box.clickedButton() is not discard:
                return
        super().reject()

    # -- live re-translation ------------------------------------------------------------

    def retranslate(self) -> None:
        self.setWindowTitle(tr("dlg_prefs_title"))
        self._tabs.setTabText(0, tr("tab_general"))
        self._tabs.setTabText(1, tr("tab_record_defaults"))
        self._run_grp.setTitle(tr("grp_run_defaults"))
        self._app_grp.setTitle(tr("grp_app_settings"))
        self._delay_lbl.setText(tr("lbl_delay_rows"))
        self._limit_lbl.setText(tr("lbl_row_limit"))
        self._lang_lbl.setText(tr("lbl_language"))
        self._delay_spin.setToolTip(tr("tip_delay"))
        self._limit_spin.setToolTip(tr("tip_limit"))
        self._limit_spin.setSpecialValueText(tr("spin_all_rows"))
        self._dryrun_check.setText(tr("chk_dryrun_default"))
        self._dryrun_check.setToolTip(tr("tip_dryrun"))
        self._updates_check.setText(tr("chk_check_updates"))
        self._updates_check.setToolTip(tr("tip_check_updates"))
        self._auto_purge_check.setText(tr("chk_auto_purge"))
        self._auto_purge_check.setToolTip(tr("tip_auto_purge"))
        self._lang_combo.setToolTip(tr("tip_language"))
        self._record_note.setText(tr("note_record_defaults"))
        self._record_grp.setTitle(tr("grp_record_defaults"))
        self._ok_btn.setText(tr("btn_ok"))
        self._cancel_btn.setText(tr("btn_cancel"))
        self._apply_btn.setText(tr("btn_apply"))
        self._on_tab_changed(self._tabs.currentIndex())
        self._banner.retranslate()
        self._banner.clear()
        self._toast_timer.stop()
        # Only ever called right after a successful apply, so disk == widgets and reloading
        # the record form to pick up new labels is lossless.
        self._load_record_widgets(ensure_mapping_file(), reset_snapshot=True)
        self._refresh_dirty_ui()
