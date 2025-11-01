"""FastAPI dependency helpers."""

from fastapi import Request

from .config import AppSettings, get_settings
from .storage import BroadcastHub, InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    """Return the shared in-memory storage."""

    return request.app.state.store


def get_broadcast(request: Request) -> BroadcastHub:
    """Return the shared publish/subscribe hub."""

    return request.app.state.broadcast


def get_app_settings(_: Request) -> AppSettings:
    """Expose cached settings through dependency injection."""

    return get_settings()
