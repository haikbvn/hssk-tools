"""Background workers that run the engine off the UI thread and stream results back via signals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from hssk.auth.browser_login import capture_token
from hssk.auth.token_store import TokenData
from hssk.config import Settings
from hssk.excel import reader
from hssk.excel.coerce import coerce_row
from hssk.mapping import MappingConfig
from hssk.pipeline import runner


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
        try:
            data: TokenData = capture_token(
                on_status=lambda m: self.status.emit(m),
                should_cancel=lambda: self._cancel,
            )
            self.finished.emit(data)
        except Exception as exc:  # surface any failure to the UI
            self.failed.emit(str(exc))


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
        try:
            rows = reader.read_rows(self._input, self._mapping)
            total = len(rows)
            valid = invalid = warns = 0
            for i, (idx, raw) in enumerate(rows):
                if self._cancel:
                    break
                self.progress.emit(i, total)
                r = coerce_row(raw, self._mapping, idx)
                if r.ok:
                    valid += 1
                else:
                    invalid += 1
                warns += len(r.warnings)
                if not (r.ok and not r.warnings):
                    identifier = str(raw.get(self._mapping.identifier.column, ""))
                    message = "; ".join(list(r.errors) + [f"⚠ {w}" for w in r.warnings])
                    self.problem.emit(ValidationProblem(idx, identifier, bool(r.errors), message))
            self.progress.emit(valid + invalid, total)
            self.finished.emit(ValidationSummary(valid, invalid, warns, total))
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
        update_mode: bool = False,
    ) -> None:
        super().__init__()
        self._input = input_path
        self._mapping = mapping
        self._token = token
        self._dry_run = dry_run
        self._limit = limit
        self._settings = settings
        self._update_mode = update_mode
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        try:
            cb = runner.Callbacks(
                on_progress=lambda d, t: self.progress.emit(d, t),
                on_row=lambda o: self.row.emit(o),
                on_log=lambda m: self.log.emit(m),
            )
            engine_fn = runner.run_update if self._update_mode else runner.run
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
