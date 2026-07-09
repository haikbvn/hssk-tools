"""The GUI update notification's version logic and GitHub fetch (hssk_gui/update_check.py)."""

from __future__ import annotations

import httpx
import pytest
import respx

from hssk_gui.update_check import (
    LATEST_RELEASE_URL,
    RELEASES_PAGE_URL,
    Asset,
    extract_release,
    extract_release_info,
    fetch_latest_release,
    fetch_release_info,
    is_newer,
    parse_version,
    select_asset,
)

# -- parse_version -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.4.0", (1, 4, 0)),
        ("V2.0", (2, 0)),
        ("1.3.8", (1, 3, 8)),
        ("v10", (10,)),
    ],
)
def test_parse_version_ok(tag: str, expected: tuple[int, ...]) -> None:
    assert parse_version(tag) == expected


@pytest.mark.parametrize("tag", ["", "v", "abc", "1.4.0-beta", "v1..2", "1.x"])
def test_parse_version_malformed(tag: str) -> None:
    assert parse_version(tag) is None


# -- is_newer ----------------------------------------------------------------------------


def test_is_newer_basic() -> None:
    assert is_newer("v1.4.0", "1.3.8")
    assert not is_newer("v1.3.8", "1.3.8")
    assert not is_newer("v1.3.7", "1.3.8")


def test_is_newer_pads_shorter_versions() -> None:
    assert is_newer("v1.4", "1.3.9")
    assert not is_newer("v1.4", "1.4.0")
    assert is_newer("v1.4.1", "1.4")


def test_is_newer_false_on_garbage_either_side() -> None:
    assert not is_newer("nightly", "1.3.8")
    assert not is_newer("v1.4.0", "dev")


# -- extract_release ---------------------------------------------------------------------


def test_extract_release_happy_path() -> None:
    data = {"tag_name": "v1.4.0", "html_url": "https://github.com/x/releases/tag/v1.4.0"}
    assert extract_release(data) == ("v1.4.0", "https://github.com/x/releases/tag/v1.4.0")


def test_extract_release_missing_url_falls_back_to_releases_page() -> None:
    assert extract_release({"tag_name": "v1.4.0"}) == ("v1.4.0", RELEASES_PAGE_URL)


@pytest.mark.parametrize("data", [None, [], "x", {}, {"tag_name": ""}, {"tag_name": 3}])
def test_extract_release_unusable_shapes(data: object) -> None:
    assert extract_release(data) is None


# -- fetch_latest_release (respx-mocked httpx) --------------------------------------------


@respx.mock
def test_fetch_happy_path() -> None:
    respx.get(LATEST_RELEASE_URL).mock(
        return_value=httpx.Response(
            200, json={"tag_name": "v9.9.9", "html_url": "https://example.com/rel"}
        )
    )
    assert fetch_latest_release() == ("v9.9.9", "https://example.com/rel")


@respx.mock
def test_fetch_non_200_returns_none() -> None:
    respx.get(LATEST_RELEASE_URL).mock(return_value=httpx.Response(404))
    assert fetch_latest_release() is None


@respx.mock
def test_fetch_network_error_returns_none() -> None:
    respx.get(LATEST_RELEASE_URL).mock(side_effect=httpx.ConnectError("no network"))
    assert fetch_latest_release() is None


@respx.mock
def test_fetch_non_json_body_returns_none() -> None:
    respx.get(LATEST_RELEASE_URL).mock(return_value=httpx.Response(200, text="<html>rate limit"))
    assert fetch_latest_release() is None


# -- extract_release_info / assets --------------------------------------------------------

_SAMPLE_PAYLOAD = {
    "tag_name": "v1.14.0",
    "html_url": "https://github.com/haikbvn/hssk-tools/releases/tag/v1.14.0",
    "assets": [
        {
            "name": "HSSK-Tools-1.14.0-apple-silicon.dmg",
            "browser_download_url": (
                "https://github.com/haikbvn/hssk-tools/releases/download/v1.14.0/"
                "HSSK-Tools-1.14.0-apple-silicon.dmg"
            ),
            "size": 245901022,
            "digest": "sha256:e1fb24323bde1ff39ca5b444b66a8d77f06f2f7e08f18f311c5fc853dddfc42",
        },
        {
            "name": "HSSK-Tools-1.14.0-intel.dmg",
            "browser_download_url": (
                "https://github.com/haikbvn/hssk-tools/releases/download/v1.14.0/"
                "HSSK-Tools-1.14.0-intel.dmg"
            ),
            "size": 258125499,
            "digest": "sha256:da10100767bb5fd33d03cb26db1f1679db42230b00276829d6214ff0b0df54",
        },
        {
            "name": "HSSK-Tools-Setup-1.14.0.exe",
            "browser_download_url": (
                "https://github.com/haikbvn/hssk-tools/releases/download/v1.14.0/"
                "HSSK-Tools-Setup-1.14.0.exe"
            ),
            "size": 198808501,
            "digest": "sha256:94db46f6b1d855c2b8cbe7a43cafc6e7e474d87a42823ef9b073d4a82931f0f",
        },
    ],
}


def test_extract_release_info_happy_path() -> None:
    info = extract_release_info(_SAMPLE_PAYLOAD)
    assert info is not None
    assert info.tag == "v1.14.0"
    assert info.html_url == _SAMPLE_PAYLOAD["html_url"]
    assert len(info.assets) == 3
    exe = next(a for a in info.assets if a.name.endswith(".exe"))
    assert exe.size == 198808501
    assert exe.sha256 == "94db46f6b1d855c2b8cbe7a43cafc6e7e474d87a42823ef9b073d4a82931f0f"


def test_extract_release_info_digest_absent_is_none() -> None:
    payload = {
        "tag_name": "v1.0.0",
        "html_url": "https://example.com/rel",
        "assets": [
            {"name": "app.exe", "browser_download_url": "https://example.com/app.exe", "size": 10}
        ],
    }
    info = extract_release_info(payload)
    assert info is not None
    assert info.assets[0].sha256 is None


def test_extract_release_info_digest_non_sha256_is_none() -> None:
    payload = {
        "tag_name": "v1.0.0",
        "html_url": "https://example.com/rel",
        "assets": [
            {
                "name": "app.exe",
                "browser_download_url": "https://example.com/app.exe",
                "size": 10,
                "digest": "md5:deadbeef",
            }
        ],
    }
    info = extract_release_info(payload)
    assert info is not None
    assert info.assets[0].sha256 is None


@pytest.mark.parametrize(
    "item",
    [
        {"browser_download_url": "https://x", "size": 1},  # missing name
        {"name": "a", "size": 1},  # missing url
        {"name": "a", "browser_download_url": "https://x"},  # missing size
        {"name": "a", "browser_download_url": "https://x", "size": "10"},  # size not int
        "not-a-dict",
    ],
)
def test_extract_release_info_skips_malformed_assets(item: object) -> None:
    payload = {"tag_name": "v1.0.0", "html_url": "https://example.com/rel", "assets": [item]}
    info = extract_release_info(payload)
    assert info is not None
    assert info.assets == []


def test_extract_release_info_assets_missing_or_wrong_type() -> None:
    payload = {"tag_name": "v1.0.0", "html_url": "https://example.com/rel"}
    info = extract_release_info(payload)
    assert info is not None
    assert info.assets == []


def test_extract_release_stays_derived_from_release_info() -> None:
    assert extract_release(_SAMPLE_PAYLOAD) == ("v1.14.0", _SAMPLE_PAYLOAD["html_url"])


# -- select_asset ---------------------------------------------------------------------------


def test_select_asset_windows() -> None:
    info = extract_release_info(_SAMPLE_PAYLOAD)
    assert info is not None
    picked = select_asset(info.assets, system="win32", machine="AMD64")
    assert picked is not None
    assert picked.name == "HSSK-Tools-Setup-1.14.0.exe"


def test_select_asset_macos_arm64() -> None:
    info = extract_release_info(_SAMPLE_PAYLOAD)
    assert info is not None
    picked = select_asset(info.assets, system="darwin", machine="arm64")
    assert picked is not None
    assert picked.name == "HSSK-Tools-1.14.0-apple-silicon.dmg"


def test_select_asset_macos_intel() -> None:
    info = extract_release_info(_SAMPLE_PAYLOAD)
    assert info is not None
    picked = select_asset(info.assets, system="darwin", machine="x86_64")
    assert picked is not None
    assert picked.name == "HSSK-Tools-1.14.0-intel.dmg"


def test_select_asset_unsupported_platform_returns_none() -> None:
    info = extract_release_info(_SAMPLE_PAYLOAD)
    assert info is not None
    assert select_asset(info.assets, system="linux", machine="x86_64") is None


def test_select_asset_no_matching_asset_returns_none() -> None:
    assets = [Asset(name="readme.txt", url="https://x", size=1, sha256=None)]
    assert select_asset(assets, system="win32", machine="AMD64") is None
    assert select_asset(assets, system="darwin", machine="arm64") is None


# -- fetch_release_info (respx-mocked httpx) ------------------------------------------------


@respx.mock
def test_fetch_release_info_happy_path() -> None:
    respx.get(LATEST_RELEASE_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_PAYLOAD))
    info = fetch_release_info()
    assert info is not None
    assert info.tag == "v1.14.0"
    assert len(info.assets) == 3


@respx.mock
def test_fetch_release_info_non_200_returns_none() -> None:
    respx.get(LATEST_RELEASE_URL).mock(return_value=httpx.Response(404))
    assert fetch_release_info() is None


@respx.mock
def test_fetch_release_info_network_error_returns_none() -> None:
    respx.get(LATEST_RELEASE_URL).mock(side_effect=httpx.ConnectError("no network"))
    assert fetch_release_info() is None
