# Direwolf Display Server

This project packages a lightweight FastAPI backend plus tooling that turns
Direwolf APRS CSV logs into live SSE feeds and packet storage on something
small like a Raspberry Pi. Run the service, stream packets into it, and point a
Leaflet UI or other client at `/v1/stream` to watch updates in real time.

## Quick start

Install dependencies with [uv](https://github.com/astral-sh/uv) (Python 3.11+):

```bash
uv sync
```

Launch the FastAPI service through uv so it reuses the virtual environment it just created in `.venv/`:

```bash
uv run uvicorn app.main:create_app --factory --reload --port 9090
```

Hit `http://127.0.0.1:9090/healthz` to confirm it is up, and subscribe to the
live stream with:

```bash
curl -N http://127.0.0.1:9090/v1/stream
```

`/stats` returns current buffer counts, and the SSE channel pushes both the
recent history and live updates as JSON events.

Open `http://127.0.0.1:9090/` in a browser to launch the bundled Leaflet map.
It connects to the same `/v1/stream` feed, shows live packet markers, and
displays running totals from `/stats`. On load it pre-populates the map with
every station heard in the last hour using `GET /v1/stations`.

## Direwolf configuration

Add the following directives to `direwolf.conf` (adjust the paths to match your
system):

```
LOGDIR /var/log/direwolf
LOGFILE %Y-%m-%d.log
LOGFIXCSV 1
```
Restart `direwolf` or `direwolf.service` so the logger begins writing CSV rows
into `/var/log/direwolf/`.

## Feeding packets into the service

`uv run python tools/direwolf_csv_tail.py` tails the CSV logs, normalises each row, and now
supports posting packets directly to the FastAPI API. Typical usage on the same
host as Direwolf:

```bash
uv run python tools/direwolf_csv_tail.py \
  --log-dir /var/log/direwolf \
  --since-start \
  --post-url http://127.0.0.1:9090/v1 \
  --batch-size 25 \
  --no-stdout
```

Key flags:

- `--post-url`: Base URL for the backend. The script automatically appends
  `/packets` when needed.
- `--batch-size`: Send packets in small batches to reduce HTTP chatter.
- `--no-stdout`: Suppress JSON printing once packets are published via HTTP.
- `--pretty` and `--since-start` still work when you want to inspect output or
  replay from the beginning.

The script logs delivery issues but keeps tailing, so the buffer drains again
once the API is back online.

## Monitoring RSSI with rtl_power

`uv run python tools/rtl_power_monitor.py` wraps `rtl_power` to collect channel power readings
and forward them to the FastAPI `/v1/rssi` endpoint. Example invocation:

```bash
uv run python tools/rtl_power_monitor.py \
  --frequency-mhz 144.39 \
  --integration 5 \
  --post-url http://127.0.0.1:9090/v1 \
  --batch-size 6 \
  --no-stdout
```

Key options:

- `--span-khz`: sample a window around the center frequency instead of a single bin.
- `--integration`: integration time per `rtl_power` run (seconds); the script uses `-1`
  to exit after a single capture.
- `--interval`: delay between invocations if you want slower polling.
- `--gain` / `--ppm`: pass tuner gain or frequency correction straight to `rtl_power`.
- `--timezone`: choose the timezone applied to rtl_power timestamps (default UTC).

If you append `--simulate-rssi` to `tools/replay_fixture.py`, it will synthesize
RSSI samples from packet audio levels so the backend can be exercised without
hardware.

## Replaying fixtures

Use `uv run python tools/replay_fixture.py` to push an existing CSV into a running service
for testing or demos:

```bash
uv run python tools/replay_fixture.py tests/fixtures/2025-10-30.log \
  --endpoint http://127.0.0.1:9090
```

This batches packets behind the scenes and exercises the same `/v1/packets`
ingest path as the tailer.

## Event structure

Packet payloads mirror Direwolf’s columns with some normalization (ISO-8601
timestamps, parsed audio levels, float telemetry fields, source/destination
callsigns). RSSI samples use `/v1/rssi` and contain `timestamp`, `dbm`,
`frequency_mhz`, and optional metadata for rtl-power or other monitors. The SSE
stream emits events with types `packet`, `rssi`, and `heartbeat`, each carrying
the JSON payload that clients can consume directly.

## Testing

Install the development dependencies and run the automated tests:

```bash
uv sync --extra dev
uv run pytest
```

The suite exercises storage retention logic, ingest endpoints, SSE delivery,
and the replay helper’s synthetic RSSI path so regressions surface quickly.

## Next steps

- Build out the Leaflet frontend to visualise `/v1/stream` events.
- Wrap the FastAPI app, tailer, and rtl-power monitor in systemd units for the
  Raspberry Pi.
- Add real RSSI ingestion once the rtl-power sampling script is ready, then
  align packets and RF metrics for richer tooltips.
