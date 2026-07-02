"""Inline, dismissible notice banner — non-modal replacement for error popups.

Errors surface here instead of ``QMessageBox`` so the log pane and results table stay
readable while the message is shown. The text stays mouse-selectable (popups allowed
copying via Ctrl+C; the banner must not lose that).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from . import theme
from .i18n import tr


class NoticeBanner(QWidget):
    """A coloured, word-wrapped, selectable message with an optional link and a ✕ button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noticeBanner")
        # Plain QWidgets ignore stylesheet backgrounds without this attribute.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._severity = "danger"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 4, 4)
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._link = QLabel()
        self._link.setTextFormat(Qt.TextFormat.RichText)
        self._link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self._link.setVisible(False)
        self._close = QToolButton()
        self._close.setText("✕")
        self._close.setAutoRaise(True)
        self._close.clicked.connect(self.clear)
        lay.addWidget(self._label, stretch=1)
        lay.addWidget(self._link)
        lay.addWidget(self._close, alignment=Qt.AlignmentFlag.AlignTop)

        self.retranslate()
        self.hide()

    def show_message(
        self,
        text: str,
        *,
        severity: str = "danger",
        link_text: str = "",
        link_url: str = "",
    ) -> None:
        self._severity = severity
        self._label.setText(text)
        if link_text and link_url:
            self._link.setText(f'<a href="{link_url}">{link_text}</a>')
            self._link.setVisible(True)
        else:
            self._link.clear()
            self._link.setVisible(False)
        self.refresh_theme()
        self.show()

    def clear(self) -> None:
        self._label.clear()
        self._link.clear()
        self.hide()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.notice_qss(self._severity))

    def retranslate(self) -> None:
        self._close.setToolTip(tr("tip_dismiss_banner"))
        self._close.setAccessibleName(tr("tip_dismiss_banner"))
        self.setAccessibleName(tr("a11y_error_banner"))
