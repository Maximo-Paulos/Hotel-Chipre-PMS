"""Business-date read and controlled one-day advancement for local simulation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.business_clock import HotelBusinessClock
from app.services import audit_log_service
from app.services.timezones import (
    business_clock_enabled_for_hotel,
    hotel_timezone_name,
    hotel_today,
)


class BusinessClockDisabledError(RuntimeError):
    """The local-only clock gate is not open for this hotel and runtime."""


def get_business_clock(db: Session, hotel_id: int) -> dict:
    return {
        "hotel_id": hotel_id,
        "business_date": hotel_today(db, hotel_id),
        "hotel_timezone": hotel_timezone_name(db, hotel_id),
        "simulation_enabled": business_clock_enabled_for_hotel(hotel_id),
    }


def advance_business_clock(
    db: Session,
    *,
    hotel_id: int,
    actor_user_id: int,
) -> HotelBusinessClock:
    """Advance exactly one business day and append a real-time audit event.

    SQLite's atomic upsert prevents concurrent local requests from overwriting
    each other's day increment. On first use, the new date is tomorrow in the
    hotel's timezone. Both the state mutation and audit row share the caller's
    transaction.
    """
    if not business_clock_enabled_for_hotel(hotel_id):
        raise BusinessClockDisabledError

    current_date = hotel_today(db, hotel_id)
    next_date = current_date + timedelta(days=1)
    real_now = datetime.now(timezone.utc)
    statement = sqlite_insert(HotelBusinessClock).values(
        hotel_id=hotel_id,
        business_date=next_date,
        advanced_at=real_now,
        advanced_by_user_id=actor_user_id,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[HotelBusinessClock.hotel_id],
        set_={
            "business_date": func.date(HotelBusinessClock.business_date, "+1 day"),
            "advanced_at": real_now,
            "advanced_by_user_id": actor_user_id,
        },
    )
    db.execute(statement)
    clock = db.get(HotelBusinessClock, hotel_id)
    db.refresh(clock)
    # Derive the prior date from the atomic row result so the audit event is
    # accurate even when the very first advancement races with another local
    # request to create this hotel's clock row.
    previous_date = clock.business_date - timedelta(days=1)

    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name=HotelBusinessClock.__tablename__,
        record_id=hotel_id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=actor_user_id,
        payload_before={"business_date": previous_date},
        payload_after={"business_date": clock.business_date},
    )
    return clock
