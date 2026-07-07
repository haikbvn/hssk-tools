"""Thread-lifecycle safety net for MainWindow's four background jobs (login, update-check,
validate, run), each run through a ``WorkerHandle`` (see hssk_gui/worker_thread.py).

Every assertion here is on observable UI state (button enabled, window closed cleanly) rather than
the private ``_X_handle`` fields, so the tests describe the contract, not the wiring. The headline
case is ``close_while_running``: CLAUDE.md documents a real SIGABRT (commit 5ea2803) from
destroying a running QThread, and ``closeEvent`` guards it with cancel-then-wait. Each test drives
a worker that blocks until cancelled, so a regression would hang or crash the test process, not
just fail an assertion.

These tests also pin the fix that motivated ``WorkerHandle``: the old per-site wiring paired
``thread.finished → deleteLater`` with a same-handler null-out of the Python reference — two
competing deletion paths that raced into an intermittent segfault under rapid start/stop cycling
(which this file, constructing and tearing down many MainWindows per run, reproduced reliably).
``WorkerHandle``'s single Python-owned deletion path (no ``deleteLater``) closed it; run this file
in a loop and it must be crash-free.

Fake workers replace LoginWorker/ValidateWorker/RunWorker/UpdateCheckWorker via monkeypatching the
names ``hssk_gui.main_window`` imported them under, so no real engine/network code ever runs.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QObject, QSettings, Signal, Slot

from hssk import config as hssk_config
from hssk.auth.token_store import TokenData, save_token
from hssk.mapping import MappingConfig
from hssk.pipeline.results import RunSummary
from hssk_gui.main_window import MainWindow
from hssk_gui.workers import ValidationSummary

_WAIT_MS = 5000


def _make_jwt(exp: int) -> str:
    """A JWT-shaped (but unsigned) token good enough for decode_exp/load_token round-tripping."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


# -- isolation: no real settings file, config dir, or data dir is ever touched -------------------


@pytest.fixture(autouse=True)
def _isolated_qt_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # UiSettings.__init__ does QSettings(_ORG, _APP) — the 2-arg (organization, application)
    # constructor, which on this Qt/platform combo ignores setDefaultFormat() and always resolves
    # to NativeFormat (the real OS registry/plist), unlike the fully-explicit 4-arg constructor
    # (format, scope, org, app), which does respect setPath(). So: patch the QSettings name
    # hssk_gui/settings.py resolves through to a factory that always builds the explicit form,
    # redirected to an ini file under tmp_path — never the developer's real settings store.
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    def _isolated_qsettings(organization: str, application: str) -> QSettings:
        return QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, organization, application
        )

    monkeypatch.setattr("hssk_gui.settings.QSettings", _isolated_qsettings)

    # hssk.config.settings() is lru_cache'd process-wide, so env-var overrides only take effect
    # if the cache is cleared after setting them (same pattern as test_cli.py).
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HSSK_CONFIG_DIR", str(tmp_path))
    hssk_config.settings.cache_clear()
    yield
    hssk_config.settings.cache_clear()
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "")


@pytest.fixture
def make_window(qtbot, mapping: MappingConfig, monkeypatch: pytest.MonkeyPatch):
    """Factory for an isolated MainWindow: no real mapping I/O, no automatic update-check thread.

    Suppresses the automatic startup update-check via the (isolated) settings rather than
    monkeypatching MainWindow._start_update_check itself — patching the method at class level
    would also shadow the dedicated update-check tests' own explicit call to the real method.

    Registers each window with qtbot so pytest-qt closes it (running closeEvent → cancel + wait)
    and reclaims it at test teardown.
    """

    def _make() -> MainWindow:
        from hssk_gui.settings import UiSettings

        UiSettings().check_updates = False
        # Persisted (not just set as a window._token attribute) so that _refresh_token_status()
        # — called from __init__ and again after every run/validate finishes — keeps finding a
        # valid token instead of resetting window._token back to None mid-test.
        save_token(_make_jwt(exp=int(time.time()) + 3600))
        monkeypatch.setattr(MainWindow, "_load_mapping", lambda self, mode="create": mapping)
        window = MainWindow()
        qtbot.addWidget(window)
        window._excel_path = Path("fake.xlsx")  # never read: the run/validate workers are faked
        window._update_start_enabled()  # refresh validate_btn/start_btn now that both are set
        return window

    return _make


# -- fake workers: same public Signal/cancel/run shape as the real ones, no engine/network calls --


## Each fake is a plain QObject subclass (no mixin: PySide6's signal/slot metaclass machinery
## wants QObject directly in the bases, not behind a mixin) with identical cancel/run plumbing.
## ``_stop`` exists from construction, not created lazily inside ``run()``, so ``cancel()`` is
## race-free no matter whether it's called before, during, or after ``run()`` actually starts
## executing on the worker thread.


class _FakeLoginWorker(QObject):
    status = Signal(object)
    finished = Signal(object)
    failed = Signal(str, object)

    def __init__(self, on_run: Callable[[Any], None]) -> None:
        super().__init__()
        self._on_run = on_run
        self._stop = threading.Event()
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self._stop.set()

    @Slot()
    def run(self) -> None:
        self._on_run(self)


class _FakeUpdateCheckWorker(QObject):
    finished = Signal(object)
    failed = Signal(str, object)

    def __init__(self, on_run: Callable[[Any], None]) -> None:
        super().__init__()
        self._on_run = on_run
        self._stop = threading.Event()
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self._stop.set()

    @Slot()
    def run(self) -> None:
        self._on_run(self)


class _FakeValidateWorker(QObject):
    progress = Signal(int, int)
    problem = Signal(object)
    finished = Signal(object)
    failed = Signal(str, object)

    def __init__(self, on_run: Callable[[Any], None]) -> None:
        super().__init__()
        self._on_run = on_run
        self._stop = threading.Event()
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self._stop.set()

    @Slot()
    def run(self) -> None:
        self._on_run(self)


class _FakeRunWorker(QObject):
    progress = Signal(int, int)
    row = Signal(object)
    log = Signal(object)
    finished = Signal(object)
    failed = Signal(str, object)

    def __init__(self, on_run: Callable[[Any], None]) -> None:
        super().__init__()
        self._on_run = on_run
        self._stop = threading.Event()
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self._stop.set()

    @Slot()
    def run(self) -> None:
        self._on_run(self)


def _factory(fake_cls: type, on_run: Callable[[Any], None]) -> Callable[..., Any]:
    """A drop-in for the real worker class: accepts (and ignores) whatever positional/keyword
    args main_window.py passes to the real constructor, and returns a configured fake."""

    def make(*_args: object, **_kwargs: object) -> Any:
        return fake_cls(on_run)

    return make


def _finish_soon(payload: object) -> Callable[[Any], None]:
    """run() that completes immediately by emitting `finished` — the normal-completion path."""

    def on_run(worker: Any) -> None:
        worker.finished.emit(payload)

    return on_run


def _block_until_cancelled(payload: object) -> Callable[[Any], None]:
    """run() that hangs until cancel() is called — the path closeEvent must safely tear down.

    Waits on the worker's own ``_stop`` event (set by ``cancel()``, created at __init__ time), so
    this is race-free regardless of whether cancel() fires before run() even starts.
    """

    def on_run(worker: Any) -> None:
        worker._stop.wait(timeout=_WAIT_MS / 1000)
        worker.finished.emit(payload)

    return on_run


def _fake_token() -> TokenData:
    return TokenData(token="fake", captured_at=0.0, exp=None)


def _fake_run_summary(tmp_path: Path) -> RunSummary:
    return RunSummary(total=0, counts={}, outcomes=[], run_dir=tmp_path / "run-fake", aborted=False)


def _fake_validation_summary() -> ValidationSummary:
    return ValidationSummary(valid=1, invalid=0, warns=0, total=1)


# -- login ----------------------------------------------------------------------------------


def test_login_start_and_finish(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window()
    monkeypatch.setattr(
        "hssk_gui.main_window.LoginWorker", _factory(_FakeLoginWorker, _finish_soon(_fake_token()))
    )
    window.login_btn.click()
    assert not window.login_btn.isEnabled()  # disabled the instant the action starts
    qtbot.waitUntil(lambda: window.login_btn.isEnabled(), timeout=_WAIT_MS)


def test_login_close_while_running(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window()
    monkeypatch.setattr(
        "hssk_gui.main_window.LoginWorker",
        _factory(_FakeLoginWorker, _block_until_cancelled(_fake_token())),
    )
    window.login_btn.click()
    qtbot.waitUntil(lambda: not window.login_btn.isEnabled(), timeout=_WAIT_MS)
    # Must not SIGABRT (the historical bug, commit 5ea2803) and must not hang: closeEvent cancels
    # the worker and waits for the thread before accepting the close.
    assert window.close() is True
    assert not window.isVisible()


# -- update-check -----------------------------------------------------------------------------


def test_update_check_start_and_finish(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    # Asserts the worker's own signal fires (proving the thread ran and completed normally) —
    # NOT window.update_banner.isVisible(). That would additionally exercise a pre-existing,
    # separate bug (spawn_task-flagged): _on_update_check_finished currently runs on the worker
    # thread instead of the main thread, so NoticeBanner.show_message()'s widget-child creation
    # silently fails cross-thread. Out of scope for thread-*lifecycle* safety (this file's
    # purpose) — the close-while-running test below is what actually matters for that.
    window = make_window()
    fake = _FakeUpdateCheckWorker(_finish_soon(("v99.0.0", "https://example.com/rel")))
    monkeypatch.setattr("hssk_gui.main_window.UpdateCheckWorker", lambda: fake)
    with qtbot.waitSignal(fake.finished, timeout=_WAIT_MS):
        window._start_update_check()


def test_update_check_close_while_running(
    qtbot, make_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = make_window()
    monkeypatch.setattr(
        "hssk_gui.main_window.UpdateCheckWorker",
        _factory(_FakeUpdateCheckWorker, _block_until_cancelled(None)),
    )
    window._start_update_check()
    assert window.close() is True
    assert not window.isVisible()


# -- validate -------------------------------------------------------------------------------


def test_validate_start_and_finish(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window()
    monkeypatch.setattr(
        "hssk_gui.main_window.ValidateWorker",
        _factory(_FakeValidateWorker, _finish_soon(_fake_validation_summary())),
    )
    window.validate_btn.click()
    assert not window.validate_btn.isEnabled()
    qtbot.waitUntil(lambda: window.validate_btn.isEnabled(), timeout=_WAIT_MS)


def test_validate_stop_cancels(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    # Communicates with the worker thread through plain Python objects (`started`/`result`) rather
    # than reaching back into the fake worker, so the assertion never touches a QObject whose C++
    # side the WorkerHandle may already have released.
    window = make_window()
    started = threading.Event()
    result: dict[str, bool] = {}

    def on_run(worker: _FakeValidateWorker) -> None:
        started.set()
        # Blocks until _stop_run()'s cancel() sets _stop — never finishes on its own.
        worker._stop.wait(timeout=_WAIT_MS / 1000)
        result["cancelled"] = worker.cancelled
        worker.finished.emit(_fake_validation_summary())

    monkeypatch.setattr(
        "hssk_gui.main_window.ValidateWorker", _factory(_FakeValidateWorker, on_run)
    )
    window.validate_btn.click()
    qtbot.waitUntil(lambda: started.is_set(), timeout=_WAIT_MS)
    window._stop_run()
    qtbot.waitUntil(lambda: window.validate_btn.isEnabled(), timeout=_WAIT_MS)
    assert result.get("cancelled") is True


def test_validate_close_while_running(qtbot, make_window, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window()
    monkeypatch.setattr(
        "hssk_gui.main_window.ValidateWorker",
        _factory(_FakeValidateWorker, _block_until_cancelled(_fake_validation_summary())),
    )
    window.validate_btn.click()
    qtbot.waitUntil(lambda: not window.validate_btn.isEnabled(), timeout=_WAIT_MS)
    assert window.close() is True
    assert not window.isVisible()


# -- run ------------------------------------------------------------------------------------


def test_run_start_and_finish(
    qtbot, make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    window.dryrun_check.setChecked(True)  # skip the type-to-confirm production dialog
    monkeypatch.setattr(
        "hssk_gui.main_window.RunWorker",
        _factory(_FakeRunWorker, _finish_soon(_fake_run_summary(tmp_path))),
    )
    window.start_btn.click()
    qtbot.waitUntil(lambda: window.start_btn.isEnabled(), timeout=_WAIT_MS)


def test_run_stop_cancels(
    qtbot, make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # See test_validate_stop_cancels: talks to the worker thread via plain Python objects, not by
    # reaching back into the fake worker.
    window = make_window()
    window.dryrun_check.setChecked(True)
    started = threading.Event()
    result: dict[str, bool] = {}

    def on_run(worker: _FakeRunWorker) -> None:
        started.set()
        # Blocks until _stop_run()'s cancel() sets _stop, so the thread can quit afterward
        # instead of dangling past the end of the test.
        worker._stop.wait(timeout=_WAIT_MS / 1000)
        result["cancelled"] = worker.cancelled
        worker.finished.emit(_fake_run_summary(tmp_path))

    monkeypatch.setattr("hssk_gui.main_window.RunWorker", _factory(_FakeRunWorker, on_run))
    window.start_btn.click()
    qtbot.waitUntil(lambda: started.is_set(), timeout=_WAIT_MS)
    window._stop_run()
    qtbot.waitUntil(lambda: window.start_btn.isEnabled(), timeout=_WAIT_MS)
    assert result.get("cancelled") is True


def test_run_close_while_running(
    qtbot, make_window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window = make_window()
    window.dryrun_check.setChecked(True)
    monkeypatch.setattr(
        "hssk_gui.main_window.RunWorker",
        _factory(_FakeRunWorker, _block_until_cancelled(_fake_run_summary(tmp_path))),
    )
    window.start_btn.click()
    qtbot.waitUntil(lambda: not window.start_btn.isEnabled(), timeout=_WAIT_MS)
    assert window.close() is True
    assert not window.isVisible()
