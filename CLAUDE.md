# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A cross-platform (Windows + macOS) desktop app that bulk-pushes health-checkup ("khám sức khoẻ")
data from an Excel file into the national health-record system **hososuckhoe.com.vn**, via that
site's **internal/undocumented** API using the operator's own authorized account. Operators are
clinic staff, hence the GUI; the CLI exists for debugging the same engine.

> The hard safety constraints below (throttling, dry-run default, ledger, exact-match) are product
> requirements locked with the project owner — treat them as invariants, not implementation details
> to be optimized away.

## Library docs & setup — use Context7

When a task needs **library/API documentation, code generation, or setup/configuration steps** for
any third-party dependency (PySide6, pydantic, Playwright, openpyxl, httpx, PyInstaller, …),
**proactively use the Context7 MCP** (`resolve-library-id` → `query-docs`) to pull current docs
first — without waiting to be asked. Prefer it over recalling version-specific APIs from memory.

## Commands

Dev runs from a Python **3.12** venv at `.venv` (the dev Mac's system 3.14 is too new for some
wheels — `brew install python@3.12`).

```bash
.venv/bin/pip install -e ".[dev]"        # install with dev deps (latest compatible)
# CI instead pins versions: pip install -e ".[dev]" -c constraints.txt  (see Packaging)
.venv/bin/playwright install chromium    # one-time, for the login flow
.venv/bin/hssk-gui                        # launch the GUI

pytest -q                                 # run all tests (pyproject sets pythonpath=src)
pytest tests/test_coerce.py              # one file
pytest tests/test_coerce.py::test_name   # one test
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy                            # packages configured in pyproject

.venv/bin/pyinstaller packaging/hssk_gui.spec   # build the app for the current OS
```

CLI (debugging the engine without the GUI): `hssk login` | `hssk template -o out.xlsx`
(`--update` adds the `medicalRecordId` column) | `hssk validate -i in.xlsx` |
`hssk run -i in.xlsx` (create) | `hssk update -i in.xlsx` (update existing records). Both `run` and
`update` are dry-run by default; add `--commit` to send and `--yes` to skip the production prompt.

Runtime knobs are `Settings` fields overridable via `HSSK_*` env vars or a `.env`
(e.g. `HSSK_REQUEST_DELAY=2`, `HSSK_DATA_DIR=/tmp/hssk` for an isolated sandbox).

## Architecture

**One engine, two frontends.** `src/hssk/` is a pure, UI-free engine; `src/hssk_gui/` (PySide6) and
`src/hssk/cli.py` are thin drivers. The engine reports progress through plain `runner.Callbacks`
(`on_progress`/`on_row`/`on_log`) and never imports any UI — so the CLI and GUI share identical
behavior. When adding engine features, keep this boundary: no Qt/print inside `hssk/`.

**Per-row pipeline** (`hssk/pipeline/runner.py`, the orchestrator to read first). `run` (create) and
`run_update` (update) share one skeleton, `_run_batch` — it owns the loop, coercion, the dry-run
write, the send/abort error ladder, and reporting; each mode passes a `process_row` closure for the
part that differs. The **create** path:

```
read_rows (excel/reader)        # Excel → {header: value}, validates required columns exist
  → coerce_row (excel/coerce)   # types/dates/VN-decimals → API-ready values + warnings; bad cell = row error, not a crash
  → Ledger.done?                # skip if (identifier, exam-date) already processed
  → patients.resolve            # search API → real patientId + medicalIdentifierCode
  → builder.build (payload/)    # canonical template ⊕ mapping defaults ⊕ row values
  → dry-run: write payloads/row_N.json   |   commit: exams.create → Ledger.mark_done
```

The **update** path (`run_update`) skips both patient search and the ledger: it reads a
`medicalRecordId` from the row, `records.fetch_detail`s the existing record to recover its
`patientId`, then `update_builder.build_update` overlays the row's values and `records.update` sends
it. Re-running an update with corrected data is intentional, so it **never** consults or writes the
ledger.

Each row is wrapped in `try/except` so one bad row never kills the batch. Auth/rate failures
(`AuthExpired`, `RateLimited`) **abort** the whole batch cleanly; per-row failures
(`PatientNotFound`, `MultiMatch`, `ApiError`, invalid) are recorded and the loop continues. Every
outcome is a `Status` enum value surfaced in the GUI table and the written report.

### Safety invariants (don't weaken these)

- **Never overload the server.** All HTTP goes through `api/client.py:ApiClient`: strictly
  sequential, a min `request_delay` (+jitter) between calls, full-jitter exponential backoff on
  429/5xx + transient errors (honoring `Retry-After`), and a circuit breaker that trips after N
  consecutive failures. Do not add concurrency or bypass this client.
- **Dry-run is the default.** Sending live records requires `--commit` (CLI) or unticking Dry-run
  **and** confirming the PRODUCTION prompt (GUI).
- **Resumable & dedup-safe.** `pipeline/ledger.py` is an append-only JSONL keyed by
  `(medicalIdentifierCode, examinationDate)`, written immediately after each successful create, so a
  re-run skips already-pushed rows.
- **One batch at a time.** `pipeline/lock.py:RunLock` is a cross-process advisory lock held for the
  whole batch (acquired in `_run_batch`), so a GUI + CLI (or two GUIs) can't race the ledger's
  read-time `done()` check and double-send. A blocked acquire raises `AlreadyRunning`; the GUI also
  takes a `QLockFile` at startup so a second window won't even open. Interruptible client waits
  (`ApiClient(cancel=…)`) let Stop abort a long back-off promptly.
- **Never guess between patients.** `patients.resolve` raises `MultiMatch` rather than picking one
  (unless the mapping's `search.multi_match` says otherwise).

### Patient search mirrors the website (subtle, easy to get wrong)

The Excel "Mã định danh" identifier is usually a **CCCD or insurance number, not** the patient's
`medicalIdentifierCode`. `patients.search` broadcasts that one value into six fields at once
(`fullname`, `medicalIdentifierCode`, `identification`, `homePhoneNumber`, `personalPhoneNumber`,
`healthInsuranceNumber`) and matches if any hits — exactly what the website's search box does.
`resolve()` returns the matched patient's **real** `medicalIdentifierCode` + `patientId`, and
`builder.build` uses those in the create payload, **not** the searched value. The search response
JSON shape is undocumented, so `_find_patient_list` probes several list keys and the runner dumps the
first response to `first_search_response.json` for inspection.

### Payload assembly (`payload/templates.py` + `payload/builder.py`)

`templates.py` is the single source of truth for the create-request body shape and its constant
defaults (organ descriptions → "Bình thường", money fields → null, etc.). `builder.build` layers:
canonical template → deep-merge the mapping's `defaults` block → inject per-row coerced values into
the correct sub-object (a target is routed by membership in `RECORD_INFO_TARGETS` vs
`PATIENT_DETAIL_TARGETS`) → set `patientId`/`medicalIdentifierCode` last. `validate_targets` rejects
any mapped target that isn't a real field in these templates — run it before any batch.
`update_builder.build_update` reuses `builder.build`, then stamps `medicalRecordId`, adds
`concludesDisease`, and the two empty `deleted*` lists the update endpoint requires. `builder.build`
also fills operator-identity fields from the cached login profile (`auth/profile.py`, fetched once at
login) when the row leaves them blank.

### Config & the mapping file (`mapping.py`, `config.py`)

The Excel-column → API-field map is a **user-editable** `mapping.yaml`, seeded on first run from
`config/mapping.example.yaml`. It lives in the OS config dir (`config_dir()`), **not** the repo.
Update mode adds a second user file, `mapping.update.yaml` (seeded from
`config/mapping.update.example.yaml`) — a **columns-only overlay** merged onto `mapping.yaml` by
`load_mapping(overlay_path=…)`, base-wins on key collision — that carries the update-only
`medicalRecordId` column so the main mapping stays unchanged.
A pydantic validator enforces that `identifier.column` maps to target `medicalIdentifierCode`. All
writable runtime files (token, browser profile, ledger, output reports) live under the platformdirs
user-data dir via `config.py` helpers — never next to the (possibly read-only, frozen) executable.
Bundled read-only resources resolve via `bundle_root()`, which returns `sys._MEIPASS` when frozen by
PyInstaller.

### Auth (`auth/browser_login.py`, `auth/token_store.py`)

Login opens the real site in a **persistent** Playwright Chromium profile, sniffs the `Authorization:
Bearer` header off any XHR to the API host (fallback: scan `localStorage` for a JWT), and saves the
token to a `chmod 600` file. This uses Playwright's **sync** API, so it must run off any asyncio loop
— i.e. the CLI main thread or a `QThread` worker, never an async context. The JWT `exp` is decoded
locally (no signature check) to warn before expiry; a server 401 surfaces as `AuthExpired`.

### GUI threading invariant (`hssk_gui/main_window.py`)

Login and run both execute on a `QThread` + worker (`hssk_gui/workers.py`) so the UI stays
responsive. **Destroying a running `QThread` aborts the whole process** (this was a real SIGABRT bug,
commit 5ea2803). The fixed lifecycle: `worker.finished/failed → thread.quit`; only on
`thread.finished` do `deleteLater` and drop the Python references. `closeEvent` cancels workers and
`wait()`s for threads before accepting. Preserve this ordering when touching the worker wiring.

### GUI shell (`hssk_gui/`)

`app.py:main` is the entry point: it loads the language from `UiSettings` (`settings.py`, a QSettings
wrapper), shows the **first-run consent gate** (`legal_dialog.LegalDialog(consent=True)`; declining
exits the app and does not persist `terms_accepted`), then opens `MainWindow`.

Every user-facing string goes through `i18n.tr(key)` — a flat VI/EN dict in `i18n.py`, **Vietnamese
default**, switched in Preferences (applies on restart). Add a key there rather than a bare literal.

**Engine→frontend messages are typed, not strings.** The engine never authors a human sentence: it
emits `events.MessageCode` + a params dict (as `Msg` on `RowOutcome.msgs` / `ConfigError.msg`, and
`LogEvent` on `Callbacks.on_log`). `events.render_en` is the single engine-owned English renderer
(CLI + written reports stay byte-stable; `events.jsonl` also stores `codes`+params). The GUI renders
the same codes in the UI language via `hssk_gui/render.py` (keys `msg_<CODE>` in `i18n.py`). When you
add an engine message, add a `MessageCode` + a `render_en` branch + `msg_<CODE>` vi/en keys — never a
bare English string the GUI must parse. `Msg.detail` carries raw server/exception text shown verbatim.
`tests/golden/vi_messages_golden.json` + `test_events.py`/`test_gui_i18n.py` pin the wording.

Dialogs: `preferences_dialog` (run defaults + record defaults — the latter edits the mapping's
`defaults` block in place), `legal_dialog` (Terms/Privacy/Security, also opened read-only from Help),
`guide_dialog`, `sponsor_dialog` (VietQR + MoMo QR images, reachable from the Help menu and a grey
footer link), and `confirm_dialog.ConfirmProductionDialog` (type-to-confirm PRODUCTION push — the
operator must type the literal `YES`, mirroring the CLI's `--commit` prompt; replaces a plain
Yes/No message box). `results_panel` is the live results table.

**One rendered appearance on both OSes.** `app.py:main` pins `QApplication.setStyle("Fusion")`
before constructing the app, and `fonts.apply_app_font` loads a bundled Vietnamese-first font
(Be Vietnam Pro, `assets/fonts/`, SIL OFL) as the app-wide default — together these remove the
Segoe-UI-vs-SF-Pro metric drift that used to make "the same layout" look different per OS. Native
OS chrome that's *supposed* to differ (menu bar placement, file dialogs, dialog button order) is
untouched — only the app's own content area is pinned. `theme.build_palette(scheme)` builds the
full QPalette Fusion renders from (surface/text/border/highlight tokens in `theme.py`, alongside
the existing accent tokens); `theme.app_qss()` layers a modern Primer-flavored design system on
top (card-style `QGroupBox` sections, bordered/focus-ringed buttons and inputs, flat table header,
slim progress bar/scrollbars, flat tabs/menus) generated from those same tokens — an unknown token
raises `KeyError` at build time rather than silently rendering unstyled. `theme.apply_app_theme`
applies both the palette and the stylesheet, and rebuilds both live on an OS Light/Dark switch. A
widget's own `setStyleSheet` (the danger button, notice banners, splitter grip, stepper labels)
always wins over these app-level rules. `components/stepper.SafetyStepper` is a read-only strip
(Login → File → Validated → Dry-run/Commit) reflecting the same state `MainWindow._update_start_enabled` already
tracks — it does not gate anything itself.

## Packaging

PyInstaller can't cross-compile, so each OS builds on its own GitHub Actions runner
(`.github/workflows/build.yml`): install deps, run `pytest`, `playwright install chromium` into
`$PLAYWRIGHT_BROWSERS_PATH`, then `pyinstaller packaging/hssk_gui.spec`. The spec bundles that
Chromium (so operators install nothing) plus `mapping.example.yaml`, `mapping.update.example.yaml`,
and the sponsor QR PNGs (`assets/sponsor/`); `runtime_hook_playwright.py`
points the frozen app at the bundled browser. Output is a Windows `.exe` folder and a macOS `.app`,
uploaded per build and attached to `v*` tag releases.

**Reproducible builds.** CI installs with `pip install -e ".[dev]" -c constraints.txt` so every run
pins the exact same dependency versions. `constraints.txt` is a **universal** lockfile (it carries
`sys_platform`/`platform_python_implementation` markers, so the same file pins the right wheels on
Linux, Windows, and both macOS arches — e.g. `pefile`/`pywin32-ctypes` only on win32, `macholib`
only on darwin). `pyproject.toml` stays the source of truth for *which* deps; the lockfile only pins
*which versions*. It targets the CI Python (3.12). Regenerate it after changing `pyproject.toml`
deps with the command recorded in the file's header:
`uv pip compile pyproject.toml --extra dev --universal --python-version 3.12 --no-annotate -o constraints.txt`
(uv needs network; run it via `uvx`/`pipx` or a transient `pip install uv` — it is not a project
dependency). CI runs `pytest` on every platform against the locked set before building, so a bad pin
turns CI red rather than shipping.

## Notes

- Excel files, reports, the token, and `mapping.yaml`/`mapping.update.yaml` all contain PII or
  secrets and are gitignored — never commit them. `~$hssk_template.xlsx` is an Excel lock file;
  ignore it.
- Vietnamese text and locale quirks are pervasive (comma decimals, `dd/MM/yyyy HH:mm:ss` dates,
  diacritics in field defaults). Keep `ensure_ascii=False` when writing JSON and preserve the exact
  Vietnamese constant strings in `templates.py`.
