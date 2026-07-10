"""Append-only ledger of processed rows for resumability and duplicate protection.

Keyed by ``(medicalIdentifierCode, examinationDate)``. A "done" entry is written only after a
create is confirmed successful, so a crash mid-batch never loses progress and a re-run skips rows
already pushed. A "pending" entry is written *before* the send, as a write-ahead marker: if the
process is interrupted after the server received the request but before the response arrived, the
next run sees the lone pending entry and flags the row for manual verification instead of silently
re-creating it — closing the window a done-only ledger could not cover.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..config import ledger_path


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._done: dict[str, Any] = {}
        self._pending: set[str] = set()
        # Lines load() could not parse as JSON (e.g. truncated by a crash mid-write). Those
        # entries are lost, so the rows they recorded may be re-sent — the runner warns.
        self.corrupt_lines: int = 0

    @staticmethod
    def make_key(identifier: str | None, exam_date: str | None) -> str:
        # Escape the separator so a value containing '|' can't collide across the boundary.
        # Ordinary data (an id + a formatted date, no '|' or '\') is byte-identical to the old
        # "id|date" format, so existing ledgers keep matching after this change.
        def esc(v: str | None) -> str:
            s = "" if v is None else str(v)
            return s.replace("\\", "\\\\").replace("|", "\\|")

        return f"{esc(identifier)}|{esc(exam_date)}"

    @classmethod
    def load(cls, path: Path | None = None) -> Ledger:
        p = path or ledger_path()
        led = cls(p)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    # Blank lines and valid-JSON-without-"key" records are not counted —
                    # only text that fails to parse at all.
                    led.corrupt_lines += 1
                    continue
                if "key" in rec:
                    if rec.get("pending"):
                        led._pending.add(rec["key"])
                    else:
                        led._done[rec["key"]] = rec.get("recordId")
        return led

    def done(self, key: str) -> bool:
        return key in self._done

    def pending(self, key: str) -> bool:
        """A previous commit run wrote the write-ahead marker but never confirmed success."""
        return key in self._pending and key not in self._done

    def record_id(self, key: str) -> Any:
        return self._done.get(key)

    def _append(self, rec: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def mark_pending(self, key: str) -> None:
        self._pending.add(key)
        self._append({"key": key, "pending": True, "ts": time.time()})

    def mark_done(self, key: str, record_id: Any) -> None:
        self._done[key] = record_id
        self._append({"key": key, "recordId": record_id, "ts": time.time()})

    def reset(self) -> None:
        self._done.clear()
        self._pending.clear()
        if self.path.exists():
            self.path.unlink()

    def __len__(self) -> int:
        return len(self._done)
