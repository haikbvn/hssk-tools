"""Record-id extraction — now lives in :mod:`hssk.api.adapters`; re-exported here for callers."""

from __future__ import annotations

from .adapters import extract_record_id

__all__ = ["extract_record_id"]
