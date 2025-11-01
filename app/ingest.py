"""REST endpoints for packet and RSSI ingestion."""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Depends

from .deps import get_broadcast, get_store
from .models import (
    IngestResponse,
    PacketEvent,
    PacketIngestRequest,
    RssiIngestRequest,
    RssiSample,
    StreamMessage,
)
from .storage import BroadcastHub, InMemoryStore

router = APIRouter()


PacketsPayload = Union[PacketIngestRequest, PacketEvent]


@router.post("/packets", response_model=IngestResponse, tags=["ingest"])
async def ingest_packets(
    payload: PacketsPayload,
    store: InMemoryStore = Depends(get_store),
    hub: BroadcastHub = Depends(get_broadcast),
) -> IngestResponse:
    """Accept APRS packets and broadcast them to connected clients."""

    packets = payload.packets if isinstance(payload, PacketIngestRequest) else [payload]
    accepted = 0
    for packet in packets:
        await store.add_packet(packet)
        message = StreamMessage(event_type="packet", payload=packet.model_dump(mode="json"))
        await hub.publish(message)
        accepted += 1
    return IngestResponse(accepted=accepted)


@router.post("/rssi", response_model=IngestResponse, tags=["ingest"])
async def ingest_rssi(
    payload: RssiIngestRequest,
    store: InMemoryStore = Depends(get_store),
    hub: BroadcastHub = Depends(get_broadcast),
) -> IngestResponse:
    """Accept RSSI samples from rtl-power or similar monitors."""

    accepted = 0
    for sample in payload.samples:
        await store.add_rssi(sample)
        message = StreamMessage(event_type="rssi", payload=sample.model_dump(mode="json"))
        await hub.publish(message)
        accepted += 1
    return IngestResponse(accepted=accepted)
