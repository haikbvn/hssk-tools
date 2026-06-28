"""Centralised, dark-mode-aware colour tokens + a small global stylesheet.

Single source of truth for the accent colours the GUI paints programmatically (status text,
the production banner, the live-PUSH button) plus a conservative app-wide stylesheet (focus
outlines on form inputs, the drag-drop highlight). Native push-button/group-box rendering is
left untouched on purpose — only widgets we already custom-style are themed here, so the app
keeps its platform-native look in both light and dark mode.

Colours follow GitHub Primer's light/dark accent ramps, which are tuned for contrast on either
background. ``apply_app_theme`` wires ``QStyleHints.colorSchemeChanged`` so a system Light/Dark
switch re-themes the running app live.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from hssk.pipeline.results import Status

# token -> {"light": hex, "dark": hex}
_TOKENS: dict[str, dict[str, str]] = {
    "success": {"light": "#1a7f37", "dark": "#3fb950"},
    "info": {"light": "#0969da", "dark": "#58a6ff"},
    "warning": {"light": "#bf8700", "dark": "#d29922"},
    "danger": {"light": "#cf222e", "dark": "#f85149"},
    "muted": {"light": "#6e7781", "dark": "#8b949e"},
    # live-PUSH / UPDATE button (a flat danger background with hover/press/disabled states)
    "danger_btn": {"light": "#cf222e", "dark": "#da3633"},
    "danger_btn_hover": {"light": "#b01c27", "dark": "#f85149"},
    "danger_btn_pressed": {"light": "#8a141d", "dark": "#b62324"},
    "danger_btn_disabled_bg": {"light": "#e3a6ab", "dark": "#6e2b2b"},
    "danger_btn_disabled_fg": {"light": "#fbe9ea", "dark": "#d9b8b8"},
    # production banner
    "banner_bg": {"light": "#cf222e", "dark": "#da3633"},
    "banner_fg": {"light": "#ffffff", "dark": "#ffffff"},
}

# Status -> token name; replaces the old literal _STATUS_COLORS map in results_panel.
STATUS_COLOR_TOKENS: dict[Status, str] = {
    Status.CREATED: "success",
    Status.UPDATED: "success",
    Status.DRY_RUN_OK: "info",
    Status.SKIPPED_ALREADY: "muted",
    Status.INVALID: "warning",
    Status.NO_PATIENT: "warning",
    Status.MULTI_MATCH: "warning",
    Status.FAILED: "danger",
    Status.AUTH_EXPIRED: "danger",
    Status.RATE_LIMITED: "danger",
}


def current_scheme() -> str:
    """Return "dark" or "light" for the active application colour scheme."""
    if QApplication.instance() is None:
        return "light"
    if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def color(token: str) -> str:
    """Hex colour for ``token`` in the active scheme (raises on an unknown token)."""
    return _TOKENS[token][current_scheme()]


def status_color(status: Status) -> str:
    """Hex colour for a row Status, falling back to the default text colour."""
    token = STATUS_COLOR_TOKENS.get(status)
    return color(token) if token else color("muted")


def danger_button_qss() -> str:
    """Scoped stylesheet for the live-PUSH/UPDATE button (set on that button only).

    Keeping it a flat override but with explicit hover/press/disabled states so the most
    dangerous control still gives feedback and visibly greys out while a run is in progress.
    """
    return f"""
QPushButton {{
    background: {color("danger_btn")};
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
}}
QPushButton:hover {{ background: {color("danger_btn_hover")}; }}
QPushButton:pressed {{ background: {color("danger_btn_pressed")}; }}
QPushButton:disabled {{
    background: {color("danger_btn_disabled_bg")};
    color: {color("danger_btn_disabled_fg")};
}}
"""


def banner_qss() -> str:
    """Scoped stylesheet for the production warning banner label."""
    return (
        f"background:{color('banner_bg')}; color:{color('banner_fg')}; "
        "font-weight:bold; padding:4px; border-radius:4px;"
    )


def label_qss(token: str) -> str:
    """``color:…; font-weight:bold;`` for a status label, themed by ``token``."""
    return f"color:{color(token)}; font-weight:bold;"


def app_qss() -> str:
    """Conservative app-wide stylesheet: focus outlines on inputs + the drag-drop highlight.

    Deliberately avoids styling QPushButton/QGroupBox so native rendering is preserved on
    macOS/Windows. Only form inputs (which already render with a border) get a focus accent.
    """
    accent = color("info")
    return f"""
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent};
}}
QWidget[dropTarget="true"] {{
    border: 2px dashed {accent};
    border-radius: 6px;
}}
"""


def apply_app_theme(app: QApplication, on_change: Callable[[], None] | None = None) -> None:
    """Apply the global stylesheet and re-apply (plus call ``on_change``) on a Light/Dark switch."""
    app.setStyleSheet(app_qss())
    hints = app.styleHints()
    if hints is not None:

        def _refresh() -> None:
            app.setStyleSheet(app_qss())
            if on_change is not None:
                on_change()

        hints.colorSchemeChanged.connect(lambda _scheme: _refresh())
