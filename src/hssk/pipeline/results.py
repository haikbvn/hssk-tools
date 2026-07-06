"""Lightweight result types for the pipeline — no heavy engine imports.

Kept separate from runner.py so the GUI can import Status/RowOutcome/RunSummary at startup
without dragging in httpx, openpyxl, or the entire API stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..events import Msg, render_en


class Status(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    DRY_RUN_OK = "DRY_RUN_OK"
    SKIPPED_ALREADY = "SKIPPED_ALREADY"
    INVALID = "INVALID"
    NO_PATIENT = "NO_PATIENT"
    MULTI_MATCH = "MULTI_MATCH"
    FAILED = "FAILED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass
class RowOutcome:
    row_index: int
    identifier: str | None
    status: Status
    patient_id: Any = None
    record_id: Any = None
    # Typed message(s) for this row — usually one, but an INVALID row carries every coerce error.
    # Frontends render these (the GUI in the UI language, `message` below in English).
    msgs: list[Msg] = field(default_factory=list)
    warnings: list[Msg] = field(default_factory=list)
    # ISO-8601 local time, stamped by the runner when the outcome is recorded. Kept last so
    # positional construction of the fields above keeps working.
    timestamp: str = ""

    @property
    def message(self) -> str:
        """English rendering of the message(s), for the CLI and written reports (byte-stable)."""
        return "; ".join(render_en(m) for m in self.msgs)

    @property
    def warning_texts(self) -> list[str]:
        """English renderings of the warnings, for the CLI and written reports."""
        return [render_en(m) for m in self.warnings]


@dataclass
class RunSummary:
    total: int
    counts: dict[Status, int]
    outcomes: list[RowOutcome]
    run_dir: Path
    aborted: bool = False
    abort_reason: str = ""

    @property
    def created(self) -> int:
        return self.counts.get(Status.CREATED, 0)

    @property
    def updated(self) -> int:
        return self.counts.get(Status.UPDATED, 0)

    @property
    def deleted(self) -> int:
        return self.counts.get(Status.DELETED, 0)

    @property
    def failed(self) -> int:
        return sum(
            self.counts.get(s, 0)
            for s in (Status.FAILED, Status.NO_PATIENT, Status.MULTI_MATCH, Status.INVALID)
        )
