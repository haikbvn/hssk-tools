"""The Results group box: progress, status/counter, filter, log pane, the per-row table, buttons.

A self-contained view widget. ``MainWindow`` owns the threads and run orchestration and pushes
outcomes here via the small method API (``reset`` / ``set_progress`` / ``add_row`` / ``append_log``
/ ``set_status`` / ``set_counter`` / ``record_run``). The panel keeps no engine logic — only display
state (row counts, the last run directory for the Open buttons).
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from hssk.pipeline.results import RowOutcome, Status

from . import theme
from .i18n import tr
from .render import render_all, render_status, render_validation_row
from .workers import ValidationProblem

try:  # accessibility announcements (Qt 6.8+); degrade gracefully if unavailable
    from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent

    _ANNOUNCE_OK = True
except ImportError:  # pragma: no cover - depends on Qt build
    _ANNOUNCE_OK = False

# Run statuses that count as "problems" for the problems-only filter (success/skip are hidden).
_PROBLEM_STATUSES = frozenset(
    {
        Status.INVALID,
        Status.NO_PATIENT,
        Status.MULTI_MATCH,
        Status.FAILED,
        Status.AUTH_EXPIRED,
        Status.RATE_LIMITED,
        Status.PENDING_VERIFY,
    }
)

# Qt item-data roles for our own bookkeeping on each row.
# _ROLE_TOKEN: theme token for the status cell, so rows re-colour on a Light/Dark switch.
# _ROLE_PROBLEM: bool, whether the row is a "problem" (for the problems-only filter).
# _ROLE_STATUS: the raw Status enum on the status cell (for the status dropdown filter).
_ROLE_TOKEN = Qt.ItemDataRole.UserRole
_ROLE_PROBLEM = Qt.ItemDataRole.UserRole + 1
_ROLE_STATUS = Qt.ItemDataRole.UserRole + 2

# Pseudo status keys for validation rows (deliberately NOT Status values) so the status
# dropdown can filter invalid-vs-warning findings during validation too.
_VAL_KIND_INVALID = "VAL_INVALID"
_VAL_KIND_WARNING = "VAL_WARNING"

_TABLE_COL_KEYS = [
    "col_row",
    "col_identifier",
    "col_status",
    "col_patient_id",
    "col_record_id",
    "col_message",
]

# Rows can arrive far faster than 0.2 s apart (validation passes, ledger-skipped rows,
# coercion-invalid rows), so incoming rows are buffered and inserted in one batch per tick
# instead of doing O(rows) work per row. The filter is debounced so typing at 10k rows
# doesn't rescan the table on every keystroke.
_FLUSH_INTERVAL_MS = 120
_FILTER_DEBOUNCE_MS = 200
_LOG_MAX_BLOCKS = 5000  # cap the log document so long/repeated runs don't grow it unbounded

# A buffered row awaiting insertion: (cells, status token, is_problem, status filter key).
_PendingRow = tuple[list[str], "str | None", bool, "str | None"]


class _StatusPillDelegate(QStyledItemDelegate):
    """Paints the status cell as a subtle rounded pill (GitHub-label style).

    Background comes from ``pill_<token>_bg``, text from the base accent token — both resolved
    at paint time, so a Light/Dark switch only needs a viewport repaint. Cells without a
    ``_ROLE_TOKEN`` fall back to plain text.
    """

    _H_PAD = 8  # horizontal padding inside the pill
    _V_PAD = 2  # vertical padding inside the pill
    _MARGIN = 4  # pill offset from the cell's left edge

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        # Native background pass (selection / zebra / focus) with the text blanked out;
        # calling super().paint() later would double-draw the background.
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        if not text:
            return
        painter.save()
        token = index.data(_ROLE_TOKEN)
        if not token:
            painter.setPen(opt.palette.text().color())
            painter.drawText(
                opt.rect.adjusted(self._MARGIN, 0, -self._MARGIN, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            painter.restore()
            return
        fm = opt.fontMetrics
        pill_h = min(fm.height() + 2 * self._V_PAD, opt.rect.height() - 2)
        pill_w = min(
            fm.horizontalAdvance(text) + 2 * self._H_PAD,
            opt.rect.width() - 2 * self._MARGIN,
        )
        rect = QRect(
            opt.rect.left() + self._MARGIN,
            opt.rect.top() + (opt.rect.height() - pill_h) // 2,
            pill_w,
            pill_h,
        )
        radius = pill_h / 2
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.color(f"pill_{token}_bg")))
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QColor(theme.color(token)))
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            fm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - self._H_PAD),
        )
        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        s = super().sizeHint(option, index)
        return QSize(
            s.width() + 2 * (self._H_PAD + self._MARGIN),
            max(s.height(), option.fontMetrics.height() + 10),
        )


class ResultsPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__(tr("group_results"))
        self._counts: dict[Status, int] = {}
        self._counter_parts: list[tuple[str, int, str]] = []  # (label, count, theme token)
        self._run_start: float = 0.0
        self._last_run_dir: Path | None = None
        self._last_results_file: Path | None = None

        # Row-streaming state: buffer incoming rows and flush them in batches (see _flush_pending).
        self._pending_rows: list[_PendingRow] = []
        self._visible_rows = 0  # live count of shown rows; replaces an O(rows)-per-insert scan
        self._counter_dirty = False  # a run row arrived since the counter was last rendered
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(_FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(_FILTER_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(self._apply_filter)

        lay = QVBoxLayout(self)

        prog_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setAccessibleName(tr("col_status"))
        # Idle look: a "0%" label on an empty bar reads like a broken input — show the
        # percentage only once a run/validation actually starts (set_progress).
        self.progress.setTextVisible(False)
        self.status_label = QLabel("")
        self.counter_label = QLabel("")
        self.counter_label.setAccessibleName(tr("col_status"))
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addWidget(self.status_label)
        prog_row.addWidget(self.counter_label)
        lay.addLayout(prog_row)

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setPlaceholderText(tr("ph_filter"))
        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.status_combo = QComboBox()
        self.status_combo.setToolTip(tr("tip_status_filter"))
        self._populate_status_combo(for_validation=False)
        self.status_combo.currentIndexChanged.connect(self._apply_filter)
        self.problems_check = QCheckBox(tr("chk_problems_only"))
        self.problems_check.stateChanged.connect(self._apply_filter)
        self.clear_log_btn = QPushButton(tr("btn_clear_log"))
        self.clear_log_btn.clicked.connect(self._clear_log)
        filter_row.addWidget(self.filter_edit, stretch=1)
        filter_row.addWidget(self.status_combo)
        filter_row.addWidget(self.problems_check)
        filter_row.addWidget(self.clear_log_btn)
        lay.addLayout(filter_row)

        # Log pane and table share a resizable splitter so operators can drag the log taller
        # to read recovery guidance after a run. Its layout persists across sessions
        # (save_splitter/restore_splitter, wired by MainWindow).
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(6)
        self._splitter.setStyleSheet(theme.splitter_qss())
        self.log_pane = QPlainTextEdit()
        self.log_pane.setReadOnly(True)
        self.log_pane.setMaximumBlockCount(_LOG_MAX_BLOCKS)  # bound growth over long runs
        self.log_pane.setPlaceholderText(tr("log_placeholder"))
        self._splitter.addWidget(self.log_pane)

        self.table = QTableWidget(0, len(_TABLE_COL_KEYS))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _TABLE_COL_KEYS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(len(_TABLE_COL_KEYS) - 1, QHeaderView.ResizeMode.Stretch)
        # Row and Status hug their content (the status column used to truncate); the pill
        # delegate's sizeHint feeds column 2 so pills are never clipped.
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        # Our first column already numbers the Excel rows — Qt's built-in row numbers next
        # to it were pure confusion. The hidden header still drives row height; +6px gives
        # the pills breathing room.
        vh = self.table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(vh.defaultSectionSize() + 6)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegateForColumn(2, _StatusPillDelegate(self.table))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setSortingEnabled(True)
        # setRowHidden is positional: a re-sort moves items but not hidden flags, so
        # visibility must be recomputed after every sort change.
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._apply_filter)
        QShortcut(QKeySequence.StandardKey.Copy, self.table, self._copy_selection)
        self._splitter.addWidget(self.table)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([80, 400])
        lay.addWidget(self._splitter, stretch=1)

        # Empty-state overlay centred over the table's viewport.
        self._empty_label = QLabel(tr("empty_results"), self.table.viewport())
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self.table.viewport().installEventFilter(self)
        self._refresh_empty_state()

        bottom = QHBoxLayout()
        self.export_btn = QPushButton(tr("btn_export_csv"))
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_csv)
        bottom.addWidget(self.export_btn)
        bottom.addStretch(1)
        self.open_results_btn = QPushButton(tr("btn_open_results"))
        self.open_results_btn.setEnabled(False)
        self.open_results_btn.clicked.connect(self._open_results)
        bottom.addWidget(self.open_results_btn)
        self.open_report_btn = QPushButton(tr("btn_open_report"))
        self.open_report_btn.setEnabled(False)
        self.open_report_btn.clicked.connect(self._open_report)
        bottom.addWidget(self.open_report_btn)
        lay.addLayout(bottom)

    # -- run/validate lifecycle ---------------------------------------------------------

    def reset(self, for_validation: bool = False) -> None:
        # Drop any rows still buffered from a previous pass before clearing the table, so a
        # late timer tick can never flush stale rows into the fresh run.
        self._flush_timer.stop()
        self._filter_timer.stop()
        self._pending_rows.clear()
        self._counter_dirty = False
        self.table.setRowCount(0)
        self._visible_rows = 0
        # Back to insertion order; a user-chosen sort from the previous run must not
        # scatter the incoming rows.
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        # Swap the filter's vocabulary to match the incoming rows (run statuses vs the two
        # validation kinds); repopulating also resets the selection to "all".
        self._populate_status_combo(for_validation)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self._counts = {}
        self._counter_parts = []
        self.counter_label.setText("")
        self.counter_label.setStyleSheet("")
        self.status_label.setText("")
        self.log_pane.clear()
        self.open_report_btn.setEnabled(False)
        self.open_results_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        # col indices: 0=row, 1=identifier, 2=status, 3=patient_id, 4=record_id, 5=message
        self.table.setColumnHidden(3, for_validation)
        self.table.setColumnHidden(4, for_validation)
        self._run_start = time.monotonic()
        self._refresh_empty_state()

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setTextVisible(True)
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        if done == 0:
            self.status_label.setText(tr("prog_starting").format(total=total))
        elif done >= total:
            self.status_label.setText(tr("prog_all_done").format(total=total))
        else:
            elapsed = time.monotonic() - self._run_start
            if elapsed > 0:
                rem = int((elapsed / done) * (total - done))
                if rem >= 60:
                    eta = tr("eta_min_sec").format(m=rem // 60, s=rem % 60)
                else:
                    eta = tr("eta_sec").format(s=rem)
                self.status_label.setText(tr("prog_row_of").format(done=done, total=total, eta=eta))
            else:
                self.status_label.setText(tr("prog_row_of_no_eta").format(done=done, total=total))

    def add_row(self, outcome: RowOutcome) -> None:
        self._counts[outcome.status] = self._counts.get(outcome.status, 0) + 1
        cells = [
            str(outcome.row_index),
            outcome.identifier or "",
            render_status(outcome.status),
            "" if outcome.patient_id is None else str(outcome.patient_id),
            "" if outcome.record_id is None else str(outcome.record_id),
            render_all(outcome.msgs),
        ]
        token = theme.STATUS_COLOR_TOKENS.get(outcome.status)
        self._counter_dirty = True  # counter is re-rendered once per flush, not per row
        self._enqueue_row(
            cells,
            token,
            is_problem=outcome.status in _PROBLEM_STATUSES,
            status_key=outcome.status.value,
        )

    def add_validation_row(self, problem: ValidationProblem) -> None:
        status_text = tr("val_status_invalid") if problem.has_errors else tr("val_status_warning")
        token = "danger" if problem.has_errors else "warning"
        cells = [
            str(problem.row_index),
            problem.identifier,
            status_text,
            "",
            "",
            render_validation_row(problem.errors, problem.warnings),
        ]
        self._enqueue_row(
            cells,
            token,
            is_problem=True,
            status_key=_VAL_KIND_INVALID if problem.has_errors else _VAL_KIND_WARNING,
        )

    def _enqueue_row(
        self,
        cells: list[str],
        token: str | None,
        *,
        is_problem: bool,
        status_key: str | None = None,
    ) -> None:
        self._pending_rows.append((cells, token, is_problem, status_key))
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def flush_now(self) -> None:
        """Insert any buffered rows immediately.

        Called by MainWindow's finish/fail handlers (so summaries reflect a complete table)
        and before reading the table for Export/Copy-all.
        """
        self._flush_timer.stop()
        self._flush_pending()

    def _flush_pending(self) -> None:
        if not self._pending_rows:
            return
        batch, self._pending_rows = self._pending_rows, []
        # Inserting while sortingEnabled scatters cells across rows — classic Qt pitfall.
        # Do the whole batch with sorting and repaints off, then restore once.
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        first = self.table.rowCount()
        try:
            self.table.setRowCount(first + len(batch))
            for offset, (cells, token, is_problem, status_key) in enumerate(batch):
                self._insert_row_items(first + offset, cells, token, is_problem, status_key)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(sorting)  # re-sorts once if a user sort is active
        if sorting and not self._is_default_sort():
            # Re-enabling sorting moved the new rows somewhere in the middle; hidden flags
            # are positional, so recompute them all. Don't fight the user's chosen sort
            # with a scroll.
            self._apply_filter()
        else:
            for r in range(first, first + len(batch)):
                if self._set_row_visible(r):
                    self._visible_rows += 1
            self.table.scrollToBottom()
            self._refresh_empty_state()
        if self._counter_dirty:
            self._counter_dirty = False
            self._update_counter_label()
        self.export_btn.setEnabled(True)

    def _insert_row_items(
        self,
        r: int,
        cells: list[str],
        token: str | None,
        is_problem: bool,
        status_key: str | None,
    ) -> None:
        items = [QTableWidgetItem(text) for text in cells]
        # An int DisplayRole makes the Row column sort numerically (text() still yields the
        # string for copy/CSV). Must start from an EMPTY item: setData(DisplayRole, 2) on an
        # item constructed with "2" is a silent no-op (QVariant('2') == QVariant(2) in Qt).
        items[0] = QTableWidgetItem()
        items[0].setData(Qt.ItemDataRole.DisplayRole, int(cells[0]))
        # Full text on hover — the message column truncates for long diagnostics.
        for c, item in enumerate(items):
            if cells[c]:
                item.setToolTip(cells[c])
        if token is not None:
            # The pill delegate paints from this token; no per-item foreground needed.
            items[2].setData(_ROLE_TOKEN, token)
        if status_key is not None:
            items[2].setData(_ROLE_STATUS, status_key)
        items[0].setData(_ROLE_PROBLEM, is_problem)
        for c, item in enumerate(items):
            self.table.setItem(r, c, item)

    def _is_default_sort(self) -> bool:
        header = self.table.horizontalHeader()
        return (
            header.sortIndicatorSection() == 0
            and header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        )

    def _update_counter_label(self) -> None:
        ok = (
            self._counts.get(Status.CREATED, 0)
            + self._counts.get(Status.UPDATED, 0)
            + self._counts.get(Status.DELETED, 0)
            + self._counts.get(Status.DRY_RUN_OK, 0)
        )
        skipped = self._counts.get(Status.SKIPPED_ALREADY, 0)
        failed = sum(
            self._counts.get(s, 0)
            for s in (
                Status.FAILED,
                Status.NO_PATIENT,
                Status.MULTI_MATCH,
                Status.INVALID,
                Status.PENDING_VERIFY,
            )
        )
        aborted = self._counts.get(Status.AUTH_EXPIRED, 0) + self._counts.get(
            Status.RATE_LIMITED, 0
        )
        self.set_counts(
            [
                (tr("counter_ok"), ok, "success"),
                (tr("counter_skipped"), skipped, "muted"),
                (tr("counter_failed"), failed, "danger"),
                (tr("counter_aborted"), aborted, "warning"),
            ]
        )

    def set_counts(self, parts: list[tuple[str, int, str]]) -> None:
        """Show labeled, colored counts. ``parts`` = (translated label, count, theme token)."""
        self._counter_parts = list(parts)
        self._render_counter()

    def _render_counter(self) -> None:
        spans = [
            f'<span style="color:{theme.color(token)}; font-weight:600;">{count} {label}</span>'
            for label, count, token in self._counter_parts
            if count
        ]
        self.counter_label.setText("&nbsp;·&nbsp;".join(spans))

    # -- filtering ----------------------------------------------------------------------

    def _populate_status_combo(self, for_validation: bool) -> None:
        """Fill the status filter for the upcoming pass (validation kinds vs run statuses).

        userData holds plain str keys (Status is a StrEnum and QVariant round-trips it as
        str anyway); item 0 is always "all" (userData None), so repopulating resets the
        selection.
        """
        combo = self.status_combo
        combo.blockSignals(True)  # clear() would fire currentIndexChanged mid-reset
        combo.clear()
        combo.addItem(tr("filter_all_statuses"), None)
        if for_validation:
            combo.addItem(tr("val_status_invalid"), _VAL_KIND_INVALID)
            combo.addItem(tr("val_status_warning"), _VAL_KIND_WARNING)
        else:
            for status in Status:
                combo.addItem(render_status(status), status.value)
        combo.blockSignals(False)

    def _row_matches(self, r: int) -> bool:
        if self.problems_check.isChecked():
            first = self.table.item(r, 0)
            if first is None or not first.data(_ROLE_PROBLEM):
                return False
        wanted = self.status_combo.currentData()
        if wanted is not None:
            status_item = self.table.item(r, 2)
            if status_item is None or status_item.data(_ROLE_STATUS) != wanted:
                return False
        needle = self.filter_edit.text().strip().lower()
        if not needle:
            return True
        for c in range(self.table.columnCount()):
            if self.table.isColumnHidden(c):
                continue
            item = self.table.item(r, c)
            if item is not None and needle in item.text().lower():
                return True
        return False

    def _on_filter_text_changed(self, _text: str) -> None:
        # Debounce: restart the timer on each keystroke so a full-table rescan runs once the
        # user pauses, not on every character (which is O(rows·cols) at 10k rows).
        self._filter_timer.start()

    def _set_row_visible(self, r: int) -> bool:
        visible = self._row_matches(r)
        self.table.setRowHidden(r, not visible)
        return visible

    def _apply_filter(self) -> None:
        self._visible_rows = sum(
            1 for r in range(self.table.rowCount()) if self._set_row_visible(r)
        )
        self._refresh_empty_state()

    # -- empty-state overlay ------------------------------------------------------------

    def _refresh_empty_state(self) -> None:
        self._empty_label.setGeometry(self.table.viewport().rect())
        self._empty_label.setVisible(self._visible_rows == 0)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.table.viewport() and event.type() == QEvent.Type.Resize:
            self._empty_label.setGeometry(self.table.viewport().rect())
        return super().eventFilter(obj, event)

    # -- copy / context menu ------------------------------------------------------------

    def _visible_cols(self) -> list[int]:
        return [c for c in range(self.table.columnCount()) if not self.table.isColumnHidden(c)]

    def _cell_text(self, r: int, c: int) -> str:
        item = self.table.item(r, c)
        return item.text() if item is not None else ""

    def _header_text(self, c: int) -> str:
        item = self.table.horizontalHeaderItem(c)
        return item.text() if item is not None else ""

    def _row_tsv(self, r: int) -> str:
        return "\t".join(self._cell_text(r, c) for c in self._visible_cols())

    def _copy_selection(self) -> None:
        rows = sorted({it.row() for it in self.table.selectedItems()})
        if rows:
            QApplication.clipboard().setText("\n".join(self._row_tsv(r) for r in rows))

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.table.itemAt(pos)
        menu = QMenu(self)
        act_cell = menu.addAction(tr("ctx_copy_cell"))
        act_row = menu.addAction(tr("ctx_copy_row"))
        act_all = menu.addAction(tr("ctx_copy_all"))
        if item is None:
            act_cell.setEnabled(False)
            act_row.setEnabled(False)
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_cell and item is not None:
            QApplication.clipboard().setText(item.text())
        elif chosen is act_row and item is not None:
            QApplication.clipboard().setText(self._row_tsv(item.row()))
        elif chosen is act_all:
            QApplication.clipboard().setText(self._all_visible_tsv())

    def _all_visible_tsv(self) -> str:
        self.flush_now()  # include any buffered rows in a mid-stream Copy-all
        cols = self._visible_cols()
        lines = ["\t".join(self._header_text(c) for c in cols)]
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                lines.append(self._row_tsv(r))
        return "\n".join(lines)

    # -- CSV export ---------------------------------------------------------------------

    def _export_csv(self) -> None:
        self.flush_now()  # include any buffered rows in a mid-stream export
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_export_csv_title"), "results.csv", tr("filter_csv")
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        cols = self._visible_cols()
        # utf-8-sig so Excel opens Vietnamese diacritics correctly.
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow([self._header_text(c) for c in cols])
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    writer.writerow([self._cell_text(r, c) for c in cols])

    # -- small setters used by MainWindow's finished/failed handlers --------------------

    def append_log(self, message: str) -> None:
        self.log_pane.appendPlainText(message)

    def _clear_log(self) -> None:
        self.log_pane.clear()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self._announce(text)

    def set_counter(self, text: str, color: str = "") -> None:
        self.counter_label.setText(text)
        self.counter_label.setStyleSheet(color)

    def _announce(self, text: str) -> None:
        if _ANNOUNCE_OK and text:
            QAccessible.updateAccessibility(QAccessibleAnnouncementEvent(self.status_label, text))

    def record_run(self, run_dir: Path) -> None:
        """Remember a finished run's output dir and enable the Open buttons."""
        self._last_run_dir = run_dir
        self._last_results_file = run_dir / "results.xlsx"
        self.open_report_btn.setEnabled(True)
        self.open_results_btn.setEnabled(self._last_results_file.exists())

    # -- splitter persistence (wired by MainWindow next to window geometry) --------------

    def save_splitter(self) -> QByteArray:
        return self._splitter.saveState()

    def restore_splitter(self, state: QByteArray) -> None:
        if not state.isEmpty():
            self._splitter.restoreState(state)

    # -- live re-translation / theming --------------------------------------------------

    def retranslate(self) -> None:
        self.setTitle(tr("group_results"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _TABLE_COL_KEYS])
        self.filter_edit.setPlaceholderText(tr("ph_filter"))
        # Rewrite combo item texts in place so the current selection index is preserved.
        self.status_combo.setItemText(0, tr("filter_all_statuses"))
        for i in range(1, self.status_combo.count()):
            value = self.status_combo.itemData(i)
            if value == _VAL_KIND_INVALID:
                self.status_combo.setItemText(i, tr("val_status_invalid"))
            elif value == _VAL_KIND_WARNING:
                self.status_combo.setItemText(i, tr("val_status_warning"))
            elif value is not None:
                self.status_combo.setItemText(i, render_status(Status(value)))
        self.status_combo.setToolTip(tr("tip_status_filter"))
        self.clear_log_btn.setText(tr("btn_clear_log"))
        self.problems_check.setText(tr("chk_problems_only"))
        self.log_pane.setPlaceholderText(tr("log_placeholder"))
        self._empty_label.setText(tr("empty_results"))
        self.export_btn.setText(tr("btn_export_csv"))
        self.open_results_btn.setText(tr("btn_open_results"))
        self.open_report_btn.setText(tr("btn_open_report"))

    def on_theme_changed(self) -> None:
        """Re-colour themed chrome after a Light/Dark switch."""
        self._splitter.setStyleSheet(theme.splitter_qss())
        self._render_counter()  # colored spans embed resolved token colors
        self.table.viewport().update()  # the pill delegate resolves colors at paint time

    # -- Open buttons -------------------------------------------------------------------

    def _open_results(self) -> None:
        if self._last_results_file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_results_file)))

    def _open_report(self) -> None:
        if self._last_run_dir is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_run_dir)))
