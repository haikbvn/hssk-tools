"""Type-to-confirm PRODUCTION dialog — the GUI counterpart of the CLI's typed-YES prompt.

A plain ``QMessageBox`` Yes/No pair is one click an operator's muscle memory can fire without
reading it. Requiring the same literal ``YES`` the CLI requires (``cli.py:_confirm_production``)
is a deliberately higher-friction, unambiguous confirmation for the one action that sends live
data — and being custom-drawn from plain widgets, it renders identically on both OSes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .i18n import tr

CONFIRM_WORD = "YES"  # deliberately untranslated — matches the CLI's literal prompt exactly


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

        hint = QLabel(tr("dlg_type_to_confirm_hint"))
        lay.addWidget(hint)

        self._input = QLineEdit()
        self._input.setPlaceholderText(CONFIRM_WORD)
        self._input.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._input)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("btn_confirm_push"))
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("btn_cancel"))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        lay.addWidget(self._buttons)

        self._input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(text == CONFIRM_WORD)

    @staticmethod
    def confirm(message: str, *, parent: QWidget | None = None) -> bool:
        """Show the dialog; True only if the operator typed the confirm word and clicked OK."""
        dlg = ConfirmProductionDialog(message, parent=parent)
        return dlg.exec() == QDialog.DialogCode.Accepted
