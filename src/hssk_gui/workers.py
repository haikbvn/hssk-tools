"""Background workers that run the engine off the UI thread and stream results back via signals."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, Signal, Slot

from hssk.auth.token_store import TokenData
from hssk.config import Settings
from hssk.errors import ConfigError
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
    has_errors: bool
    message: str


@dataclass
class ValidationSummary:
    valid: int
    invalid: int
    warns: int
    total: int
    cancelled: bool = False  # True if the user stopped the pass before all rows were checked


class LoginWorker(QObject):
    status = Signal(str)
    finished = Signal(object)  # TokenData
    failed = Signal(str)

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
            self.failed.emit(str(exc))


class UpdateCheckWorker(QObject):
    """Fetch the latest GitHub release tag in the background (startup notification)."""

    finished = Signal(object)  # (tag, html_url) tuple or None
    failed = Signal(str)  # never emitted in practice; kept for lifecycle symmetry

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
    failed = Signal(str)

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
            header_warnings: list[str] = []
            try:
                rows = reader.read_rows(
                    self._input, self._mapping, on_warning=header_warnings.append
                )
            except ConfigError as exc:
                # A file-level structural error (missing/duplicate mapped column) means no rows
                # can be read. Surface it as a synthetic INVALID row in the results table (where
                # operators look) in addition to the failed banner. The message localizes via
                # add_validation_row → _tr_coerce_msgs → _tr_file_error.
                self.problem.emit(ValidationProblem(self._mapping.header_row, "", True, str(exc)))
                self.failed.emit(str(exc))
                return
            for w in header_warnings:
                self.problem.emit(ValidationProblem(self._mapping.header_row, "", False, f"⚠ {w}"))
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
                    message = "; ".join(list(r.errors) + [f"⚠ {w}" for w in r.warnings])
                    self.problem.emit(ValidationProblem(idx, identifier, bool(r.errors), message))
            self.progress.emit(valid + invalid, total)
            self.finished.emit(ValidationSummary(valid, invalid, warns, total, cancelled))
        except Exception as exc:
            self.failed.emit(str(exc))


class RunWorker(QObject):
    progress = Signal(int, int)  # done, total
    row = Signal(object)  # RowOutcome
    log = Signal(str)
    finished = Signal(object)  # RunSummary
    failed = Signal(str)

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

    def cancel(self) -> None:
        self._cancel = True

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
            )
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))
