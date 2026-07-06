"""Centralised, dark-mode-aware colour tokens — and the app-wide Fusion palette built from them.

Single source of truth for every colour the GUI uses: the accent colours it paints
programmatically (status text, the production banner, the live-PUSH button, the drag-drop
border) AND the app's base surface palette (window/text/border/highlight), applied via a pinned
Fusion style so the app renders identically on Windows and macOS instead of each OS's native
widget chrome.

Colours follow GitHub Primer's light/dark ramps, which are tuned for contrast on either
background. ``apply_app_theme`` wires ``QStyleHints.colorSchemeChanged`` so a system Light/Dark
switch re-themes the running app live (both the custom-painted surfaces and the Fusion palette).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
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
    # -- app-wide Fusion palette surfaces (GitHub Primer canvas/border/text ramps) --
    # surface_window is the app CANVAS (subtly tinted, not flat white) — surface_base/card_bg
    # below are what actually render white-on-canvas (inputs, tables, QGroupBox cards), giving
    # the modern-QSS layer (app_qss) something to contrast against.
    "surface_window": {"light": "#f6f8fa", "dark": "#0d1117"},
    "surface_base": {"light": "#ffffff", "dark": "#0d1117"},
    "surface_alt_base": {"light": "#f6f8fa", "dark": "#161b22"},
    "surface_button": {"light": "#f6f8fa", "dark": "#21262d"},
    "surface_tooltip": {"light": "#1f2328", "dark": "#e6edf3"},
    "surface_tooltip_text": {"light": "#ffffff", "dark": "#0d1117"},
    "surface_text": {"light": "#1f2328", "dark": "#e6edf3"},
    "surface_text_disabled": {"light": "#8c959f", "dark": "#6e7681"},
    "surface_border": {"light": "#d0d7de", "dark": "#30363d"},
    "surface_highlight": {"light": "#0969da", "dark": "#1f6feb"},
    "surface_highlight_text": {"light": "#ffffff", "dark": "#ffffff"},
    "surface_link": {"light": "#0969da", "dark": "#58a6ff"},
    # -- modern QSS layer (app_qss): cards, button/menu states, progress track, scrollbars --
    "card_bg": {"light": "#ffffff", "dark": "#161b22"},
    "hover_bg": {"light": "#f3f4f6", "dark": "#30363d"},
    "button_hover_bg": {"light": "#eef1f4", "dark": "#30363d"},
    "button_pressed_bg": {"light": "#e7ebf0", "dark": "#282e33"},
    "progress_track": {"light": "#eaeef2", "dark": "#21262d"},
    "scrollbar_hover": {"light": "#afb8c1", "dark": "#484f58"},
}

# Spacing/radius constants shared by scoped QSS and any custom-painted geometry, so hand-built
# widgets (stepper, confirm dialog) share a rhythm with the rest of the app instead of guessing.
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}
RADIUS = {"sm": 4, "md": 6, "lg": 8}

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


def build_palette(scheme: str) -> QPalette:
    """A QPalette for ``scheme`` ("light"/"dark") from the surface_* tokens above.

    Applied on top of the Fusion style so the app renders identically on Windows and macOS —
    Fusion is the one built-in Qt style that fully respects an app-supplied QPalette (native
    styles only partially do), which is also what makes dark mode deterministic here rather than
    dependent on OS-style quirks.
    """

    def c(token: str) -> QColor:
        return QColor(_TOKENS[token][scheme])

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, c("surface_window"))
    p.setColor(QPalette.ColorRole.WindowText, c("surface_text"))
    p.setColor(QPalette.ColorRole.Base, c("surface_base"))
    p.setColor(QPalette.ColorRole.AlternateBase, c("surface_alt_base"))
    p.setColor(QPalette.ColorRole.ToolTipBase, c("surface_tooltip"))
    p.setColor(QPalette.ColorRole.ToolTipText, c("surface_tooltip_text"))
    p.setColor(QPalette.ColorRole.Text, c("surface_text"))
    p.setColor(QPalette.ColorRole.PlaceholderText, c("surface_text_disabled"))
    p.setColor(QPalette.ColorRole.Button, c("surface_button"))
    p.setColor(QPalette.ColorRole.ButtonText, c("surface_text"))
    p.setColor(QPalette.ColorRole.BrightText, c("danger"))
    p.setColor(QPalette.ColorRole.Link, c("surface_link"))
    p.setColor(QPalette.ColorRole.LinkVisited, c("surface_link"))
    p.setColor(QPalette.ColorRole.Highlight, c("surface_highlight"))
    p.setColor(QPalette.ColorRole.HighlightedText, c("surface_highlight_text"))
    p.setColor(QPalette.ColorRole.Light, c("surface_border"))
    p.setColor(QPalette.ColorRole.Mid, c("surface_border"))
    p.setColor(QPalette.ColorRole.Dark, c("surface_border"))
    disabled_text = c("surface_text_disabled")
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    return p


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


def app_qss() -> str:
    """The app-wide modern design system: Primer-flavored cards, buttons, inputs, table, etc.

    Built entirely from tokens/SPACING/RADIUS (an unknown token raises ``KeyError`` here, at
    build time, rather than silently falling back to nothing). Applied over the Fusion style +
    palette in ``apply_app_theme`` — a widget's own ``setStyleSheet`` (the danger button, notice
    banners, the splitter grip, stepper labels) still wins over these app-level rules, so those
    stay exactly as they were.

    Deliberately does NOT touch: bare ``QWidget`` or global ``QLabel`` (would repaint
    ``_DropArea``'s custom border, the results-table empty-state overlay, and banner children),
    or ``QCheckBox``/``QRadioButton`` (Fusion already renders their indicator from the palette
    Highlight color and draws its own focus rect — restyling them risks losing both for no
    visual gain).
    """
    c = color
    sp, rad = SPACING, RADIUS
    return f"""
QGroupBox {{
    background: {c("card_bg")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["lg"]}px;
    padding: {sp["md"]}px;
    padding-top: 34px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    margin: {sp["sm"]}px 0 0 {sp["md"]}px;
    padding: 0;
    font-weight: 600;
    color: {c("surface_text")};
    background: transparent;
}}

QPushButton {{
    background: {c("surface_button")};
    color: {c("surface_text")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    padding: 5px 14px;
    min-height: 28px;
}}
QPushButton:hover {{ background: {c("button_hover_bg")}; }}
QPushButton:pressed {{ background: {c("button_pressed_bg")}; }}
QPushButton:disabled {{
    background: {c("surface_alt_base")};
    color: {c("surface_text_disabled")};
    border-color: {c("surface_border")};
}}
QPushButton:focus {{ border: 1px solid {c("surface_highlight")}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {c("surface_base")};
    color: {c("surface_text")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    padding: 4px {sp["sm"]}px;
    min-height: 26px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c("surface_highlight")};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {c("surface_alt_base")};
    color: {c("surface_text_disabled")};
}}
QComboBox::drop-down {{ border: none; background: transparent; width: 24px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    border: none; background: transparent; width: 18px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none; background: transparent; width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {c("card_bg")};
    border: 1px solid {c("surface_border")};
    selection-background-color: {c("surface_highlight")};
    selection-color: {c("surface_highlight_text")};
    padding: 2px;
}}

QTableWidget {{
    background: {c("surface_base")};
    alternate-background-color: {c("surface_alt_base")};
    gridline-color: {c("surface_border")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    selection-background-color: {c("surface_highlight")};
    selection-color: {c("surface_highlight_text")};
}}
QHeaderView::section {{
    background: {c("surface_alt_base")};
    color: {c("surface_text")};
    border: none;
    border-bottom: 1px solid {c("surface_border")};
    padding: 6px 18px 6px {sp["sm"]}px;
    font-weight: 600;
}}

QPlainTextEdit, QTextBrowser {{
    background: {c("surface_base")};
    color: {c("surface_text")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    padding: 4px;
}}

QProgressBar {{
    background: {c("progress_track")};
    border: none;
    border-radius: 4px;
    text-align: center;
    min-height: 16px;
    max-height: 16px;
    color: {c("surface_text")};
}}
QProgressBar::chunk {{
    background: {c("surface_highlight")};
    border-radius: 3px;
}}

QTabWidget::pane {{
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    top: -1px;
    background: {c("card_bg")};
}}
QTabBar::tab {{
    background: transparent;
    color: {c("muted")};
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {c("surface_text")};
    border-bottom: 2px solid {c("surface_highlight")};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {c("surface_text")}; }}

QMenuBar {{ background: transparent; }}
QMenuBar::item {{ padding: 4px {sp["sm"]}px; border-radius: {rad["sm"]}px; }}
QMenuBar::item:selected {{ background: {c("hover_bg")}; }}
QMenu {{
    background: {c("card_bg")};
    border: 1px solid {c("surface_border")};
    border-radius: {rad["md"]}px;
    padding: 4px;
}}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: {rad["sm"]}px; }}
QMenu::item:selected {{ background: {c("hover_bg")}; }}
QMenu::item:disabled {{ color: {c("surface_text_disabled")}; }}
QMenu::separator {{ height: 1px; background: {c("surface_border")}; margin: 4px {sp["sm"]}px; }}

QToolTip {{
    background: {c("surface_tooltip")};
    color: {c("surface_tooltip_text")};
    border: 1px solid {c("surface_border")};
    padding: 4px 6px;
}}

QScrollBar:vertical {{ width: 10px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c("surface_border")};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {c("scrollbar_hover")}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; width: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {c("surface_border")};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c("scrollbar_hover")}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
"""


def apply_app_theme(app: QApplication, on_change: Callable[[], None] | None = None) -> None:
    """Apply the Fusion palette for the current scheme, then keep it (and ``on_change``) live.

    The app is pinned to the Fusion style (set once, in ``app.py``, before this runs) so the
    palette and app_qss() modern design system below are both fully respected on both OSes. On
    every OS Light/Dark switch this rebuilds the palette AND re-applies the stylesheet (Qt only
    re-polishes styled widgets on a stylesheet change, not on a bare palette change) for the new
    scheme, then calls ``on_change`` so the few custom-painted surfaces (banners, the drag-drop
    border, status text) repaint from ``color()`` too.
    """
    app.setPalette(build_palette(current_scheme()))
    app.setStyleSheet(app_qss())
    hints = app.styleHints()
    if hints is None:
        return

    def _on_scheme_changed(_scheme: Qt.ColorScheme) -> None:
        app.setPalette(build_palette(current_scheme()))
        app.setStyleSheet(app_qss())
        if on_change is not None:
            on_change()

    hints.colorSchemeChanged.connect(_on_scheme_changed)
