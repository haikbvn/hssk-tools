# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds a Windows folder/exe or a macOS .app.

Bundles the Playwright Chromium that CI installs into ``$PLAYWRIGHT_BROWSERS_PATH`` before the
build, plus the example mapping. Run from the repo root: ``pyinstaller packaging/hssk_gui.spec``.
"""

import os
import shutil
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

# Locate the Playwright Chromium to bundle (so operators install nothing). CI installs it into
# $PLAYWRIGHT_BROWSERS_PATH; a plain local `playwright install chromium` puts it in Playwright's
# default per-user cache. Honor the env var if set, else fall back to that cache so local builds
# aren't silently shipped without a browser. The actual copy happens *after* the build (see below) —
# routing the nested "Google Chrome for Testing.app" through Analysis flattens its framework symlinks
# and makes PyInstaller's ad-hoc codesign step reject it as an invalid bundle.
def _default_browsers_path():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ms-playwright"
    return Path.home() / ".cache" / "ms-playwright"


_env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
_browsers = Path(_env) if _env else _default_browsers_path()
if not (_browsers.is_dir() and any(_browsers.glob("chromium-*"))):
    raise SystemExit(
        f"No Playwright Chromium found at {_browsers}. Run `playwright install chromium` "
        "(or set PLAYWRIGHT_BROWSERS_PATH) before building, or the app will ship without a browser."
    )

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

_icon = str(ROOT / "packaging" / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico"))

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hssk-gui",
    console=False,
    disable_windowed_traceback=False,
    icon=_icon,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="hssk-gui")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="HSSK Tools.app",
        icon=_icon,
        bundle_identifier="vn.hososuckhoe.hssktools",
    )
    _ms_dest = Path(DISTPATH) / "HSSK Tools.app" / "Contents" / "Resources" / "ms-playwright"
else:
    _ms_dest = Path(DISTPATH) / "hssk-gui" / "ms-playwright"

# Copy Chromium into the finished app, preserving symlinks so the nested .app/.framework bundles stay
# valid. Done here (post-build) rather than via Analysis datas to avoid symlink flattening and the
# ad-hoc codesign step that rejects the collected browser binary. runtime_hook_playwright.py then
# points PLAYWRIGHT_BROWSERS_PATH at this directory.
shutil.copytree(_browsers, _ms_dest, symlinks=True, dirs_exist_ok=True)
