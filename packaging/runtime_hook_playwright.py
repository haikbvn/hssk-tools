"""PyInstaller runtime hook: point Playwright at the Chromium bundled inside the frozen app."""

import os
import sys

_meipass = getattr(sys, "_MEIPASS", None)
if _meipass:
    bundled = os.path.join(_meipass, "ms-playwright")
    if os.path.isdir(bundled):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", bundled)
