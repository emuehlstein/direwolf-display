from zoneinfo import ZoneInfo

from tools.rtl_power_monitor import (
    build_command,
    build_frequency_argument,
    parse_output,
    parse_rtl_power_line,
)


def test_build_frequency_argument_single_bin():
    freq_arg = build_frequency_argument(144.39, 0.0, 2000)
    assert freq_arg == "144390000:144390000:2000"


def test_build_frequency_argument_with_span():
    freq_arg = build_frequency_argument(10.0, 50.0, 1000)
    # 10 MHz +/- 25 kHz
    assert freq_arg == "9975000:10025000:1000"


def test_parse_rtl_power_line_returns_sample():
    line = "2025-10-30, 02:01:50, 144390000, 144390000, 2000, 1, -55.0"
    sample = parse_rtl_power_line(line, integration_ms=5000, tz=ZoneInfo("UTC"))
    assert sample is not None
    assert sample.frequency_mhz == 144.39
    assert abs(sample.dbm - (-55.0)) < 1e-6
    assert sample.metadata["bin_width_hz"] == 2000
    assert sample.integration_ms == 5000


def test_parse_output_ignores_comments():
    output = "# header line\n2025-10-30, 02:01:50, 144390000, 144390000, 2000, 1, -42.0"
    samples = parse_output(output, integration_ms=1000, tz=ZoneInfo("UTC"))
    assert len(samples) == 1


def test_build_command_includes_optional_fields():
    args = type(
        "Args",
        (),
        {
            "rtl_power": "/usr/bin/rtl_power",
            "frequency_mhz": 144.39,
            "span_khz": 0.0,
            "bin_width_hz": 2000,
            "integration": 2.5,
            "gain": 20.5,
            "ppm": 1.2,
            "additional": ["--some-flag"],
        },
    )()
    command = build_command(args)
    assert command[0] == "/usr/bin/rtl_power"
    assert "-f" in command and "-g" in command and "-p" in command
    assert command[-1] == "--some-flag"
