"""Orchestrate the batch: read rows → search patient → build payload → (dry-run | create).

Per-row ``try/except`` isolates failures so one bad row never kills the batch. Progress is reported
via plain callbacks (no UI imports) so the same engine drives both the CLI and the GUI. Auth/rate
problems abort the batch cleanly; the ledger makes the next run resumable.

``run`` (create), ``run_update`` (update), and ``run_delete`` (delete) share one skeleton,
``_run_batch``: it owns the loop, per-row coercion, the dry-run write, the send/abort error ladder,
and reporting. Each mode supplies a ``process_row`` closure for the part that differs
(resolve-vs-fetch, ledger, which builder / sender).
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import report as report_mod
from ..api import exams, patients, records
from ..api.client import ApiClient
from ..auth.profile import load_profile
from ..auth.token_store import decode_exp
from ..config import Settings, output_dir
from ..config import settings as default_settings
from ..errors import (
    ApiError,
    AuthExpired,
    BatchCancelled,
    ConfigError,
    MultiMatch,
    PatientNotFound,
    RateLimited,
)
from ..events import LogEvent, MessageCode, Msg
from ..excel import reader
from ..excel.coerce import RowResult, coerce_row
from ..mapping import MappingConfig
from ..payload import builder, update_builder
from .ledger import Ledger
from .lock import RunLock
from .results import RowOutcome, RunSummary, Status

# Re-export so existing ``from hssk.pipeline.runner import Status`` imports keep working.
__all__ = ["Callbacks", "RowOutcome", "RunSummary", "Status", "run", "run_delete", "run_update"]


@dataclass
class Callbacks:
    on_progress: Callable[[int, int], None] = lambda done, total: None
    on_row: Callable[[RowOutcome], None] = lambda outcome: None
    on_log: Callable[[LogEvent], None] = lambda event: None


@dataclass
class _Proceed:
    """A row that passed validation and is ready to dry-run-write or send.

    Returned by a mode's ``process_row`` to hand control back to ``_run_batch`` for the shared
    dry-run / send / commit tail.
    """

    payload: dict[str, Any]
    patient_id: Any
    who: str
    success_status: Status  # CREATED / UPDATED / DELETED
    success_code: MessageCode  # ROW_CREATED / ROW_UPDATED / ROW_DELETED
    send: Callable[
        [ApiClient], tuple[Any, Any]
    ]  # exams.create / records.update|delete → (rid, resp)
    on_commit: Callable[[Any], None] | None = None  # create: ledger mark_done; update/delete: None
    dryrun_record_id: str | None = None  # create: None; update/delete: medicalRecordId


# A mode returns a finished RowOutcome (emit & continue) or a _Proceed (run the shared tail).
# It may raise AuthExpired / RateLimited; _run_batch catches those to abort cleanly.
ProcessRow = Callable[[ApiClient, int, RowResult, Callable[[Any], None]], "RowOutcome | _Proceed"]

_REQUEST_OVERHEAD_S = 0.8  # rough per-request network+server time (heuristic)
_REQUESTS_PER_ROW = 2  # create: search + create; update/delete: fetch-detail + update|delete


def _passthrough_outcome(
    row_index: int, identifier: str | None, status: Status, exc: Exception
) -> RowOutcome:
    """Row outcome whose message is raw exception text (auth/rate abort, unexpected API error)."""
    return RowOutcome(
        row_index, identifier, status, msgs=[Msg(MessageCode.PASSTHROUGH, detail=str(exc))]
    )


def estimate_batch_seconds(rows: int, settings: Settings) -> float:
    """Rough upper bound on batch duration (ledger-skipped rows cost ~0, so it over-estimates)."""
    per_request = settings.request_delay + settings.jitter / 2 + _REQUEST_OVERHEAD_S
    return rows * _REQUESTS_PER_ROW * per_request


def token_expiry_warning(
    token: str, rows: int, settings: Settings, *, now: float | None = None
) -> Msg | None:
    """Warning message when the token likely expires before ``rows`` finish, else None.

    Undecodable tokens return None — same stance as ``TokenData.is_valid`` (assume usable and
    let a 401 catch it).
    """
    exp = decode_exp(token)
    if exp is None:
        return None
    remaining = exp - (now if now is not None else time.time())
    needed = estimate_batch_seconds(rows, settings)
    if remaining >= needed:
        return None
    return Msg(
        MessageCode.LOG_TOKEN_SHORT,
        {"needed": f"{needed / 60:.0f}", "left": f"{max(remaining, 0) / 60:.0f}"},
    )


def _run_batch(
    input_path: str | Path,
    mapping: MappingConfig,
    *,
    token: str,
    dry_run: bool,
    limit: int | None,
    settings: Settings | None,
    callbacks: Callbacks | None,
    should_cancel: Callable[[], bool] | None,
    process_row: ProcessRow,
    cancel: threading.Event | None = None,
) -> RunSummary:
    """Hold the single-batch lock, then run. The lock covers the whole batch (CLI and GUI),
    closing the read-time dedup race where two instances both pass ``Ledger.done()``."""
    with RunLock():
        return _run_batch_locked(
            input_path,
            mapping,
            token=token,
            dry_run=dry_run,
            limit=limit,
            settings=settings,
            callbacks=callbacks,
            should_cancel=should_cancel,
            process_row=process_row,
            cancel=cancel,
        )


def _run_batch_locked(
    input_path: str | Path,
    mapping: MappingConfig,
    *,
    token: str,
    dry_run: bool,
    limit: int | None,
    settings: Settings | None,
    callbacks: Callbacks | None,
    should_cancel: Callable[[], bool] | None,
    process_row: ProcessRow,
    cancel: threading.Event | None,
) -> RunSummary:
    s = settings or default_settings()
    cb = callbacks or Callbacks()

    def log_warn(msg: Msg) -> None:
        cb.on_log(LogEvent(msg.code, msg.params, msg.detail, level="warning"))

    rows = reader.read_rows(input_path, mapping, on_warning=log_warn)
    if limit is not None:
        rows = rows[:limit]
    total = len(rows)

    if not dry_run:
        expiry_warning = token_expiry_warning(token, total, s)
        if expiry_warning:
            log_warn(expiry_warning)

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
        outcome.timestamp = dt.datetime.now().isoformat(timespec="seconds")
        outcomes.append(outcome)
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        cb.on_row(outcome)

    last_raw: Any = None

    with ApiClient(token, s, on_log=cb.on_log, cancel=cancel) as client:

        def raw_logger(data: Any) -> None:
            nonlocal logged_raw, last_raw
            last_raw = data
            if not logged_raw:
                logged_raw = True
                (run_dir / "first_search_response.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                cb.on_log(LogEvent(MessageCode.LOG_FIRST_SEARCH_SAVED))

        for i, (row_index, raw) in enumerate(rows, start=1):
            if should_cancel is not None and should_cancel():
                aborted, abort_reason = True, "cancelled by user"
                break
            cb.on_progress(i - 1, total)
            last_raw = None
            try:
                coerced = coerce_row(raw, mapping, row_index)
            except Exception as exc:
                emit(
                    RowOutcome(
                        row_index,
                        None,
                        Status.INVALID,
                        msgs=[Msg(MessageCode.ROW_COERCE_ERROR, detail=str(exc))],
                    )
                )
                continue
            identifier = coerced.identifier

            if not coerced.ok:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.INVALID,
                        msgs=list(coerced.errors),
                        warnings=coerced.warnings,
                    )
                )
                continue

            try:
                step = process_row(client, row_index, coerced, raw_logger)
            except BatchCancelled:
                aborted, abort_reason = True, "cancelled by user"
                break
            except AuthExpired as exc:
                emit(_passthrough_outcome(row_index, identifier, Status.AUTH_EXPIRED, exc))
                aborted, abort_reason = True, str(exc)
                break
            except RateLimited as exc:
                emit(_passthrough_outcome(row_index, identifier, Status.RATE_LIMITED, exc))
                aborted, abort_reason = True, str(exc)
                break

            if isinstance(step, RowOutcome):
                if step.status in (Status.NO_PATIENT, Status.MULTI_MATCH) and last_raw is not None:
                    # Keep the exact server response for the row whose lookup failed — the
                    # case where debugging actually needs it (PII stays in the run dir,
                    # same as first_search_response.json).
                    name = f"search_response_row_{row_index}.json"
                    (run_dir / name).write_text(
                        json.dumps(last_raw, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    cb.on_log(
                        LogEvent(
                            MessageCode.LOG_SEARCH_SAVED_ROW,
                            {"row": row_index, "filename": name},
                        )
                    )
                emit(step)
                continue

            if dry_run:
                payloads_dir.mkdir(parents=True, exist_ok=True)
                (payloads_dir / f"row_{row_index}.json").write_text(
                    json.dumps(step.payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.DRY_RUN_OK,
                        patient_id=step.patient_id,
                        record_id=step.dryrun_record_id,
                        msgs=[Msg(MessageCode.ROW_DRY_RUN, {"who": step.who})],
                        warnings=coerced.warnings,
                    )
                )
                continue

            try:
                rid, _resp = step.send(client)
            except BatchCancelled:
                aborted, abort_reason = True, "cancelled by user"
                break
            except AuthExpired as exc:
                emit(_passthrough_outcome(row_index, identifier, Status.AUTH_EXPIRED, exc))
                aborted, abort_reason = True, str(exc)
                break
            except RateLimited as exc:
                emit(_passthrough_outcome(row_index, identifier, Status.RATE_LIMITED, exc))
                aborted, abort_reason = True, str(exc)
                break
            except ApiError as exc:
                emit(
                    RowOutcome(
                        row_index,
                        identifier,
                        Status.FAILED,
                        patient_id=step.patient_id,
                        msgs=[Msg(MessageCode.PASSTHROUGH, detail=str(exc))],
                        warnings=coerced.warnings,
                    )
                )
                continue

            if step.on_commit is not None:
                step.on_commit(rid)
            no_record_id = rid is None and step.dryrun_record_id is None
            params: dict[str, Any] = {"who": step.who}
            if no_record_id:
                # Create mode with an unrecognised response shape: the record exists on the
                # server but we could not learn its id (update mode falls back to the known
                # medicalRecordId, so no warning there).
                cb.on_log(
                    LogEvent(MessageCode.LOG_NO_RECORD_ID, {"row": row_index}, level="warning")
                )
                params["no_record_id"] = True
            emit(
                RowOutcome(
                    row_index,
                    identifier,
                    step.success_status,
                    patient_id=step.patient_id,
                    record_id=rid or step.dryrun_record_id,
                    msgs=[Msg(step.success_code, params)],
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
    cancel: threading.Event | None = None,
) -> RunSummary:
    bad_targets = builder.validate_targets(mapping)
    if bad_targets:
        raise ConfigError(f"Mapping uses unknown API field target(s): {bad_targets}")

    profile = load_profile()
    payload_base = builder.prepare_base(mapping)
    led = ledger if ledger is not None else Ledger.load()
    cb = callbacks or Callbacks()
    if led.corrupt_lines:
        cb.on_log(
            LogEvent(MessageCode.LOG_LEDGER_CORRUPT, {"n": led.corrupt_lines}, level="warning")
        )

    def process_row(
        client: ApiClient,
        row_index: int,
        coerced: RowResult,
        raw_logger: Callable[[Any], None],
    ) -> RowOutcome | _Proceed:
        identifier = coerced.identifier
        key = Ledger.make_key(identifier, coerced.exam_date)
        if led.done(key):
            return RowOutcome(
                row_index,
                identifier,
                Status.SKIPPED_ALREADY,
                record_id=led.record_id(key),
                msgs=[Msg(MessageCode.ROW_ALREADY_PROCESSED)],
                warnings=coerced.warnings,
            )
        if identifier is None:  # defense-in-depth: coerced.ok should guarantee this
            return RowOutcome(row_index, None, Status.INVALID, msgs=[Msg(MessageCode.ROW_ID_BLANK)])

        try:
            resolved = patients.resolve(client, identifier, mapping.search, on_raw=raw_logger)
        except PatientNotFound as exc:
            return RowOutcome(
                row_index,
                identifier,
                Status.NO_PATIENT,
                msgs=[exc.msg or Msg(MessageCode.PASSTHROUGH, detail=str(exc))],
                warnings=coerced.warnings,
            )
        except MultiMatch as exc:
            return RowOutcome(
                row_index,
                identifier,
                Status.MULTI_MATCH,
                msgs=[exc.msg or Msg(MessageCode.PASSTHROUGH, detail=str(exc))],
                warnings=coerced.warnings,
            )
        except ApiError as exc:
            return RowOutcome(
                row_index,
                identifier,
                Status.FAILED,
                msgs=[Msg(MessageCode.ROW_SEARCH_FAILED, detail=str(exc))],
                warnings=coerced.warnings,
            )

        pid = resolved.patient_id
        payload = builder.build(
            coerced,
            payload_base,
            pid,
            medical_identifier_code=resolved.medical_identifier_code,
            profile=profile,
        )
        return _Proceed(
            payload=payload,
            patient_id=pid,
            who=resolved.fullname or "",
            success_status=Status.CREATED,
            success_code=MessageCode.ROW_CREATED,
            send=lambda c: exams.create(c, payload),
            on_commit=lambda rid: led.mark_done(key, rid),
        )

    return _run_batch(
        input_path,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=limit,
        settings=settings,
        callbacks=cb,
        should_cancel=should_cancel,
        process_row=process_row,
        cancel=cancel,
    )


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
    cancel: threading.Event | None = None,
) -> RunSummary:
    """Batch-update existing medical records by overlaying Excel row values onto fetched details.

    Unlike ``run``, this does not search for patients (patientId comes from the fetched record)
    and does not consult or write the ledger (re-running an update with corrected data must be
    allowed). The mapping must include a column with ``target: medicalRecordId, required: true``.
    """
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

    profile = load_profile()
    update_payload_base = builder.prepare_base(mapping)

    def process_row(
        client: ApiClient,
        row_index: int,
        coerced: RowResult,
        raw_logger: Callable[[Any], None],
    ) -> RowOutcome | _Proceed:
        identifier = coerced.identifier
        medical_record_id = coerced.values.get("medicalRecordId")
        if medical_record_id is None:
            return RowOutcome(
                row_index,
                identifier,
                Status.INVALID,
                msgs=[Msg(MessageCode.ROW_RECORD_ID_BLANK)],
                warnings=coerced.warnings,
            )

        try:
            detail = records.fetch_detail(client, medical_record_id)
        except ApiError as exc:
            return RowOutcome(
                row_index,
                identifier,
                Status.FAILED,
                msgs=[Msg(MessageCode.ROW_FETCH_DETAIL_FAILED, detail=str(exc))],
                warnings=coerced.warnings,
            )

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
        return _Proceed(
            payload=payload,
            patient_id=patient_id,
            who=who,
            success_status=Status.UPDATED,
            success_code=MessageCode.ROW_UPDATED,
            send=lambda c: records.update(c, payload),
            dryrun_record_id=medical_record_id,
        )

    return _run_batch(
        input_path,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=limit,
        settings=settings,
        callbacks=callbacks,
        should_cancel=should_cancel,
        process_row=process_row,
        cancel=cancel,
    )


def run_delete(
    input_path: str | Path,
    mapping: MappingConfig,
    *,
    token: str,
    dry_run: bool = True,
    limit: int | None = None,
    settings: Settings | None = None,
    callbacks: Callbacks | None = None,
    should_cancel: Callable[[], bool] | None = None,
    cancel: threading.Event | None = None,
) -> RunSummary:
    """Batch-delete existing medical records by ``medicalRecordId``.

    Like ``run_update``, this fetches each record's detail first — as an existence check and to
    recover patient info for the dry-run/results display — then sends the empty-body delete. It
    does not search for patients and does not consult or write the ledger, so re-running a delete
    on an already-deleted id simply fails at fetch-detail as a per-row FAILED (the batch continues).
    The mapping must include a column with ``target: medicalRecordId, required: true``.
    """
    if not any(
        spec.target == "medicalRecordId" and spec.required for spec in mapping.columns.values()
    ):
        raise ConfigError(
            "Delete mode requires a mapping column with target: medicalRecordId, required: true. "
            "See mapping.update.example.yaml for an example ('Mã hồ sơ')."
        )

    bad_targets = builder.validate_targets(mapping)
    if bad_targets:
        raise ConfigError(f"Mapping uses unknown API field target(s): {bad_targets}")

    def process_row(
        client: ApiClient,
        row_index: int,
        coerced: RowResult,
        raw_logger: Callable[[Any], None],
    ) -> RowOutcome | _Proceed:
        identifier = coerced.identifier
        medical_record_id = coerced.values.get("medicalRecordId")
        if medical_record_id is None:
            return RowOutcome(
                row_index,
                identifier,
                Status.INVALID,
                msgs=[Msg(MessageCode.ROW_RECORD_ID_BLANK)],
                warnings=coerced.warnings,
            )

        try:
            detail = records.fetch_detail(client, medical_record_id)
        except ApiError as exc:
            return RowOutcome(
                row_index,
                identifier,
                Status.FAILED,
                msgs=[Msg(MessageCode.ROW_FETCH_DETAIL_FAILED, detail=str(exc))],
                warnings=coerced.warnings,
            )

        patient_id, mic = records.extract_patient_ref(detail)
        who = (detail.get("medicalRecordInfo") or detail.get("medicalRecords") or {}).get(
            "doctorName"
        ) or ""
        # The live delete request has an empty body; this payload is only a dry-run marker,
        # written to payloads/row_N.json so the payloads dir stays meaningful for inspection.
        payload = {
            "action": "delete",
            "medicalRecordId": medical_record_id,
            "patientId": patient_id,
            "medicalIdentifierCode": mic,
        }
        return _Proceed(
            payload=payload,
            patient_id=patient_id,
            who=who,
            success_status=Status.DELETED,
            success_code=MessageCode.ROW_DELETED,
            send=lambda c: records.delete(c, medical_record_id),
            dryrun_record_id=medical_record_id,
        )

    return _run_batch(
        input_path,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=limit,
        settings=settings,
        callbacks=callbacks,
        should_cancel=should_cancel,
        process_row=process_row,
        cancel=cancel,
    )
