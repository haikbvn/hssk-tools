"""Append-only ledger of processed rows for resumability and duplicate protection.

Keyed by ``(medicalIdentifierCode, examinationDate)`` and written immediately after a successful
create, so a crash mid-batch never loses progress or double-sends on the next run.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..config import ledger_path


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._done: dict[str, Any] = {}

    @staticmethod
    def make_key(identifier: str | None, exam_date: str | None) -> str:
        return f"{identifier}|{exam_date}"

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
                    continue
                if "key" in rec:
                    led._done[rec["key"]] = rec.get("recordId")
        return led

    def done(self, key: str) -> bool:
        return key in self._done

    def record_id(self, key: str) -> Any:
        return self._done.get(key)

    def mark_done(self, key: str, record_id: Any) -> None:
        self._done[key] = record_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"key": key, "recordId": record_id, "ts": time.time()},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def reset(self) -> None:
        self._done.clear()
        if self.path.exists():
            self.path.unlink()

    def __len__(self) -> int:
        return len(self._done)
