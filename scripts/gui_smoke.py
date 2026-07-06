"""Offscreen GUI smoke test — instantiate the real MainWindow and exercise its chrome.

Not collected by pytest (no Qt on CI needed) and not packaged; run it by hand after GUI work:

    .venv/bin/python scripts/gui_smoke.py

Renders screenshots to $HSSK_SMOKE_OUT (default: CWD) for eyeballing: idle + busy (light), a
dark-mode pass (monkeypatching theme.current_scheme — the palette and app_qss() modern design
system are both built from that one function, so this is a faithful offline stand-in for a real
OS dark-mode switch), and PreferencesDialog + LegalDialog. The script patches the update check
and recent-files persistence to no-ops so it never touches the network or the user's QSettings
beyond what a normal launch reads.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QHeaderView  # noqa: E402

from hssk.events import MessageCode, Msg  # noqa: E402
from hssk.pipeline.results import RowOutcome, Status  # noqa: E402
from hssk_gui import theme  # noqa: E402
from hssk_gui.i18n import set_language  # noqa: E402
from hssk_gui.main_window import MainWindow  # noqa: E402
from hssk_gui.results_panel import _StatusPillDelegate  # noqa: E402
from hssk_gui.settings import UiSettings  # noqa: E402
from hssk_gui.workers import ValidationProblem, ValidationSummary  # noqa: E402

OUT = os.environ.get("HSSK_SMOKE_OUT", ".")

FAKE_ROWS = [
    RowOutcome(
        2,
        "2700020596A",
        Status.CREATED,
        372954970,
        555,
        msgs=[Msg(MessageCode.ROW_CREATED, {"who": "Nguyễn Thị Hoa"})],
    ),
    RowOutcome(
        3,
        "0123456789",
        Status.SKIPPED_ALREADY,
        None,
        444,
        msgs=[Msg(MessageCode.ROW_ALREADY_PROCESSED)],
    ),
    RowOutcome(
        4,
        "2700099999B",
        Status.NO_PATIENT,
        msgs=[Msg(MessageCode.ROW_NO_PATIENT, {"query": "'2700099999B'"})],
    ),
    RowOutcome(
        5,
        "0987654321",
        Status.FAILED,
        msgs=[Msg(MessageCode.PASSTHROUGH, detail="HTTP 400: bad request — server said no")],
    ),
    RowOutcome(
        6,
        "2711122233C",
        Status.DRY_RUN_OK,
        msgs=[Msg(MessageCode.ROW_DRY_RUN, {"who": "Trần V. B"})],
    ),
    RowOutcome(
        7,
        "0333444555",
        Status.MULTI_MATCH,
        msgs=[Msg(MessageCode.ROW_MULTI_MATCH, {"count": 3, "query": "'0333444555'"})],
    ),
]


def main() -> int:
    # In-memory only: no network thread on startup, no recent-files writes.
    MainWindow._start_update_check = lambda self: None  # type: ignore[method-assign]
    UiSettings.add_recent_file = lambda self, path: None  # type: ignore[method-assign]
    real_current_scheme = theme.current_scheme  # captured before the dark-mode monkeypatch below

    app = QApplication([])
    theme.apply_app_theme(app)
    w = MainWindow()
    w.resize(960, 720)
    w.show()
    for _ in range(5):
        app.processEvents()

    t = w.results.table

    # --- idle look -------------------------------------------------------------------
    assert not t.verticalHeader().isVisible(), "built-in row numbers must be hidden"
    assert t.alternatingRowColors(), "zebra striping must be on"
    assert isinstance(t.itemDelegateForColumn(2), _StatusPillDelegate), "pill delegate missing"
    header = t.horizontalHeader()
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.ResizeToContents
    assert not w.results.progress.isTextVisible(), "idle progress must hide its % text"
    assert w.results.counter_label.text() == "", "idle counter must be empty (no stray dash)"
    w.grab().save(f"{OUT}/smoke_idle.png")

    # --- banners -----------------------------------------------------------------------
    w.error_banner.show_message("Lỗi mapping: unknown API field target(s): ['fooBar']")
    assert w.error_banner.isVisible()
    w._on_update_check_finished(("v99.0.0", "https://example.com/rel"))
    assert w.update_banner.isVisible()
    w._on_update_check_finished(None)  # silent no-op path

    # --- populated results ---------------------------------------------------------------
    w.dryrun_check.setChecked(False)  # production banner + red button in the capture
    w.results.reset()
    for outcome in FAKE_ROWS:
        w.results.add_row(outcome)
    w.results.flush_now()  # rows are buffered + flushed on a timer; force it for the sync asserts
    w.results.set_progress(6, 120)
    assert w.results.progress.isTextVisible(), "running progress must show its % text"
    counter = w.results.counter_label.text()
    assert "thành công" in counter and "✓" not in counter, f"counter not labeled: {counter}"
    assert t.rowCount() == len(FAKE_ROWS)
    for r in range(t.rowCount()):
        item = t.item(r, 5)
        assert item is not None and item.toolTip() == item.text(), "message tooltip missing"

    # numeric sort still holds (empty-item DisplayRole trick)
    t.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    order = [t.item(r, 0).text() for r in range(3)]
    assert order == ["7", "6", "5"], f"numeric sort broken: {order}"

    # insert while custom-sorted: no scattered cells, hidden flags recomputed
    w.results.add_row(
        RowOutcome(9, "E5", Status.CREATED, msgs=[Msg(MessageCode.ROW_CREATED, {"who": "X"})])
    )
    w.results.flush_now()
    assert [t.item(r, 0).text() for r in range(2)] == ["9", "7"]
    assert all(t.item(r, c) is not None for r in range(t.rowCount()) for c in range(6))

    # status dropdown filter (userData holds status.value)
    combo = w.results.status_combo
    idx = next(i for i in range(combo.count()) if combo.itemData(i) == Status.FAILED.value)
    combo.setCurrentIndex(idx)
    visible = [r for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert len(visible) == 1 and t.item(visible[0], 1).text() == "0987654321"
    combo.setCurrentIndex(0)
    t.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    # copy path still yields the status TEXT (delegate paints, items keep text)
    assert "Thất bại" in w.results._row_tsv(3) or "Failed" in w.results._row_tsv(3)

    for _ in range(5):
        app.processEvents()
    w.grab().save(f"{OUT}/smoke_busy.png")

    # --- validation mode: the status filter works on invalid-vs-warning kinds ------------
    w.results.reset(for_validation=True)
    assert combo.isEnabled() and combo.count() == 3, "validation filter must be usable"
    w.results.add_validation_row(
        ValidationProblem(
            2, "A1", errors=[Msg(MessageCode.COERCE_MISSING_REQUIRED, {"col": "'X'"})], warnings=[]
        )
    )
    w.results.add_validation_row(
        ValidationProblem(
            3,
            "B2",
            errors=[],
            warnings=[
                Msg(
                    MessageCode.COERCE_RANGE, {"target": "pulse", "value": 200, "lo": 30, "hi": 220}
                )
            ],
        )
    )
    w.results.flush_now()
    combo.setCurrentIndex(1)  # invalid
    visible = [r for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert len(visible) == 1 and t.item(visible[0], 1).text() == "A1"
    combo.setCurrentIndex(2)  # warning
    visible = [r for r in range(t.rowCount()) if not t.isRowHidden(r)]
    assert len(visible) == 1 and t.item(visible[0], 1).text() == "B2"
    combo.setCurrentIndex(0)

    # end of validation: counter carries the tally, status label only the phase + total
    w._on_validate_finished(ValidationSummary(valid=2, invalid=373, warns=0, total=375))
    counter = w.results.counter_label.text()
    assert "2 hợp lệ" in counter and "cảnh báo" not in counter, f"bad counter: {counter}"
    status_text = w.results.status_label.text()
    assert "hợp lệ" not in status_text and "375" in status_text, f"dup tally: {status_text}"

    # a run reset restores the full status vocabulary
    w.results.reset()
    assert combo.count() == len(Status) + 1

    # --- live language switch + theme refresh hooks --------------------------------------
    set_language("en")
    w.retranslate()
    assert w.results.status_combo.itemText(0) == "All statuses"
    set_language("vi")
    w.retranslate()
    w.on_theme_changed()  # must not raise; re-applies splitter QSS, counter, viewport

    # --- dialogs (built fresh each time from Help/Settings, so a plain construction + show
    # is representative — .exec() would block waiting for input) ---------------------------
    from hssk_gui.legal_dialog import LegalDialog
    from hssk_gui.preferences_dialog import PreferencesDialog

    prefs = PreferencesDialog(w)
    prefs.show()
    for _ in range(3):
        app.processEvents()
    prefs.grab().save(f"{OUT}/smoke_preferences.png")
    prefs.close()

    legal = LegalDialog(w)
    legal.show()
    for _ in range(3):
        app.processEvents()
    legal.grab().save(f"{OUT}/smoke_legal.png")
    legal.close()

    # --- dark mode: current_scheme drives both the palette and app_qss(), so monkeypatching
    # it here is a faithful offline stand-in for a real OS Light/Dark switch -----------------
    theme.current_scheme = lambda: "dark"  # type: ignore[method-assign]
    theme.apply_app_theme(app, on_change=w.on_theme_changed)
    w.on_theme_changed()
    for _ in range(3):
        app.processEvents()
    w.grab().save(f"{OUT}/smoke_dark.png")
    theme.current_scheme = real_current_scheme  # restore before closing

    def finish() -> None:
        ok = w.close()
        print("SMOKE OK" if ok else "SMOKE FAIL: close refused")
        app.quit()
        if not ok:
            sys.exit(1)

    QTimer.singleShot(500, finish)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
