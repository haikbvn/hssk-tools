# Security Policy

## Supported versions

Only the **latest release** receives security fixes. Check
[Releases](../../releases/latest) for the current version.

| Version | Supported |
|---------|-----------|
| 1.3.x (latest) | ✓ |
| < 1.3 | ✗ |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

### Preferred: GitHub private security advisory

Go to **Security → Report a vulnerability** in this repository and fill in the form.
GitHub keeps the report confidential until a fix is published.

### Fallback: email

Send details to **haikbvn@gmail.com** with the subject line
`[SECURITY] hssk-tools — <brief description>`.

We aim to acknowledge reports within **5 business days** and to provide a fix or
mitigation timeline within **14 days** of confirmation.

## What to include

- A clear description of the vulnerability and its potential impact.
- Steps to reproduce, using **synthetic or redacted data only** (see below).
- The version of HSSK Tools, OS, and whether you are running from source or the
  packaged installer.

## Critical: protect patient data in reports

This tool handles patient **personally identifiable information (PII)**. When preparing a
report:

- **Never include real patient names, ID numbers, health insurance numbers, or any other
  PII** from actual records. Use fabricated/anonymised examples.
- **Never attach real Excel files, `mapping.yaml`/`mapping.update.yaml`, payloads, or
  reports** that were generated against live data.
- **Never include API tokens or session credentials.** Revoke and rotate any token you
  suspect has been exposed before sending the report.

## Scope

**In scope** (defects in this client tool):

- Token storage at rest (`auth/token_store.py` — the `chmod 600` file on macOS/Linux or
  its Windows equivalent).
- Payload assembly that could leak or corrupt patient data.
- Dependency vulnerabilities (CVEs in httpx, Playwright, PySide6, openpyxl, etc.).
- Bypasses of the safety throttle, circuit breaker, or ledger dedup that could cause
  uncontrolled writes to the national system.
- Insecure local file handling or privilege escalation in the packaged app.

**Out of scope** (not our system to fix):

- Vulnerabilities in **hososuckhoe.com.vn** or its backend API. This project is an
  authorised client of that system; we are not its maintainer. Report those issues
  directly to the national system operator. **Do not probe or test the national system
  while investigating issues in this tool.**
- The undocumented API endpoints themselves — their design is outside our control.

## Safe-harbour

We will not pursue legal action against researchers who report vulnerabilities in good
faith under this policy, provided they do not access patient data belonging to
facilities other than their own, do not disrupt the live national system, and follow the
disclosure process above.
