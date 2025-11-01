from __future__ import annotations

import csv
import importlib.util
import os
from pathlib import Path
from typing import Iterator

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "direwolf_csv_tail.py"
SPEC = importlib.util.spec_from_file_location("direwolf_csv_tail", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)  # type: ignore[arg-type]


def load_fixture_row() -> dict[str, str]:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "2025-10-30.log"
    with fixture.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return next(reader)


def test_normalize_event_from_fixture() -> None:
    row = load_fixture_row()
    event = MODULE.normalize_event(row)

    assert event["timestamp"] == "2025-10-30T01:44:10Z"
    assert event["message_type"] == "packet"
    assert event["source_callsign"] == "KC9MHE-10"
    assert event["destination_callsign"] == "WA9NNN-10"
    assert event["error_count"] == 0
    assert event["audio"]["rms"] == 62
    assert event["audio"]["mark"] == 24
    assert event["audio"]["space"] == 17
    assert event["latitude"] == pytest.approx(41.978333)
    assert event["longitude"] == pytest.approx(-87.681833)


def test_parse_audio_level_variants() -> None:
    assert MODULE.parse_audio_level("62") == {"raw": "62", "rms": 62}
    assert MODULE.parse_audio_level("62(24/17)") == {
        "raw": "62(24/17)",
        "rms": 62,
        "mark": 24,
        "space": 17,
    }
    assert MODULE.parse_audio_level("bogus") == {"raw": "bogus"}
    assert MODULE.parse_audio_level(None) is None


def test_select_log_file_prefers_newest(tmp_path: Path) -> None:
    older = tmp_path / "older.log"
    newer = tmp_path / "newer.csv"
    older.write_text("chan,utime\n", encoding="utf-8")
    newer.write_text("chan,utime\n", encoding="utf-8")
    base = int(os.path.getmtime(older))
    os.utime(older, (base, base))
    os.utime(newer, (base + 10, base + 10))

    selected = MODULE.select_log_file(tmp_path, None)
    assert selected == newer


def test_iter_csv_records_reads_existing_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "sample.log"
    log_path.write_text(
        "chan,utime,isotime,source,heard,level,error\n"
        "0,1761788650,2025-10-30T01:44:10Z,KC9MHE-10,WA9NNN-10,62(24/17),0\n",
        encoding="utf-8",
    )

    records: Iterator[dict[str, str]] = MODULE.iter_csv_records(
        log_path, since_start=True, poll_interval=0.01
    )
    try:
        first = next(records)
    finally:
        closer = getattr(records, "close", None)
        if callable(closer):
            closer()

    assert first["source"] == "KC9MHE-10"
    assert first["heard"] == "WA9NNN-10"
