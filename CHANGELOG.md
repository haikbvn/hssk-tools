# Changelog

## v1.18.0 — 2026-07-17

### HSSK Tools now requires a purchased license

- The app is now a paid product: a valid [Polar](https://polar.sh) license key is required to use
  it at all, both the GUI and the CLI. A new **License** dialog (shown automatically on first
  launch, and any time from Help → License…) lets you paste a key or open the Polar checkout page;
  the CLI equivalent is `hssk license --set <KEY>` (install) and `hssk license` (check status).
- Licensing is checked online, with a local cache: once validated, a normal launch is instant and
  works fully offline, and the app tolerates up to **14 days** without reaching the license server
  before it needs to reconnect. A revoked or expired license is enforced immediately once the app
  is back online — the offline grace period only covers connectivity gaps, never an actual denial.
- No international card? Email **haikbvn@gmail.com** for a MoMo/bank-transfer checkout code — you
  still get a normal Polar checkout link and a regular license key.
- **Note for existing installs**: upgrading to this version will require entering a license key
  before the app opens again.
- The Terms of Use tab now explains what a purchase means: Polar is merchant of record, refunds
  are discretionary and handled by Polar (typically within 60 days), and the app will stop working
  — including Dry-run — if your license is refunded, revoked, or expires.

## v1.17.0 — 2026-07-10

### Old reports can now be cleaned up automatically (opt-in)

- New Preferences option: **"Delete reports older than the retention window on launch"** — off by
  default. Report folders hold patient data, and until now the only way to clear out old ones was
  the manual File → "Purge old reports…" action. Turning this on deletes reports older than your
  retention window (90 days by default) every time you start the app, so they don't pile up.
- Turning it on shows a one-time confirmation explaining that this permanently deletes old reports
  and can't be undone. After that, each launch that actually removes something shows a quick
  "Removed N old report folder(s)" notice — otherwise it's silent.
- The manual "Purge old reports…" action is unchanged and still available regardless of this
  setting.

## v1.16.0 — 2026-07-10

### Interrupted sends no longer risk creating a duplicate record

- If sending a new record was interrupted right after the server received it — a timeout, a crash,
  a power loss — the app had no way to tell whether it had actually gone through, and re-running
  could create a duplicate medical record. Every send is now marked *before* it's attempted; if the
  app can't confirm success, that row comes back as **"Needs verification"** instead of being
  silently resent. Check the record on the website, then re-run with `--retry-pending` (CLI) to
  send it for real once you've confirmed it wasn't created.

### One-click update install is more defensively verified

- The assisted installer download (added in v1.15.0) now refuses to offer an install when the
  release has no checksum to verify against, and only ever downloads from GitHub's own hosts —
  closing a couple of defense-in-depth gaps in that new path. The release-publishing CI job is also
  pinned to a specific, verified commit rather than a movable tag.

### Smaller fixes

- The browser login profile (which holds your active session) is now access-restricted the same
  way your saved login token already was.
- The "finish time is before start time" check no longer silently skips validation if you've
  customized the date/time format in your mapping file — it used to just not fire.
- Cleaned up the CLI's internals (the create/update/delete commands shared almost all their code)
  and added test coverage for the one-click updater's install step and for keeping the Vietnamese
  and English translations in sync — no visible change, just fewer places for a future bug to hide.

## v1.15.0 — 2026-07-09

### Update notifications now offer one-click install

- When a new version is available, the banner now offers a **Download & Install** button instead
  of just a link to the GitHub releases page. Click it and the app downloads the right installer
  for your computer (Windows, Apple Silicon Mac, or Intel Mac) in the background with a progress
  bar, checks that the download is intact, then opens it for you to confirm — on Windows the
  installer launches and the app closes to finish updating; on macOS the disk image opens so you
  can drag the app into Applications.
- If a release doesn't have a matching installer, or the download fails, the banner falls back to
  a plain "open in browser" link like before — nothing changes if you'd rather download it
  yourself.
- The startup "check for new versions" setting in Preferences is unchanged: it only controls
  whether the app quietly asks about new versions, never whether anything downloads or installs
  without your click.

## v1.14.0 — 2026-07-08

### Friendlier production confirmation

- The live-push confirmation no longer makes you type `YES`. In the app, confirming a real send to
  hososuckhoe.com.vn is now a single click on a plain Confirm/Cancel dialog (Cancel is the default
  action, so an accidental Enter can't trigger it). In the CLI, `--commit` now asks a simple
  `Proceed? [y/N]` instead of requiring the typed word.
- Everything else about the safety flow is unchanged: dry-run is still on by default, you still have
  to untick it, and the Start button still turns red before a live push.

## v1.13.1 — 2026-07-08

### Fix: the Intel (x86_64) macOS build couldn't open the login browser

The Intel `.dmg` shipped an **arm64** Chromium inside an x86_64 app, so login failed with
`Executable doesn't exist at …/chrome-mac-x64/…`. The Intel DMG is cross-built on an Apple-Silicon
CI runner under Rosetta; `arch -x86_64` makes PyInstaller emit an x64 app but does **not** reach
Playwright's bundled Node driver, which detected the runner's real arm64 hardware and downloaded the
wrong Chromium. The build now forces the driver's host platform (`PLAYWRIGHT_HOST_PLATFORM_OVERRIDE`)
for the Intel job and adds a CI check that fails the build on any app/Chromium arch mismatch. Apple
Silicon and Windows builds were unaffected.

## v1.13.0 — 2026-07-07

### Your login token now lives in the OS keychain

- The saved login token moves from a file into the **operating-system keychain** (macOS Keychain,
  Windows Credential Manager, Linux Secret Service). If the keychain isn't available for any reason,
  the app **silently falls back** to the previous protected file, so logging in never breaks. An
  existing token file is migrated into the keychain automatically the first time it's read.
- Nothing else changes for you: log in as before. Exported support bundles still never include your
  token.

_Internal:_ the roadmap's plan to drop the ~130 MB bundled Chromium by switching login to the OS's
native webview (pywebview) was **spiked and rejected** — on macOS, the system WebView can't load the
site's WAF-protected single-sign-on login page. Playwright/Chromium stays; only the keychain change
shipped from that phase.

## v1.12.0 — 2026-07-07

### Typed payload gate + API-drift warnings

- **Malformed payloads are caught before sending.** The create/update body is now checked against a
  strict field schema right before it would go out: any field the templates don't define — most
  often a typo in your `mapping.yaml` `defaults` block, which nothing previously validated — turns
  that row into a clean `INVALID` (with the offending field named), in dry-run and for real, instead
  of a silent bad record on the server. Valid rows are unchanged: the check only inspects, it never
  rewrites the payload, so what's sent is byte-for-byte what was sent before.
- **A heads-up when the website's API may have changed.** The app has always guessed defensively at
  the site's undocumented response shapes. Those guesses now live in one place and raise a one-time
  "server response not recognised — dry-run and check before committing" banner when a search or
  record-detail response doesn't look like anything expected — so an upstream change surfaces as a
  visible warning instead of mysterious "no patient found" rows. A normal empty result is never
  mistaken for drift.

## v1.11.0 — 2026-07-07

### PII hygiene & a one-click support bundle

- **Rotating, redacted log.** The app now keeps a small rotating diagnostic log at
  `<data-dir>/logs/hssk.log` so a field problem leaves a trace instead of vanishing. Bearer tokens
  and JWT-shaped strings are scrubbed from every line, and only the app's own messages are recorded
  at debug level — third-party libraries stay quiet, so patient data in request bodies never reaches
  the file.
- **Purge old reports.** File → "Purge old reports…" deletes run-report folders (which hold patient
  data) older than the retention window — default 90 days, set via `HSSK_OUTPUT_RETENTION_DAYS`.
  It always asks first and shows how many folders will go; **nothing is ever deleted automatically**.
- **Export support bundle.** Help → "Export support bundle…" saves a local zip with the redacted
  logs, your mapping files, and a versions/settings snapshot — enough to diagnose an issue without
  ever including your saved login token. The latest run's event log (which can contain patient
  identifiers) is added only if you tick the opt-in checkbox. Nothing is uploaded anywhere.

## v1.10.0 — 2026-07-07

### Internal — one hardened home for the GUI thread lifecycle

- The four background jobs (login, update-check, validate, run) each hand-repeated the same
  ~11-line `QThread` + worker teardown — the exact sequence whose mishandling once aborted the whole
  process (SIGABRT, commit 5ea2803). That lifecycle now lives once in `hssk_gui/worker_thread.py`
  (`WorkerHandle` + `run_in_thread`); `main_window.py` holds one handle per job instead of eight
  raw thread/worker fields.
- Fixes a latent teardown race in the process: the old wiring deleted each finished worker/thread
  by two competing paths at once (Qt's `deleteLater` **and** dropping the Python reference in the
  same handler), which could intermittently crash under fast start/stop cycling. `WorkerHandle`
  uses a single deletion path, so a stopped thread is never freed twice.
- New `tests/test_gui_threads.py` (pytest-qt) locks the behavior down: start→finish, Stop→cancel,
  and close-while-running for all four jobs, asserting the window shuts down cleanly rather than
  hanging or crashing.

## v1.9.0 — 2026-07-06

### Safety stepper + type-to-confirm production push

- New **safety-ladder strip** at the top of the window: Login → File → Validated → Dry-run/Commit,
  each step checked off as it completes. Purely a status display — it doesn't change what Start
  allows — but the batch's safety prerequisites are now visible at a glance instead of only showing
  up as a disabled-button tooltip.
- The PRODUCTION push confirmation is now a custom **type-to-confirm** dialog (type `YES`, mirroring
  the CLI's `--commit` prompt) instead of a plain Yes/No message box — a more deliberate, harder to
  mis-click confirmation for the one action that sends live data.
- The app keeps each OS's native widget style (Windows renders windows11, macOS renders Aqua) and
  native fonts; a cross-platform-identical look (a pinned Fusion style, a bundled font, and a custom
  design system) was built and evaluated but not kept — native look-and-feel per OS was the final
  call.

## v1.8.0 — 2026-07-06

### Internal — typed events across the engine↔GUI boundary

- The engine no longer authors human-readable English strings for row results and log lines.
  It emits stable typed events (`hssk.events.MessageCode` + params); each frontend renders the
  wording it needs. This removes a brittle, untested contract where the GUI re-parsed the engine's
  English by prefix-matching — a reworded engine message used to silently fall back to untranslated
  text in the Vietnamese UI. Adding a language (or rewording a message) no longer touches the engine.
- The CLI and the written reports keep byte-identical English (`events.render_en`), pinned by a
  golden test captured before the change. `events.jsonl` now additionally records each row's
  message `codes` + params, so reports are machine-readable without re-parsing English.
- The 221-line GUI string-parsing layer (`hssk_gui/messages.py`) is deleted, replaced by a small
  `hssk_gui/render.py`; a contract test asserts every message code renders in both languages.

No user-visible behavior change (one edge case is intentionally cleaner: an unexpected coercion
crash now shows its raw detail verbatim instead of partially re-translating arbitrary text).

## v1.7.0 — 2026-07-05

### Safety guardrails

- **Single-instance lock.** Only one push can run at a time, across both the GUI and CLI. An
  advisory OS lock is held for the whole batch, so two windows (or a window + a CLI run) can no
  longer race the dedup ledger and double-send the same row. A second GUI launch now shows a
  short "already running" notice instead of opening; a blocked CLI run exits with a clear message.
- **Responsive Stop.** Pressing Stop during a long server-requested back-off (a `Retry-After`
  wait) now aborts almost immediately, instead of appearing frozen until the wait elapsed.

### Internal

- The token clock-skew margin is now a single `HSSK_TOKEN_EXP_SKEW` setting (default 120s) rather
  than a constant repeated in several places.

## v1.6.0 — 2026-07-05

### Delete mode

- New third mode alongside Create and Update: bulk-delete existing medical records by
  `medicalRecordId` ("Mã hồ sơ"). Available as `hssk delete` (plus `validate --delete` and
  `template --delete`) and as a third entry in the GUI's mode selector.
- Fetches each record's detail first — confirming it exists and showing the patient in the
  results — before sending the delete. Dry-run by default, like every other mode; a live delete
  requires `--commit` + typed confirmation (CLI) or unticking Dry-run and confirming a
  **"PERMANENTLY DELETE"** production prompt (GUI).
- Reuses the existing `mapping.update.yaml` overlay, filtered down to just the identifier and
  "Mã hồ sơ" columns, so a minimal 2-column Excel works — a full Create/Update file with extra
  columns still loads too (unmapped columns are ignored with a warning).
- Does not use the ledger: re-running a delete on an already-removed record simply reports that
  row as failed instead of crashing the batch.

### Validation error messages

- A missing or duplicate mapped column in the Excel file used to dump a raw, untranslated wall of
  text (including every header found in the file) into the top banner. It's now condensed,
  translated (VI/EN), and shown as a single row in the results table instead — consistent with
  how every other validation problem is reported.

## v1.5.1 — 2026-07-04

### Excel template hardening

- Identifier, text, and list columns across the whole 1000-row data region are now formatted as
  Text, so Excel no longer strips leading zeros from CCCD numbers or flips long numbers to
  scientific notation. Date columns get a consistent `dd/mm/yyyy hh:mm` display format and integer
  columns display as whole numbers. Numeric/decimal columns (weight, height, BMI, temperature) are
  left as General so their existing range validation keeps working.
- The guide sheet is now easier to find (amber tab color, referenced from the identifier column's
  comment), and every example row is now clearly marked for deletion before a real run.

### Mapping & reader diagnostics

- The reader now warns (instead of silently ignoring) when the Excel file has columns that aren't
  in the mapping — a common source of silently-lost data from a typo'd mapping key. Surfaced in the
  CLI, the run/update log, and the GUI's Validate results.
- Duplicate mapped column headers in an Excel file now raise a clear error instead of silently
  keeping only the last column's data.
- A missing update-mode overlay file (`mapping.update.yaml`) now raises a clear error naming the
  file, instead of failing later with a confusing "medicalRecordId column missing" message.
- Documented three trap-prone mapping behaviors in the example YAMLs: the automatic
  `diagnosesDischarge` → `diagnosesDischargeList` mirror, `multi_match: skip` silently skipping
  rows with more than one matching patient, and why weight/height/BMI are stored as strings.

## v1.5.0 — 2026-07-03

### Preferences dialog overhaul

- **Apply button** — Settings can now be saved without closing the dialog. Apply and OK only
  write what actually changed, instead of unconditionally rewriting `mapping.yaml` on every OK.
- **Fixed a bug where a failed save could leave settings half-applied** — previously, if writing
  record defaults failed, the run defaults and language switch had already been saved with no way
  to undo them. The fallible write now happens first; on failure nothing else is touched and the
  dialog stays open with your edits intact.
- **Per-tab Reset button** whose label follows the visible tab ("Reset run settings" / "Reset
  record defaults"), replacing a single ambiguous "Restore defaults" button.
- **Unsaved-changes confirmation** on Cancel, Esc, or closing the window, instead of silently
  discarding edits.
- The success message is now a non-modal toast instead of a popup dialog, and the tab layout was
  regrouped into **General** (run settings + application settings) and **Record defaults**.

### Fixes

- The drag-and-drop file highlight (the dashed border shown while dragging an Excel file onto the
  window) now reliably appears on macOS. It previously relied on a Qt stylesheet border that the
  native macOS style silently ignores on a plain widget; it's now custom-painted, which also let us
  remove the app's global stylesheet — every widget keeps fully native rendering.

## v1.4.1 — 2026-07-03

### Performance

- **Large-batch results table no longer freezes the UI** — rows streaming into the
  results table are now buffered and inserted in batches (~120 ms) instead of one at a
  time. This removes the per-row full-table rescans (visibility, empty-state, re-sort)
  that made streaming O(n²): an offscreen benchmark that took **~72 s to stream 1,000
  rows now streams 10,000 rows in ~1 s**. The visible-row count is tracked incrementally
  rather than recomputed on every insert, and the filter box is debounced (~200 ms) so
  typing over a full table rescans once instead of per keystroke.
- **Progress updates throttled to ~10 Hz** — validation and run workers no longer emit a
  progress signal per row across the thread boundary (the terminal 100 % update always
  fires), cutting event-loop churn on big batches.
- **Log pane is now bounded** (5,000 blocks) so long or repeated runs don't grow the
  document without limit.
- **`results.xlsx` written in streaming (write-only) mode** — lower memory/time when
  reports carry thousands of rows.
- **Excel coercion** caches the parsed `default_time` instead of re-parsing it for every
  datetime cell.

  *Minor behaviour deltas from the batching:* the Export CSV button enables within ~120 ms
  of the first row (was instant), and the success/failure counter updates ~8×/s during a
  run instead of on every row.

## v1.3.6 — 2026-06-27

### Changes

- **Sponsor dialog shows MoMo only** — VietQR panel removed; dialog minimum
  width narrowed to 320 px.

### Internal / CI

- **Reproducible builds** — `constraints.txt` universal lockfile (generated by
  `uv pip compile --universal`) pins all 49 transitive dependencies with
  cross-platform markers (`pefile`/`pywin32-ctypes`/`colorama` on win32,
  `macholib` on darwin). Both CI jobs install with `-c constraints.txt`.
- **CI caching** — pip downloads cached via `setup-python` and the ~130 MB
  Playwright Chromium cached via `actions/cache@v6`, both keyed off
  `constraints.txt` so caches invalidate correctly on dep changes.
- **Build-dep caps** — `pyproject.toml` build-system requires now cap
  `setuptools<83` and `wheel<1` to block surprise major updates in the
  PEP 517 isolated build environment (not reached by `-c constraints.txt`).

## v1.3.5 — 2026-06-24

### New features

- **In-app Support/Donate dialog** — accessible from *Help → Support the Developer…* and a
  footer link. Shows VietQR and MoMo QR codes side by side; a selectable text label under each QR
  lets users on the same machine copy payment details without needing a second phone.
- **App icon at runtime** — the window, dock, and taskbar now show the polished HSSK Tools icon
  instead of the generic Qt Q. A new `app_icon()` config helper resolves to the bundled
  `packaging/assets/icon.png` in source runs and `_MEIPASS/assets/icon.png` in frozen builds.

### UX improvements

- **Live-button interactive feedback** — the *PUSH live records* and *UPDATE live records* buttons
  now show proper `:hover` (darkens), `:pressed` (darker), and `:disabled` (muted pink) states. The
  previous flat `background:#cf222e` override silently suppressed all native Qt feedback, leaving the
  button looking fully armed even while a run was in progress and the button was disabled.
- **Live-button danger glyph** — both live-action buttons now carry a `⚠ ` prefix so the warning
  reads on the control itself, not only on the production banner above it.

### Accessibility

- `token_label` and `file_label` annotated with `setAccessibleName` so screen readers announce
  their role ("Login status", "Selected file") rather than reading raw dynamic text.
- Mode, Delay, and Limit `QLabel`s in the run box now call `setBuddy(widget)` to associate each
  label with its control for keyboard and assistive-technology navigation.
- QR images in the sponsor dialog get `setAccessibleName` + `setAccessibleDescription`.

### Internal

- **httpx header idiom** — `User-Agent` now reflects the actual version (`hssk-tools/1.3.5`
  instead of the hardcoded `hssk-tools/0.1`). Constant headers (`Authorization`, `Accept`,
  `User-Agent`) moved to `httpx.Client(headers=...)` constructor per library best practice;
  per-request `_headers()` method removed. `Content-Type: application/json` is now set by httpx
  automatically only on POST requests (GETs no longer send a misleading content type header).

## v1.3.4 — 2026-06-23

### Packaging

- **macOS DMG now built per-architecture** — the v1.3.1 macOS build ran on an
  Apple Silicon CI runner and produced an arm64-only app that failed to launch on
  Intel Macs ("not supported on this Mac"). Releases now ship two DMGs:
  `HSSK-Tools-*-apple-silicon.dmg` and `HSSK-Tools-*-intel.dmg`. Because
  GitHub-hosted Intel macOS runners have been retired, the Intel DMG is cross-built
  on the Apple Silicon runner by running the universal2 framework Python under
  Rosetta (`arch -x86_64`), so pip, Playwright, and PyInstaller all target x86_64.
  (v1.3.3 attempted this via setup-python's `architecture: x64`, which was ignored —
  both legs built arm64 and the identically-named DMGs collided on upload.)

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
