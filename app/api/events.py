from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.services.domain_events import (
    RealtimeEventsUnavailable,
    get_realtime_client,
    iter_event_stream,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["Realtime events"])


@router.get("/stream")
def stream_domain_events(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
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

    # Authentication has already resolved the tenant and permissions. The
    # stream itself reads only Redis, so do not hold a synchronous SQLAlchemy
    # connection for the lifetime of this long-lived response. ``get_db`` is
    # also used by ``get_auth_context`` and FastAPI reuses that dependency
    # instance; closing it here is safe and the dependency cleanup remains
    # idempotent. The getattr guard keeps direct unit calls convenient.
    close = getattr(db, "close", None)
    if callable(close):
        close()

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
