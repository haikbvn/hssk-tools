"""Background workers that run the engine off the UI thread and stream results back via signals."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from hssk.auth.browser_login import capture_token
from hssk.auth.token_store import TokenData
from hssk.config import Settings
from hssk.mapping import MappingConfig
from hssk.pipeline import runner


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
    ) -> None:
        super().__init__()
        self._input = input_path
        self._mapping = mapping
        self._token = token
        self._dry_run = dry_run
        self._limit = limit
        self._settings = settings
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
            summary = runner.run(
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
