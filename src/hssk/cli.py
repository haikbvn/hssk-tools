"""Thin CLI for debugging the engine without the GUI: ``login``, ``validate``, ``run``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ensure_mapping_file, settings
from .errors import ConfigError, HsskError
from .excel import reader
from .excel.coerce import coerce_row
from .mapping import load_mapping
from .payload import builder
from .pipeline import runner
from .pipeline.ledger import Ledger


def _resolve_mapping(path: str | None):
    mapping_path = Path(path) if path else ensure_mapping_file()
    return load_mapping(mapping_path)


def cmd_login(args: argparse.Namespace) -> int:
    from .auth.browser_login import capture_token

    data = capture_token(on_status=lambda m: print(f"  {m}"))
    rem = data.seconds_remaining()
    from .auth.token_store import mask

    print(f"✓ Token saved ({mask(data.token)}).")
    if rem is not None:
        print(f"  Valid for ~{rem // 60} min {rem % 60}s.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    mapping = _resolve_mapping(args.mapping)
    bad = builder.validate_targets(mapping)
    if bad:
        print(f"✗ Mapping uses unknown API field target(s): {bad}")
        return 1
    rows = reader.read_rows(args.input, mapping)
    valid = invalid = 0
    for idx, raw in rows:
        r = coerce_row(raw, mapping, idx)
        if r.ok:
            valid += 1
        else:
            invalid += 1
            print(f"  row {idx}: ERROR  {'; '.join(r.errors)}")
        for w in r.warnings:
            print(f"  row {idx}: warn   {w}")
    print(f"\n{valid} valid, {invalid} invalid, {len(rows)} total.")
    return 0 if invalid == 0 else 1


def cmd_run(args: argparse.Namespace) -> int:
    from .auth.token_store import load_valid_token

    token = load_valid_token()
    mapping = _resolve_mapping(args.mapping)
    dry_run = not args.commit

    s = settings()
    if args.delay is not None:
        s = s.model_copy(update={"request_delay": args.delay})

    led = Ledger.load()
    if args.reset_ledger:
        led.reset()

    if not dry_run and not args.yes:
        print("⚠️  PRODUCTION — this will create LIVE medical records.")
        if input("   Type YES to proceed: ").strip() != "YES":
            print("Aborted.")
            return 1

    def on_row(o: runner.RowOutcome) -> None:
        print(f"  row {o.row_index:<4} {o.status.value:<16} {o.identifier or '':<14} {o.message}")

    cb = runner.Callbacks(on_row=on_row, on_log=lambda m: print(f"  · {m}"))
    summary = runner.run(
        args.input, mapping, token=token, dry_run=dry_run,
        limit=args.limit, settings=s, callbacks=cb, ledger=led,
    )

    print(f"\n{'DRY-RUN ' if dry_run else ''}done — {summary.total} rows")
    for status, count in sorted(summary.counts.items(), key=lambda kv: kv[0].value):
        print(f"  {status.value:<16} {count}")
    if summary.aborted:
        print(f"⚠️  Aborted: {summary.abort_reason}")
    print(f"Report: {summary.run_dir}")
    return 0 if not summary.aborted else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hssk", description="Push health-checkup data to hososuckhoe")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Open the website and capture the API token").set_defaults(
        func=cmd_login
    )

    v = sub.add_parser("validate", help="Offline mapping/data validation (no network)")
    v.add_argument("-i", "--input", required=True, help="Excel file path")
    v.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("run", help="Run the push (dry-run by default)")
    r.add_argument("-i", "--input", required=True, help="Excel file path")
    r.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    r.add_argument("--commit", action="store_true", help="Actually send (default is dry-run)")
    r.add_argument("--limit", type=int, help="Process at most N rows")
    r.add_argument("--delay", type=float, help="Min seconds between requests")
    r.add_argument("--reset-ledger", action="store_true", help="Clear the processed-rows ledger")
    r.add_argument("--yes", action="store_true", help="Skip the production confirmation prompt")
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (HsskError, ConfigError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
