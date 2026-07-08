"""One-click confirm dialog for a PRODUCTION push.

A plain ``QMessageBox`` Yes/No pair is one click an operator's muscle memory can fire without
reading it. This dialog is custom-drawn (renders identically on both OSes) and defaults focus to
**Cancel**, so an accidental Enter can't fire a live push — the confirmation still requires a
deliberate click on Confirm, just not a typed word.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from . import theme
from .i18n import tr


class ConfirmProductionDialog(QDialog):
    def __init__(self, message: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_confirm_push"))
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(theme.SPACING["md"])

        text = QLabel(message)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(text)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok_btn.setText(tr("btn_confirm_push"))
        cancel_btn.setText(tr("btn_cancel"))
        # Cancel is the default/focused action so a stray Enter/Space cannot fire a live push.
        ok_btn.setAutoDefault(False)
        ok_btn.setDefault(False)
        cancel_btn.setAutoDefault(True)
        cancel_btn.setDefault(True)
        cancel_btn.setFocus()
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        lay.addWidget(self._buttons)

    @staticmethod
    def confirm(message: str, *, parent: QWidget | None = None) -> bool:
        """Show the dialog; True only if the operator clicked Confirm."""
        dlg = ConfirmProductionDialog(message, parent=parent)
        return dlg.exec() == QDialog.DialogCode.Accepted
