"""GUI entry point."""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from hssk import __version__
from hssk.config import app_icon

from .i18n import set_language
from .main_window import MainWindow
from .settings import UiSettings


def _ensure_terms_accepted() -> bool:
    s = UiSettings()
    if s.terms_accepted:
        return True
    from .legal_dialog import LegalDialog

    dlg = LegalDialog(consent=True)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        s.terms_accepted = True
        return True
    return False


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HSSK Tools")
    app.setOrganizationName("hssk-tools")
    app.setApplicationVersion(__version__)
    icon_path = app_icon()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    set_language(UiSettings().language)
    if not _ensure_terms_accepted():
        return 0
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
