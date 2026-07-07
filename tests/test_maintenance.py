"""Retention helpers: find_old_runs picks only stale run-* dirs; purge_runs deletes only those."""

from __future__ import annotations

import os
import time
from pathlib import Path

from hssk.maintenance import find_old_runs, purge_runs

_DAY = 86_400


def _make_run(base: Path, name: str, age_days: float, *, now: float) -> Path:
    d = base / name
    d.mkdir()
    (d / "results.xlsx").write_text("x", encoding="utf-8")
    stamp = now - age_days * _DAY
    os.utime(d, (stamp, stamp))
    return d


def test_find_old_runs_selects_only_stale_dirs(tmp_path: Path) -> None:
    now = time.time()
    old = _make_run(tmp_path, "run-20250101-000000", age_days=100, now=now)
    _make_run(tmp_path, "run-20260601-000000", age_days=5, now=now)  # recent — kept
    # A non-run directory and a stray file must never be considered, even if old.
    other = tmp_path / "browser-profile"
    other.mkdir()
    os.utime(other, (now - 500 * _DAY, now - 500 * _DAY))
    stray = tmp_path / "ledger.jsonl"
    stray.write_text("x", encoding="utf-8")
    os.utime(stray, (now - 500 * _DAY, now - 500 * _DAY))

    found = find_old_runs(tmp_path, 90, now=now)

    assert found == [old]


def test_find_old_runs_retention_zero_disables(tmp_path: Path) -> None:
    now = time.time()
    _make_run(tmp_path, "run-20200101-000000", age_days=9999, now=now)
    assert find_old_runs(tmp_path, 0, now=now) == []


def test_find_old_runs_missing_base(tmp_path: Path) -> None:
    assert find_old_runs(tmp_path / "nope", 90) == []


def test_purge_runs_removes_only_given_dirs(tmp_path: Path) -> None:
    now = time.time()
    old = _make_run(tmp_path, "run-20250101-000000", age_days=100, now=now)
    recent = _make_run(tmp_path, "run-20260601-000000", age_days=5, now=now)

    removed = purge_runs([old])

    assert removed == 1
    assert not old.exists()
    assert recent.exists()  # untouched


def test_purge_runs_skips_missing(tmp_path: Path) -> None:
    # A path that already vanished is counted as not-removed, without raising.
    assert purge_runs([tmp_path / "run-gone"]) == 0
