## Summary

<!-- What does this PR do and why? Reference the issue it closes if applicable. -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Documentation
- [ ] Build / packaging
- [ ] Other:

## Checklist

- [ ] `pytest -q` passes
- [ ] `ruff check . && ruff format --check .` passes
- [ ] `mypy` passes
- [ ] No real patient PII, Excel files, tokens, or `mapping.yaml` / `mapping.update.yaml` committed
- [ ] Engine boundary respected — no Qt imports or `print` calls inside `src/hssk/`
- [ ] Safety invariants unchanged (throttle, dry-run default, ledger dedup, MultiMatch behaviour) — or change is explicitly justified below
- [ ] New user-facing GUI strings added to `src/hssk_gui/i18n.py` (VI + EN)
- [ ] `constraints.txt` regenerated if `pyproject.toml` dependencies changed

## Safety invariant note

<!-- If this PR intentionally touches throttling, dry-run, ledger, patient resolution,
     or the engine/UI boundary, explain the reasoning here. Otherwise delete this section. -->
