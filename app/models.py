"""Pydantic models for APRS packets, RSSI samples, and stream payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AudioInfo(BaseModel):
    raw: str
    rms: Optional[int] = None
    mark: Optional[int] = None
    space: Optional[int] = None


class PacketEvent(BaseModel):
    message_type: Literal["packet", "status", "telemetry"] = "packet"
    timestamp: Optional[datetime] = None
    unix_time: Optional[int] = Field(default=None, ge=0)
    channel: Optional[int] = Field(default=None, ge=0)
    source_callsign: Optional[str] = None
    destination_callsign: Optional[str] = None
    path: Optional[List[str]] = None
    dti: Optional[str] = None
    name: Optional[str] = None
    symbol: Optional[str] = None
    system: Optional[str] = None
    status: Optional[str] = None
    telemetry: Optional[str] = None
    comment: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    speed: Optional[float] = None
    course: Optional[float] = None
    altitude: Optional[float] = None
    frequency: Optional[float] = None
    offset: Optional[float] = None
    tone: Optional[float] = None
    audio: Optional[AudioInfo] = None
    audio_level: Optional[int] = None
    error_count: Optional[int] = Field(default=None, ge=0)
    raw_row: Optional[Dict[str, object]] = None

    model_config = ConfigDict(extra="ignore")

    @property
    def effective_datetime(self) -> datetime:
        if self.timestamp is not None:
            return _ensure_utc(self.timestamp)
        if self.unix_time is not None:
            return datetime.fromtimestamp(self.unix_time, tz=timezone.utc)
        return datetime.now(timezone.utc)


class RssiSample(BaseModel):
    timestamp: Optional[datetime] = None
    dbm: float = Field(..., description="Measured signal strength in dBm.")
    frequency_mhz: float = Field(..., description="Frequency the sample represents.")
    integration_ms: Optional[int] = Field(default=None, ge=1)
    metadata: Optional[Dict[str, object]] = None

    model_config = ConfigDict(extra="ignore")

    @property
    def effective_datetime(self) -> datetime:
        if self.timestamp is not None:
            return _ensure_utc(self.timestamp)
        return datetime.now(timezone.utc)


class StreamMessage(BaseModel):
    event_type: Literal["packet", "rssi", "heartbeat"]
    payload: Optional[Dict[str, object]] = None


class PacketIngestRequest(BaseModel):
    packets: List[PacketEvent]


class RssiIngestRequest(BaseModel):
    samples: List[RssiSample]


class IngestResponse(BaseModel):
    accepted: int


class StatsResponse(BaseModel):
    packets: int
    rssi_samples: int
    stations_tracked: int
    retention_seconds: int
    max_history_items: int
