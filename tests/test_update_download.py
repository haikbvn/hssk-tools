"""Streamed download + verification for the assisted-install auto-updater
(hssk_gui/update_download.py)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from hssk_gui.update_check import Asset
from hssk_gui.update_download import (
    DownloadCancelled,
    DownloadError,
    clear_updates_dir,
    download_asset,
    updates_dir,
)

_URL = "https://github.com/haikbvn/hssk-tools/releases/download/v99.0.0/app.exe"
_CONTENT = b"x" * 5000  # exceeds one chunk boundary isn't required for these tests
_DIGEST = hashlib.sha256(_CONTENT).hexdigest()


def _asset(
    *,
    size: int | None = None,
    sha256: str | None = _DIGEST,
    name: str = "app.exe",
    url: str = _URL,
) -> Asset:
    return Asset(
        name=name,
        url=url,
        size=len(_CONTENT) if size is None else size,
        sha256=sha256,
    )


# -- happy path -------------------------------------------------------------------------


@respx.mock
def test_download_writes_file_and_reports_progress(tmp_path: Path) -> None:
    respx.get(_URL).mock(return_value=httpx.Response(200, content=_CONTENT))
    progress: list[tuple[int, int]] = []

    path = download_asset(_asset(), tmp_path, on_progress=lambda d, t: progress.append((d, t)))

    assert path == tmp_path / "app.exe"
    assert path.read_bytes() == _CONTENT
    assert progress  # at least one progress callback fired
    assert progress[-1][0] == len(_CONTENT)  # final callback reports full size done
    assert all(total == len(_CONTENT) for _done, total in progress)
    # no leftover .part file
    assert not (tmp_path / "app.exe.part").exists()


@respx.mock
def test_download_follows_redirects(tmp_path: Path) -> None:
    respx.get(_URL).mock(
        return_value=httpx.Response(
            302, headers={"Location": "https://objects.githubusercontent.com/app.exe"}
        )
    )
    respx.get("https://objects.githubusercontent.com/app.exe").mock(
        return_value=httpx.Response(200, content=_CONTENT)
    )
    path = download_asset(_asset(), tmp_path)
    assert path.read_bytes() == _CONTENT


@respx.mock
def test_download_verifies_correct_sha256(tmp_path: Path) -> None:
    digest = hashlib.sha256(_CONTENT).hexdigest()
    respx.get(_URL).mock(return_value=httpx.Response(200, content=_CONTENT))
    path = download_asset(_asset(sha256=digest), tmp_path)
    assert path.read_bytes() == _CONTENT


# -- verification failures ---------------------------------------------------------------


@respx.mock
def test_download_size_mismatch_raises_and_deletes(tmp_path: Path) -> None:
    respx.get(_URL).mock(return_value=httpx.Response(200, content=_CONTENT))
    with pytest.raises(DownloadError, match="size mismatch"):
        download_asset(_asset(size=len(_CONTENT) + 1), tmp_path)
    assert list(tmp_path.iterdir()) == []


@respx.mock
def test_download_checksum_mismatch_raises_and_deletes(tmp_path: Path) -> None:
    respx.get(_URL).mock(return_value=httpx.Response(200, content=_CONTENT))
    with pytest.raises(DownloadError, match="checksum mismatch"):
        download_asset(_asset(sha256="0" * 64), tmp_path)
    assert list(tmp_path.iterdir()) == []


@respx.mock
def test_download_missing_sha256_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="no sha256"):
        download_asset(_asset(sha256=None), tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert respx.calls.call_count == 0  # refused before any request was made


@respx.mock
def test_download_rejects_http_scheme(tmp_path: Path) -> None:
    with pytest.raises(DownloadError):
        download_asset(_asset(url="http://github.com/haikbvn/hssk-tools/app.exe"), tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert respx.calls.call_count == 0  # refused before any request was made


@respx.mock
def test_download_rejects_off_host_url(tmp_path: Path) -> None:
    with pytest.raises(DownloadError):
        download_asset(_asset(url="https://evil.example.com/app.exe"), tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert respx.calls.call_count == 0  # refused before any request was made


# -- cancellation -------------------------------------------------------------------------


@respx.mock
def test_download_cancel_mid_stream_leaves_no_file(tmp_path: Path) -> None:
    # Larger than one 64 KiB chunk, so should_cancel() gets checked more than once and can
    # abort after the first chunk lands but before the stream completes.
    big_content = b"y" * (3 * (1 << 16))
    respx.get(_URL).mock(return_value=httpx.Response(200, content=big_content))
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # let the first chunk through, then cancel

    with pytest.raises(DownloadCancelled):
        download_asset(_asset(size=len(big_content)), tmp_path, should_cancel=should_cancel)
    assert calls["n"] > 1  # sanity: cancellation was actually reached mid-stream
    assert list(tmp_path.iterdir()) == []


# -- default destination + cleanup ---------------------------------------------------------


@respx.mock
def test_download_default_dest_uses_updates_dir_and_clears_stale_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        stale = updates_dir() / "old-installer.exe"
        stale.write_bytes(b"stale")

        respx.get(_URL).mock(return_value=httpx.Response(200, content=_CONTENT))
        path = download_asset(_asset())

        assert path == updates_dir() / "app.exe"
        assert path.read_bytes() == _CONTENT
        assert not stale.exists()  # cleared by the successful default-dest download
        assert list(updates_dir().iterdir()) == [path]
    finally:
        _settings_cached.cache_clear()


def test_clear_updates_dir_keeps_named_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    from hssk.config import settings as _settings_cached

    _settings_cached.cache_clear()
    try:
        keep = updates_dir() / "keep.exe"
        keep.write_bytes(b"keep")
        drop = updates_dir() / "drop.exe"
        drop.write_bytes(b"drop")

        clear_updates_dir(keep=keep)

        assert keep.exists()
        assert not drop.exists()
    finally:
        _settings_cached.cache_clear()
