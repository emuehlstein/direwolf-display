"""Endpoints exposing station history snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query

from .deps import get_store
from .models import PacketEvent
from .storage import InMemoryStore

router = APIRouter()


@router.get("/stations", response_model=List[PacketEvent], tags=["stations"])
async def list_recent_stations(
    within_seconds: int = Query(3600, ge=60, le=24 * 60 * 60),
    store: InMemoryStore = Depends(get_store),
) -> List[PacketEvent]:
    """Return stations heard within the requested time window."""

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
    stations = await store.recent_stations(cutoff)
    return list(stations.values())
