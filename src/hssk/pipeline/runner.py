"""Orchestrate the batch: read rows → search patient → build payload → (dry-run | create).

Per-row ``try/except`` isolates failures so one bad row never kills the batch. Progress is reported
via plain callbacks (no UI imports) so the same engine drives both the CLI and the GUI. Auth/rate
problems abort the batch cleanly; the ledger makes the next run resumable.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .. import report as report_mod
from ..api import exams, patients
from ..api.client import ApiClient
from ..config import Settings, output_dir
from ..config import settings as default_settings
from ..errors import ApiError, AuthExpired, ConfigError, MultiMatch, PatientNotFound, RateLimited
from ..excel import reader
from ..excel.coerce import coerce_row
from ..mapping import MappingConfig
from ..payload import builder
from .ledger import Ledger


class Status(StrEnum):
    CREATED = "CREATED"
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
class Callbacks:
    on_progress: Callable[[int, int], None] = lambda done, total: None
    on_row: Callable[[RowOutcome], None] = lambda outcome: None
    on_log: Callable[[str], None] = lambda msg: None


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
    def failed(self) -> int:
        return sum(
            self.counts.get(s, 0)
            for s in (Status.FAILED, Status.NO_PATIENT, Status.MULTI_MATCH, Status.INVALID)
        )


def run(
    input_path: str | Path,
    mapping: MappingConfig,
    *,
    token: str,
    dry_run: bool = True,
    limit: int | None = None,
    settings: Settings | None = None,
    callbacks: Callbacks | None = None,
    ledger: Ledger | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> RunSummary:
    s = settings or default_settings()
    cb = callbacks or Callbacks()

    bad_targets = builder.validate_targets(mapping)
    if bad_targets:
        raise ConfigError(f"Mapping uses unknown API field target(s): {bad_targets}")

    rows = reader.read_rows(input_path, mapping)
    if limit is not None:
        rows = rows[:limit]
    total = len(rows)

    led = ledger if ledger is not None else Ledger.load()
    out_base = (s.data_dir / "output") if s.data_dir else output_dir()
    out_base.mkdir(parents=True, exist_ok=True)
    run_dir = report_mod.new_run_dir(out_base, dry_run=dry_run)
    payloads_dir = run_dir / "payloads"

    outcomes: list[RowOutcome] = []
    counts: dict[Status, int] = {}
    aborted = False
    abort_reason = ""
    logged_raw = False

    def emit(outcome: RowOutcome) -> None:
        outcomes.append(outcome)
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        cb.on_row(outcome)

    with ApiClient(token, s, on_log=cb.on_log) as client:

        def raw_logger(data: Any) -> None:
            nonlocal logged_raw
            if not logged_raw:
                logged_raw = True
                (run_dir / "first_search_response.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                cb.on_log("Logged first search response for inspection.")

        for i, (row_index, raw) in enumerate(rows, start=1):
            if should_cancel is not None and should_cancel():
                aborted, abort_reason = True, "cancelled by user"
                break
            cb.on_progress(i - 1, total)
            coerced = coerce_row(raw, mapping, row_index)
            identifier = coerced.identifier
            key = Ledger.make_key(identifier, coerced.exam_date)

            if not coerced.ok:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.INVALID,
                        message="; ".join(coerced.errors),
                        warnings=coerced.warnings,
                    )
                )
                continue
            if led.done(key):
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.SKIPPED_ALREADY,
                        record_id=led.record_id(key),
                        message="already processed",
                        warnings=coerced.warnings,
                    )
                )
                continue

            assert identifier is not None  # guaranteed: coerced.ok requires identifier set
            try:
                resolved = patients.resolve(client, identifier, mapping.search, on_raw=raw_logger)
                pid = resolved.patient_id
            except PatientNotFound as exc:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.NO_PATIENT,
                        message=str(exc),
                        warnings=coerced.warnings,
                    )
                )
                continue
            except MultiMatch as exc:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.MULTI_MATCH,
                        message=str(exc),
                        warnings=coerced.warnings,
                    )
                )
                continue
            except AuthExpired as exc:
                emit(RowOutcome(row_index, identifier, Status.AUTH_EXPIRED, message=str(exc)))
                aborted, abort_reason = True, str(exc)
                break
            except RateLimited as exc:
                emit(RowOutcome(row_index, identifier, Status.RATE_LIMITED, message=str(exc)))
                aborted, abort_reason = True, str(exc)
                break

            payload = builder.build(
                coerced,
                mapping,
                pid,
                medical_identifier_code=resolved.medical_identifier_code,
            )
            who = resolved.fullname or ""

            if dry_run:
                payloads_dir.mkdir(parents=True, exist_ok=True)
                (payloads_dir / f"row_{row_index}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.DRY_RUN_OK,
                        patient_id=pid,
                        message=f"payload built (not sent) — {who}".strip(" —"),
                        warnings=coerced.warnings,
                    )
                )
                continue

            try:
                rid, _resp = exams.create(client, payload)
            except AuthExpired as exc:
                emit(RowOutcome(row_index, identifier, Status.AUTH_EXPIRED, message=str(exc)))
                aborted, abort_reason = True, str(exc)
                break
            except RateLimited as exc:
                emit(RowOutcome(row_index, identifier, Status.RATE_LIMITED, message=str(exc)))
                aborted, abort_reason = True, str(exc)
                break
            except ApiError as exc:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.FAILED,
                        patient_id=pid,
                        message=str(exc),
                        warnings=coerced.warnings,
                    )
                )
                continue

            led.mark_done(key, rid)
            emit(
                RowOutcome(
                    row_index,
                    identifier,
                    Status.CREATED,
                    patient_id=pid,
                    record_id=rid,
                    message=f"created — {who}".strip(" —"),
                    warnings=coerced.warnings,
                )
            )

    cb.on_progress(total, total)
    summary = RunSummary(
        total=total,
        counts=counts,
        outcomes=outcomes,
        run_dir=run_dir,
        aborted=aborted,
        abort_reason=abort_reason,
    )
    report_mod.write_report(run_dir, outcomes, dry_run=dry_run)
    return summary
