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

**Response probing lives in `api/adapters.py`** — the one home for the three tolerant probers
(`find_patient_list`, `extract_patient_ref`, `extract_record_id`); `patients.py`/`records.py`/
`record_id.py` re-export from it (keeps their public names + tests). Two of them take an optional
`on_drift` callback that fires **only** when a response is clearly not the expected shape — a
non-empty object with no place the data could sit (a *located-but-empty* result like
`{"data":{"items":[]}}` is a normal miss, never drift). The runner threads a once-per-endpoint
`drift_logger` in, emitting a single `LOG_DRIFT` warning the GUI raises as a "server response not
recognised — dry-run first" banner. Keep drift narrow (locate-failure only) so a normal empty search
never false-alarms.

### Payload assembly (`payload/templates.py` + `payload/builder.py`)

`templates.py` is the single source of truth for the create-request body shape and its constant
defaults (organ descriptions → "Bình thường", money fields → null, etc.). `builder.build` layers:
canonical template → deep-merge the mapping's `defaults` block → inject per-row coerced values into
the correct sub-object (a target is routed by membership in `RECORD_INFO_TARGETS` vs
`PATIENT_DETAIL_TARGETS`) → set `patientId`/`medicalIdentifierCode` last. `update_builder.build_update`
reuses `builder.build`, then stamps `medicalRecordId`, adds `concludesDisease`, and the two empty
`deleted*` lists the update endpoint requires. `builder.build` also fills operator-identity fields
from the cached login profile (`auth/profile.py`, fetched once at login) when the row leaves them blank.

**`payload/models.py` is the pydantic schema for the body shape** (`CreateExamPayload` +
`MedicalRecordInfo`/`MedicalPatientDetailInfo`, all `extra="forbid"`). It is the **single source of
truth for the field set**: `RECORD_INFO_TARGETS`/`PATIENT_DETAIL_TARGETS` derive from `model_fields`,
so `validate_targets` (run before any batch) rejects a mapped target the model doesn't define. The
**templates stay the source of default *values***; `tests/test_payload_models.py` pins `model_fields`
≡ the template keys so the two can't drift. `builder.build` ends with a **validate-only gate**
(`validate_payload`): it runs `CreateExamPayload.model_validate` for its *rejection* behavior and
sends the original dict unchanged (never a `model_dump`, so the wire bytes are unaffected). A failure
raises `PayloadInvalid`, which the runner turns into a per-row `INVALID` (`ROW_PAYLOAD_INVALID`) — in
dry-run and commit. This is what catches a typo in the mapping's `defaults` block (otherwise
unvalidated). Field *value* types are deliberately permissive (`str_num` coercion yields strings like
`"18"`); the gate's value is `extra="forbid"`, not value strictness — don't tighten value types
without checking the builder/pipeline goldens. The error detail is built from pydantic `loc`+`msg`
only (never `input`), so patient cell values don't leak into reports/logs.

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
token via `token_store.save_token`. This uses Playwright's **sync** API, so it must run off any asyncio
loop — i.e. the CLI main thread or a `QThread` worker, never an async context. The JWT `exp` is decoded
locally (no signature check) to warn before expiry; a server 401 surfaces as `AuthExpired`.

**Token at rest → OS keychain, with a file fallback.** `token_store` stores the token in the OS
keychain (macOS Keychain / Windows Credential Manager / Linux Secret Service) under service
`hssk-tools`; if the keychain is unavailable (no backend, locked, any error) it **silently falls back**
to the previous gitignored `chmod 600` file, so login never breaks. A legacy token file is migrated
into the keychain on first read (file → keychain → delete). `keyring` is a lazy `import` inside the
store (never at module load); every keyring call is wrapped so a failure just degrades to the file.
Passing an explicit `path=` to `save_token`/`load_token` bypasses the keychain (file only) — this is
what the tests use, and `tests/conftest.py` installs an **autouse in-memory keyring backend** so no
test ever touches (or prompts) the real OS keychain. Note: the frozen-app keychain path and the macOS
Keychain prompt on an unsigned build are only verifiable on a real build — the file fallback makes
them non-load-bearing.

> Phase 6 note: the roadmap's Chromium-free (pywebview) login was **spiked and rejected** — macOS
> WKWebView can't run the site's WAF-protected Keycloak-OIDC SPA (the login page renders blank, and
> WKWebView's `request_sent` never sees XHR), so **Playwright stays**. Only the keychain migration
> (originally deferred from Phase 4) shipped from Phase 6.

### GUI threading invariant (`hssk_gui/worker_thread.py`)

All four background jobs (login, update-check, validate, run) run on a `QThread` + worker
(`hssk_gui/workers.py`) so the UI stays responsive. **Destroying a running `QThread` aborts the
whole process** (this was a real SIGABRT bug, commit 5ea2803). The lifecycle now lives in **one
place** — `worker_thread.py:WorkerHandle` — instead of being hand-copied at four sites: it does
`moveToThread` → `started→run` → `worker.finished/failed → thread.quit`, and on `thread.finished`
invokes the caller's `on_thread_finished` callback (where `MainWindow` nulls its `_X_handle` and
re-enables controls). Construct+start via `run_in_thread(worker, on_thread_finished=…)`; callers
still connect their own domain signals (`status`/`progress`/`row`/`log`/`problem`/`finished`/
`failed`) before it starts. `MainWindow` holds one `_X_handle: WorkerHandle | None` per job, and
"`handle is None` ⇔ that job is idle" is the invariant every idle-state reader relies on.

**Deletion is single-path on purpose — do not add `deleteLater`.** The old wiring paired
`thread.finished → deleteLater` with a same-handler null-out of the Python reference; those are two
competing deletion paths (a queued C++ deferred-delete and Python's refcount drop) that race into
an intermittent segfault under rapid start/stop cycling. `WorkerHandle` keeps the worker+thread
referenced for its whole life and uses **no** `deleteLater`, so the C++ objects are freed exactly
once, by Python, when the handle is dropped — and a handle is only dropped after `thread.finished`
(thread stopped), never mid-run. `closeEvent` cancels each handle, then `quit()`s + `wait()`s
(cancel alone can't stop it — the main thread is blocked in `wait()`, so the queued
`worker.finished→quit` hop can't fire; `quit()` stops the thread's event loop directly).
`tests/test_gui_threads.py` is the regression net (run it in a loop; it must stay crash-free).

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
footer link), and `confirm_dialog.ConfirmProductionDialog` (one-click Confirm/Cancel for a PRODUCTION
push, custom-drawn so it renders identically on both OSes; Cancel is the default/focused action so a
stray Enter can't fire a live push). `results_panel` is the live results table.

**Native look per OS, on purpose.** No app-wide style, palette, or stylesheet is installed —
Windows renders the windows11 style, macOS renders Aqua, and each follows its own OS Light/Dark
switch natively. `theme.py`'s tokens (`color(token)`, Primer light/dark ramps) exist only for the
handful of surfaces the app custom-paints on top of native widgets: the production banner, notice
banners, the live-PUSH/UPDATE danger button, the results-table splitter grip and status pills, and
the stepper/confirm-dialog above. `theme.apply_app_theme` wires `QStyleHints.colorSchemeChanged`
so those custom-painted surfaces re-theme live when the OS switches Light/Dark; native widgets
aren't touched — they already follow the OS automatically. `SPACING`/`RADIUS` constants keep the
stepper and confirm dialog's hand-built geometry consistent with each other without a shared
stylesheet to inherit from. `components/stepper.SafetyStepper` is a read-only strip (Login → File
→ Validated → Dry-run/Commit) reflecting the same state `MainWindow._update_start_enabled` already
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
- **PII at rest & diagnostics.** `logging_setup.configure_logging()` (called once from `cli.main` /
  `app.main`) attaches a rotating file log at `data_dir()/logs/hssk.log` whose `RedactionFilter`
  scrubs Bearer/JWT strings; it turns up only the `hssk`/`hssk_gui` loggers to DEBUG so third-party
  request bodies (patient PII) never hit disk. The shared JWT shape lives in `logging_setup.JWT_BODY`
  (`browser_login` anchors it). `maintenance.find_old_runs`/`purge_runs` back the File → "Purge old
  reports…" action — retention (`Settings.output_retention_days`, default 90) is **not** enforced
  automatically by default; an operator may opt in via Preferences (`UiSettings.auto_purge`, default
  off) to a launch-time purge that silently reuses the same helpers and shows a count banner, gated
  by a one-time enable-time confirmation. `support_bundle.build_support_bundle` (engine-side,
  UI-free) zips redacted logs + mapping + a versions/settings snapshot for Help → "Export support
  bundle…"; it **never** includes `secrets/` (token + profile), and the latest run's `events.jsonl`
  only on the GUI's opt-in checkbox. Keep those exclusions when touching either file.
- Vietnamese text and locale quirks are pervasive (comma decimals, `dd/MM/yyyy HH:mm:ss` dates,
  diacritics in field defaults). Keep `ensure_ascii=False` when writing JSON and preserve the exact
  Vietnamese constant strings in `templates.py`.
