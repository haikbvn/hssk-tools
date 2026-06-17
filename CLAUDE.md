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

## Commands

Dev runs from a Python **3.12** venv at `.venv` (the dev Mac's system 3.14 is too new for some
wheels — `brew install python@3.12`).

```bash
.venv/bin/pip install -e ".[dev]"        # install with dev deps
.venv/bin/playwright install chromium    # one-time, for the login flow
.venv/bin/hssk-gui                        # launch the GUI

pytest -q                                 # run all tests (pyproject sets pythonpath=src)
pytest tests/test_coerce.py              # one file
pytest tests/test_coerce.py::test_name   # one test
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy                            # packages configured in pyproject

.venv/bin/pyinstaller packaging/hssk_gui.spec   # build the app for the current OS
```

CLI (debugging the engine without the GUI): `hssk login` | `hssk template -o out.xlsx` |
`hssk validate -i in.xlsx` | `hssk run -i in.xlsx` (dry-run; add `--commit` to send).

Runtime knobs are `Settings` fields overridable via `HSSK_*` env vars or a `.env`
(e.g. `HSSK_REQUEST_DELAY=2`, `HSSK_DATA_DIR=/tmp/hssk` for an isolated sandbox).

## Architecture

**One engine, two frontends.** `src/hssk/` is a pure, UI-free engine; `src/hssk_gui/` (PySide6) and
`src/hssk/cli.py` are thin drivers. The engine reports progress through plain `runner.Callbacks`
(`on_progress`/`on_row`/`on_log`) and never imports any UI — so the CLI and GUI share identical
behavior. When adding engine features, keep this boundary: no Qt/print inside `hssk/`.

**Per-row pipeline** (`hssk/pipeline/runner.py`, the orchestrator to read first):

```
read_rows (excel/reader)        # Excel → {header: value}, validates required columns exist
  → coerce_row (excel/coerce)   # types/dates/VN-decimals → API-ready values + warnings; bad cell = row error, not a crash
  → Ledger.done?                # skip if (identifier, exam-date) already processed
  → patients.resolve            # search API → real patientId + medicalIdentifierCode
  → builder.build (payload/)    # canonical template ⊕ mapping defaults ⊕ row values
  → dry-run: write payloads/row_N.json   |   commit: exams.create → Ledger.mark_done
```

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

### Config & the mapping file (`mapping.py`, `config.py`)

The Excel-column → API-field map is a **user-editable** `mapping.yaml`, seeded on first run from
`config/mapping.example.yaml`. It lives in the OS config dir (`config_dir()`), **not** the repo.
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

## Packaging

PyInstaller can't cross-compile, so each OS builds on its own GitHub Actions runner
(`.github/workflows/build.yml`): install deps, run `pytest`, `playwright install chromium` into
`$PLAYWRIGHT_BROWSERS_PATH`, then `pyinstaller packaging/hssk_gui.spec`. The spec bundles that
Chromium (so operators install nothing) plus `mapping.example.yaml`; `runtime_hook_playwright.py`
points the frozen app at the bundled browser. Output is a Windows `.exe` folder and a macOS `.app`,
uploaded per build and attached to `v*` tag releases.

## Notes

- Excel files, reports, the token, and `mapping.yaml` all contain PII or secrets and are gitignored —
  never commit them. `~$hssk_template.xlsx` is an Excel lock file; ignore it.
- Vietnamese text and locale quirks are pervasive (comma decimals, `dd/MM/yyyy HH:mm:ss` dates,
  diacritics in field defaults). Keep `ensure_ascii=False` when writing JSON and preserve the exact
  Vietnamese constant strings in `templates.py`.
