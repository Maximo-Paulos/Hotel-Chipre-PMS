from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.guest import Guest, GuestRatingEnum, GuestTag, GuestTagTypeEnum
from app.models.reservation import Reservation
from app.models.security_audit_log import SecurityAuditLog


class GuestServiceError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int,
    details: dict[str, Any],
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=json.dumps(details, sort_keys=True, default=str),
        )
    )


def _get_guest(db: Session, hotel_id: int, guest_id: int) -> Guest:
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == hotel_id).one_or_none()
    if guest is None:
        raise GuestServiceError("Guest not found")
    return guest


def _active_tag_filter():
    now = _now()
    return or_(GuestTag.expires_at.is_(None), GuestTag.expires_at > now)


def search_guests(db: Session, hotel_id: int, search: str, *, limit: int = 20) -> list[Guest]:
    term = (search or "").strip()
    query = db.query(Guest).filter(Guest.hotel_id == hotel_id)
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                Guest.document_number.ilike(pattern),
                Guest.phone.ilike(pattern),
                Guest.email.ilike(pattern),
                Guest.last_name.ilike(pattern),
            )
        )
    return query.order_by(Guest.last_name.asc(), Guest.first_name.asc(), Guest.id.asc()).limit(limit).all()


def list_active_tags(db: Session, *, hotel_id: int, guest_id: int) -> list[GuestTag]:
    _get_guest(db, hotel_id, guest_id)
    return (
        db.query(GuestTag)
        .filter(
            GuestTag.hotel_id == hotel_id,
            GuestTag.guest_id == guest_id,
            _active_tag_filter(),
        )
        .order_by(GuestTag.created_at.desc(), GuestTag.id.desc())
        .all()
    )


def quick_profile(db: Session, *, hotel_id: int, guest_id: int) -> dict[str, Any]:
    guest = _get_guest(db, hotel_id, guest_id)
    last_stays = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id, Reservation.guest_id == guest_id)
        .order_by(Reservation.check_out_date.desc(), Reservation.id.desc())
        .limit(5)
        .all()
    )
    return {
        "guest": guest,
        "active_tags": list_active_tags(db, hotel_id=hotel_id, guest_id=guest_id),
        "last_stays": [
            {
                "reservation_id": stay.id,
                "confirmation_code": stay.confirmation_code,
                "status": stay.status,
                "check_in_date": stay.check_in_date,
                "check_out_date": stay.check_out_date,
                "room_id": stay.room_id,
                "room_number": stay.room.room_number if stay.room else None,
                "notes": stay.notes,
            }
            for stay in last_stays
        ],
    }


def add_tag(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    tag_type: GuestTagTypeEnum,
    note: str | None = None,
    expires_at: datetime | None = None,
    user_id: int | None = None,
) -> GuestTag:
    _get_guest(db, hotel_id, guest_id)
    tag = GuestTag(
        hotel_id=hotel_id,
        guest_id=guest_id,
        tag_type=tag_type,
        note=note,
        expires_at=expires_at,
        created_by_user_id=user_id,
    )
    db.add(tag)
    db.flush()
    _audit(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action="guest.tag.added",
        resource_type="guest_tag",
        resource_id=tag.id,
        details={"guest_id": guest_id, "tag_type": tag_type.value, "note": note, "expires_at": expires_at},
    )
    db.flush()
    return tag


def resolve_tag(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    tag_id: int,
    user_id: int | None = None,
) -> GuestTag:
    _get_guest(db, hotel_id, guest_id)
    tag = (
        db.query(GuestTag)
        .filter(GuestTag.id == tag_id, GuestTag.hotel_id == hotel_id, GuestTag.guest_id == guest_id)
        .one_or_none()
    )
    if tag is None:
        raise GuestServiceError("Guest tag not found")
    tag.expires_at = _now()
    _audit(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action="guest.tag.resolved",
        resource_type="guest_tag",
        resource_id=tag.id,
        details={"guest_id": guest_id, "tag_type": tag.tag_type.value, "note": tag.note},
    )
    db.flush()
    return tag


def set_rating(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    rating: GuestRatingEnum,
    user_id: int | None = None,
) -> Guest:
    guest = _get_guest(db, hotel_id, guest_id)
    old_rating = guest.rating
    guest.rating = rating
    _audit(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action="guest.rating.updated",
        resource_type="guest",
        resource_id=guest.id,
        details={"old_rating": old_rating.value if old_rating else None, "new_rating": rating.value},
    )
    db.flush()
    return guest
