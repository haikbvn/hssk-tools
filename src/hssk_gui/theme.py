"""Centralised, dark-mode-aware colour tokens.

Single source of truth for the accent colours the GUI paints programmatically (status text,
the production banner, the live-PUSH button, the drag-drop border). No app-wide stylesheet is
installed — every widget keeps its platform-native look in both light and dark mode; only the
handful of surfaces we already custom-paint read their colours from here.

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
    # inline notice banner (subtle Primer alert palettes: bg / fg / border per severity)
    "notice_danger_bg": {"light": "#ffebe9", "dark": "#442726"},
    "notice_danger_fg": {"light": "#82071e", "dark": "#ffdcd7"},
    "notice_danger_border": {"light": "#ffb1a8", "dark": "#8a3a36"},
    "notice_warning_bg": {"light": "#fff8c5", "dark": "#3a3117"},
    "notice_warning_fg": {"light": "#9a6700", "dark": "#f0d867"},
    "notice_warning_border": {"light": "#eed888", "dark": "#6e5c1f"},
    "notice_info_bg": {"light": "#ddf4ff", "dark": "#12283b"},
    "notice_info_fg": {"light": "#0a3069", "dark": "#a5d6ff"},
    "notice_info_border": {"light": "#a5d6ff", "dark": "#204a72"},
    "notice_success_bg": {"light": "#dafbe1", "dark": "#12351f"},
    "notice_success_fg": {"light": "#1a7f37", "dark": "#3fb950"},
    "notice_success_border": {"light": "#aceebb", "dark": "#2ea043"},
    # status pill backgrounds (results table Trạng thái column); pill TEXT reuses the base
    # accent tokens above (success/info/warning/danger/muted), same as STATUS_COLOR_TOKENS.
    "pill_success_bg": {"light": "#dafbe1", "dark": "#12351f"},
    "pill_info_bg": {"light": "#ddf4ff", "dark": "#12283b"},
    "pill_warning_bg": {"light": "#fff8c5", "dark": "#3a3117"},
    "pill_danger_bg": {"light": "#ffebe9", "dark": "#442726"},
    "pill_muted_bg": {"light": "#eaeef2", "dark": "#30363d"},
    # the log/table splitter grip (a soft bar so operators discover it's draggable)
    "splitter_grip": {"light": "#d0d7de", "dark": "#30363d"},
}

# Status -> token name; replaces the old literal _STATUS_COLORS map in results_panel.
STATUS_COLOR_TOKENS: dict[Status, str] = {
    Status.CREATED: "success",
    Status.UPDATED: "success",
    Status.DELETED: "success",
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


def splitter_qss() -> str:
    """Scoped stylesheet making the log/table splitter handle visible (set on that splitter).

    A soft full-width bar — no fixed horizontal margins, which would break at small widths.
    """
    return (
        f"QSplitter::handle:vertical {{ background: {color('splitter_grip')}; "
        "height: 4px; border-radius: 2px; margin: 1px 0; }"
    )


def notice_qss(severity: str) -> str:
    """Scoped stylesheet for a NoticeBanner container, themed by a severity token triple."""
    bg = color(f"notice_{severity}_bg")
    fg = color(f"notice_{severity}_fg")
    border = color(f"notice_{severity}_border")
    return f"""
QWidget#noticeBanner {{
    background: {bg};
    border: 1px solid {border};
    border-radius: 4px;
}}
QLabel {{ color: {fg}; background: transparent; border: none; }}
QToolButton {{ color: {fg}; background: transparent; border: none; font-weight: bold; }}
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


def apply_app_theme(app: QApplication, on_change: Callable[[], None] | None = None) -> None:
    """Call ``on_change`` whenever the system switches Light/Dark, so the app re-themes live.

    No app-wide stylesheet is installed: every widget keeps fully native rendering (and native
    focus indication). The few custom-painted surfaces (banners, the drag-drop border, status
    text) read their colours from ``color()`` at paint time and repaint via ``on_change``.
    """
    hints = app.styleHints()
    if hints is not None and on_change is not None:
        hints.colorSchemeChanged.connect(lambda _scheme: on_change())
