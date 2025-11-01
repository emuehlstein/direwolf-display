"""Health and stats endpoints."""

from fastapi import APIRouter, Depends

from .deps import get_app_settings, get_store
from .models import StatsResponse
from .storage import InMemoryStore

router = APIRouter()


@router.get("/healthz", tags=["status"])
async def healthz() -> dict[str, str]:
    """Simple health check for uptime monitoring."""

    return {"status": "ok"}


@router.get("/stats", response_model=StatsResponse, tags=["status"])
async def stats(
    store: InMemoryStore = Depends(get_store),
    settings=Depends(get_app_settings),
) -> StatsResponse:
    """Return basic counts for packets, RSSI samples, and tracked stations."""

    counts = await store.stats()
    return StatsResponse(
        packets=counts["packets"],
        rssi_samples=counts["rssi_samples"],
        stations_tracked=counts["stations_tracked"],
        retention_seconds=settings.history_retention_seconds,
        max_history_items=settings.max_history_items,
    )
