"""The support bundle: redacted logs + mapping + snapshot; never secrets; events opt-in only."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from hssk.config import settings
from hssk.support_bundle import build_support_bundle

_FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzZWNyZXQifQ.SIGSIGSIGSIG"


@pytest.fixture
def seeded_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A temp data dir + config dir seeded with a token-bearing log, secrets, mapping, and a run."""
    data = tmp_path / "data"
    cfg = tmp_path / "cfg"
    (data / "logs").mkdir(parents=True)
    (data / "secrets").mkdir(parents=True)
    run = data / "output" / "run-20260101-000000"
    run.mkdir(parents=True)
    cfg.mkdir(parents=True)

    (data / "logs" / "hssk.log").write_text(
        f"DEBUG captured Bearer {_FAKE_JWT}\nordinary line\n", encoding="utf-8"
    )
    (data / "secrets" / "token.json").write_text("super-secret-token", encoding="utf-8")
    (cfg / "mapping.yaml").write_text("col: field\n", encoding="utf-8")
    (run / "events.jsonl").write_text('{"row": 1, "id": "PATIENT-123"}\n', encoding="utf-8")

    monkeypatch.setenv("HSSK_DATA_DIR", str(data))
    monkeypatch.setenv("HSSK_CONFIG_DIR", str(cfg))
    settings.cache_clear()
    yield tmp_path
    settings.cache_clear()


def _read_all(zip_path: Path) -> tuple[list[str], bytes]:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        blob = b"".join(zf.read(n) for n in names)
    return names, blob


def test_bundle_excludes_secrets_and_redacts_logs(seeded_dirs: Path) -> None:
    dest = build_support_bundle(seeded_dirs / "bundle.zip")
    names, blob = _read_all(dest)

    assert "logs/hssk.log" in names
    assert "config/mapping.yaml" in names
    assert "snapshot.json" in names
    # No secrets, no raw token, no un-redacted Bearer value anywhere in the archive.
    assert not any("secret" in n or "token" in n for n in names)
    assert _FAKE_JWT.encode() not in blob
    assert b"super-secret-token" not in blob


def test_events_excluded_by_default(seeded_dirs: Path) -> None:
    names, blob = _read_all(build_support_bundle(seeded_dirs / "b.zip"))
    assert "events.jsonl" not in names
    assert b"PATIENT-123" not in blob


def test_events_included_on_opt_in(seeded_dirs: Path) -> None:
    names, blob = _read_all(build_support_bundle(seeded_dirs / "b.zip", include_events=True))
    assert "events.jsonl" in names
    assert b"PATIENT-123" in blob


def test_snapshot_has_versions_and_extra_ui(seeded_dirs: Path) -> None:
    dest = build_support_bundle(seeded_dirs / "b.zip", extra_snapshot={"language": "vi"})
    with zipfile.ZipFile(dest) as zf:
        snap = json.loads(zf.read("snapshot.json"))
    assert snap["versions"]["hssk-tools"]
    assert snap["ui"] == {"language": "vi"}
    assert "platform" in snap
