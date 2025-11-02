"""Utility helpers for generating APRS-IS passcodes from a callsign.

The algorithm is the classic 0x73E2 XOR method used by aprs.fi and Direwolf.
"""

from __future__ import annotations

import argparse
import re
import sys

CALLSIGN_PATTERN = re.compile(r"^[A-Z0-9]{1,6}(?:-[0-9A-Z]{1,2})?$")


def normalize_callsign(callsign: str) -> str:
    """Return an uppercase callsign trimmed to the APRS base form."""
    normalized = callsign.strip().upper()
    base = normalized.split("-", 1)[0]
    return base


def validate_callsign(callsign: str) -> str:
    """Validate the callsign shape raises ValueError on failure."""
    normalized = callsign.strip().upper()
    if not normalized:
        raise ValueError("Callsign cannot be empty")
    if not CALLSIGN_PATTERN.match(normalized):
        raise ValueError(f"Invalid callsign format: {callsign!r}")
    return normalized


def generate_passcode(callsign: str) -> int:
    """Generate the APRS-IS passcode for the given callsign."""
    validate_callsign(callsign)
    base = normalize_callsign(callsign)
    code = 0x73E2
    for i in range(0, len(base), 2):
        code ^= ord(base[i]) << 8
        if i + 1 < len(base):
            code ^= ord(base[i + 1])
    return code & 0x7FFF


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate APRS-IS passcode from a callsign",
    )
    parser.add_argument(
        "--callsign",
        required=True,
        help="Amateur radio callsign (optionally with SSID, e.g. N0CALL-10)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        code = generate_passcode(args.callsign)
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    print(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
