"""Widget-level tests for the SafetyStepper strip (Login → File → Validated → Dry-run/Commit).

Covers i18n key resolution for the step labels, the done/not-done glyph+color mapping, the
dry-run/commit mode inversion, and — the regression guard for the separator re-theming fix —
that the ``→`` separators restyle to the active color scheme on every ``update_state`` call.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hssk_gui import theme
from hssk_gui.components.stepper import SafetyStepper
from hssk_gui.i18n import set_language, tr

_STEP_KEYS = [
    "step_login",
    "step_file",
    "step_validated",
    "step_dryrun",
    "step_commit",
]


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    yield
    set_language("vi")


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_all_step_keys_translate(lang: str) -> None:
    set_language(lang)
    for key in _STEP_KEYS:
        text = tr(key)
        assert text, f"{key!r} is empty for lang={lang}"
        assert text != key, f"{key!r} fell through to key itself for lang={lang}"


def test_done_step_shows_success_check(qtbot) -> None:
    stepper = SafetyStepper()
    qtbot.addWidget(stepper)
    stepper.update_state(logged_in=True, file_chosen=True, validated=True, dry_run=True)
    assert stepper._login._glyph.text() == "✓"
    assert theme.color("success") in stepper._login._glyph.styleSheet()


def test_incomplete_step_shows_muted_circle(qtbot) -> None:
    stepper = SafetyStepper()
    qtbot.addWidget(stepper)
    stepper.update_state(logged_in=True, file_chosen=True, validated=True, dry_run=True)
    # dry_run=True → the mode step is NOT done.
    assert stepper._mode._glyph.text() == "○"
    assert theme.color("muted") in stepper._mode._text.styleSheet()


def test_mode_step_inverts_with_dry_run(qtbot) -> None:
    set_language("en")
    stepper = SafetyStepper()
    qtbot.addWidget(stepper)
    stepper.update_state(logged_in=False, file_chosen=False, validated=False, dry_run=True)
    assert stepper._mode._text.text() == tr("step_dryrun")
    assert stepper._mode._glyph.text() == "○"
    stepper.update_state(logged_in=False, file_chosen=False, validated=False, dry_run=False)
    assert stepper._mode._text.text() == tr("step_commit")
    assert stepper._mode._glyph.text() == "✓"


def test_separators_retheme_on_scheme_change(qtbot, monkeypatch) -> None:
    # The forced ``offscreen`` Qt platform makes real ``styleHints().setColorScheme()`` a no-op,
    # so drive the scheme at the ``theme`` layer: ``theme.color()`` looks up ``current_scheme`` in
    # the theme module's globals at call time, so monkeypatching it still exercises the real
    # ``color()`` lookup and ``_TOKENS`` values.
    dark_hex = "#8b949e"
    light_hex = "#6e7781"
    stepper = SafetyStepper()
    qtbot.addWidget(stepper)

    monkeypatch.setattr(theme, "current_scheme", lambda: "dark")
    stepper.update_state(logged_in=False, file_chosen=False, validated=False, dry_run=True)
    assert theme.color("muted") == dark_hex  # sanity: monkeypatch drives the scheme
    assert stepper._seps, "no separators collected"
    for sep in stepper._seps:
        assert dark_hex in sep.styleSheet()
        assert light_hex not in sep.styleSheet()

    monkeypatch.setattr(theme, "current_scheme", lambda: "light")
    stepper.update_state(logged_in=False, file_chosen=False, validated=False, dry_run=True)
    assert theme.color("muted") == light_hex
    for sep in stepper._seps:
        assert light_hex in sep.styleSheet()
        assert dark_hex not in sep.styleSheet()
