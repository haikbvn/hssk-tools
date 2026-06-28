"""Preferences dialog: Run defaults + Record defaults (medicalRecordInfo)."""

from __future__ import annotations

from typing import Any

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
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hssk.auth.profile import load_profile
from hssk.config import ensure_mapping_file, example_mapping_path
from hssk.errors import ConfigError, HsskError
from hssk.mapping import MappingConfig, load_mapping, save_record_defaults

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


class PreferencesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_prefs_title"))
        self.setMinimumWidth(520)

        self._ui = UiSettings()
        self._widgets: dict[str, QWidget] = {}
        # Tracks which mapping the current Record widgets reflect; None when load failed.
        self._mapping: MappingConfig | None = None

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_run_tab(), tr("tab_run_defaults"))
        tabs.addTab(self._build_record_tab(), tr("tab_record_defaults"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._restore_btn = QPushButton(tr("btn_restore_defaults"))
        self._restore_btn.clicked.connect(self._restore_record_defaults)
        buttons.addButton(self._restore_btn, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- tab builders -------------------------------------------------------------------

    def _build_run_tab(self) -> QWidget:
        w = QWidget()
        box = QGroupBox(tr("grp_run_defaults"))
        form = QFormLayout(box)

        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.2, 10.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setValue(self._ui.delay)
        form.addRow(tr("lbl_delay_rows"), self._delay_spin)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 1_000_000)
        self._limit_spin.setSpecialValueText(tr("spin_all_rows"))
        self._limit_spin.setValue(self._ui.limit)
        form.addRow(tr("lbl_row_limit"), self._limit_spin)

        self._dryrun_check = QCheckBox(tr("chk_dryrun_default"))
        self._dryrun_check.setChecked(self._ui.dry_run)
        form.addRow("", self._dryrun_check)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Tiếng Việt", "vi")
        self._lang_combo.addItem("English", "en")
        idx = self._lang_combo.findData(self._ui.language)
        self._lang_combo.setCurrentIndex(max(idx, 0))
        form.addRow(tr("lbl_language"), self._lang_combo)

        lay = QVBoxLayout(w)
        lay.addWidget(box)
        lay.addStretch(1)
        return w

    def _build_record_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        note = QLabel(tr("note_record_defaults"))
        note.setWordWrap(True)
        lay.addWidget(note)

        box = QGroupBox(tr("grp_record_defaults"))
        form = QFormLayout(box)
        lay.addWidget(box)
        lay.addStretch(1)

        self._record_form = form
        self._load_record_widgets(ensure_mapping_file())
        return w

    def _load_record_widgets(self, mapping_path: Any) -> None:
        form = self._record_form
        # Clear existing rows
        while form.rowCount():
            form.removeRow(0)
        self._widgets.clear()

        try:
            mapping: MappingConfig | None = load_mapping(mapping_path)
        except (ConfigError, HsskError) as exc:
            mapping = None
            error_label = QLabel(tr("msg_mapping_error_prefs").format(exc=exc))
            error_label.setWordWrap(True)
            form.addRow(error_label)

        self._mapping = mapping
        if mapping is None:
            return

        profile = load_profile()

        # Read-only facility ID row (locked to the logged-in account).
        facility_text = (profile.identity_label() if profile else None) or tr("ph_not_logged_in")
        facility_label = QLabel(facility_text)
        facility_label.setStyleSheet("color: #6e7781;")
        form.addRow(_label("healthfacilitiesId") + ":", facility_label)

        # normal_desc_value comes first among editable fields
        nv = mapping.defaults.normal_desc_value
        w_nv = QLineEdit(str(nv))
        form.addRow(_label("normal_desc_value") + ":", w_nv)
        self._widgets["normal_desc_value"] = w_nv

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

    # -- actions ------------------------------------------------------------------------

    def _restore_record_defaults(self) -> None:
        example = example_mapping_path()
        if example.exists():
            self._load_record_widgets(example)

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

    def _accept(self) -> None:
        # Save run defaults immediately (in-memory only, no IO that can fail).
        self._ui.delay = self._delay_spin.value()
        self._ui.limit = self._limit_spin.value()
        self._ui.dry_run = self._dryrun_check.isChecked()

        # Save language selection and apply it immediately; MainWindow re-translates live on
        # accept (it compares the stored language before/after), so no restart is needed.
        new_lang: str = self._lang_combo.currentData()
        if new_lang != self._ui.language:
            self._ui.language = new_lang
            set_language(new_lang)

        if self._mapping is None:
            # Active mapping is unreadable — inform the user and accept with run defaults only.
            QMessageBox.information(
                self,
                tr("dlg_run_defaults_saved"),
                tr("msg_run_defaults_saved"),
            )
            self.accept()
            return

        # Build record values; split comma-joined text back into lists for list-typed keys.
        record_info, normal_desc_value = self._read_record_values()
        orig_rec: dict[str, Any] = self._mapping.defaults.medicalRecordInfo
        for key, val in record_info.items():
            if isinstance(val, str) and isinstance(orig_rec.get(key), list):
                record_info[key] = [s.strip() for s in val.split(",") if s.strip()]

        try:
            save_record_defaults(
                ensure_mapping_file(),
                record_info=record_info,
                normal_desc_value=normal_desc_value,
            )
        except (ConfigError, HsskError, RuntimeError) as exc:
            QMessageBox.critical(self, tr("dlg_save_error"), str(exc))
            return

        self.accept()
