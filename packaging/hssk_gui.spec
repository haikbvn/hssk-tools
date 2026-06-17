# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds a Windows folder/exe or a macOS .app.

Bundles the Playwright Chromium that CI installs into ``$PLAYWRIGHT_BROWSERS_PATH`` before the
build, plus the example mapping. Run from the repo root: ``pyinstaller packaging/hssk_gui.spec``.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(os.getcwd())

datas = []
binaries = []
hiddenimports = ["hssk", "hssk_gui"]

# Playwright package + driver
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")
datas += pw_datas
binaries += pw_binaries
hiddenimports += pw_hidden

# Bundle the browser CI installed into PLAYWRIGHT_BROWSERS_PATH -> "ms-playwright/" in the app.
_browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
if _browsers and Path(_browsers).is_dir():
    base = Path(_browsers)
    for f in base.rglob("*"):
        if f.is_file():
            datas.append((str(f), str(Path("ms-playwright") / f.relative_to(base).parent)))

# App resources
datas.append((str(ROOT / "config" / "mapping.example.yaml"), "config"))

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[str(ROOT / "packaging" / "runtime_hook_playwright.py")],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hssk-gui",
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="hssk-gui")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="HSSK Tools.app",
        icon=None,
        bundle_identifier="vn.hososuckhoe.hssktools",
    )
