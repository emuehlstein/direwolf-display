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

## Running under systemd

The repository includes a sample unit file at `infra/systemd/direwolf-display.service`.
Update the `WorkingDirectory`, `User`, and `Group` fields for your deployment,
copy it into `/etc/systemd/system/`, then enable it:

```bash
sudo cp infra/systemd/direwolf-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now direwolf-display
```

To feed packets automatically, install the tailer unit as well:

```bash
sudo cp infra/systemd/direwolf-tail.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now direwolf-tail
```

## Automated provisioning (Ansible)

For hands-free Raspberry Pi setup, use the playbook in `infra/ansible/site.yml`.
It installs required apt packages, syncs this repository to `/opt/direwolf-display`,
creates the uv environment, configures Direwolf (including PTT, optional Digi/iGate
rules, and SA818 programming), and enables the systemd units.

```bash
ansible-galaxy collection install ansible.posix
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/site.yml \
  --extra-vars "direwolf_display_repo_src=$(pwd)"
```

### Pi first-boot helper

`scripts/firstrun.sh` wraps cloning plus provisioning so you can seed station
details during the initial boot:

```bash
sudo ./scripts/firstrun.sh \
  --callsign N0CALL-10 \
  --profile shari_usb \
  --lat 33.7991 \
  --lon -84.2935 \
  --comment "ShariPi IGate" \
  --digipeater \
  --rx-igate \
  --dest /opt/direwolf-display-src
```

Flags you might care about:

- `--callsign`: seeds the `MYCALL` line in Direwolf and, when `--rx-igate` is
  supplied, doubles as the APRS-IS login/passcode seed.
- `--profile`: selects hardware presets (`shari_usb`, `digirig_mobile`, or `rtlsdr`).
- `--lat` / `--lon`: decimal-degree coordinates converted to APRS `DD^MM.mmH`
  format for RF and IG beacons.
- `--comment`: APRS status comment broadcast in both beacons.
- `--tx-delay`, `--tx-tail`, `--dwait`, `--tx-level`: tune Direwolf key-up delay,
  hang time, post-carrier wait, and audio output level without editing templates.
- `--digipeater`: enables a WIDEn-N-rule by default; use the `--digipeater-*`
  overrides to supply custom match/replace/options.
- `--rx-igate`: connects to APRS-IS (default rotate: `noam.aprs2.net`); combine
  with `--igate-login`, `--igate-filter`, and `--igate-server` to tune behaviour.
- `--igate-passcode`: optional; if omitted we derive the standard APRS-IS passcode
  from the login (or callsign).

`digirig_mobile` currently mirrors the `shari_usb` defaults so you can refine
audio/PTT settings later. The `rtlsdr` profile turns the stack into a receive-only
IGate: it pipes `rtl_fm` audio into Direwolf, disables RF beaconing/PTT, and
starts the bundled `rtl_power` monitor to feed RSSI samples into the backend.

The script accepts `--dest` when you want the repository in a different path.
If the path already exists it skips the clone and just invokes the post-install
step.

### Post-install provisioning script

`scripts/pi_postinstall.sh` is what the first-run helper calls. It can be used
independently on a Pi that already has this repository checked out:

```bash
sudo ./scripts/pi_postinstall.sh \
  --callsign N0CALL-10 \
  --profile shari_usb \
  --lat 33.7991 \
  --lon -84.2935 \
  --comment "ShariPi IGate" \
  --digipeater \
  --rx-igate \
  /opt/direwolf-display-src
```

Highlights:

- Writes `/etc/direwolf.conf` using `infra/templates/direwolf.conf.j2`, including
  SharPi audio defaults (`plughw:2,0`), PTT via the CM108 GPIO (or disabling PTT
  for receive-only profiles), optional digipeater rules, APRS-IS settings, and RF/IG PBEACON entries when coordinates
  are supplied.
- Installs the `direwolf.service`, `direwolf-display.service`, and `direwolf-tail.service`
  units and reloads systemd.
- When the `rtlsdr` profile is selected, also enables `rtl-power.service` and the
  bundled rtl_fm audio pipeline for receive-only IGate operation.
- Installs the `sa818` Python package and configures the SA818-based SharPi:
  `scripts/run_direwolf.sh` auto-programs frequency, squelch, bandwidth, tones,
  and filters via `uv run -- sa818 …` before launching Direwolf.
- Generates the APRS-IS passcode automatically when `--rx-igate` is enabled and a
  login (or callsign) is available; you can still supply `--igate-passcode` to force
  a specific key.

### Raspberry Pi Imager integration

When customising Raspberry Pi Imager, reference `scripts/firstrun.sh` in the
run-on-first-boot hook so the Pi clones this repository and provisions itself:

```bash
curl -fsSL https://github.com/emuehlstein/direwolf-display/archive/refs/heads/main.tar.gz \
  | tar -xz --strip-components=1 -C /opt/direwolf-display-src && \
sudo bash /opt/direwolf-display-src/scripts/firstrun.sh --callsign N0CALL-10 --profile shari_usb --digipeater --rx-igate
```

After the first boot completes, tail the services to confirm healthy startup:

```bash
journalctl -u direwolf-display -u direwolf-tail -f
```

3. **Validate**: open `http://<pi-hostname>:9090/` to view the map, and confirm
   `/stats` increments as packets arrive.

Before running the playbook, edit `infra/templates/direwolf.conf.j2` to set your
callsign, tactical aliases, and audio device names so the rendered `/etc/direwolf.conf`
matches the station you are deploying.

## Next steps

- Build out the Leaflet frontend to visualise `/v1/stream` events.
- Wrap the FastAPI app, tailer, and rtl-power monitor in systemd units for the
  Raspberry Pi.
- Add real RSSI ingestion once the rtl-power sampling script is ready, then
  align packets and RF metrics for richer tooltips.
