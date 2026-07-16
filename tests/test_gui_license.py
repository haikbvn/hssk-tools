"""LicenseDialog + app._ensure_licensed() — the GUI half of Plan 012's Polar license gate."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from PySide6.QtCore import Qt

from hssk import licensing
from hssk.config import settings as _settings_cached
from hssk.licensing import LicenseCheck
from hssk_gui.i18n import set_language, tr
from hssk_gui.license_dialog import LicenseDialog

ORG_ID = "11111111-1111-1111-1111-111111111111"
VALIDATE_URL = "https://api.polar.sh" + licensing.VALIDATE_PATH

_LICENSE_KEYS = [
    "menu_license",
    "license_title",
    "license_status_active",
    "license_status_perpetual",
    "license_status_grace",
    "license_reason_missing_key",
    "license_reason_unconfigured",
    "license_reason_revoked",
    "license_reason_disabled",
    "license_reason_expired",
    "license_reason_not_found",
    "license_reason_malformed_response",
    "license_reason_offline_no_cache",
    "license_reason_offline_grace_expired",
    "license_input_label",
    "license_apply",
    "license_buy",
    "license_buy_momo_note",
    "license_continue",
    "license_quit",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolate the license key/cache location and configure an org id (pattern:
    tests/test_licensing.py) so LicenseDialog's real check_license()/save_key() calls never
    touch the developer's real OS data dir."""
    monkeypatch.setenv("HSSK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HSSK_POLAR_ORGANIZATION_ID", ORG_ID)
    _settings_cached.cache_clear()
    try:
        yield tmp_path
    finally:
        _settings_cached.cache_clear()


# -- i18n parity --------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_license_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _LICENSE_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"


def test_license_strings_differ_by_language() -> None:
    set_language("en")
    en_vals = {k: tr(k) for k in _LICENSE_KEYS}
    set_language("vi")
    vi_vals = {k: tr(k) for k in _LICENSE_KEYS}
    assert any(en_vals[k] != vi_vals[k] for k in _LICENSE_KEYS)


# -- dialog rendering / interaction ---------------------------------------------------------


def test_menu_mode_shows_missing_key_reason(qtbot, sandbox: Path) -> None:
    dlg = LicenseDialog(gate=False)
    qtbot.addWidget(dlg)
    assert dlg._status_label.text() == tr("license_reason_missing_key")


def test_gate_mode_continue_disabled_without_a_license(qtbot, sandbox: Path) -> None:
    dlg = LicenseDialog(gate=True)
    qtbot.addWidget(dlg)
    assert not dlg._continue_btn.isEnabled()


@respx.mock
def test_apply_granted_key_writes_files_and_enables_continue(qtbot, sandbox: Path) -> None:
    respx.post(VALIDATE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "granted",
                "expires_at": None,
                "display_key": "MY-****",
                "customer": {"email": "clinic@example.com"},
            },
        )
    )
    dlg = LicenseDialog(gate=True)
    qtbot.addWidget(dlg)
    assert not dlg._continue_btn.isEnabled()

    dlg._key_input.setText("MY-KEY")
    qtbot.mouseClick(dlg._apply_btn, Qt.MouseButton.LeftButton)

    from hssk.config import license_cache_path, license_path

    assert license_path().exists()
    assert license_cache_path().exists()
    assert dlg._continue_btn.isEnabled()
    assert dlg.current_check().ok is True
    assert dlg._status_label.text() == tr("license_status_active").format(
        who="clinic@example.com", expires=tr("license_status_perpetual")
    )


@respx.mock
def test_apply_not_found_shows_reason_and_continue_stays_disabled(qtbot, sandbox: Path) -> None:
    respx.post(VALIDATE_URL).mock(return_value=httpx.Response(404))
    dlg = LicenseDialog(gate=True)
    qtbot.addWidget(dlg)

    dlg._key_input.setText("BAD-KEY")
    qtbot.mouseClick(dlg._apply_btn, Qt.MouseButton.LeftButton)

    assert dlg._status_label.text() == tr("license_reason_not_found")
    assert not dlg._continue_btn.isEnabled()
    assert dlg.current_check().ok is False


# -- app._ensure_licensed() ------------------------------------------------------------------


def test_ensure_licensed_short_circuits_when_already_granted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A granted check must return True without ever constructing LicenseDialog."""
    import hssk_gui.app as app_module

    monkeypatch.setattr(app_module, "check_license", lambda: LicenseCheck(ok=True, source="cache"))

    def _must_not_construct(*_a: object, **_kw: object) -> None:
        raise AssertionError("LicenseDialog must not be constructed when already licensed")

    monkeypatch.setattr("hssk_gui.license_dialog.LicenseDialog", _must_not_construct)

    assert app_module._ensure_licensed() is True
