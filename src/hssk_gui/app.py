"""GUI entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from hssk import __version__
from hssk.config import app_icon, data_dir
from hssk.logging_setup import configure_logging

from .i18n import set_language, tr
from .main_window import MainWindow
from .settings import UiSettings
from .theme import apply_app_theme


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
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("HSSK Tools")
    app.setOrganizationName("hssk-tools")
    app.setApplicationVersion(__version__)
    icon_path = app_icon()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    set_language(UiSettings().language)
    # A single GUI instance keeps the dedup ledger safe (two windows could race the done-check);
    # the lock is held for the process lifetime and dropped by the OS even on a hard crash.
    lock = QLockFile(str(data_dir() / "hssk-gui.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.warning(None, "HSSK Tools", tr("msg_gui_already_running"))
        return 0
    if not _ensure_terms_accepted():
        return 0
    window = MainWindow()
    # Re-theme the window's programmatically-coloured labels/button when the OS toggles Light/Dark.
    apply_app_theme(app, on_change=window.on_theme_changed)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
