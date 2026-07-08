"""Confirm-dialog i18n + widget-level behavior for the one-click PRODUCTION confirm.

``dlg_type_to_confirm_hint`` and the typed-``YES`` gate were removed in favor of a plain
Confirm/Cancel dialog (still custom-drawn, so it renders identically on both OSes) with Cancel
defaulted so a stray Enter can't fire a live push.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from hssk_gui.confirm_dialog import ConfirmProductionDialog
from hssk_gui.i18n import set_language, tr

_CONFIRM_KEYS = [
    "dlg_confirm_push",
    "msg_confirm_push",
    "msg_confirm_push_update",
    "msg_confirm_push_delete",
    "btn_confirm_push",
    "btn_cancel",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_confirm_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _CONFIRM_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"


def test_ok_button_enabled_immediately(qtbot) -> None:
    dlg = ConfirmProductionDialog("test message")
    qtbot.addWidget(dlg)
    ok_btn = dlg._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_btn.isEnabled()  # no typed-word gate — one click is enough


def test_cancel_is_the_default_action(qtbot) -> None:
    # isDefault() is what actually controls Enter-key activation; hasFocus() additionally needs
    # real window-manager activation, which the offscreen test platform doesn't reliably grant.
    dlg = ConfirmProductionDialog("test message")
    qtbot.addWidget(dlg)
    ok_btn = dlg._buttons.button(QDialogButtonBox.StandardButton.Ok)
    cancel_btn = dlg._buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel_btn.isDefault()
    assert not ok_btn.isDefault()


def test_confirm_accept_returns_true(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert ConfirmProductionDialog.confirm("msg") is True


def test_confirm_reject_returns_false(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert ConfirmProductionDialog.confirm("msg") is False


def test_ok_click_accepts_dialog(qtbot) -> None:
    dlg = ConfirmProductionDialog("test message")
    qtbot.addWidget(dlg)
    ok_btn = dlg._buttons.button(QDialogButtonBox.StandardButton.Ok)
    qtbot.mouseClick(ok_btn, Qt.MouseButton.LeftButton)
    assert dlg.result() == QDialog.DialogCode.Accepted
