"""Confirm-dialog i18n + the confirm word contract, without instantiating a live QDialog.

Widget-lifecycle testing (actually typing into the QLineEdit, clicking buttons) is deferred to
the pytest-qt harness added in a later phase; this pins what's testable without a display: the
literal word the CLI and GUI both require, and that every dialog string translates.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk_gui.confirm_dialog import CONFIRM_WORD
from hssk_gui.i18n import set_language, tr

_CONFIRM_KEYS = [
    "dlg_confirm_push",
    "msg_confirm_push",
    "msg_confirm_push_update",
    "msg_confirm_push_delete",
    "dlg_type_to_confirm_hint",
    "btn_confirm_push",
    "btn_cancel",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


def test_confirm_word_matches_cli() -> None:
    # cli.py:_confirm_production requires the operator to type this exact word; the GUI dialog
    # must require the same one so CLI and GUI teach one shared safety habit.
    assert CONFIRM_WORD == "YES"


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_confirm_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _CONFIRM_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"


def test_confirm_hint_is_not_translated_into_a_different_word() -> None:
    # The hint text may be phrased differently per language, but must still tell the operator to
    # type the literal, untranslated CONFIRM_WORD (translating "YES" itself would break the gate).
    for lang in ("en", "vi"):
        set_language(lang)
        assert CONFIRM_WORD in tr("dlg_type_to_confirm_hint")
