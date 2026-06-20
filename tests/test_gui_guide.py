"""In-app User Guide: i18n keys resolve and the bilingual guide body stays structurally whole.

These run without a QApplication — importing the dialog module only needs PySide6 on the path
(same as test_gui_i18n.py), and the guide content is selected by the pure ``guide_html`` helper.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk_gui.guide_dialog import guide_html
from hssk_gui.i18n import set_language, tr

# Anchor names defined in guide_dialog._GUIDE_HTML / _GUIDE_HTML_VI. If a section is dropped or
# an anchor renamed, the TOC links break silently in the dialog — this list guards against that.
_SECTION_ANCHORS = [
    "overview",
    "template",
    "fill",
    "login",
    "validate",
    "dryrun",
    "push",
    "results",
    "rerun",
    "modes",
    "prefs",
    "mapping",
    "trouble",
    "files",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


def test_menu_and_title_keys_translate() -> None:
    for lang in ("en", "vi"):
        set_language(lang)
        for key in ("menu_user_guide", "guide_title"):
            text = tr(key)
            assert text and text != key


def test_guide_html_differs_by_language() -> None:
    en = guide_html("en")
    vi = guide_html("vi")
    assert en and vi
    assert en != vi
    # An unknown language falls back to English (matches the dialog's selector).
    assert guide_html("fr") == en


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_guide_html_has_every_section_anchor_and_toc_link(lang: str) -> None:
    html = guide_html(lang)
    for anchor in _SECTION_ANCHORS:
        assert f'name="{anchor}"' in html, f"missing section anchor: {anchor}"
        assert f'href="#{anchor}"' in html, f"missing TOC link: {anchor}"
