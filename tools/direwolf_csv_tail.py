#!/usr/bin/env python3
"""Tail Direwolf CSV logs and emit JSON packet events."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from datetime import datetime, timezone
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import httpx

CSV_ENCODINGS: tuple[str, ...] = ("utf-8", "utf-8-sig", "latin-1")
LEVEL_RE = re.compile(r"^\s*(?P<rms>-?\d+)(?:\((?P<mark>-?\d+)\s*/\s*(?P<space>-?\d+)\))?\s*$")


def detect_encoding(path: Path) -> str:
    """Return the first encoding able to read the provided file."""
    for encoding in CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                handle.read(1024)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def parse_header(handle: io.TextIOBase) -> List[str]:
    """Read and return the CSV header row, skipping blank/comment lines."""
    while True:
        line = handle.readline()
        if not line:
            return []
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        reader = csv.reader([line])
        header = next(reader)
        return [column.strip() for column in header]


def parse_csv_line(line: str, fieldnames: List[str]) -> Optional[Dict[str, str]]:
    if not line.strip():
        return None
    try:
        reader = csv.DictReader(io.StringIO(line), fieldnames=fieldnames)
        row = next(reader)
    except (StopIteration, csv.Error):
        return None
    return row


def is_header_row(row: Dict[str, str], fieldnames: List[str]) -> bool:
    for name in fieldnames:
        if not name:
            continue
        if (row.get(name) or "").strip() != name:
            return False
    return True


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def coalesce_timestamp(row: Dict[str, str]) -> Optional[str]:
    iso = (row.get("isotime") or row.get("timestamp") or "").strip()
    if iso:
        return iso
    unix_value = parse_int(row.get("utime"))
    if unix_value is None:
        return None
    return datetime.fromtimestamp(unix_value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def parse_audio_level(level: Optional[str]) -> Optional[Dict[str, object]]:
    if not level:
        return None
    match = LEVEL_RE.match(level)
    if not match:
        return {"raw": level.strip()}
    result: Dict[str, object] = {"raw": level.strip()}
    rms = match.group("rms")
    if rms is not None:
        try:
            result["rms"] = int(rms)
        except ValueError:
            result["rms"] = rms
    mark = match.group("mark")
    if mark is not None:
        try:
            result["mark"] = int(mark)
        except ValueError:
            result["mark"] = mark
    space = match.group("space")
    if space is not None:
        try:
            result["space"] = int(space)
        except ValueError:
            result["space"] = space
    return result


def infer_message_type(row: Dict[str, str]) -> str:
    telemetry = (row.get("telemetry") or "").strip()
    if telemetry:
        return "telemetry"
    status = (row.get("status") or "").strip()
    if status:
        return "status"
    return "packet"


def normalize_event(row: Dict[str, str]) -> Dict[str, object]:
    cleaned = {key: (value.strip() if value is not None else "") for key, value in row.items()}
    event: Dict[str, object] = {"message_type": infer_message_type(cleaned)}

    timestamp = coalesce_timestamp(cleaned)
    if timestamp:
        event["timestamp"] = timestamp

    channel = parse_int(cleaned.get("chan"))
    if channel is not None:
        event["channel"] = channel

    unix_time = parse_int(cleaned.get("utime"))
    if unix_time is not None:
        event["unix_time"] = unix_time

    source = cleaned.get("source") or None
    if source:
        event["source_callsign"] = source
    heard = cleaned.get("heard") or None
    if heard:
        event["destination_callsign"] = heard

    event_keys = {
        "dti": "dti",
        "name": "name",
        "symbol": "symbol",
        "system": "system",
        "status": "status",
        "telemetry": "telemetry",
        "comment": "comment",
    }
    for source_key, target_key in event_keys.items():
        value = cleaned.get(source_key) or None
        if value:
            event[target_key] = value

    level_info = parse_audio_level(cleaned.get("level"))
    if level_info:
        event["audio"] = level_info
        if "rms" in level_info:
            event["audio_level"] = level_info["rms"]

    error_count = parse_int(cleaned.get("error"))
    if error_count is not None:
        event["error_count"] = error_count

    coordinate_fields = {
        "latitude": "latitude",
        "longitude": "longitude",
    }
    for key, target in coordinate_fields.items():
        value = parse_float(cleaned.get(key))
        if value is not None:
            event[target] = value

    optional_float_fields = {
        "speed": "speed",
        "course": "course",
        "altitude": "altitude",
        "frequency": "frequency",
        "offset": "offset",
        "tone": "tone",
    }
    for key, target in optional_float_fields.items():
        value = parse_float(cleaned.get(key))
        if value is not None:
            event[target] = value
        else:
            raw_value = cleaned.get(key)
            if raw_value:
                event[target] = raw_value

    path_fields = ("path", "via", "digipeaters", "route")
    for field_name in path_fields:
        path_value = cleaned.get(field_name)
        if path_value:
            components = [component.strip() for component in path_value.split(",") if component.strip()]
            if components:
                event["path"] = components
            break

    event["raw_row"] = dict(row)
    return event


def iter_csv_records(path: Path, *, since_start: bool, poll_interval: float) -> Iterator[Dict[str, str]]:
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as handle:
        fieldnames = parse_header(handle)
        if not fieldnames:
            return

        if since_start:
            for row in csv.DictReader(handle, fieldnames=fieldnames):
                if not row or is_header_row(row, fieldnames):
                    continue
                yield row
        else:
            handle.seek(0, 2)

        while True:
            position = handle.tell()
            line = handle.readline()
            if not line:
                time.sleep(poll_interval)
                handle.seek(position)
                continue
            row = parse_csv_line(line, fieldnames)
            if not row or is_header_row(row, fieldnames):
                continue
            yield row


def emit_event(event: Dict[str, object], pretty: bool) -> None:
    if pretty:
        print(json.dumps(event, indent=2))
    else:
        print(json.dumps(event, separators=(",", ":")))


def select_log_file(log_dir: Path, explicit: Optional[str]) -> Path:
    if explicit:
        target = (log_dir / explicit).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"Direwolf log '{target}' does not exist")
        return target

    candidates: list[Path] = []
    for pattern in ("*.csv", "*.log"):
        candidates.extend(path for path in log_dir.glob(pattern) if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"No Direwolf CSV logs found under {log_dir}")
    candidates.sort(key=lambda entry: entry.stat().st_mtime, reverse=True)
    return candidates[0]


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tail Direwolf CSV logs and emit JSON events.")
    parser.add_argument(
        "--log-dir",
        default="/var/log/direwolf",
        help="Directory containing Direwolf CSV logs (LOGDIR).",
    )
    parser.add_argument(
        "--log-file",
        help="Specific CSV/LOG file inside LOGDIR to tail (default: newest *.log).",
    )
    parser.add_argument(
        "--since-start",
        action="store_true",
        help="Replay the entire CSV before following appended rows.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output instead of dense JSON Lines.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Tail poll interval in seconds when waiting for new rows.",
    )
    parser.add_argument(
        "--post-url",
        help="If provided, POST packets to the FastAPI service at this base URL (e.g., http://127.0.0.1:9090/v1/packets).",
    )
    parser.add_argument(
        "--post-timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds for POST requests when --post-url is used.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of packets per HTTP request when posting to the service.",
    )
    parser.add_argument(
        "--no-stdout",
        action="store_true",
        help="Suppress printing packets to stdout (useful when posting to the API).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser.parse_args(argv)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


@contextmanager
def http_client(post_url: Optional[str], timeout: float) -> Iterable[Optional[httpx.Client]]:
    if not post_url:
        yield None
        return
    timeout_config = httpx.Timeout(timeout)
    with httpx.Client(timeout=timeout_config) as client:
        yield client


def post_packets(client: httpx.Client, url: str, packets: Sequence[Dict[str, object]]) -> None:
    payload = {"packets": list(packets)}
    response = client.post(url, json=payload)
    response.raise_for_status()


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger("direwolf_csv_tail")

    log_dir = Path(args.log_dir).expanduser()
    target = select_log_file(log_dir, args.log_file)

    if args.post_url and not args.post_url.endswith("/packets"):
        post_url = args.post_url.rstrip("/") + "/packets"
    else:
        post_url = args.post_url

    batch: List[Dict[str, object]] = []

    try:
        with http_client(post_url, args.post_timeout) as client:
            for row in iter_csv_records(target, since_start=args.since_start, poll_interval=args.poll_interval):
                event = normalize_event(row)
                if not args.no_stdout:
                    emit_event(event, pretty=args.pretty)
                if client and post_url:
                    batch.append(event)
                    if len(batch) >= max(1, args.batch_size):
                        try:
                            post_packets(client, post_url, batch)
                            logger.debug("Posted %d packets", len(batch))
                        except Exception as exc:
                            logger.error("Failed to post packets: %s", exc)
                        finally:
                            batch.clear()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return 1
    if batch and post_url:
        with http_client(post_url, args.post_timeout) as client:
            if client:
                try:
                    post_packets(client, post_url, batch)
                    logger.debug("Posted %d packets during shutdown flush", len(batch))
                except Exception as exc:
                    logger.error("Failed to post packets during shutdown flush: %s", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
