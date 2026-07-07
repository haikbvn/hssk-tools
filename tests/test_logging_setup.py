"""The rotating file log: redaction scrubs credentials, and configure_logging is idempotent."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from hssk.config import settings
from hssk.logging_setup import _HANDLER_NAME, configure_logging, redact

_FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzZWNyZXQifQ.SIGSIGSIGSIG"


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point data_dir() at a temp path and remove our root handler afterward (global state)."""
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    settings.cache_clear()
    yield tmp_path
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME]:
        root.removeHandler(handler)
        handler.close()
    settings.cache_clear()


def test_redact_masks_bearer_and_jwt() -> None:
    assert _FAKE_JWT not in redact(f"Authorization: Bearer {_FAKE_JWT}")
    assert "secret" not in redact(f"leaked {_FAKE_JWT} here")  # bare JWT still caught
    assert redact("nothing sensitive here") == "nothing sensitive here"


def test_configure_logging_is_idempotent(isolated_data_dir: Path) -> None:
    p1 = configure_logging()
    p2 = configure_logging()
    assert p1 == p2 == isolated_data_dir / "logs" / "hssk.log"
    root = logging.getLogger()
    handlers = [h for h in root.handlers if getattr(h, "name", None) == _HANDLER_NAME]
    assert len(handlers) == 1  # not stacked


def test_written_log_is_redacted(isolated_data_dir: Path) -> None:
    log_path = configure_logging()
    logging.getLogger("hssk.test").debug("captured Bearer %s from header", _FAKE_JWT)
    logging.shutdown()  # flush the handler
    text = log_path.read_text(encoding="utf-8")
    assert _FAKE_JWT not in text
    assert "«redacted»" in text
