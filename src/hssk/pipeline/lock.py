"""Cross-platform advisory lock guarding a single active batch.

Two concurrent batches (two GUI windows, or a GUI + CLI) would both load the ledger, both pass
the ``Ledger.done()`` check for the same row, and both send it — the dedup invariant is a
read-time race no storage layer fixes. A single OS-level advisory lock on one file, held for the
whole batch, closes it across processes regardless of frontend.

The lock is advisory (it only blocks other holders of *this* lock), non-blocking (a second
acquirer fails immediately rather than waiting), and released when the process exits even on a
hard crash — the OS drops the file handle. POSIX uses ``fcntl.flock``; Windows uses
``msvcrt.locking``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import TracebackType
from typing import IO

from ..config import data_dir
from ..errors import AlreadyRunning


def lock_path() -> Path:
    return data_dir() / "hssk.lock"


class RunLock:
    """Hold the batch lock for the duration of a ``with`` block.

    Raises :class:`AlreadyRunning` on ``__enter__`` if another process holds it. The open file
    handle is kept for the block's lifetime; closing it (in ``__exit__`` or at process exit)
    releases the OS lock.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or lock_path()
        self._fh: IO[str] | None = None

    def __enter__(self) -> RunLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        # Open (not truncate) so a stale file from a previous run is reused, never clobbered.
        fh = open(self._path, "a+")
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            raise AlreadyRunning(
                "Another hssk operation is already running. Close the other window "
                "(or wait for the current batch to finish) and try again."
            ) from exc
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
