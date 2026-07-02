"""The GUI update notification's version logic and GitHub fetch (hssk_gui/update_check.py)."""

from __future__ import annotations

import httpx
import pytest
import respx

from hssk_gui.update_check import (
    LATEST_RELEASE_URL,
    RELEASES_PAGE_URL,
    extract_release,
    fetch_latest_release,
    is_newer,
    parse_version,
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
