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
    excludes=["tkinter", "PIL", "mypy", "mypyc", "pytest", "_pytest", "numpy"],
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

# Copy only the headed Chromium into the finished app (skip headless shell, firefox, webkit, ffmpeg).
# Preserving symlinks is required so the nested .app/.framework bundles stay valid; done post-build
# rather than via Analysis to avoid symlink flattening and the ad-hoc codesign rejection.
# runtime_hook_playwright.py then points PLAYWRIGHT_BROWSERS_PATH at this directory.
_COPY_PREFIXES = ("chromium-",)
_SKIP_SUBSTRINGS = ("headless_shell",)
_ms_dest.mkdir(parents=True, exist_ok=True)
for child in _browsers.iterdir():
    if not any(child.name.startswith(p) for p in _COPY_PREFIXES):
        continue
    if any(s in child.name for s in _SKIP_SUBSTRINGS):
        continue
    shutil.copytree(child, _ms_dest / child.name, symlinks=True, dirs_exist_ok=True)

# Prune Qt frameworks bundled by PyInstaller's PySide6 hook but never used by this pure-QtWidgets
# app. The denylist is deliberately conservative: it EXCLUDES frameworks that a startup-loaded
# library hard-links (verified with `otool -L`), since deleting one of those makes dyld abort the
# process before any window shows. Notably NOT pruned:
#   - QtDBus: hard-linked by QtGui (always loaded) → removing it crashes the app at launch.
#   - QtSvg:  linked by the svg imageformat + svg icon-engine plugins → removing it breaks icons.
# QtPdf is only linked by the optional ``imageformats/libqpdf`` plugin, so we drop that plugin too.
_QT_LIB_PRUNE = {
    "QtPdf", "QtQuick", "QtQml", "QtQmlModels", "QtQmlMeta",
    "QtQmlWorkerScript", "QtOpenGL",
    "QtVirtualKeyboard", "QtVirtualKeyboardQml",
}
_QT_PLUGIN_PRUNE = ("imageformats/libqpdf",)  # orphaned once QtPdf is gone
_TOP_LEVEL_PRUNE = {"PIL", "mypy", "ast_serialize"}

def _prune(root: Path) -> None:
    """Remove unused Qt frameworks/DLLs and stray dev packages from the built bundle."""
    # Qt frameworks (macOS: <name>.framework dirs; Windows: Qt<name>*.dll + PySide6/<name>.pyd)
    qt_lib = root / "PySide6" / "Qt" / "lib"
    if qt_lib.is_dir():
        for entry in qt_lib.iterdir():
            stem = entry.name.split(".")[0]  # "QtPdf.framework" → "QtPdf"
            if stem in _QT_LIB_PRUNE and entry.exists():
                shutil.rmtree(entry)
    # Windows-style DLLs live directly under PySide6/
    pyside_dir = root / "PySide6"
    if pyside_dir.is_dir():
        for entry in pyside_dir.iterdir():
            stem = entry.stem  # "Qt6Pdf.dll" → "Qt6Pdf"
            for name in _QT_LIB_PRUNE:
                if stem == name or stem == f"Qt6{name[2:]}":  # strip "Qt" prefix for Qt6 DLLs
                    entry.unlink(missing_ok=True)
                    break
    # Orphaned plugins whose backing framework we just removed (dylib on mac, dll on win)
    plugins = root / "PySide6" / "Qt" / "plugins"
    for rel in _QT_PLUGIN_PRUNE:
        for ext in (".dylib", ".dll"):
            (plugins / rel).with_suffix(ext).unlink(missing_ok=True)
    # Qt translations (all unused; app ships its own i18n.py)
    qt_trans = root / "PySide6" / "Qt" / "translations"
    if qt_trans.is_dir():
        shutil.rmtree(qt_trans)
    # Top-level dev packages
    for name in _TOP_LEVEL_PRUNE:
        p = root / name
        if p.is_dir():
            shutil.rmtree(p)

if sys.platform == "darwin":
    _prune(Path(DISTPATH) / "HSSK Tools.app" / "Contents" / "Resources")
else:
    _prune(Path(DISTPATH) / "hssk-gui" / "_internal")
