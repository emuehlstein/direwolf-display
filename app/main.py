"""FastAPI application factory for Direwolf realtime streaming."""

from fastapi import FastAPI

from .config import get_settings
from .frontend import router as frontend_router
from .ingest import router as ingest_router
from .stations import router as stations_router
from .status import router as status_router
from .storage import BroadcastHub, InMemoryStore
from .stream import router as stream_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Direwolf Display Server", version="0.1.0")

    app.state.settings = settings
    app.state.store = InMemoryStore(
        retention_seconds=settings.history_retention_seconds,
        max_items=settings.max_history_items,
    )
    app.state.broadcast = BroadcastHub()

    app.include_router(frontend_router)
    app.include_router(status_router)
    app.include_router(stations_router, prefix="/v1")
    app.include_router(ingest_router, prefix="/v1")
    app.include_router(stream_router, prefix="/v1")

    return app
