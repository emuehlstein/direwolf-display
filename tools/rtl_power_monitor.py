#!/usr/bin/env python3
"""Invoke rtl_power, parse RSSI samples, and forward them to the FastAPI service."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import httpx
from zoneinfo import ZoneInfo


DEFAULT_FREQ_MHZ = 144.39


@dataclass
class SampleResult:
    timestamp: str
    dbm: float
    frequency_mhz: float
    integration_ms: int
    metadata: dict[str, object]


def build_frequency_argument(frequency_mhz: float, span_khz: float, bin_width_hz: int) -> str:
    center_hz = frequency_mhz * 1_000_000
    if span_khz > 0:
        span_hz = span_khz * 1_000
        half_span = span_hz / 2
        start_hz = int(center_hz - half_span)
        stop_hz = int(center_hz + half_span)
    else:
        start_hz = stop_hz = int(center_hz)
    return f"{start_hz}:{stop_hz}:{bin_width_hz}"


def parse_rtl_power_line(
    line: str,
    *,
    integration_ms: int,
    tz: ZoneInfo,
) -> Optional[SampleResult]:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    parts = [segment.strip() for segment in raw.split(",")]
    if len(parts) < 7:
        return None

    date_part, time_part = parts[0], parts[1]
    try:
        timestamp = datetime.fromisoformat(f"{date_part}T{time_part}")
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=tz)
    else:
        timestamp = timestamp.astimezone(tz)

    try:
        start_hz = int(float(parts[2]))
        stop_hz = int(float(parts[3]))
        bin_width_hz = int(float(parts[4]))
        bin_count = int(float(parts[5]))
    except ValueError:
        return None

    bin_values: List[float] = []
    for entry in parts[6:]:
        if not entry:
            continue
        try:
            bin_values.append(float(entry))
        except ValueError:
            continue

    if not bin_values:
        return None

    average_dbm = sum(bin_values) / len(bin_values)
    metadata = {
        "start_hz": start_hz,
        "stop_hz": stop_hz,
        "bin_width_hz": bin_width_hz,
        "bin_count": bin_count,
        "max_dbm": max(bin_values),
        "min_dbm": min(bin_values),
    }

    midpoint_hz = (start_hz + stop_hz) / 2
    return SampleResult(
        timestamp=timestamp.isoformat(),
        dbm=average_dbm,
        frequency_mhz=midpoint_hz / 1_000_000,
        integration_ms=integration_ms,
        metadata=metadata,
    )


def parse_output(
    stdout: str,
    *,
    integration_ms: int,
    tz: ZoneInfo,
) -> List[SampleResult]:
    samples: List[SampleResult] = []
    for line in stdout.splitlines():
        sample = parse_rtl_power_line(line, integration_ms=integration_ms, tz=tz)
        if sample:
            samples.append(sample)
    return samples


def build_command(args: argparse.Namespace) -> List[str]:
    freq_arg = build_frequency_argument(args.frequency_mhz, args.span_khz, args.bin_width_hz)
    command = [args.rtl_power]
    command.extend(["-f", freq_arg])
    command.extend(["-i", str(args.integration)])
    command.append("-1")
    if args.gain is not None:
        command.extend(["-g", str(args.gain)])
    if args.ppm is not None:
        command.extend(["-p", str(args.ppm)])
    if args.additional:
        command.extend(args.additional)
    return command


def run_rtl_power(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


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


def emit_sample(sample: SampleResult, *, pretty: bool) -> None:
    payload = {
        "timestamp": sample.timestamp,
        "dbm": sample.dbm,
        "frequency_mhz": sample.frequency_mhz,
        "integration_ms": sample.integration_ms,
        "metadata": sample.metadata,
    }
    if pretty:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps(payload, separators=(",", ":")))


def post_samples(client: httpx.Client, url: str, samples: Sequence[SampleResult]) -> None:
    payload = {"samples": [sample.__dict__ for sample in samples]}
    response = client.post(url, json=payload)
    response.raise_for_status()


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample RF power using rtl_power and forward RSSI readings.")
    parser.add_argument("--rtl-power", default="rtl_power", help="Path to the rtl_power binary.")
    parser.add_argument(
        "--frequency-mhz",
        type=float,
        default=DEFAULT_FREQ_MHZ,
        help="Center frequency to sample in MHz.",
    )
    parser.add_argument(
        "--span-khz",
        type=float,
        default=0.0,
        help="Span around the center frequency in kHz (default: 0 for single-bin samples).",
    )
    parser.add_argument(
        "--bin-width-hz",
        type=int,
        default=2000,
        help="Bin width in Hz for rtl_power sampling.",
    )
    parser.add_argument(
        "--integration",
        type=float,
        default=5.0,
        help="Integration time per measurement in seconds.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="Seconds to sleep between measurements (in addition to integration time).",
    )
    parser.add_argument("--gain", type=float, help="Tuner gain passed to rtl_power (-g).")
    parser.add_argument("--ppm", type=float, help="Frequency correction PPM for rtl_power (-p).")
    parser.add_argument(
        "--count",
        type=int,
        help="Number of measurements to perform. Omit for continuous operation.",
    )
    parser.add_argument(
        "--timezone",
        default="UTC",
        help="Timezone name for rtl_power timestamps (default: UTC).",
    )
    parser.add_argument(
        "--no-stdout",
        action="store_true",
        help="Suppress printing samples to stdout when posting to the API.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON when stdout is enabled.",
    )
    parser.add_argument(
        "--post-url",
        help="If provided, POST samples to the FastAPI service at this base URL (e.g., http://127.0.0.1:9090/v1/rssi).",
    )
    parser.add_argument(
        "--post-timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds when posting to the service.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of samples per HTTP request when posting to the service.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "additional",
        nargs=argparse.REMAINDER,
        help="Any extra arguments passed to rtl_power after a '--' separator.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger("rtl_power_monitor")

    integration_ms = int(args.integration * 1000)
    try:
        tz = ZoneInfo(args.timezone)
    except Exception:  # noqa: BLE001
        logger.warning("Unknown timezone '%s', defaulting to UTC", args.timezone)
        tz = ZoneInfo("UTC")

    if args.post_url and not args.post_url.endswith("/rssi"):
        post_url = args.post_url.rstrip("/") + "/rssi"
    else:
        post_url = args.post_url

    batch: List[SampleResult] = []
    iterations = 0

    try:
        with http_client(post_url, args.post_timeout) as client:
            while True:
                command = build_command(args)
                logger.debug("Running command: %s", " ".join(command))
                result = run_rtl_power(command)
                if result.returncode != 0:
                    logger.error("rtl_power exited with %s: %s", result.returncode, result.stderr.strip())
                samples = parse_output(result.stdout, integration_ms=integration_ms, tz=tz)
                if not samples:
                    logger.debug("No samples parsed from rtl_power output.")
                for sample in samples:
                    if not args.no_stdout:
                        emit_sample(sample, pretty=args.pretty)
                    if client and post_url:
                        batch.append(sample)
                        if len(batch) >= max(1, args.batch_size):
                            try:
                                post_samples(client, post_url, batch)
                                logger.debug("Posted %d RSSI samples", len(batch))
                            except Exception as exc:  # noqa: BLE001
                                logger.error("Failed to post RSSI samples: %s", exc)
                            finally:
                                batch.clear()
                iterations += 1
                if args.count and iterations >= args.count:
                    break
                if args.interval > 0:
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error: %s", exc)
        return 1

    if batch and post_url:
        with http_client(post_url, args.post_timeout) as client:
            if client:
                try:
                    post_samples(client, post_url, batch)
                    logger.debug("Posted %d samples during shutdown flush", len(batch))
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to post samples during shutdown flush: %s", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
