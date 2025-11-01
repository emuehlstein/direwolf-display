"""Server-Sent Events endpoint for realtime updates."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from .deps import get_app_settings, get_broadcast, get_store
from .models import StreamMessage
from .storage import BroadcastHub, InMemoryStore

router = APIRouter()


def _format_message(message: StreamMessage) -> str:
    payload = message.payload or {}
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {message.event_type}\ndata: {data}\n\n"


@router.get("/stream", tags=["stream"])
async def stream_updates(
    request: Request,
    store: InMemoryStore = Depends(get_store),
    hub: BroadcastHub = Depends(get_broadcast),
    settings=Depends(get_app_settings),
) -> StreamingResponse:
    """Return an SSE stream with recent history and new events."""

    heartbeat_interval = settings.sse_heartbeat_interval
    initial_messages = await store.snapshot_stream_events()
    queue = await hub.subscribe()

    async def event_publisher():
        try:
            for message in initial_messages:
                yield _format_message(message)

            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                except asyncio.TimeoutError:
                    heartbeat = StreamMessage(
                        event_type="heartbeat",
                        payload={"timestamp": datetime.now(timezone.utc).isoformat()},
                    )
                    yield _format_message(heartbeat)
                    continue
                yield _format_message(message)
        finally:
            await hub.unsubscribe(queue)

    return StreamingResponse(event_publisher(), media_type="text/event-stream")
