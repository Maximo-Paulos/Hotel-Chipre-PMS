from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.database import get_session_factory
from app.dependencies.auth import AuthContext, get_auth_context
from app.schemas.domain_event import DomainEventRecoveryResponse
from app.services.domain_events import (
    RealtimeEventsUnavailable,
    get_domain_event_recovery,
    get_realtime_client,
    iter_event_stream,
)
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.services.tenant_context import set_tenant_user_context


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["Realtime events"])


@router.get("/recovery", response_model=DomainEventRecoveryResponse)
def recover_domain_events(
    after_cursor: int | None = Query(
        default=None,
        ge=0,
        description="Último cursor de outbox procesado para el hotel autorizado.",
    ),
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Recover invalidation domains after a cursor without exposing payloads."""

    return get_domain_event_recovery(
        db,
        hotel_id=context.hotel_id,
        after_cursor=after_cursor,
    )


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

    def authorization_check() -> bool:
        # A short-lived session is opened only during periodic stream checks;
        # the request/session dependency is not held for the SSE lifetime.
        check_db = get_session_factory()()
        try:
            set_tenant_user_context(check_db, context.user_id)
            user = check_db.query(User).filter(User.id == context.user_id, User.is_active.is_(True)).one_or_none()
            membership = (
                check_db.query(HotelMembership)
                .filter(
                    HotelMembership.hotel_id == context.hotel_id,
                    HotelMembership.user_id == context.user_id,
                    HotelMembership.status == "active",
                )
                .one_or_none()
            )
            return user is not None and membership is not None
        finally:
            check_db.close()

    return StreamingResponse(
        iter_event_stream(
            context.hotel_id,
            client,
            heartbeat_seconds=heartbeat_seconds,
            authorization_check=authorization_check,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
