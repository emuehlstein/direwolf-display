from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from tools.replay_fixture import post_events, post_rssi, simulate_rssi_samples

from app.main import create_app


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_packet_ingest_updates_stats_and_stream():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        packet_payload = {
            "timestamp": utc_iso(),
            "source_callsign": "TEST-1",
            "destination_callsign": "GATE",
            "message_type": "packet",
            "path": ["WIDE1-1", "GATE*"],
        }
        response = await client.post("/v1/packets", json={"packets": [packet_payload]})
        assert response.status_code == 200
        assert response.json()["accepted"] == 1

        stats = await client.get("/stats")
        body = stats.json()
        assert body["packets"] == 1
        assert body["stations_tracked"] == 1

        async with client.stream("GET", "/v1/stream") as stream:
            async for line in stream.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    assert "packet" in line
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:"))
                    assert payload["source_callsign"] == "TEST-1"
                    assert payload["path"] == ["WIDE1-1", "GATE*"]
                    break


@pytest.mark.asyncio
async def test_rssi_ingest_counts_samples():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        rssi_payload = {
            "timestamp": utc_iso(),
            "dbm": -42.5,
            "frequency_mhz": 144.39,
            "integration_ms": 500,
        }
        response = await client.post("/v1/rssi", json={"samples": [rssi_payload]})
        assert response.status_code == 200
        assert response.json()["accepted"] == 1

        stats = await client.get("/stats")
        assert stats.json()["rssi_samples"] == 1


@pytest.mark.asyncio
async def test_replay_helpers_post_packets_and_simulated_rssi():
    app = create_app()
    events = [
        {
            "timestamp": utc_iso(),
            "source_callsign": "SIM-1",
            "audio_level": 60,
            "message_type": "packet",
        },
        {
            "timestamp": utc_iso(),
            "source_callsign": "SIM-2",
            "message_type": "packet",
        },
    ]

    await post_events(events, "http://testserver", 10, app=app)
    samples = simulate_rssi_samples(events, frequency_mhz=144.39)
    assert len(samples) == 2
    await post_rssi(samples, "http://testserver", 10, app=app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        stats = await client.get("/stats")
        body = stats.json()
        assert body["packets"] == 2
        assert body["rssi_samples"] == 2


@pytest.mark.asyncio
async def test_frontend_served_from_root():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "leaflet" in response.text.lower()


@pytest.mark.asyncio
async def test_recent_stations_endpoint_returns_unique_latest_packets():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        base_payload = {
            "timestamp": utc_iso(),
            "source_callsign": "HOUR-1",
            "message_type": "packet",
            "latitude": 41.5,
            "longitude": -87.6,
            "path": ["WIDE2-1", "IGATE*"],
        }
        response = await client.post("/v1/packets", json={"packets": [base_payload]})
        assert response.status_code == 200

        stations = await client.get("/v1/stations?within_seconds=3600")
        assert stations.status_code == 200
        payload = stations.json()
        assert isinstance(payload, list)
        assert payload and payload[0]["source_callsign"] == "HOUR-1"
