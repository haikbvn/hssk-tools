"""Retention housekeeping for run-report folders (patient PII at rest).

Each batch writes an ``output_dir()/run-<stamp>/`` folder holding ``results.xlsx``, the raw
``search_response_row_N.json`` dumps, and payloads — all of which contain patient data and
otherwise accumulate forever. These helpers find and delete folders older than a retention window.

Deletion is **never automatic by default**: the GUI calls these from an explicit, confirmed "Purge
old reports" action, or — only when the operator has opted in via GUI Preferences (default off) —
from a launch-time purge that runs these same helpers silently. The engine helpers themselves never
delete on their own; they are pure enough to unit-test with a faked ``now`` and touched mtimes, and
they only ever touch ``run-*`` directories directly under ``base`` — never files, never anything
else in the data dir.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

_RUN_GLOB = "run-*"
_SECONDS_PER_DAY = 86_400


def find_old_runs(base: Path, retention_days: int, *, now: float | None = None) -> list[Path]:
    """Return the ``run-*`` folders under ``base`` last modified more than ``retention_days`` ago.

    ``now`` (unix seconds) is injectable so tests can reason about a fixed clock. A non-positive
    ``retention_days`` returns nothing — retention is effectively disabled rather than deleting
    everything.
    """
    if retention_days <= 0 or not base.is_dir():
        return []
    cutoff = (time.time() if now is None else now) - retention_days * _SECONDS_PER_DAY
    old = [p for p in base.glob(_RUN_GLOB) if p.is_dir() and p.stat().st_mtime < cutoff]
    return sorted(old)


def purge_runs(paths: list[Path]) -> int:
    """Delete each given run folder (recursively); return how many were removed.

    A folder that vanished or can't be removed is skipped rather than aborting the batch, so one
    locked directory never blocks purging the rest.
    """
    removed = 0
    for p in paths:
        try:
            shutil.rmtree(p)
            removed += 1
        except OSError:
            continue
    return removed
