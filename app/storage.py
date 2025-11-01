"""In-memory storage for APRS packets and RSSI samples."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List

from .models import PacketEvent, RssiSample, StreamMessage


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BroadcastHub:
    """Simple asyncio-based publish/subscribe hub for stream events."""

    def __init__(self) -> None:
        self._listeners: set[asyncio.Queue[StreamMessage]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[StreamMessage]:
        queue: asyncio.Queue[StreamMessage] = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._listeners.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[StreamMessage]) -> None:
        async with self._lock:
            self._listeners.discard(queue)

    async def publish(self, message: StreamMessage) -> None:
        async with self._lock:
            listeners = list(self._listeners)
        for queue in listeners:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the oldest item to make room, then enqueue the latest.
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    # Listener is completely overwhelmed; skip this message.
                    continue


class InMemoryStore:
    """Retention-limited storage for packets and RSSI samples."""

    def __init__(self, *, retention_seconds: int, max_items: int) -> None:
        self._packets: Deque[PacketEvent] = deque()
        self._rssi: Deque[RssiSample] = deque()
        self._last_seen_by_station: Dict[str, PacketEvent] = {}
        self._retention = timedelta(seconds=retention_seconds)
        self._max_items = max_items
        self._lock = asyncio.Lock()

    async def add_packet(self, packet: PacketEvent) -> None:
        async with self._lock:
            self._packets.append(packet)
            if packet.source_callsign:
                self._last_seen_by_station[packet.source_callsign] = packet
            self._trim(self._packets, prune_last_seen=True)

    async def add_rssi(self, sample: RssiSample) -> None:
        async with self._lock:
            self._rssi.append(sample)
            self._trim(self._rssi)

    async def get_recent_packets(self) -> List[PacketEvent]:
        async with self._lock:
            return list(self._packets)

    async def get_recent_rssi(self) -> List[RssiSample]:
        async with self._lock:
            return list(self._rssi)

    async def get_last_seen(self) -> Dict[str, PacketEvent]:
        async with self._lock:
            return dict(self._last_seen_by_station)

    async def snapshot_stream_events(self) -> List[StreamMessage]:
        """Return packets and RSSI samples as stream messages for replay."""

        async with self._lock:
            entries: List[tuple[datetime, StreamMessage]] = []
            for packet in self._packets:
                entries.append(
                    (packet.effective_datetime, StreamMessage(event_type="packet", payload=packet.model_dump(mode="json")))
                )
            for sample in self._rssi:
                entries.append(
                    (sample.effective_datetime, StreamMessage(event_type="rssi", payload=sample.model_dump(mode="json")))
                )
        entries.sort(key=lambda item: item[0])
        return [message for _, message in entries]

    async def stats(self) -> Dict[str, object]:
        async with self._lock:
            return {
                "packets": len(self._packets),
                "rssi_samples": len(self._rssi),
                "stations_tracked": len(self._last_seen_by_station),
            }

    def _trim(self, collection: Deque[PacketEvent | RssiSample], *, prune_last_seen: bool = False) -> None:
        cutoff = _now() - self._retention
        while collection and self._is_stale(collection[0], cutoff):
            collection.popleft()
        while len(collection) > self._max_items:
            collection.popleft()
        if prune_last_seen:
            self._prune_last_seen(cutoff)

    @staticmethod
    def _is_stale(item: PacketEvent | RssiSample, cutoff: datetime) -> bool:
        return item.effective_datetime < cutoff

    def _prune_last_seen(self, cutoff: datetime) -> None:
        stale_callsigns = [
            callsign
            for callsign, packet in self._last_seen_by_station.items()
            if packet.effective_datetime < cutoff
        ]
        for callsign in stale_callsigns:
            self._last_seen_by_station.pop(callsign, None)

    async def recent_stations(self, since: datetime) -> Dict[str, PacketEvent]:
        async with self._lock:
            return {
                callsign: packet
                for callsign, packet in self._last_seen_by_station.items()
                if packet.effective_datetime >= since
            }
