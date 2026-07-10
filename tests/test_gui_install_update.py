"""Platform handoff of `MainWindow._install_update` — the branch `test_gui_threads.py` deliberately
stubs out.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from hssk.auth.token_store import save_token
from hssk.mapping import MappingConfig
from hssk_gui.main_window import MainWindow


def _make_jwt(exp: int) -> str:
    """A JWT-shaped (but unsigned) token good enough for decode_exp/load_token round-tripping."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


@pytest.fixture
def make_window(qtbot, mapping: MappingConfig, monkeypatch: pytest.MonkeyPatch):
    """Factory for an isolated MainWindow: no real mapping I/O, no automatic update-check thread.

    Duplicated from tests/test_gui_threads.py:84 (that fixture is local to its file, not shared
    via conftest.py, and the repo's convention is to duplicate rather than import fixtures across
    test files).
    """

    def _make() -> MainWindow:
        from hssk_gui.settings import UiSettings

        UiSettings().check_updates = False
        save_token(_make_jwt(exp=int(time.time()) + 3600))
        monkeypatch.setattr(MainWindow, "_load_mapping", lambda self, mode="create": mapping)
        window = MainWindow()
        qtbot.addWidget(window)
        window._excel_path = Path("fake.xlsx")
        window._update_start_enabled()
        return window

    return _make


# -- Windows: confirm dialog gates the launch, default is "No" (safe choice) --------------------


def test_windows_confirm_yes_launches_and_closes(
    make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    monkeypatch.setattr(sys, "platform", "win32")

    calls: list[str] = []
    monkeypatch.setattr(
        "hssk_gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(os, "startfile", lambda path: calls.append("startfile"), raising=False)
    monkeypatch.setattr(window, "close", lambda: calls.append("close") or True)

    path = tmp_path / "Setup.exe"
    window._install_update(path, "https://example.com/rel")

    assert calls == ["startfile", "close"]


def test_windows_confirm_no_aborts(
    make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    monkeypatch.setattr(sys, "platform", "win32")

    calls: list[str] = []
    monkeypatch.setattr(
        "hssk_gui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    monkeypatch.setattr(os, "startfile", lambda path: calls.append("startfile"), raising=False)
    monkeypatch.setattr(window, "close", lambda: calls.append("close") or True)

    path = tmp_path / "Setup.exe"
    window._install_update(path, "https://example.com/rel")

    assert calls == []


# -- macOS: opens the downloaded artifact and shows a success hint, never closes ------------------


def test_macos_opens_dmg_and_hints(
    make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    monkeypatch.setattr(sys, "platform", "darwin")

    popen_calls: list[list[str]] = []
    monkeypatch.setattr(
        "hssk_gui.main_window.subprocess.Popen",
        lambda args: popen_calls.append(args),
    )
    close_calls: list[str] = []
    monkeypatch.setattr(window, "close", lambda: close_calls.append("close") or True)

    banner_calls: list[dict] = []
    monkeypatch.setattr(
        window.update_banner,
        "show_message",
        lambda text, **kw: banner_calls.append({"text": text, **kw}),
    )

    path = tmp_path / "Setup.dmg"
    window._install_update(path, "https://example.com/rel")

    assert popen_calls == [["open", str(path)]]
    assert close_calls == []
    assert len(banner_calls) == 1
    assert banner_calls[0]["severity"] == "success"


# -- any other platform: no scripted handoff, same fallback as a download failure -----------------


def test_other_platform_falls_back_to_link(
    make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    monkeypatch.setattr(sys, "platform", "linux")

    startfile_calls: list[str] = []
    monkeypatch.setattr(
        os, "startfile", lambda path: startfile_calls.append("startfile"), raising=False
    )
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(
        "hssk_gui.main_window.subprocess.Popen",
        lambda args: popen_calls.append(args),
    )
    banner_calls: list[dict] = []
    monkeypatch.setattr(
        window.update_banner,
        "show_message",
        lambda text, **kw: banner_calls.append({"text": text, **kw}),
    )

    path = tmp_path / "Setup.tar.gz"
    window._install_update(path, "https://example.com/rel")

    assert startfile_calls == []
    assert popen_calls == []
    assert len(banner_calls) == 1
    assert banner_calls[0]["link_url"] == "https://example.com/rel"
