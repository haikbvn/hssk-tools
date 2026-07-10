"""Thin CLI for debugging the engine without the GUI.

Subcommands: ``login``, ``template``, ``validate``, ``run`` (create), ``update``, ``delete``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ensure_mapping_file, ensure_update_overlay_file, settings
from .errors import ConfigError, HsskError
from .events import render_en
from .excel import reader
from .excel.coerce import coerce_row
from .mapping import filter_for_delete, load_mapping
from .payload import builder
from .pipeline import runner
from .pipeline.ledger import Ledger


def _resolve_mapping(path: str | None, *, update: bool = False, delete: bool = False):
    mapping_path = Path(path) if path else ensure_mapping_file()
    # Delete mode reuses the update overlay (it carries the medicalRecordId column), then keeps
    # only the identifier + medicalRecordId columns so a slim 2-column Excel loads.
    overlay = ensure_update_overlay_file() if (update or delete) else None
    mapping = load_mapping(mapping_path, overlay_path=overlay)
    return filter_for_delete(mapping) if delete else mapping


def _confirm_production(action: str) -> bool:
    """Require an explicit y/N confirmation before sending live data.

    Returns False (abort) when stdin isn't interactive, so a piped or closed stdin can never
    silently fall through to a live run.
    """
    print(f"⚠️  PRODUCTION — this will {action} LIVE medical records.")
    try:
        answer = input("   Proceed? [y/N]: ").strip().lower()
    except EOFError:
        print("Aborted (no interactive input).")
        return False
    if answer not in ("y", "yes"):
        print("Aborted.")
        return False
    return True


def cmd_login(args: argparse.Namespace) -> int:
    from .auth.browser_login import capture_token
    from .auth.profile import load_profile
    from .auth.token_store import mask

    data = capture_token(on_status=lambda m: print(f"  {render_en(m)}"))
    rem = data.seconds_remaining()
    print(f"✓ Token saved ({mask(data.token)}).")
    if rem is not None:
        print(f"  Valid for ~{rem // 60} min {rem % 60}s.")
    profile = load_profile()
    if profile is not None:
        print(f"  Logged in as: {profile.identity_label()}")
    return 0


def cmd_template(args: argparse.Namespace) -> int:
    from .excel.template import make_template

    mapping = _resolve_mapping(args.mapping, update=args.update, delete=args.delete)
    out = make_template(
        mapping, args.output, examples=not args.no_examples, protect=not args.no_protect
    )
    print(f"✓ Template written to {out}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    mapping = _resolve_mapping(args.mapping, delete=args.delete)
    bad = builder.validate_targets(mapping)
    if bad:
        print(f"✗ Mapping uses unknown API field target(s): {bad}")
        return 1
    rows = reader.read_rows(args.input, mapping, on_warning=lambda m: print(f"  ⚠ {render_en(m)}"))
    valid = invalid = 0
    for idx, raw in rows:
        r = coerce_row(raw, mapping, idx)
        if r.ok:
            valid += 1
        else:
            invalid += 1
            print(f"  row {idx}: ERROR  {'; '.join(render_en(e) for e in r.errors)}")
        for w in r.warnings:
            print(f"  row {idx}: warn   {render_en(w)}")
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

    if not dry_run and not args.yes and not _confirm_production("create"):
        return 1

    def on_row(o: runner.RowOutcome) -> None:
        print(f"  row {o.row_index:<4} {o.status.value:<16} {o.identifier or '':<14} {o.message}")

    cb = runner.Callbacks(on_row=on_row, on_log=lambda e: print(f"  · {render_en(e)}"))
    summary = runner.run(
        args.input,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=args.limit,
        settings=s,
        callbacks=cb,
        ledger=led,
        retry_pending=args.retry_pending,
    )

    print(f"\n{'DRY-RUN ' if dry_run else ''}done — {summary.total} rows")
    for status, count in sorted(summary.counts.items(), key=lambda kv: kv[0].value):
        print(f"  {status.value:<16} {count}")
    if summary.aborted:
        print(f"⚠️  Aborted: {summary.abort_reason}")
    print(f"Report: {summary.run_dir}")
    return 0 if not summary.aborted else 2


def cmd_update(args: argparse.Namespace) -> int:
    from .auth.token_store import load_valid_token

    token = load_valid_token()
    mapping = _resolve_mapping(args.mapping, update=True)
    dry_run = not args.commit

    s = settings()
    if args.delay is not None:
        s = s.model_copy(update={"request_delay": args.delay})

    if not dry_run and not args.yes and not _confirm_production("update"):
        return 1

    def on_row(o: runner.RowOutcome) -> None:
        print(f"  row {o.row_index:<4} {o.status.value:<16} {o.identifier or '':<14} {o.message}")

    cb = runner.Callbacks(on_row=on_row, on_log=lambda e: print(f"  · {render_en(e)}"))
    summary = runner.run_update(
        args.input,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=args.limit,
        settings=s,
        callbacks=cb,
    )

    print(f"\n{'DRY-RUN ' if dry_run else ''}done — {summary.total} rows")
    for status, count in sorted(summary.counts.items(), key=lambda kv: kv[0].value):
        print(f"  {status.value:<16} {count}")
    if summary.aborted:
        print(f"⚠️  Aborted: {summary.abort_reason}")
    print(f"Report: {summary.run_dir}")
    return 0 if not summary.aborted else 2


def cmd_delete(args: argparse.Namespace) -> int:
    from .auth.token_store import load_valid_token

    token = load_valid_token()
    mapping = _resolve_mapping(args.mapping, delete=True)
    dry_run = not args.commit

    s = settings()
    if args.delay is not None:
        s = s.model_copy(update={"request_delay": args.delay})

    if not dry_run and not args.yes and not _confirm_production("PERMANENTLY DELETE"):
        return 1

    def on_row(o: runner.RowOutcome) -> None:
        print(f"  row {o.row_index:<4} {o.status.value:<16} {o.identifier or '':<14} {o.message}")

    cb = runner.Callbacks(on_row=on_row, on_log=lambda e: print(f"  · {render_en(e)}"))
    summary = runner.run_delete(
        args.input,
        mapping,
        token=token,
        dry_run=dry_run,
        limit=args.limit,
        settings=s,
        callbacks=cb,
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

    t = sub.add_parser("template", help="Generate a blank Excel template matching the mapping")
    t.add_argument("-o", "--output", default="hssk_template.xlsx", help="Output .xlsx path")
    t.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    t.add_argument("--no-examples", action="store_true", help="Omit the example rows")
    t.add_argument("--no-protect", action="store_true", help="Skip header row protection")
    t_mode = t.add_mutually_exclusive_group()
    t_mode.add_argument(
        "--update",
        action="store_true",
        help="Template for `hssk update` (adds the medicalRecordId / 'Mã hồ sơ' column)",
    )
    t_mode.add_argument(
        "--delete",
        action="store_true",
        help="Template for `hssk delete` (2 columns: 'Mã định danh' + 'Mã hồ sơ')",
    )
    t.set_defaults(func=cmd_template)

    v = sub.add_parser("validate", help="Offline mapping/data validation (no network)")
    v.add_argument("-i", "--input", required=True, help="Excel file path")
    v.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    v.add_argument(
        "--delete",
        action="store_true",
        help="Validate a `hssk delete` file (2-column identifier + medicalRecordId mapping)",
    )
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("run", help="Run the push (dry-run by default)")
    r.add_argument("-i", "--input", required=True, help="Excel file path")
    r.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    r.add_argument("--commit", action="store_true", help="Actually send (default is dry-run)")
    r.add_argument("--limit", type=int, help="Process at most N rows")
    r.add_argument("--delay", type=float, help="Min seconds between requests")
    r.add_argument("--reset-ledger", action="store_true", help="Clear the processed-rows ledger")
    r.add_argument(
        "--retry-pending",
        action="store_true",
        help="Re-send rows a previous interrupted run left in 'pending' state "
        "(only after verifying on the website that they were NOT created)",
    )
    r.add_argument("--yes", action="store_true", help="Skip the production confirmation prompt")
    r.set_defaults(func=cmd_run)

    u = sub.add_parser(
        "update",
        help="Update existing records (dry-run by default); uses mapping.update.yaml",
    )
    u.add_argument("-i", "--input", required=True, help="Excel file path")
    u.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    u.add_argument("--commit", action="store_true", help="Actually send (default is dry-run)")
    u.add_argument("--limit", type=int, help="Process at most N rows")
    u.add_argument("--delay", type=float, help="Min seconds between requests")
    u.add_argument("--yes", action="store_true", help="Skip the production confirmation prompt")
    u.set_defaults(func=cmd_update)

    d = sub.add_parser(
        "delete",
        help="Delete existing records by 'Mã hồ sơ' (dry-run by default); uses mapping.update.yaml",
    )
    d.add_argument("-i", "--input", required=True, help="Excel file path")
    d.add_argument("-m", "--mapping", help="Mapping YAML path (defaults to user config)")
    d.add_argument("--commit", action="store_true", help="Actually send (default is dry-run)")
    d.add_argument("--limit", type=int, help="Process at most N rows")
    d.add_argument("--delay", type=float, help="Min seconds between requests")
    d.add_argument("--yes", action="store_true", help="Skip the production confirmation prompt")
    d.set_defaults(func=cmd_delete)

    return p


def main(argv: list[str] | None = None) -> int:
    from .logging_setup import configure_logging

    configure_logging()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (HsskError, ConfigError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
