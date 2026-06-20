"""Lightweight result types for the pipeline — no heavy engine imports.

Kept separate from runner.py so the GUI can import Status/RowOutcome/RunSummary at startup
without dragging in httpx, openpyxl, or the entire API stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Status(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
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
    message: str = ""
    warnings: list[str] = field(default_factory=list)


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
    def failed(self) -> int:
        return sum(
            self.counts.get(s, 0)
            for s in (Status.FAILED, Status.NO_PATIENT, Status.MULTI_MATCH, Status.INVALID)
        )
