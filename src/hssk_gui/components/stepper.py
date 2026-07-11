"""The safety-ladder stepper: Login → File → Validated → Dry-run/Commit, always visible.

A read-only progress indicator, not a gate — it makes the batch's existing safety invariants
(you need a token and a file before Start does anything useful; validating first is strongly
recommended before a live push) *visible* instead of only surfacing as a disabled-button tooltip
or a warning inside the confirm dialog. It never changes what MainWindow allows; it just reflects
the same state MainWindow already tracks (``_token``, ``_excel_path``, ``_validated_path``,
the dry-run checkbox).
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import theme
from ..i18n import tr


class _Step(QWidget):
    """One pill: a status glyph + label, coloured by whether the step is complete."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACING["xs"])
        self._glyph = QLabel()
        self._text = QLabel()
        lay.addWidget(self._glyph)
        lay.addWidget(self._text)

    def set_state(self, label: str, *, done: bool) -> None:
        self._text.setText(label)
        self._glyph.setText("✓" if done else "○")
        token = "success" if done else "muted"
        style = f"color: {theme.color(token)};"
        self._glyph.setStyleSheet(style + " font-weight: bold;")
        self._text.setStyleSheet(style)


class SafetyStepper(QWidget):
    """Four-step strip: Login, File, Validated, and the current run mode (dry-run/commit)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(theme.SPACING["md"])
        self._login = _Step()
        self._file = _Step()
        self._validated = _Step()
        self._mode = _Step()
        self._seps: list[QLabel] = []
        for i, step in enumerate((self._login, self._file, self._validated, self._mode)):
            if i > 0:
                sep = QLabel("→")
                self._seps.append(sep)
                lay.addWidget(sep)
            lay.addWidget(step)
        lay.addStretch(1)
        # MainWindow calls update_state() once during construction (via _update_start_enabled);
        # this initial paint only covers the instant before that.
        self.update_state(logged_in=False, file_chosen=False, validated=False, dry_run=True)

    def update_state(
        self, *, logged_in: bool, file_chosen: bool, validated: bool, dry_run: bool
    ) -> None:
        """Re-render every step from scratch — also how language/theme changes propagate here,
        since MainWindow re-invokes this (via _refresh_run_controls/_update_start_enabled) on
        both retranslate() and on_theme_changed()."""
        self._login.set_state(tr("step_login"), done=logged_in)
        self._file.set_state(tr("step_file"), done=file_chosen)
        self._validated.set_state(tr("step_validated"), done=validated)
        self._mode.set_state(tr("step_dryrun") if dry_run else tr("step_commit"), done=not dry_run)
        sep_style = f"color: {theme.color('muted')};"
        for sep in self._seps:
            sep.setStyleSheet(sep_style)
