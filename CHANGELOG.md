# Changelog

## v1.3.2 — 2026-06-22

### Packaging

- **macOS DMG now built per-architecture** — the v1.3.1 macOS build ran on an
  Apple Silicon CI runner and produced an arm64-only app that failed to launch on
  Intel Macs ("not supported on this Mac"). Releases now ship two DMGs:
  `HSSK-Tools-*-apple-silicon.dmg` (built on `macos-14`) and
  `HSSK-Tools-*-intel.dmg` (built on `macos-13`).

## v1.3.1 — 2026-06-22

### Packaging

- **Native installers** — releases now ship a Windows per-user installer
  (`HSSK-Tools-Setup-*.exe`, no admin required, Start Menu + optional Desktop shortcut,
  uninstaller) and a macOS drag-to-Applications DMG (`HSSK-Tools-*.dmg`) instead of
  raw `.tgz` archives.

## v1.3.0 — 2026-06-22

### New features

- **Update-mode overlay (`mapping.update.yaml`)** — `hssk update` (and GUI Update mode) no longer
  requires manually editing `mapping.yaml` to uncomment a `medicalRecordId` line. On first use,
  the tool auto-seeds a small `mapping.update.yaml` file in your config directory (from a bundled
  example) and merges its `columns` on top of your base mapping. The file is user-editable — rename
  the `"Mã hồ sơ"` column header if your Excel uses a different name. Create mode is unaffected;
  create payloads keep `medicalRecordId: null`. If you already had `medicalRecordId` mapped in your
  `mapping.yaml`, the overlay becomes a no-op for that key (base-wins semantics).
- **`template --update` CLI flag** — `hssk template --update` generates an Excel template that
  already includes the "Mã hồ sơ" column, so operators get update-ready headers without any
  config editing.

### UX improvements

- **Coloured, bordered Excel template** — the generated template header row now uses amber / red /
  blue fill with contrasting text to distinguish identifier, required, and optional columns at a
  glance. Data cells have a visible grid border across 1 000 rows, and the header row is protected
  (Review → Unprotect Sheet to edit structure).
- **Per-column data validation** — the generated template enforces type-appropriate rules:
  - *Stop* / whole-number for code-int targets (`typeOfExamination`, `reasonCode`, etc.)
  - *Warning* / between for vitals (`pulse`, `bloodPressureMax`, `weight`, `height`, …) using the
    same reference ranges as the coercion engine
  - *Warning* / between for eye-acuity (0–10) and circumference (20–250 cm) columns
  - *Decimal* between for temperature
  - *Date* between (2000–2100) for examination date; a cross-field custom formula warns when finish
    date precedes start date
- **Colour legend** in the guide sheet labels the three header-colour categories with live swatches.
- **Updated in-app guide** (both VI + EN) — describes the new `mapping.update.yaml` overlay flow
  instead of the old "uncomment a line" instruction.

### Internal

- **Application icons refreshed** — higher-resolution `.icns` / `.ico` assets and full macOS
  iconset (16 × 16 → 512 × 512 @2x).

---

## v1.2.1 — 2026-06-22

### Internal

- **Engine de-duplication** — `ApiClient.get`/`post` now share a single `_request` method,
  eliminating the duplicate ~40-line retry/backoff/circuit-breaker ladder. Public API unchanged.
- **Runner de-duplication** — `run()` and `run_update()` now delegate their shared skeleton
  (loop, coercion, dry-run write, send/abort error ladder, reporting) to a private `_run_batch`
  helper, removing ~190 lines of near-identical code. Public signatures unchanged.
- **GUI god-object split** — `MainWindow` (941 → 691 lines) extracted into two focused modules:
  `hssk_gui/messages.py` (pure i18n formatters, independently testable) and
  `hssk_gui/results_panel.py` (`ResultsPanel(QGroupBox)` owning progress, log, table, counters,
  and Open buttons). Thread/worker lifecycle left untouched.

---

## v1.2.0 — 2026-06-21

### New features
- **Complete bilingual UI (Vietnamese / English)** — every user-facing string is now translated,
  not just static labels. The Results table translates all 10 `Status` values and engine-authored
  Message text in both the run and validate paths (coercion-error prefixes, bare and compound
  errors, the four coerce patterns — missing required column, unparseable cell, out-of-range value,
  finishDate-before-startDate). Raw API/exception text passes through untranslated. The previously
  hardcoded "Mapping uses unknown API field target(s)" error now routes through `tr()`.
- **In-app User Guide** — a bilingual (VI + EN) operator guide reachable from
  **Help → User Guide / Hướng dẫn sử dụng**, rendered in the active UI language. It covers the full
  workflow (login → template → fill Excel → validate → dry-run → push → read results → re-run
  safely), plus Create/Update modes, Preferences, mapping, troubleshooting, and files/privacy. The
  end-user docs previously lived only in the developer README, outside the app.

### UX improvements
- **Drag-and-drop** an Excel file onto the window (idle state only) instead of always using the
  file picker.
- **Window geometry persisted** across restarts via `QSettings`.
- **Start button tooltip** explains why it is disabled (need login / need file / busy).
- **Smarter live-push confirmation** — the prompt now distinguishes a file that was never validated
  ("not validated yet") from one validated with errors ("found N invalid rows"); previously both
  showed the same misleading text.
- **Run summary inline** — the run-complete summary is written to the log pane instead of a blocking
  `QMessageBox`.
- **Token countdown** renders every second from cached `TokenData` (no per-tick disk I/O); low-token
  (<5 min) and expired events are logged once.
- **Validate button** re-enables after a validate run finishes.

### Fixes & robustness
- **Batch-safety hardening** (audit of the run/coerce paths):
  - The runner now catches `ApiError` raised during patient **search**; a non-401 4xx previously
    escaped the resolve `try/except` and aborted the whole run, breaking the "one bad row never
    kills the batch" invariant. The row is now recorded as FAILED and the loop continues.
  - `coerce` rejects non-finite numbers (`inf`/`nan`, e.g. `"1e400"`) as clean per-cell errors
    instead of letting `OverflowError` escape.
  - The CLI aborts cleanly when stdin is non-interactive — the PRODUCTION confirmation prompt no
    longer raises an uncaught `EOFError` on piped/closed stdin and never falls through to a live run.
  - The ledger escapes the `|` key separator so values containing `|` can't collide across the
    id/date boundary (backward-compatible — ordinary data yields a byte-identical key), and
    flush + fsync each append so a created row's dedup entry is durable before proceeding.
- Stopping a validation pass early no longer marks the file as validated. A cancelled pass reports
  partial counts and leaves the file unvalidated, so the "not validated yet" nudge stays honest; a
  re-check also clears any stale verdict at the start.

---

## v1.1.1 — 2026-06-20

### Fixes
- **Login loop fixed** — with a persistent browser profile, an expired JWT left in `localStorage`
  from a previous session was captured immediately at login, causing the browser to close in under
  a second and the same expired token to be saved in a loop. Both token-capture paths now validate
  the `exp` claim before accepting a token; the browser stays open until a genuine fresh login
  provides a valid one. A still-valid remembered session is still captured instantly.
- **Bundle size 929 MB → 573 MB** — the build spec previously copied every `chromium-*` directory
  found in the Playwright cache, including stale revisions left by older Playwright installs. It
  now reads the pinned revision from the bundled Playwright's own `browsers.json` and copies only
  that exact directory.
- **CI `--no-shell` flag order** — corrected `playwright install --no-shell chromium` (flag must
  precede the positional browser name); the previous order silently ignored the flag and downloaded
  the headless shell unnecessarily.

---

## v1.1.0 — 2026-06-18

### New features
- **Vietnamese UI** — the GUI launches in Vietnamese (Tiếng Việt) by default, the native language
  of clinic-staff operators. A language selector in Preferences lets users switch to English; the
  change takes effect on the next launch. Legal dialogs (Terms, Privacy, Security) also ship full
  Vietnamese translations.
- **Validate tab overhaul** — validation results now populate the Results table instead of a
  blocking `QMessageBox`, so there is no 200-line truncation and errors are scannable row-by-row.
  Only problem rows (errors or warnings) appear; PatientId / RecordId columns are hidden during
  validation and restored when a run starts. Validation now runs on a `QThread` (same lifecycle as
  the run worker) so the UI stays responsive, the progress bar fills row-by-row with a live ETA,
  and Stop cancels mid-way. Mapping-target validation (`builder.validate_targets`) runs upfront —
  broken mappings are caught before any row is touched.

---

## v1.0.0 — 2026-06-18

First public release.

### New features
- **Excel template generator** — `hssk template` CLI command and GUI button produce a pre-formatted
  `.xlsx` file that operators fill in and feed back to the tool.
- **Login user & facility capture** — after a successful Playwright login the tool retrieves and
  persists the operator's user profile and facility ID, which are injected into subsequent API
  payloads automatically.
- **Preferences dialog** — operators can adjust request delay, max retries, and other engine
  settings from inside the GUI without touching environment variables.

### Fixes & robustness
- Playwright Chromium was silently missing from the packaged macOS `.app`; the build spec now
  copies the browser into the bundle after PyInstaller's codesign step to preserve symlinks.
- Engine robustness: full-jitter backoff, circuit breaker, and cleaner run-feedback in the GUI
  status bar.
- CI gates: ruff, mypy, and pytest all gate the build; lint runs on Ubuntu before the platform
  build matrix starts.

### Tests
Broad new coverage: ledger, `patients.resolve`, report generation, HTTP retry logic, config,
token store, Excel template, and CLI integration tests.

---

### Installing an unsigned build

The Windows `.exe` and macOS `.app` in the release assets are **not code-signed**.

**macOS** — right-click the `.app` → Open, then click Open in the dialog. Or from a terminal:
```sh
xattr -dr com.apple.quarantine "HSSK Tools.app"
```

**Windows** — when SmartScreen appears, click "More info" → "Run anyway".
