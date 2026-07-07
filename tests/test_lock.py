"""Tests for pipeline/lock.py — the single-batch advisory lock guarding the dedup ledger."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from hssk.errors import AlreadyRunning
from hssk.pipeline.lock import RunLock


def test_lock_acquire_release_roundtrip(tmp_path: Path):
    lock_file = tmp_path / "hssk.lock"
    with RunLock(lock_file):
        pass
    # Released — a second acquisition in the same process must succeed.
    with RunLock(lock_file):
        pass


def test_second_process_is_blocked(tmp_path: Path):
    """While one process holds the lock, another acquiring the same file must raise."""
    lock_file = tmp_path / "hssk.lock"
    child = textwrap.dedent(
        f"""
        from pathlib import Path
        from hssk.pipeline.lock import RunLock
        from hssk.errors import AlreadyRunning
        try:
            with RunLock(Path({str(lock_file)!r})):
                print("ACQUIRED")
        except AlreadyRunning:
            print("BLOCKED")
        """
    )
    with RunLock(lock_file):
        result = subprocess.run(
            [sys.executable, "-c", child], capture_output=True, text=True, timeout=30
        )
    assert result.stdout.strip() == "BLOCKED", result.stderr


def test_lock_reacquirable_across_processes_after_release(tmp_path: Path):
    """After the holder releases, a fresh process can take the lock."""
    lock_file = tmp_path / "hssk.lock"
    child = textwrap.dedent(
        f"""
        from pathlib import Path
        from hssk.pipeline.lock import RunLock
        with RunLock(Path({str(lock_file)!r})):
            print("ACQUIRED")
        """
    )
    with RunLock(lock_file):
        pass  # holder releases here
    result = subprocess.run(
        [sys.executable, "-c", child], capture_output=True, text=True, timeout=30
    )
    assert result.stdout.strip() == "ACQUIRED", result.stderr


def test_double_acquire_same_instance_raises(tmp_path: Path):
    lock_file = tmp_path / "hssk.lock"
    outer = RunLock(lock_file)
    outer.acquire()
    try:
        with pytest.raises(AlreadyRunning):
            RunLock(lock_file).acquire()
    finally:
        outer.release()
