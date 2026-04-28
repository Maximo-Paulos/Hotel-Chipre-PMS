from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.analytics import RoomStateEvent
from app.schemas.analytics_api import RoomStateEventCreate, RoomStateEventRead
from app.services.analytics_service import (
    close_room_state_event,
    create_room_state_event,
    require_analytics_plan,
)


router = APIRouter(prefix="/api/room-state-events", tags=["Room State Events"])


@router.get("", response_model=list[RoomStateEventRead])
def list_room_state_events(
    room_id: int | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    query = db.query(RoomStateEvent).filter(RoomStateEvent.hotel_id == context.hotel_id)
    if room_id is not None:
        query = query.filter(RoomStateEvent.room_id == room_id)
    if date_from is not None:
        query = query.filter(RoomStateEvent.started_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to is not None:
        query = query.filter(RoomStateEvent.started_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    return query.order_by(RoomStateEvent.started_at.desc(), RoomStateEvent.id.desc()).all()


@router.post("", response_model=RoomStateEventRead, status_code=201)
def create_room_state_event_route(
    payload: RoomStateEventCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    event = create_room_state_event(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, payload=payload)
    db.commit()
    db.refresh(event)
    return event


@router.post("/{event_id}/close", response_model=RoomStateEventRead)
def close_room_state_event_route(
    event_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    event = close_room_state_event(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, event_id=event_id)
    db.commit()
    db.refresh(event)
    return event
