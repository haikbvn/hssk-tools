"""Preferences dialog: Run defaults + Record defaults (medicalRecordInfo)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
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

from .settings import UiSettings

# Friendly Vietnamese labels for the common medicalRecordInfo defaults.
_LABELS: dict[str, str] = {
    "normal_desc_value": "Mô tả bình thường",
    "doctorName": "Bác sĩ (mặc định)",
    "healthfacilitiesId": "Mã cơ sở y tế",
    "typeOfExamination": "Mã hình thức khám",
    "reasonCode": "Mã đối tượng khám",
    "reasonsMedicalexamination": "Lý do khám",
    "symptoms": "Bệnh sử mặc định",
    "treatmentDayNumber": "Số ngày điều trị",
    "diagnosesDischarge": "Kết luận mặc định",
    "diagnosesDischargeList": "Danh sách bệnh kèm (cách nhau bởi dấu phẩy)",
    "noteDisease": "Bệnh theo dõi mặc định",
    "treatmentDirection": "Tư vấn điều trị mặc định",
    "treatmentResultId": "Mã kết quả khám",
    "dischargeStatusId": "Mã tình trạng ra viện",
}


class PreferencesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(520)

        self._ui = UiSettings()
        self._widgets: dict[str, QWidget] = {}
        # Tracks which mapping the current Record widgets reflect; None when load failed.
        self._mapping: MappingConfig | None = None

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_run_tab(), "Run defaults")
        tabs.addTab(self._build_record_tab(), "Record defaults")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._restore_btn = QPushButton("Restore defaults")
        self._restore_btn.clicked.connect(self._restore_record_defaults)
        buttons.addButton(self._restore_btn, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- tab builders -------------------------------------------------------------------

    def _build_run_tab(self) -> QWidget:
        w = QWidget()
        box = QGroupBox("Saved run defaults (applied on each launch)")
        form = QFormLayout(box)

        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.2, 10.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setValue(self._ui.delay)
        form.addRow("Delay between rows:", self._delay_spin)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 1_000_000)
        self._limit_spin.setSpecialValueText("0 (all rows)")
        self._limit_spin.setValue(self._ui.limit)
        form.addRow("Row limit:", self._limit_spin)

        self._dryrun_check = QCheckBox("Dry-run by default (don't send)")
        self._dryrun_check.setChecked(self._ui.dry_run)
        form.addRow("", self._dryrun_check)

        lay = QVBoxLayout(w)
        lay.addWidget(box)
        lay.addStretch(1)
        return w

    def _build_record_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        note = QLabel(
            "These values are stamped on every uploaded record when the matching Excel "
            "column is blank or absent. Per-row Excel values always take precedence."
        )
        note.setWordWrap(True)
        lay.addWidget(note)

        box = QGroupBox("medicalRecordInfo defaults")
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
            error_label = QLabel(
                f"Cannot load mapping file: {exc}\n\n"
                "Record defaults cannot be edited until the mapping is valid.\n"
                "Click 'Restore defaults' to recover from the bundled example."
            )
            error_label.setWordWrap(True)
            form.addRow(error_label)

        self._mapping = mapping
        if mapping is None:
            return

        profile = load_profile()

        # Read-only facility ID row (locked to the logged-in account).
        facility_text = (profile.identity_label() if profile else None) or "(chưa đăng nhập)"
        facility_label = QLabel(facility_text)
        facility_label.setStyleSheet("color: #6e7781;")
        form.addRow(_LABELS.get("healthfacilitiesId", "Mã cơ sở y tế") + ":", facility_label)

        # normal_desc_value comes first among editable fields
        nv = mapping.defaults.normal_desc_value
        w_nv = QLineEdit(str(nv))
        form.addRow(_LABELS.get("normal_desc_value", "normal_desc_value") + ":", w_nv)
        self._widgets["normal_desc_value"] = w_nv

        # rest of medicalRecordInfo (skip healthfacilitiesId — read-only above)
        rec: dict[str, Any] = mapping.defaults.medicalRecordInfo
        for key, val in rec.items():
            if key == "healthfacilitiesId":
                continue
            label = _LABELS.get(key, key)
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
                widget.setPlaceholderText(f"(từ tài khoản: {profile.display_name})")
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

        if self._mapping is None:
            # Active mapping is unreadable — inform the user and accept with run defaults only.
            QMessageBox.information(
                self,
                "Run defaults saved",
                "Run defaults were saved.\n\n"
                "Record defaults could not be saved because the mapping file is unreadable. "
                "Click 'Restore defaults' to recover from the bundled example.",
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
            QMessageBox.critical(self, "Save error", str(exc))
            return

        self.accept()
