"""License dialog: paste a purchased Polar license key, see status, or open the checkout page.

Used both as the startup gate (``gate=True`` — the app can't proceed until the license checks
out, so "Continue" only enables once it does) and as a Help-menu status view (``gate=False``,
reachable any time to look up who's licensed or install a replacement key).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hssk.config import settings as engine_settings
from hssk.licensing import LicenseCheck, check_license, save_key

from .i18n import tr

# Maps LicenseCheck.reason -> the i18n key for its human-readable explanation.
_REASON_KEYS = {
    "missing_key": "license_reason_missing_key",
    "unconfigured": "license_reason_unconfigured",
    "revoked": "license_reason_revoked",
    "disabled": "license_reason_disabled",
    "expired": "license_reason_expired",
    "not_found": "license_reason_not_found",
    "malformed_response": "license_reason_malformed_response",
    "offline_no_cache": "license_reason_offline_no_cache",
    "offline_grace_expired": "license_reason_offline_grace_expired",
}


class LicenseDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, gate: bool = False) -> None:
        super().__init__(parent)
        self._gate = gate
        self.setWindowTitle(tr("license_title"))
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._status_label)

        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel(tr("license_input_label")))
        self._key_input = QLineEdit()
        self._apply_btn = QPushButton(tr("license_apply"))
        self._apply_btn.clicked.connect(self._on_apply)
        entry_row.addWidget(self._key_input, 1)
        entry_row.addWidget(self._apply_btn)
        layout.addLayout(entry_row)

        buy_row = QHBoxLayout()
        self._buy_btn = QPushButton(tr("license_buy"))
        self._buy_btn.clicked.connect(self._on_buy)
        checkout_url = engine_settings().polar_checkout_url
        if not checkout_url:
            self._buy_btn.setEnabled(False)
            self._buy_btn.setToolTip(tr("license_reason_unconfigured"))
        buy_row.addWidget(self._buy_btn)
        buy_row.addStretch(1)
        layout.addLayout(buy_row)

        momo_note = QLabel(tr("license_buy_momo_note"))
        momo_note.setWordWrap(True)
        layout.addWidget(momo_note)

        self._buttons = QDialogButtonBox()
        if gate:
            self._continue_btn = self._buttons.addButton(
                tr("license_continue"), QDialogButtonBox.ButtonRole.AcceptRole
            )
            quit_btn = self._buttons.addButton(
                tr("license_quit"), QDialogButtonBox.ButtonRole.RejectRole
            )
            self._continue_btn.clicked.connect(self.accept)
            quit_btn.clicked.connect(self.reject)
        else:
            close_btn = self._buttons.addButton(QDialogButtonBox.StandardButton.Close)
            close_btn.clicked.connect(self.reject)
        layout.addWidget(self._buttons)

        self._check: LicenseCheck = check_license()
        self._render_status()

    def current_check(self) -> LicenseCheck:
        return self._check

    def _render_status(self) -> None:
        c = self._check
        if c.ok:
            who = c.customer_email or c.display_key or "?"
            expires = (
                tr("license_status_perpetual")
                if c.expires_at is None
                else c.expires_at.strftime("%Y-%m-%d")
            )
            text = tr("license_status_active").format(who=who, expires=expires)
            if c.source == "grace":
                text = f"{text}\n{tr('license_status_grace')}"
            self._status_label.setText(text)
        else:
            key = _REASON_KEYS.get(c.reason or "", "license_reason_malformed_response")
            self._status_label.setText(tr(key))
        if self._gate:
            self._continue_btn.setEnabled(c.ok)

    def _on_apply(self) -> None:
        key = self._key_input.text().strip()
        if not key:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            save_key(key)
            self._check = check_license(force_refresh=True)
        finally:
            QApplication.restoreOverrideCursor()
        self._render_status()

    def _on_buy(self) -> None:
        url = engine_settings().polar_checkout_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
