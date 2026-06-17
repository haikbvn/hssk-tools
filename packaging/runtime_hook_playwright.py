"""PyInstaller runtime hook: point Playwright at the Chromium bundled inside the frozen app.

The browser is bundled into an ``ms-playwright/`` directory (see hssk_gui.spec). Where that lands at
runtime depends on platform and PyInstaller version: it is ``sys._MEIPASS`` for a Windows/onedir
build, but inside a macOS ``.app`` the data may sit under ``Contents/Resources`` while ``_MEIPASS``
points at ``Contents/Frameworks`` (or vice-versa). Probe the likely roots and point
``PLAYWRIGHT_BROWSERS_PATH`` at the first ``ms-playwright`` directory we find, so Playwright doesn't
fall back to its (absent) default browser location.
"""

import os
import sys
from pathlib import Path


def _candidate_roots():
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass)
        roots += [p, p.parent / "Resources", p.parent / "Frameworks"]
    exe_dir = Path(sys.executable).resolve().parent  # .../Contents/MacOS on a .app
    roots += [exe_dir, exe_dir.parent / "Resources", exe_dir.parent / "Frameworks"]
    return roots


if getattr(sys, "frozen", False):
    for root in _candidate_roots():
        bundled = root / "ms-playwright"
        if bundled.is_dir():
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))
            break
