"""Bundle and apply a single Vietnamese-first font app-wide.

Segoe UI (Windows) and SF Pro (macOS) differ enough in metrics that "the same layout" never
quite looks the same cross-platform — one real driver behind pinning Fusion (see ``theme.py``).
Bundling Be Vietnam Pro (SIL OFL, full Vietnamese diacritic coverage) removes that drift and
renders diacritics better than either OS default, for a UI where every label is Vietnamese.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from hssk.config import font_asset

FAMILY = "Be Vietnam Pro"
_FILES = ("BeVietnamPro-Regular.ttf", "BeVietnamPro-Medium.ttf", "BeVietnamPro-SemiBold.ttf")
_POINT_SIZE = 10


def load_bundled_font() -> str | None:
    """Register the bundled TTFs and return the loadable family name, or None if unavailable.

    Missing font files (e.g. a source checkout without the bundled assets) degrade gracefully:
    the app keeps the platform default font rather than failing to start.
    """
    loaded_any = False
    for filename in _FILES:
        path = font_asset(filename)
        if path.exists():
            if QFontDatabase.addApplicationFont(str(path)) != -1:
                loaded_any = True
    return FAMILY if loaded_any else None


def apply_app_font(app: QApplication) -> None:
    """Set the bundled font as the application-wide default, if it loaded."""
    family = load_bundled_font()
    if family is not None:
        app.setFont(QFont(family, _POINT_SIZE))
