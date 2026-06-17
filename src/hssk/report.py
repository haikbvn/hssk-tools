"""Write per-run reports: results.xlsx, results.csv, events.jsonl."""

from __future__ import annotations

import csv
import datetime as dt
import json
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openpyxl import Workbook

if TYPE_CHECKING:
    from .pipeline.runner import RowOutcome

_COLUMNS = ["row", "identifier", "status", "patientId", "recordId", "message", "warnings"]


def new_run_dir(base: Path, *, dry_run: bool) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "-dryrun" if dry_run else ""
    run_dir = base / f"run-{stamp}{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _row(outcome: RowOutcome) -> list[Any]:
    status = getattr(outcome.status, "value", outcome.status)
    return [
        outcome.row_index,
        outcome.identifier or "",
        status,
        outcome.patient_id if outcome.patient_id is not None else "",
        outcome.record_id if outcome.record_id is not None else "",
        outcome.message,
        "; ".join(outcome.warnings),
    ]


def write_report(run_dir: Path, outcomes: Iterable[RowOutcome], *, dry_run: bool) -> Path:
    outcomes = list(outcomes)
    run_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(_COLUMNS)
        for o in outcomes:
            w.writerow(_row(o))

    # JSONL events
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as f:
        for o in outcomes:
            record = dict(zip(_COLUMNS, _row(o), strict=True))
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append(_COLUMNS)
    for o in outcomes:
        ws.append(_row(o))
    wb.save(run_dir / "results.xlsx")

    return run_dir
