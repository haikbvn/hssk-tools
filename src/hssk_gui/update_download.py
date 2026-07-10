"""Download and verify a release asset for the assisted-install auto-updater.

Qt-free so it tests headless (respx mocks httpx). Downloads land under ``data_dir()/updates/``
(see ``hssk.config.data_dir``) — the same OS user-data root as logs, reports, and the ledger,
kept in its own subfolder. A successful download clears any other file left there by a prior
check, so stale installers never pile up.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from hssk.config import data_dir

from .update_check import Asset

_CHUNK_SIZE = 1 << 16  # 64 KiB

# Only the initial request is checked; redirects stay allowed (GitHub serves assets via a
# redirect to its own CDN) because the connection is TLS-verified end to end regardless of host.
_ALLOWED_HOSTS = frozenset(
    {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
)


class DownloadError(Exception):
    """The response, size, or checksum didn't check out."""


class DownloadCancelled(Exception):
    """``should_cancel`` returned True mid-download."""


def updates_dir() -> Path:
    d = data_dir() / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def clear_updates_dir(*, keep: Path | None = None) -> None:
    """Remove every file in ``updates_dir()`` except ``keep`` (best-effort)."""
    for f in updates_dir().iterdir():
        if f.is_file() and f != keep:
            try:
                f.unlink()
            except OSError:
                pass


def _verify(path: Path, asset: Asset) -> None:
    actual_size = path.stat().st_size
    if actual_size != asset.size:
        raise DownloadError(f"size mismatch: expected {asset.size}, got {actual_size}")
    if asset.sha256:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != asset.sha256.lower():
            raise DownloadError("checksum mismatch")


def download_asset(
    asset: Asset,
    dest_dir: Path | None = None,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    timeout: float = 30.0,
) -> Path:
    """Stream ``asset`` into ``dest_dir`` (default ``updates_dir()``), verify, return the path.

    Raises :class:`DownloadCancelled` if ``should_cancel`` returns True mid-stream (the partial
    file is removed), or :class:`DownloadError` if the size/checksum don't match. Network
    failures propagate as ``httpx`` exceptions — callers treat any exception here as a failure.
    """
    if not asset.sha256:
        raise DownloadError("release asset has no sha256 digest — refusing unverifiable download")

    parts = urlsplit(asset.url)
    if parts.scheme != "https" or parts.hostname not in _ALLOWED_HOSTS:
        raise DownloadError(f"refusing download from unexpected URL host: {parts.hostname!r}")

    dest = dest_dir if dest_dir is not None else updates_dir()
    final_path = dest / asset.name
    tmp_path = dest / f"{asset.name}.part"

    cancelled = False
    with httpx.stream("GET", asset.url, follow_redirects=True, timeout=timeout) as resp:
        resp.raise_for_status()
        done = 0
        with tmp_path.open("wb") as f:
            for chunk in resp.iter_bytes(_CHUNK_SIZE):
                if should_cancel is not None and should_cancel():
                    cancelled = True
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, asset.size)

    if cancelled:
        tmp_path.unlink(missing_ok=True)
        raise DownloadCancelled

    try:
        _verify(tmp_path, asset)
    except DownloadError:
        tmp_path.unlink(missing_ok=True)
        raise

    tmp_path.replace(final_path)
    if dest_dir is None:
        clear_updates_dir(keep=final_path)
    return final_path
