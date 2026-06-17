# HSSK Tools

Desktop app to push nationwide health-checkup ("khám sức khoẻ") data from an Excel file into the
national health-record system **hososuckhoe.com.vn**.

It opens the website so you log in once and saves the session, then for each Excel row it calls the
site's patient-search API to resolve the patient and the health-examination API to create the
record. **Dry-run is the default** and the app is deliberately throttled — see _Safety_ below.

> ⚠️ This uses the website's **internal/undocumented** API with **your own authorized account**.
> Use only with permission. The app makes strictly sequential, throttled, backed-off requests to
> avoid overloading the server.

## Requirements

- **Python 3.12** (3.11/3.13 also work; the dev Mac's system 3.14 is too new for some wheels).
- A browser is downloaded automatically by Playwright (`playwright install chromium`).

## Setup (run from source)

### macOS

```bash
brew install python@3.12
/usr/local/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
.venv/bin/hssk-gui            # launch the GUI
```

### Windows

```powershell
winget install Python.Python.3.12        # or the python.org installer
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\playwright install chromium
.venv\Scripts\hssk-gui
```

## Usage

1. **Log in** — click _Open website & log in_; a browser opens. Log in normally. The app captures
   and saves the API token (and remembers your browser session for next time).
2. **Pick your Excel file** and click **Validate** to check the column mapping with no network calls.
3. **Dry-run** (default) builds the payloads without sending — inspect them in the output folder.
4. Untick **Dry-run**, confirm the PRODUCTION prompt, and **Start** to push for real. Start with a
   small **Limit** (e.g. 1) and verify it in the website before scaling up.

### Configuring the column mapping

The mapping lives at your user-config dir (`~/Library/Application Support/hssk-tools/mapping.yaml`
on macOS, `%APPDATA%\hssk-tools\mapping.yaml` on Windows), seeded from
[`config/mapping.example.yaml`](config/mapping.example.yaml) on first run. Edit the Excel column
names on the left to match your spreadsheet; the API `target` on the right stays as-is. Constant
values (doctor, facility, "Bình thường" descriptions) live under `defaults`.

### CLI (for debugging)

```bash
hssk login                       # capture a token
hssk validate -i data/input.xlsx # offline mapping/validation report
hssk run -i data/input.xlsx      # dry-run by default; add --commit to send
```

## Safety

- **Dry-run by default**; sending requires `--commit` (CLI) / unticking Dry-run + confirming (GUI).
- A local **ledger** records processed `(identifier, exam-date)` keys and skips them on re-run.
- The patient must match the medical identifier code **exactly** — the app never guesses between
  multiple matches.
- The token is stored locally (gitignored, `chmod 600`) and never logged. Excel/reports contain
  patient PII and are gitignored.

## Packaging (Windows `.exe` + macOS `.app`)

PyInstaller can't cross-compile, so each OS builds on its own GitHub Actions runner
([`.github/workflows/build.yml`](.github/workflows/build.yml)). Artifacts (Windows `.exe`, macOS
`.app`) are uploaded per build and attached to tagged releases. The Playwright Chromium is bundled
so operators install nothing.

To test a build locally on your current OS:

```bash
.venv/bin/pyinstaller packaging/hssk_gui.spec
```
