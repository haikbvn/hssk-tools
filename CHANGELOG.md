# Changelog

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
