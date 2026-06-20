"""Orchestrate the batch: read rows → search patient → build payload → (dry-run | create).

Per-row ``try/except`` isolates failures so one bad row never kills the batch. Progress is reported
via plain callbacks (no UI imports) so the same engine drives both the CLI and the GUI. Auth/rate
problems abort the batch cleanly; the ledger makes the next run resumable.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import report as report_mod
from ..api import exams, patients, records
from ..api.client import ApiClient
from ..auth.profile import load_profile
from ..config import Settings, output_dir
from ..config import settings as default_settings
from ..errors import ApiError, AuthExpired, ConfigError, MultiMatch, PatientNotFound, RateLimited
from ..excel import reader
from ..excel.coerce import coerce_row
from ..mapping import MappingConfig
from ..payload import builder, update_builder
from .ledger import Ledger
from .results import RowOutcome, RunSummary, Status

# Re-export so existing ``from hssk.pipeline.runner import Status`` imports keep working.
__all__ = ["Callbacks", "RowOutcome", "RunSummary", "Status", "run", "run_update"]


@dataclass
class Callbacks:
    on_progress: Callable[[int, int], None] = lambda done, total: None
    on_row: Callable[[RowOutcome], None] = lambda outcome: None
    on_log: Callable[[str], None] = lambda msg: None


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
    profile = load_profile()

    bad_targets = builder.validate_targets(mapping)
    if bad_targets:
        raise ConfigError(f"Mapping uses unknown API field target(s): {bad_targets}")

    rows = reader.read_rows(input_path, mapping)
    if limit is not None:
        rows = rows[:limit]
    total = len(rows)

    led = ledger if ledger is not None else Ledger.load()
    payload_base = builder.prepare_base(mapping)
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
            try:
                coerced = coerce_row(raw, mapping, row_index)
            except Exception as exc:
                emit(RowOutcome(row_index, None, Status.INVALID, message=f"coercion error: {exc}"))
                continue
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

            if identifier is None:  # defense-in-depth: coerced.ok should guarantee this
                emit(RowOutcome(row_index, None, Status.INVALID, message="identifier is blank"))
                continue
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
                payload_base,
                pid,
                medical_identifier_code=resolved.medical_identifier_code,
                profile=profile,
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


def run_update(
    input_path: str | Path,
    mapping: MappingConfig,
    *,
    token: str,
    dry_run: bool = True,
    limit: int | None = None,
    settings: Settings | None = None,
    callbacks: Callbacks | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> RunSummary:
    """Batch-update existing medical records by overlaying Excel row values onto fetched details.

    Unlike ``run``, this does not search for patients (patientId comes from the fetched record)
    and does not consult or write the ledger (re-running an update with corrected data must be
    allowed). The mapping must include a column with ``target: medicalRecordId, required: true``.
    """
    s = settings or default_settings()
    cb = callbacks or Callbacks()
    profile = load_profile()

    if not any(
        spec.target == "medicalRecordId" and spec.required for spec in mapping.columns.values()
    ):
        raise ConfigError(
            "Update mode requires a mapping column with target: medicalRecordId, required: true. "
            "See mapping.example.yaml for an example ('Mã hồ sơ')."
        )

    bad_targets = builder.validate_targets(mapping)
    if bad_targets:
        raise ConfigError(f"Mapping uses unknown API field target(s): {bad_targets}")

    rows = reader.read_rows(input_path, mapping)
    if limit is not None:
        rows = rows[:limit]
    total = len(rows)

    update_payload_base = builder.prepare_base(mapping)
    out_base = (s.data_dir / "output") if s.data_dir else output_dir()
    out_base.mkdir(parents=True, exist_ok=True)
    run_dir = report_mod.new_run_dir(out_base, dry_run=dry_run)
    payloads_dir = run_dir / "payloads"

    outcomes: list[RowOutcome] = []
    counts: dict[Status, int] = {}
    aborted = False
    abort_reason = ""

    def emit(outcome: RowOutcome) -> None:
        outcomes.append(outcome)
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        cb.on_row(outcome)

    with ApiClient(token, s, on_log=cb.on_log) as client:
        for i, (row_index, raw) in enumerate(rows, start=1):
            if should_cancel is not None and should_cancel():
                aborted, abort_reason = True, "cancelled by user"
                break
            cb.on_progress(i - 1, total)
            try:
                coerced = coerce_row(raw, mapping, row_index)
            except Exception as exc:
                emit(RowOutcome(row_index, None, Status.INVALID, message=f"coercion error: {exc}"))
                continue
            identifier = coerced.identifier

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

            medical_record_id = coerced.values.get("medicalRecordId")
            if medical_record_id is None:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.INVALID,
                        message="medicalRecordId is blank",
                        warnings=coerced.warnings,
                    )
                )
                continue

            try:
                detail = records.fetch_detail(client, medical_record_id)
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
                        message=f"fetch detail: {exc}",
                        warnings=coerced.warnings,
                    )
                )
                continue

            patient_id, mic = records.extract_patient_ref(detail)
            payload = update_builder.build_update(
                coerced,
                mapping,
                patient_id,
                medical_record_id=medical_record_id,
                medical_identifier_code=mic,
                profile=profile,
                _base=update_payload_base,
            )
            who = (detail.get("medicalRecordInfo") or detail.get("medicalRecords") or {}).get(
                "doctorName"
            ) or ""

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
                        patient_id=patient_id,
                        record_id=medical_record_id,
                        message=f"payload built (not sent) — {who}".strip(" —"),
                        warnings=coerced.warnings,
                    )
                )
                continue

            try:
                rid, _resp = records.update(client, payload)
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
                        patient_id=patient_id,
                        message=str(exc),
                        warnings=coerced.warnings,
                    )
                )
                continue

            emit(
                RowOutcome(
                    row_index,
                    identifier,
                    Status.UPDATED,
                    patient_id=patient_id,
                    record_id=rid or medical_record_id,
                    message=f"updated — {who}".strip(" —"),
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
