"""Build a redacted support bundle (a zip) the operator can hand to a maintainer.

Gathers just enough to debug a field problem without leaking secrets or — by default — patient
data: the redacted rotating logs, the column→field mapping files (config, not PII), and a JSON
snapshot of versions + non-secret settings. The token/profile under ``secrets/`` are **never**
included, and the newest run's ``events.jsonl`` (which can carry patient identifiers) is added only
on explicit opt-in. Everything is written locally to a path the operator chooses; nothing is
uploaded. Engine-side and UI-free — the GUI passes any non-PII UI settings via ``extra_snapshot``.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import zipfile
from importlib import metadata
from pathlib import Path
from typing import Any

from . import __version__
from .config import config_dir, data_dir, output_dir, settings
from .logging_setup import redact

# Dependency versions worth capturing for support (read via metadata, so nothing is imported).
_DEP_VERSIONS = ("PySide6", "httpx", "pydantic", "playwright", "openpyxl")


def _snapshot(extra: dict[str, Any] | None) -> dict[str, Any]:
    versions: dict[str, str] = {"hssk-tools": __version__, "python": sys.version.split()[0]}
    for name in _DEP_VERSIONS:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "(not installed)"
    s = settings()
    engine_settings = {k: (str(v) if isinstance(v, Path) else v) for k, v in s.model_dump().items()}
    snap: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "platform": platform.platform(),
        "versions": versions,
        "settings": engine_settings,
    }
    if extra:
        snap["ui"] = extra
    return snap


def _latest_events_jsonl() -> Path | None:
    base = output_dir()
    runs = sorted((p for p in base.glob("run-*") if p.is_dir()), key=lambda p: p.stat().st_mtime)
    for run in reversed(runs):
        candidate = run / "events.jsonl"
        if candidate.exists():
            return candidate
    return None


def build_support_bundle(
    dest_zip: Path,
    *,
    include_events: bool = False,
    extra_snapshot: dict[str, Any] | None = None,
) -> Path:
    """Write the support zip to ``dest_zip`` and return the path.

    ``include_events`` opts the newest run's ``events.jsonl`` (potential PII) into the bundle;
    ``extra_snapshot`` lets the GUI add non-PII UI settings under a ``ui`` key in ``snapshot.json``.
    """
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "snapshot.json",
            json.dumps(_snapshot(extra_snapshot), ensure_ascii=False, indent=2),
        )

        # Logs are redacted a second time on the way in (the handler already redacts on write) —
        # cheap belt-and-braces, and it covers any file a user hand-edited. Includes rotated
        # backups (hssk.log.1, …).
        logs_dir = data_dir() / "logs"
        if logs_dir.is_dir():
            for log_file in sorted(logs_dir.glob("*.log*")):
                try:
                    text = log_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                zf.writestr(f"logs/{log_file.name}", redact(text))

        cfg = config_dir()
        for name in ("mapping.yaml", "mapping.update.yaml"):
            mapping_file = cfg / name
            if mapping_file.exists():
                zf.writestr(f"config/{name}", mapping_file.read_text(encoding="utf-8"))

        if include_events:
            events = _latest_events_jsonl()
            if events is not None:
                zf.writestr("events.jsonl", events.read_text(encoding="utf-8"))
    return dest_zip
