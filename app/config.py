"""Application configuration models and helpers."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration for the FastAPI service."""

    history_retention_seconds: int = Field(
        default=60 * 60,
        ge=60,
        description="Retention window for packets/RSSI samples (seconds).",
    )
    max_history_items: int = Field(
        default=10_000,
        ge=1,
        description="Hard cap on ring buffer size to prevent unbounded growth.",
    )
    sse_heartbeat_interval: float = Field(
        default=15.0,
        gt=0,
        description="Seconds between heartbeat events for idle SSE clients.",
    )
    stats_include_history: bool = Field(
        default=True,
        description="Include history-derived counts in /stats responses.",
    )

    model_config = SettingsConfigDict(env_prefix="direwolf_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached settings instance for reuse across request handlers."""

    return AppSettings()
