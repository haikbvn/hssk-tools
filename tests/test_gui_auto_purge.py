"""Launch-time auto-purge (opt-in, default off — see Plan 007).

``MainWindow._auto_purge_on_launch`` runs during ``__init__``, before any worker exists, and
reuses the same run-*-only scanner (``hssk.maintenance.find_old_runs``/``purge_runs``) as the
existing manual "Purge old reports" action. These tests cover the four documented behaviors:
flag off (no-op), flag on with stale dirs (purge + banner), flag on with nothing stale (silent
no-op), and the mid-batch-safety property that the purge is fully done by the time __init__
returns and none of MainWindow's four background-job handles have ever been created.

Isolation fixtures (``_isolated_qt_env``, ``make_window``) are copied from
``tests/test_gui_threads.py`` rather than imported, per that file's own convention of keeping
each GUI test module self-contained.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from hssk import config as hssk_config
from hssk.auth.token_store import save_token
from hssk.mapping import MappingConfig
from hssk_gui.main_window import MainWindow
from hssk_gui.settings import UiSettings


def _make_jwt(exp: int) -> str:
    """A JWT-shaped (but unsigned) token good enough for decode_exp/load_token round-tripping."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


@pytest.fixture(autouse=True)
def _isolated_qt_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # See test_gui_threads.py for the full rationale: UiSettings.__init__'s 2-arg QSettings()
    # ignores setDefaultFormat() on this Qt/platform combo, so the QSettings name settings.py
    # resolves through is patched to a factory that always builds the fully-explicit
    # (format, scope, org, app) form, redirected to an ini file under tmp_path — never the
    # developer's real settings store, and freshly isolated per test.
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    def _isolated_qsettings(organization: str, application: str) -> QSettings:
        return QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, organization, application
        )

    monkeypatch.setattr("hssk_gui.settings.QSettings", _isolated_qsettings)

    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HSSK_CONFIG_DIR", str(tmp_path))
    hssk_config.settings.cache_clear()
    yield
    hssk_config.settings.cache_clear()
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "")


@pytest.fixture
def make_window(qtbot, mapping: MappingConfig, monkeypatch: pytest.MonkeyPatch):
    """Factory for an isolated MainWindow: no real mapping I/O, no automatic update-check thread.

    Copied from test_gui_threads.py's fixture of the same name/shape (that file's docstring
    explains why: no import across GUI test modules).
    """

    def _make() -> MainWindow:
        UiSettings().check_updates = False
        save_token(_make_jwt(exp=int(time.time()) + 3600))
        monkeypatch.setattr(MainWindow, "_load_mapping", lambda self, mode="create": mapping)
        window = MainWindow()
        qtbot.addWidget(window)
        window._excel_path = Path("fake.xlsx")
        window._update_start_enabled()
        return window

    return _make


# -- flag off: no-op ------------------------------------------------------------------------


def test_auto_purge_off_does_not_scan_or_delete(
    make_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "hssk.maintenance.find_old_runs", lambda *a, **k: calls.append("find") or []
    )
    monkeypatch.setattr("hssk.maintenance.purge_runs", lambda *a, **k: calls.append("purge") or 0)

    UiSettings().auto_purge = False
    window = make_window()

    assert calls == []
    assert not window.error_banner.isVisible()


# -- flag on + stale dirs: purge + banner ----------------------------------------------------


def test_auto_purge_on_with_stale_dirs_purges_and_banners(
    qtbot, make_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = [Path("/fake/output/run-1"), Path("/fake/output/run-2")]
    purge_calls: list[list[Path]] = []
    monkeypatch.setattr("hssk.maintenance.find_old_runs", lambda *a, **k: list(stale))
    monkeypatch.setattr(
        "hssk.maintenance.purge_runs",
        lambda paths: (purge_calls.append(list(paths)), len(paths))[1],
    )

    UiSettings().auto_purge = True
    window = make_window()

    assert purge_calls == [stale]
    # The banner is populated during __init__, before the window is ever shown — a widget whose
    # top-level ancestor was never shown always reports isVisible() == False regardless of
    # whether show_message() ran correctly (see test_gui_threads.py), so show the window first.
    window.show()
    qtbot.waitExposed(window)
    assert window.error_banner.isVisible()
    assert "2" in window.error_banner._label.text()
    window.close()


# -- flag on + nothing stale: silent no-op ----------------------------------------------------


def test_auto_purge_on_with_nothing_stale_is_silent(
    make_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    purge_calls: list[object] = []
    monkeypatch.setattr("hssk.maintenance.find_old_runs", lambda *a, **k: [])
    monkeypatch.setattr("hssk.maintenance.purge_runs", lambda paths: purge_calls.append(paths) or 0)

    UiSettings().auto_purge = True
    window = make_window()

    assert purge_calls == []
    assert not window.error_banner.isVisible()


# -- mid-batch safety: purge is done before any worker exists --------------------------------


def test_auto_purge_runs_before_any_worker_handle_exists(
    make_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The purge must be fully synchronous, inside __init__, before the run/validate/login/
    update/download machinery is even reachable — i.e. it can never race a batch in progress,
    because at the point it runs, no batch (or any other worker) could possibly exist yet."""
    stale = [Path("/fake/output/run-1")]
    order: list[str] = []
    monkeypatch.setattr(
        "hssk.maintenance.find_old_runs", lambda *a, **k: (order.append("scanned"), list(stale))[1]
    )
    monkeypatch.setattr(
        "hssk.maintenance.purge_runs", lambda paths: (order.append("purged"), len(paths))[1]
    )

    UiSettings().auto_purge = True
    window = make_window()

    assert order == ["scanned", "purged"]
    assert window._login_handle is None
    assert window._validate_handle is None
    assert window._run_handle is None
    assert window._update_handle is None
    assert window._download_handle is None
