"""The modern app_qss() design system: builds cleanly and every colour traces back to a token.

Sets QT_QPA_PLATFORM=offscreen (same trick as scripts/gui_smoke.py) so this can construct a real
QApplication and actually apply the stylesheet — the only way to catch a QSS syntax error Qt would
otherwise only report as a runtime qWarning ("Could not parse stylesheet"), never an exception.

Most tests here don't touch Qt at all (they call app_qss() as a pure string builder with
current_scheme monkeypatched). Only test_app_qss_parses_without_qt_warnings needs a real,
widget-capable QApplication — created at import time, like test_gui_validate_worker.py's
QCoreApplication, so it wins the one-per-process app slot. A QCoreApplication cannot be upgraded
to a full QApplication after the fact, so if some other module's QCoreApplication.instance() runs
first (only possible if a new test file collects alphabetically before this one and creates a
bare QCoreApplication of its own), that one test skips instead of failing the whole suite.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QPushButton

from hssk_gui import theme

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def app() -> QApplication:
    if not isinstance(_app, QApplication):
        pytest.skip("process-wide Qt app singleton is a bare QCoreApplication, not a QApplication")
    return _app


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_app_qss_builds_for_every_scheme(monkeypatch: pytest.MonkeyPatch, scheme: str) -> None:
    monkeypatch.setattr(theme, "current_scheme", lambda: scheme)
    qss = theme.app_qss()
    assert qss.strip(), f"app_qss() produced empty output for scheme={scheme}"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_hex_literal_traces_to_a_token(monkeypatch: pytest.MonkeyPatch, scheme: str) -> None:
    """Guards against a future hardcoded colour sneaking into app_qss() (bypassing color())."""
    monkeypatch.setattr(theme, "current_scheme", lambda: scheme)
    qss = theme.app_qss()
    known = {v[scheme].lower() for v in theme._TOKENS.values()}
    found = {h.lower() for h in _HEX_RE.findall(qss)}
    assert found, "expected at least one colour in app_qss() output"
    unknown = found - known
    assert not unknown, f"app_qss() ({scheme}) uses colour(s) not in _TOKENS: {unknown}"


def test_app_qss_parses_without_qt_warnings(app: QApplication) -> None:
    """Applying the stylesheet to a real (offscreen) QApplication must not trigger Qt's
    "Could not parse stylesheet" warning — Qt only logs that, it never raises."""
    messages: list[str] = []

    def handler(_msg_type: QtMsgType, _context: object, msg: str) -> None:
        messages.append(msg)

    qInstallMessageHandler(handler)
    try:
        app.setStyleSheet(theme.app_qss())
        # The stylesheet is only actually parsed/polished once something needs to render with
        # it; a real (if invisible, offscreen) widget forces that pass.
        btn = QPushButton("test")
        btn.show()
        app.processEvents()
        btn.close()
    finally:
        qInstallMessageHandler(None)
        app.setStyleSheet("")

    parse_warnings = [m for m in messages if "stylesheet" in m.lower()]
    assert not parse_warnings, f"Qt reported stylesheet parse warning(s): {parse_warnings}"


def test_build_palette_and_app_qss_agree_on_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check that light and dark actually produce different output (no scheme collapsed
    to the other by a copy-paste key mistake in _TOKENS)."""
    monkeypatch.setattr(theme, "current_scheme", lambda: "light")
    light_qss = theme.app_qss()
    monkeypatch.setattr(theme, "current_scheme", lambda: "dark")
    dark_qss = theme.app_qss()
    assert light_qss != dark_qss
