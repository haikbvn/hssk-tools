# Contributing to HSSK Tools

Thank you for your interest in improving HSSK Tools. Please read this guide before
opening issues or pull requests.

## Scope & ethics

This tool processes patient **personally identifiable information (PII)** and writes
permanent records into the national health system (`hososuckhoe.com.vn`). Contributions
must respect that context:

- Use and test only with **synthetic / anonymised data**. Never commit real patient
  records, Excel files, API tokens, `mapping.yaml`, `mapping.update.yaml`, `payloads/`,
  or session files — these are gitignored for a reason.
- Do not add features that bypass, weaken, or circumvent the safety invariants described
  below. Such PRs will be closed.
- Contributions that interact with the live national system during development must use
  your **own authorised account** for your own facility only.

## Dev setup

Requires **Python 3.12** (3.11/3.13 also work; 3.14 is too new for some wheels).

**macOS**
```bash
brew install python@3.12
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
.venv/bin/hssk-gui          # launch the GUI
```

**Windows**
```powershell
winget install Python.Python.3.12
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\playwright install chromium
.venv\Scripts\hssk-gui
```

## Before you push

All three checks must pass:

```bash
pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy
```

CI runs the same checks on every PR.

## Safety invariants — non-negotiable

These are product requirements locked with the project owner. PRs that weaken any of
them will be rejected regardless of other merits:

| Invariant | Where it lives |
|-----------|---------------|
| All HTTP goes through `ApiClient` — strictly sequential, throttled, backed-off, with a circuit breaker. No added concurrency. | `src/hssk/api/client.py` |
| Dry-run is the default. Live writes require explicit opt-in (`--commit` / untick GUI + confirm prompt). | `src/hssk/pipeline/runner.py` |
| Ledger dedup — each `(medicalIdentifierCode, examinationDate)` pair is written immediately after a successful create and skipped on re-runs. | `src/hssk/pipeline/ledger.py` |
| Never guess between patients — `patients.resolve` raises `MultiMatch` rather than picking arbitrarily. | `src/hssk/api/patients.py` |
| Engine stays UI-free — `src/hssk/` must not import Qt, call `print`, or reference `hssk_gui`. | Architecture boundary |

## i18n

Every user-facing string in the GUI goes through `i18n.tr(key)` (Vietnamese is the
default). Add a VI + EN entry to `src/hssk_gui/i18n.py` rather than embedding a bare
string literal.

One exception: the engine (`src/hssk/`) emits the literal English verb heads `"created"`
and `"updated"` in row-level messages. The GUI matches on these exact strings — keep them
untranslated at the source.

## Reproducible builds

`constraints.txt` is a universal lockfile that pins exact dependency versions for CI.
If you change `[project.dependencies]` or `[project.optional-dependencies]` in
`pyproject.toml`, regenerate it:

```bash
uvx uv pip compile pyproject.toml --extra dev --universal \
  --python-version 3.12 --no-annotate -o constraints.txt
```

(The full command is also in the file header.)

## Commit & PR conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(gui): add dark-mode toggle
fix: handle MultiMatch when search returns duplicate patients
chore: release v1.3.8
```

Scope is optional but helpful (`gui`, `engine`, `api`, `packaging`).

One logical change per commit; keep PRs focused. Reference the issue number in the PR
description (`Closes #N`).
