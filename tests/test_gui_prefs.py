"""Preferences dialog: pure helpers, label coverage, factory constants, and i18n keys.

The repo has no Qt-widget test harness (no pytest-qt; these tests run without a
QApplication), so widget behaviour lives on the manual checklist. Here we cover the pure
logic that the dialog is built on.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk.mapping import MappingConfig
from hssk_gui.i18n import set_language, tr
from hssk_gui.preferences_dialog import _LABEL_KEYS, coerce_record_values, split_list_text
from hssk_gui.settings import UiSettings


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


# -- split_list_text --------------------------------------------------------------------


def test_split_list_text_trims_and_drops_empties() -> None:
    assert split_list_text("a, b , ,c") == ["a", "b", "c"]


def test_split_list_text_empty() -> None:
    assert split_list_text("") == []
    assert split_list_text("   ") == []


# -- coerce_record_values ---------------------------------------------------------------


def test_coerce_splits_list_typed_keys() -> None:
    record_info = {"diagnosesDischargeList": "A, B ,C", "symptoms": "khỏe"}
    reference = {"diagnosesDischargeList": ["x"], "symptoms": "y"}
    out = coerce_record_values(record_info, reference)
    assert out["diagnosesDischargeList"] == ["A", "B", "C"]
    assert out["symptoms"] == "khỏe"


def test_coerce_passes_through_non_strings_and_unknown_keys() -> None:
    record_info = {"treatmentDayNumber": 3, "flag": True, "notInRef": "x, y"}
    reference: dict[str, object] = {"treatmentDayNumber": 1}
    out = coerce_record_values(record_info, reference)
    assert out == {"treatmentDayNumber": 3, "flag": True, "notInRef": "x, y"}


def test_coerce_does_not_mutate_input() -> None:
    record_info = {"diagnosesDischargeList": "A, B"}
    reference = {"diagnosesDischargeList": ["x"]}
    coerce_record_values(record_info, reference)
    assert record_info == {"diagnosesDischargeList": "A, B"}


# -- label coverage guard ---------------------------------------------------------------


def test_every_record_default_field_has_a_label(mapping: MappingConfig) -> None:
    keys = set(mapping.defaults.medicalRecordInfo) | {"normal_desc_value"}
    missing = keys - set(_LABEL_KEYS)
    assert not missing, f"medicalRecordInfo keys without an i18n label: {missing}"


# -- factory constants ------------------------------------------------------------------


def test_ui_settings_factory_constants() -> None:
    assert UiSettings.DELAY_DEFAULT == 1.0
    assert UiSettings.LIMIT_DEFAULT == 0
    assert UiSettings.DRY_RUN_DEFAULT is True
    assert UiSettings.CHECK_UPDATES_DEFAULT is True
    assert UiSettings.LANGUAGE_DEFAULT == "vi"


# -- i18n resolution --------------------------------------------------------------------

_PREFS_KEYS = [
    "btn_ok",
    "btn_cancel",
    "btn_apply",
    "btn_restore_run_defaults",
    "btn_restore_record_defaults",
    "tip_restore_run",
    "tip_restore_record",
    "msg_prefs_applied",
    "msg_prefs_save_failed",
    "dlg_discard_title",
    "msg_discard_changes",
    "btn_discard",
    "btn_keep_editing",
    "tab_general",
    "grp_app_settings",
    "tip_language",
    "tip_facility_locked",
    "grp_run_defaults",
    "msg_mapping_error_prefs",
]


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_prefs_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _PREFS_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"
