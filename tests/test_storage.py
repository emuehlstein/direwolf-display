from datetime import datetime, timedelta, timezone

import pytest

from app.models import PacketEvent, RssiSample
from app.storage import InMemoryStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_store_discards_entries_outside_retention_window():
    store = InMemoryStore(retention_seconds=60, max_items=100)

    old_timestamp = utc_now() - timedelta(seconds=180)
    recent_timestamp = utc_now() - timedelta(seconds=10)

    await store.add_packet(PacketEvent(source_callsign="OLD", timestamp=old_timestamp))
    await store.add_packet(PacketEvent(source_callsign="RECENT", timestamp=recent_timestamp))

    packets = await store.get_recent_packets()
    callsigns = {packet.source_callsign for packet in packets}

    assert "RECENT" in callsigns
    assert "OLD" not in callsigns


@pytest.mark.asyncio
async def test_store_enforces_max_history_items():
    store = InMemoryStore(retention_seconds=3600, max_items=3)

    for index in range(5):
        await store.add_rssi(
            RssiSample(
                dbm=-50.0,
                frequency_mhz=144.39,
                timestamp=utc_now() + timedelta(seconds=index),
            )
        )

    samples = await store.get_recent_rssi()
    assert len(samples) == 3
    # Ensure only the newest timestamps remain.
    timestamps = [sample.timestamp for sample in samples]
    assert timestamps == sorted(timestamps)
