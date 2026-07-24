from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.dependencies.auth import AuthContext, get_auth_context
from app.services.domain_events import (
    RealtimeEventsUnavailable,
    get_realtime_client,
    iter_event_stream,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["Realtime events"])


@router.get("/stream")
def stream_domain_events(context: AuthContext = Depends(get_auth_context)):
    """Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed APIs."""

    try:
        client = get_realtime_client()
    except RealtimeEventsUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Realtime event backend unavailable",
        ) from exc
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Realtime event backend unavailable",
        )

    settings = get_settings()
    heartbeat_seconds = max(5, min(int(settings.REALTIME_EVENTS_HEARTBEAT_SECONDS), 60))
    return StreamingResponse(
        iter_event_stream(context.hotel_id, client, heartbeat_seconds=heartbeat_seconds),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
