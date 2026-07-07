"""Attach a rotating, secret-redacting file log for the CLI and GUI.

The engine logs through ``logging.getLogger(__name__)`` at DEBUG but ships no handler, so those
records normally drop silently. ``configure_logging()`` gives them a home — a small rotating file
under ``data_dir()/logs/`` — while a redaction filter scrubs Bearer tokens and JWT-shaped strings
from every record so the log can never persist a credential. Both frontends call it once at
startup (``cli.main`` / ``app.main``).

Only our own ``hssk``/``hssk_gui`` loggers are turned up to DEBUG; third-party libraries (httpx,
playwright, openpyxl) keep their default WARNING level, so their verbose DEBUG output — which can
include request bodies carrying patient PII — never lands on disk. Redaction is the second line of
defense, not the only one.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import data_dir

# One definition of the JWT shape (three base64url segments), shared with auth.browser_login, which
# anchors it (``^...$``) for a full-string localStorage match. Here it stays unanchored so a token
# embedded mid-line is still found and masked.
JWT_BODY = r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]+")
_JWT_RE = re.compile(JWT_BODY)
_REDACTED = "«redacted»"

_LOG_FILENAME = "hssk.log"
_MAX_BYTES = 1_000_000  # ~1 MB per file
_BACKUP_COUNT = 3
_HANDLER_NAME = "hssk-rotating-file"


def redact(text: str) -> str:
    """Mask Bearer tokens and JWT-shaped strings so no credential is ever written to disk."""
    # Bearer first: its value gets a placeholder, so the JWT pass below won't re-match it. A bare
    # JWT (e.g. from a localStorage scan log) is then caught by the second substitution.
    text = _BEARER_RE.sub(f"Bearer {_REDACTED}", text)
    return _JWT_RE.sub(_REDACTED, text)


class RedactionFilter(logging.Filter):
    """Rewrite each record's fully-formatted message through :func:`redact` before it is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact the final text (msg % args), then clear args so the handler re-formats the
        # already-scrubbed string rather than re-interpolating the raw token.
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def configure_logging(*, level: int = logging.DEBUG) -> Path:
    """Attach the rotating, redacting file handler to the root logger, once.

    Idempotent: a second call (or a test re-import) won't stack duplicate handlers. Returns the
    log file path.
    """
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILENAME

    # Turn up only our own namespaces; leave the root logger (and thus every third-party library)
    # at its default WARNING so their PII-bearing DEBUG output never reaches the file.
    logging.getLogger("hssk").setLevel(level)
    logging.getLogger("hssk_gui").setLevel(level)

    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "name", None) == _HANDLER_NAME:
            return log_path  # already configured this process

    handler = RotatingFileHandler(
        log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.set_name(_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
    return log_path
