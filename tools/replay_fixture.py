"""Replay Direwolf CSV fixtures into the FastAPI service."""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import httpx
from httpx import ASGITransport

try:  # Prefer package-relative import when available.
    from .direwolf_csv_tail import detect_encoding, normalize_event  # type: ignore
except ImportError:  # Fallback for direct script execution.
    from direwolf_csv_tail import detect_encoding, normalize_event


def read_events(path: Path) -> List[dict]:
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        events = [normalize_event(row) for row in reader if row]
    return events


async def post_events(
    events: List[dict],
    endpoint: str,
    batch_size: int,
    *,
    app: Optional[object] = None,
) -> None:
    transport = ASGITransport(app=app) if app is not None else None
    async with httpx.AsyncClient(transport=transport, base_url=endpoint) as client:
        for start in range(0, len(events), batch_size):
            chunk = events[start : start + batch_size]
            payload = {"packets": chunk}
            response = await client.post("/v1/packets", json=payload, timeout=15)
            response.raise_for_status()


def _event_timestamp(event: dict) -> Optional[str]:
    timestamp = event.get("timestamp")
    if timestamp:
        return timestamp
    unix_time = event.get("unix_time")
    if unix_time is not None:
        return datetime.fromtimestamp(float(unix_time), tz=timezone.utc).isoformat()
    return None


def simulate_rssi_samples(events: List[dict], *, frequency_mhz: float) -> List[dict]:
    samples: List[dict] = []
    for event in events:
        timestamp = _event_timestamp(event)
        if not timestamp:
            continue
        audio_level = event.get("audio_level") or event.get("audio", {}).get("rms")
        base_dbm = -120.0
        if audio_level is not None:
            try:
                base_dbm = -160.0 + float(audio_level)
            except (TypeError, ValueError):
                base_dbm = -120.0
        samples.append(
            {
                "timestamp": timestamp,
                "dbm": base_dbm,
                "frequency_mhz": frequency_mhz,
                "metadata": {"source": "simulated", "packet_source": event.get("source_callsign")},
            }
        )
    return samples


async def post_rssi(
    samples: List[dict],
    endpoint: str,
    batch_size: int,
    *,
    app: Optional[object] = None,
) -> None:
    if not samples:
        return
    transport = ASGITransport(app=app) if app is not None else None
    async with httpx.AsyncClient(transport=transport, base_url=endpoint) as client:
        for start in range(0, len(samples), batch_size):
            chunk = samples[start : start + batch_size]
            payload = {"samples": chunk}
            response = await client.post("/v1/rssi", json=payload, timeout=15)
            response.raise_for_status()


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Direwolf CSV packets into the FastAPI service.")
    parser.add_argument("csv", type=Path, help="Path to the Direwolf CSV/LOG fixture.")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:9090",
        help="Base URL for the FastAPI service (default: http://127.0.0.1:9090).",
    )
    parser.add_argument("--batch-size", type=int, default=50, help="Number of packets per POST request.")
    parser.add_argument(
        "--simulate-rssi",
        action="store_true",
        help="Derive synthetic RSSI samples from packet audio levels and ingest them.",
    )
    parser.add_argument(
        "--rssi-frequency",
        type=float,
        default=144.39,
        help="Frequency in MHz to assign to simulated RSSI samples.",
    )
    parser.add_argument(
        "--rssi-batch-size",
        type=int,
        default=50,
        help="Number of RSSI samples per POST request when --simulate-rssi is used.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    events = read_events(args.csv)
    if not events:
        print("No events found in fixture.")
        return 0
    asyncio.run(post_events(events, args.endpoint, args.batch_size))
    print(f"Replayed {len(events)} packets to {args.endpoint}/v1/packets")

    if args.simulate_rssi:
        samples = simulate_rssi_samples(events, frequency_mhz=args.rssi_frequency)
        if samples:
            asyncio.run(post_rssi(samples, args.endpoint, args.rssi_batch_size))
            print(f"Replayed {len(samples)} RSSI samples to {args.endpoint}/v1/rssi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
