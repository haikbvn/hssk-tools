"""Sponsor dialog i18n: all keys resolve in both languages without a QApplication."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk_gui.i18n import set_language, tr

_SPONSOR_KEYS = [
    "menu_sponsor",
    "footer_sponsor",
    "sponsor_title",
    "sponsor_intro",
    "sponsor_vietqr_caption",
    "sponsor_momo_caption",
    "sponsor_thanks",
    "sponsor_qr_missing",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_sponsor_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _SPONSOR_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"


def test_sponsor_strings_differ_by_language() -> None:
    set_language("en")
    en_vals = {k: tr(k) for k in _SPONSOR_KEYS}
    set_language("vi")
    vi_vals = {k: tr(k) for k in _SPONSOR_KEYS}
    # At least some strings must differ between languages.
    assert any(en_vals[k] != vi_vals[k] for k in _SPONSOR_KEYS)
