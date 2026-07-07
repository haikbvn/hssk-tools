"""One place for the QThread + worker lifecycle the GUI repeats for login/update/validate/run.

CLAUDE.md documents a real SIGABRT (commit 5ea2803) from tearing down a *running* QThread, and the
fix was an 11-line lifecycle: ``worker.finished/failed → thread.quit``; only on ``thread.finished``
release anything. That sequence was hand-copied at four sites in ``main_window.py`` — four chances
for a future edit to reintroduce the crash. ``WorkerHandle`` owns it once.

**Deletion is single-path on purpose.** The historical fix also wired ``thread.finished`` to
``worker.deleteLater`` + ``thread.deleteLater`` *and* dropped the Python references in the same
handler. Those are two competing deletion paths — a queued C++ deferred-delete and Python's
refcount drop — and under rapid start/stop cycling they race into an intermittent
segfault/abort (reproduced under ``tests/test_gui_threads.py`` while writing this module; the same
latent race lived in the old code, just rarely hit because production cycles threads a handful of
times, not dozens per second). ``WorkerHandle`` uses **no** ``deleteLater``: it keeps the worker
and thread referenced for its whole life, so the C++ objects are freed exactly once, by Python,
when the handle itself is dropped — and callers only drop a handle after ``thread.finished`` (the
thread has stopped), so a stopped thread is never destroyed from under a pending event.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QThread, SignalInstance


class LifecycleWorker(Protocol):
    """What every GUI worker already provides: done/error signals, cancel, run, thread move.

    Structural (not nominal) so the four concrete workers in ``workers.py`` satisfy it without
    importing anything from here — the handle only needs this much of each worker.
    """

    finished: SignalInstance  # emitted with the worker's result when it completes
    failed: SignalInstance  # emitted (message, Msg | None) when it errors

    def cancel(self) -> None: ...

    def run(self) -> None: ...

    # Signature mirrors QObject.moveToThread exactly (positional-only, bool return) so the concrete
    # workers — all QObject subclasses — structurally satisfy this Protocol.
    def moveToThread(self, thread: QThread, /) -> bool: ...


def _noop() -> None:
    """Callback slot after the handle has already fired once — makes re-entry a no-op."""


class WorkerHandle:
    """Owns a ``QThread`` running one ``LifecycleWorker`` and its full teardown.

    Construct via :func:`run_in_thread` (which also starts it). Callers connect their own domain
    signals (``status``/``progress``/``row``/``log``/``problem`` and the ``finished``/``failed``
    they need for UI) on the worker *before* starting — the handle only owns the lifecycle, not
    the payloads. When the thread finishes, ``on_thread_finished`` is invoked exactly once (on the
    main thread); it is where callers null their reference to this handle and re-enable controls.
    """

    def __init__(self, worker: LifecycleWorker, *, on_thread_finished: Callable[[], None]) -> None:
        self._worker = worker
        self._thread = QThread()
        self._on_thread_finished = on_thread_finished
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        # Stop the thread's event loop the instant the worker reports it is done, either way.
        worker.finished.connect(self._thread.quit)
        worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._handle_thread_finished)

    def _handle_thread_finished(self) -> None:
        # Runs on the main thread once the worker thread has fully stopped. Swap the callback out
        # before calling so a stray re-emit can't run it twice.
        cb, self._on_thread_finished = self._on_thread_finished, _noop
        cb()

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        """Ask the worker to stop; it will emit ``finished``/``failed`` and the thread quits."""
        self._worker.cancel()

    def quit(self) -> None:
        """Ask the thread's event loop to exit directly.

        Needed only for ``closeEvent``, which blocks the main thread in :meth:`wait` — there the
        queued ``worker.finished → thread.quit`` connection can't be serviced, so the caller quits
        the loop itself after :meth:`cancel` lets ``run()`` return.
        """
        self._thread.quit()

    def wait(self, ms: int) -> bool:
        """Block until the thread finishes or ``ms`` elapses; True if it finished."""
        return self._thread.wait(ms)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()


def run_in_thread(
    worker: LifecycleWorker, *, on_thread_finished: Callable[[], None]
) -> WorkerHandle:
    """Wire ``worker`` into a fresh ``WorkerHandle``, start it, and return the handle."""
    handle = WorkerHandle(worker, on_thread_finished=on_thread_finished)
    handle.start()
    return handle
