"""Schemas for the background worker health and control endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkerHealthResponse(BaseModel):
    """Liveness summary for the background worker (no secrets)."""

    worker_name: str
    configured: bool = Field(description="Whether the worker is enabled in settings.")
    running: bool = Field(description="Whether a recent heartbeat indicates liveness.")
    paused: bool
    status: str
    cycle_count: int
    last_beat_at: datetime | None
    seconds_since_beat: float | None
    recent_failures: int
    detail: str | None = None


class WorkerControlResponse(BaseModel):
    """Result of a pause/resume control action."""

    worker_name: str
    paused: bool
    status: str
