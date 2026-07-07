"""Background workers that run the engine off the UI thread and stream results back via signals."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, Signal, Slot

from hssk.auth.token_store import TokenData
from hssk.config import Settings
from hssk.errors import ConfigError
from hssk.events import MessageCode, Msg
from hssk.mapping import MappingConfig

_PROGRESS_INTERVAL_S = 0.1  # ~10 Hz cap on progress signals crossing the thread boundary


class ProgressThrottle:
    """Rate-limit progress updates: ``allow()`` returns True at most once per interval.

    The first call always passes (so the "starting…" update at done==0 is never dropped);
    the injectable ``clock`` keeps it unit-testable without sleeping. Callers still emit the
    terminal done==total update unconditionally so the bar always lands on 100%.
    """

    def __init__(
        self,
        interval_s: float = _PROGRESS_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._interval = interval_s
        self._clock = clock
        self._last: float | None = None

    def allow(self) -> bool:
        now = self._clock()
        if self._last is None or now - self._last >= self._interval:
            self._last = now
            return True
        return False


@dataclass
class ValidationProblem:
    row_index: int
    identifier: str
    errors: list[Msg]
    warnings: list[Msg]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


@dataclass
class ValidationSummary:
    valid: int
    invalid: int
    warns: int
    total: int
    cancelled: bool = False  # True if the user stopped the pass before all rows were checked


class LoginWorker(QObject):
    status = Signal(object)  # Msg (login progress)
    finished = Signal(object)  # TokenData
    failed = Signal(str, object)  # str(exc), and exc.msg (a Msg) if the exception carried one

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        from hssk.auth.browser_login import capture_token

        try:
            data: TokenData = capture_token(
                on_status=lambda m: self.status.emit(m),
                should_cancel=lambda: self._cancel,
            )
            self.finished.emit(data)
        except Exception as exc:  # surface any failure to the UI
            self.failed.emit(str(exc), getattr(exc, "msg", None))


class UpdateCheckWorker(QObject):
    """Fetch the latest GitHub release tag in the background (startup notification)."""

    finished = Signal(object)  # (tag, html_url) tuple or None
    failed = Signal(str, object)  # never emitted in practice; kept for lifecycle symmetry

    def __init__(self) -> None:
        super().__init__()
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        from .update_check import fetch_latest_release

        # fetch_latest_release cannot raise, so `finished` fires on every path and the
        # thread's quit is always triggered.
        result = fetch_latest_release()
        self.finished.emit(None if self._cancel else result)


class ValidateWorker(QObject):
    progress = Signal(int, int)  # done, total
    problem = Signal(object)  # ValidationProblem
    finished = Signal(object)  # ValidationSummary
    failed = Signal(str, object)  # str(exc), and exc.msg (a Msg) if the exception carried one

    def __init__(self, input_path: Path, mapping: MappingConfig) -> None:
        super().__init__()
        self._input = input_path
        self._mapping = mapping
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        from hssk.excel import reader
        from hssk.excel.coerce import coerce_row

        try:
            header_warnings: list[Msg] = []
            try:
                rows = reader.read_rows(
                    self._input, self._mapping, on_warning=header_warnings.append
                )
            except ConfigError as exc:
                # A file-level structural error (missing/duplicate mapped column) means no rows
                # can be read. Surface it as a synthetic INVALID row in the results table (where
                # operators look) in addition to the failed banner.
                err = exc.msg or Msg(MessageCode.PASSTHROUGH, detail=str(exc))
                self.problem.emit(
                    ValidationProblem(self._mapping.header_row, "", errors=[err], warnings=[])
                )
                self.failed.emit(str(exc), exc.msg)
                return
            for w in header_warnings:
                self.problem.emit(
                    ValidationProblem(self._mapping.header_row, "", errors=[], warnings=[w])
                )
            total = len(rows)
            valid = invalid = 0
            warns = len(header_warnings)
            cancelled = False
            throttle = ProgressThrottle()
            for i, (idx, raw) in enumerate(rows):
                if self._cancel:
                    cancelled = True
                    break
                if throttle.allow():
                    self.progress.emit(i, total)
                r = coerce_row(raw, self._mapping, idx)
                if r.ok:
                    valid += 1
                else:
                    invalid += 1
                warns += len(r.warnings)
                if not (r.ok and not r.warnings):
                    id_cell = raw.get(self._mapping.identifier.column)
                    identifier = "" if id_cell is None else str(id_cell)
                    self.problem.emit(
                        ValidationProblem(
                            idx, identifier, errors=list(r.errors), warnings=list(r.warnings)
                        )
                    )
            self.progress.emit(valid + invalid, total)
            self.finished.emit(ValidationSummary(valid, invalid, warns, total, cancelled))
        except Exception as exc:
            self.failed.emit(str(exc), getattr(exc, "msg", None))


class RunWorker(QObject):
    progress = Signal(int, int)  # done, total
    row = Signal(object)  # RowOutcome
    log = Signal(object)  # LogEvent
    finished = Signal(object)  # RunSummary
    failed = Signal(str, object)  # str(exc), and exc.msg (a Msg) if the exception carried one

    def __init__(
        self,
        input_path: Path,
        mapping: MappingConfig,
        token: str,
        *,
        dry_run: bool,
        limit: int | None,
        settings: Settings,
        mode: Literal["create", "update", "delete"] = "create",
    ) -> None:
        super().__init__()
        self._input = input_path
        self._mapping = mapping
        self._token = token
        self._dry_run = dry_run
        self._limit = limit
        self._settings = settings
        self._mode = mode
        self._cancel = False
        # Set alongside the flag so the client's throttle/backoff waits abort at once, not just
        # between rows (a Stop during a long Retry-After backoff would otherwise hang).
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel = True
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        from hssk.pipeline import runner

        throttle = ProgressThrottle()

        def on_progress(done: int, total: int) -> None:
            # Always emit the terminal update so the bar lands on 100%; rate-limit the rest.
            if done >= total or throttle.allow():
                self.progress.emit(done, total)

        try:
            cb = runner.Callbacks(
                on_progress=on_progress,
                on_row=lambda o: self.row.emit(o),
                on_log=lambda m: self.log.emit(m),
            )
            engine_fn = {
                "create": runner.run,
                "update": runner.run_update,
                "delete": runner.run_delete,
            }[self._mode]
            summary = engine_fn(
                self._input,
                self._mapping,
                token=self._token,
                dry_run=self._dry_run,
                limit=self._limit,
                settings=self._settings,
                callbacks=cb,
                should_cancel=lambda: self._cancel,
                cancel=self._cancel_event,
            )
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc), getattr(exc, "msg", None))
