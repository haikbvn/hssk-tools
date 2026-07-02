from __future__ import annotations

import json

from hssk.pipeline.ledger import Ledger


def test_empty_ledger_has_nothing_done(tmp_path):
    led = Ledger.load(tmp_path / "ledger.jsonl")
    assert not led.done("a|2024-01-01")
    assert len(led) == 0


def test_mark_done_persists_and_is_found(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger.load(path)
    led.mark_done("MIC001|01/01/2024 00:00:00", 999)

    assert led.done("MIC001|01/01/2024 00:00:00")
    assert led.record_id("MIC001|01/01/2024 00:00:00") == 999
    assert path.exists()


def test_resume_across_instances(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led1 = Ledger.load(path)
    led1.mark_done("MIC001|01/01/2024 00:00:00", 42)

    led2 = Ledger.load(path)
    assert led2.done("MIC001|01/01/2024 00:00:00")
    assert led2.record_id("MIC001|01/01/2024 00:00:00") == 42
    assert len(led2) == 1


def test_different_keys_are_independent(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger.load(path)
    led.mark_done("MIC001|01/01/2024 00:00:00", 1)
    led.mark_done("MIC002|01/01/2024 00:00:00", 2)

    assert led.done("MIC001|01/01/2024 00:00:00")
    assert led.done("MIC002|01/01/2024 00:00:00")
    assert not led.done("MIC003|01/01/2024 00:00:00")


def test_load_skips_malformed_lines(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        '{"key": "GOOD|2024-01-01", "recordId": 7, "ts": 0}\n'
        "not valid json\n"
        "\n"
        '{"key": "ALSO_GOOD|2024-01-01", "recordId": 8, "ts": 0}\n',
        encoding="utf-8",
    )
    led = Ledger.load(path)
    assert led.done("GOOD|2024-01-01")
    assert led.done("ALSO_GOOD|2024-01-01")
    assert len(led) == 2
    # Only the unparseable line counts as corrupt — the blank line does not.
    assert led.corrupt_lines == 1


def test_load_skips_records_without_key(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"recordId": 1, "ts": 0}\n', encoding="utf-8")
    led = Ledger.load(path)
    assert len(led) == 0
    # Valid JSON without a "key" is skipped but is not corrupt.
    assert led.corrupt_lines == 0


def test_corrupt_lines_zero_on_clean_or_missing_ledger(tmp_path):
    assert Ledger.load(tmp_path / "missing.jsonl").corrupt_lines == 0
    path = tmp_path / "ledger.jsonl"
    led = Ledger.load(path)
    led.mark_done("MIC001|01/01/2024 00:00:00", 1)
    assert Ledger.load(path).corrupt_lines == 0


def test_reset_clears_memory_and_file(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger.load(path)
    led.mark_done("MIC001|date", 10)
    assert led.done("MIC001|date")

    led.reset()
    assert not led.done("MIC001|date")
    assert not path.exists()


def test_reset_on_empty_ledger_is_safe(tmp_path):
    led = Ledger.load(tmp_path / "ledger.jsonl")
    led.reset()  # should not raise


def test_make_key_is_backward_compatible_for_ordinary_values():
    # Ordinary ids/dates contain no '|' or '\', so the key must equal the original "id|date"
    # format — otherwise existing ledgers would stop matching and re-send processed rows.
    assert Ledger.make_key("MIC001", "01/01/2024 00:00:00") == "MIC001|01/01/2024 00:00:00"


def test_make_key_avoids_separator_collision():
    # A '|' inside a value must not collide across the id/date boundary.
    assert Ledger.make_key("ABC|DEF", "2024") != Ledger.make_key("ABC", "DEF|2024")


def test_make_key_treats_none_as_empty():
    # A missing exam date must produce an empty segment, not the literal string "None".
    assert Ledger.make_key("MIC001", None) == "MIC001|"
    assert Ledger.make_key(None, None) == "|"


def test_jsonl_format_is_correct(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger.load(path)
    led.mark_done("MIC001|01/01/2024 00:00:00", "rec-123")

    line = path.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["key"] == "MIC001|01/01/2024 00:00:00"
    assert rec["recordId"] == "rec-123"
    assert "ts" in rec
