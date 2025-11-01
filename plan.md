# Real-Time Direwolf Map Plan

## Objectives
- Deliver a minimum viable real-time map that renders Direwolf APRS packets in Leaflet with minimal infrastructure on a single Raspberry Pi.
- Normalize and enrich packet metadata just enough to plot markers with useful tooltips/status.
- Capture rtl-power signal readings on the APRS channel (e.g., 144.390 MHz) to correlate RF strength with packets.
- Grow toward a scalable architecture only if the single-node deployment needs to scale up later.

## Phase A – MVP Pipeline (Weeks 1-2)
- Harden `direwolf_csv_tail.py` for continuous local execution on the Pi (logging, watchdog, CLI flags).
- Run the tailer locally and stream JSON into a lightweight Node/FastAPI service on the same device that keeps packets in memory.
- Add a simple rtl-power monitor that samples the APRS channel on a fixed cadence and posts dB readings to the local service.
- Serve a Leaflet single-page app from the service; use Server-Sent Events/WebSocket to push new packets + latest RSSI to any browser pointed at the Pi.
- Implement basic map features: live markers, recent breadcrumb trail, hover tooltips with timestamp, path, and signal strength.
- Persist short-term history (e.g., 15 minutes) in memory; optionally dump to disk for manual backfill if needed.

## Phase B – MVP Hardening (Weeks 3-4)
- Package the Direwolf tailer, rtl-power monitor, and web service as systemd units for hands-off Pi startup.
- Add configurable filtering (callsign whitelist, bounding box) before events reach the map.
- Introduce minimal persistence (SQLite or flat JSONL) to recover data after Raspberry Pi reboots.
- Layer in basic auth/API keys for the SSE/WebSocket channel if remote viewing is exposed.
- Add smoke tests and a synthetic data generator to validate the map without live packets.

## Phase C – Scalable Architecture (Post-MVP)
- If the workload outgrows a single Pi, replace the in-memory buffer with a lightweight store (Redis, PostgreSQL) for reliability.
- Normalize positions (lat/lon, course/speed) and filter invalid packets.
- Align channel-power samples to APRS packets (time window + frequency) to calculate per-packet RSSI/quality metrics.
- Maintain current device state cache and archive historical tracks/RF metrics in a time-series store (TimescaleDB, InfluxDB).
- Build replay tooling and richer analytics endpoints once the data layer is solid.

## Phase D – Realtime Map Enhancements
- Expand Leaflet UI with filtering (callsign, symbol, geo fence) and session playback controls.
- Overlay per-station or per-packet RF strength indicators (color scale, sparkline, tooltip with dB reading).
- Add connection-state widgets, latency indicators, and alert banners for stale data.
- Integrate historical playback once persistence infrastructure from Phase C is available.

## Phase E – Deployment & Observability
- Create systemd runbooks (restart scripts, log rotation) tailored for the Raspberry Pi environment.
- Add lightweight monitoring (node exporter + Prometheus on-device, or external health check) to watch CPU, disk, and service uptime.
- If remote access is needed, provision TLS and dynamic DNS for the Pi.
- Document recovery steps for SD card corruption, power loss, or USB dongle issues.
- Schedule load tests and disaster-recovery rehearsals once Phase C is complete.

- Which local transport (Unix socket vs localhost HTTPS) is simplest and resilient on the Pi?
- Do we need offline buffering when the rtl-sdr or Direwolf process restarts?
- What data retention period is required for historical playback/reporting?
- What sampling cadence and averaging window gives reliable channel-power readings without exhausting CPU?
- How should we calibrate dB values across different dongles/antennas to keep readings comparable?
- Who are the consumers (local network only vs public Internet) and what auth model do they need?
- Any regulatory constraints on transmitting position data?

## Next Steps
1. Confirm local network access, browser clients, and latency targets for the Pi-hosted MVP.
2. Stand up the lightweight ingestion + Leaflet service on the Pi and validate it with replayed Direwolf logs.
3. Draft schemas for APRS packets and channel-power readings, including correlation keys.
4. Implement the rtl-power sampling script and confirm dB readings align with packet timestamps.
5. Create systemd unit files and deployment scripts so the stack auto-starts on Pi boot.
