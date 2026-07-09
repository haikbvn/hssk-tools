"""Inline, dismissible notice banner — non-modal replacement for error popups.

Errors surface here instead of ``QMessageBox`` so the log pane and results table stay
readable while the message is shown. The text stays mouse-selectable (popups allowed
copying via Ctrl+C; the banner must not lose that).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .i18n import tr


class NoticeBanner(QWidget):
    """A coloured, word-wrapped, selectable message with an optional link, action button,
    progress bar, and a ✕ button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noticeBanner")
        # Plain QWidgets ignore stylesheet backgrounds without this attribute.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._severity = "danger"
        self._on_action: Callable[[], None] | None = None
        self._on_close: Callable[[], None] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 4, 4)
        outer.setSpacing(2)
        row = QHBoxLayout()
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._link = QLabel()
        self._link.setTextFormat(Qt.TextFormat.RichText)
        self._link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self._link.setVisible(False)
        self._action = QPushButton()
        self._action.setVisible(False)
        self._action.clicked.connect(self._fire_action)
        self._close = QToolButton()
        self._close.setText("✕")
        self._close.setAutoRaise(True)
        self._close.clicked.connect(self._handle_close)
        row.addWidget(self._label, stretch=1)
        row.addWidget(self._link)
        row.addWidget(self._action)
        row.addWidget(self._close, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(row)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(14)
        outer.addWidget(self._progress)

        self.retranslate()
        self.hide()

    def show_message(
        self,
        text: str,
        *,
        severity: str = "danger",
        link_text: str = "",
        link_url: str = "",
        action_text: str = "",
        on_action: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self._severity = severity
        self._label.setText(text)
        if link_text and link_url:
            self._link.setText(f'<a href="{link_url}">{link_text}</a>')
            self._link.setVisible(True)
        else:
            self._link.clear()
            self._link.setVisible(False)
        if action_text and on_action is not None:
            self._action.setText(action_text)
            self._on_action = on_action
            self._action.setVisible(True)
        else:
            self._on_action = None
            self._action.setVisible(False)
        self._on_close = on_close
        self.refresh_theme()
        self.show()

    def _fire_action(self) -> None:
        if self._on_action is not None:
            self._on_action()

    def _handle_close(self) -> None:
        # e.g. cancels an in-flight download; set via show_message(..., on_close=...).
        if self._on_close is not None:
            self._on_close()
        self.clear()

    def update_progress_text(self, text: str, done: int, total: int) -> None:
        """Update just the label + progress fraction (periodic ticks) — leaves link/action as-is."""
        self._label.setText(text)
        self.set_progress(done, total)

    def begin_progress(self) -> None:
        """Show a 0%-initialised progress bar (call ``set_progress`` to advance it)."""
        self._progress.setRange(0, 0)  # busy/indeterminate until the first real total arrives
        self._progress.setVisible(True)

    def set_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(min(done, max(total, 1)))
        self._progress.setVisible(True)

    def end_progress(self) -> None:
        self._progress.setVisible(False)

    def clear(self) -> None:
        self._label.clear()
        self._link.clear()
        self._action.setVisible(False)
        self._on_action = None
        self._on_close = None
        self.end_progress()
        self.hide()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.notice_qss(self._severity))

    def retranslate(self) -> None:
        self._close.setToolTip(tr("tip_dismiss_banner"))
        self._close.setAccessibleName(tr("tip_dismiss_banner"))
        self.setAccessibleName(tr("a11y_error_banner"))
