"""The recent-files list helper (hssk_gui/settings.py, pure part)."""

from __future__ import annotations

from hssk_gui.settings import add_recent


def test_new_path_goes_to_front() -> None:
    assert add_recent(["/a", "/b"], "/c") == ["/c", "/a", "/b"]


def test_existing_path_moves_to_front_without_duplicate() -> None:
    assert add_recent(["/a", "/b", "/c"], "/b") == ["/b", "/a", "/c"]


def test_list_truncates_to_limit() -> None:
    paths = [f"/f{i}" for i in range(5)]
    out = add_recent(paths, "/new", limit=5)
    assert len(out) == 5
    assert out[0] == "/new"
    assert "/f4" not in out


def test_empty_list() -> None:
    assert add_recent([], "/a") == ["/a"]
