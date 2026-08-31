from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.decorators.audit_hooks import audited_change
from app.models.audit_log import AuditActionEnum
from app.models.guest import Guest, GuestRatingEnum, GuestTag, GuestTagTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.services.reservation_service import active_reservations
from app.services.timezones import hotel_today


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


@dataclass
class GuestCreatePayload:
    """Input payload for :func:`find_or_create_guest` (BRM §2.1 dedup)."""

    hotel_id: int
    first_name: str
    last_name: str
    document_type: str | None = None
    document_number: str | None = None
    nationality: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state_province: str | None = None
    postal_code: str | None = None
    country: str | None = None
    birth_place: str | None = None
    birth_country: str | None = None
    marital_status: str | None = None
    occupation: str | None = None
    terms_accepted: bool = False
    digital_signature: str | None = None
    special_requests: str | None = None
    observations: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def find_or_create_guest(db: Session, payload: GuestCreatePayload) -> tuple[Guest, bool]:
    """BRM §2.1: reuse an existing guest matched by (hotel, document) or create a new one.

    Returns ``(guest, created)``. When the payload carries a document
    (both ``document_type`` and ``document_number``) and a guest already exists
    for that hotel, the existing record is reused (``created=False``). Without a
    full document, a new guest is always created (``created=True``).
    """
    document_type = (payload.document_type or None)
    document_number = (payload.document_number or "").strip() or None

    if document_type and document_number:
        existing = (
            db.query(Guest)
            .filter(
                Guest.hotel_id == payload.hotel_id,
                Guest.document_type == document_type,
                Guest.document_number == document_number,
            )
            .one_or_none()
        )
        if existing is not None:
            return existing, False

    fields: dict[str, Any] = {
        "hotel_id": payload.hotel_id,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "document_type": document_type,
        "document_number": document_number,
        "nationality": payload.nationality,
        "date_of_birth": payload.date_of_birth,
        "gender": payload.gender,
        "email": payload.email,
        "phone": payload.phone,
        "address_line1": payload.address_line1,
        "address_line2": payload.address_line2,
        "city": payload.city,
        "state_province": payload.state_province,
        "postal_code": payload.postal_code,
        "country": payload.country,
        "birth_place": payload.birth_place,
        "birth_country": payload.birth_country,
        "marital_status": payload.marital_status,
        "occupation": payload.occupation,
        "terms_accepted": payload.terms_accepted,
        "digital_signature": payload.digital_signature,
        "special_requests": payload.special_requests,
        "observations": payload.observations,
        **(payload.extra or {}),
    }
    guest = Guest(**fields)
    db.add(guest)
    db.flush()
    return guest, True


_GUEST_SEARCH_FIELDS = (
    Guest.first_name,
    Guest.last_name,
    Guest.email,
    Guest.phone,
    Guest.document_number,
)
_MAX_GUEST_SEARCH_LIMIT = 200


def _escape_like_term(term: str) -> str:
    """Treat user-entered LIKE metacharacters as literal search text."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _guest_search_rank(term: str):
    """Rank exact field matches before prefixes and general substrings."""
    escaped_term = _escape_like_term(term)
    exact_match = or_(*(field.ilike(escaped_term, escape="\\") for field in _GUEST_SEARCH_FIELDS))
    prefix_match = or_(*(field.ilike(f"{escaped_term}%", escape="\\") for field in _GUEST_SEARCH_FIELDS))
    return case((exact_match, 0), (prefix_match, 1), else_=2)


def search_guests(
    db: Session,
    hotel_id: int,
    search: str,
    *,
    skip: int = 0,
    limit: int = 20,
    default_order_by_id: bool = False,
) -> list[Guest]:
    """Search guests within one hotel using bounded, SQL-side filtering.

    ``skip``/``limit`` are kept here as well as at the API boundary so callers
    that use the service directly cannot accidentally turn a search into an
    unbounded result set. The API validates the public range; the service
    defensively clamps values for internal callers.
    """
    term = (search or "").strip()
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 20), _MAX_GUEST_SEARCH_LIMIT))
    query = db.query(Guest).filter(Guest.hotel_id == hotel_id)
    order_by = (
        [Guest.id.asc()]
        if default_order_by_id
        else [Guest.last_name.asc(), Guest.first_name.asc(), Guest.id.asc()]
    )

    if term:
        escaped_term = _escape_like_term(term)
        pattern = f"%{escaped_term}%"
        query = query.filter(
            or_(*(field.ilike(pattern, escape="\\") for field in _GUEST_SEARCH_FIELDS))
        )
        order_by.insert(0, _guest_search_rank(term))

    return query.order_by(*order_by).offset(safe_skip).limit(safe_limit).all()


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


def _serialize_stay(stay: Reservation) -> dict[str, Any]:
    return {
        "reservation_id": stay.id,
        "confirmation_code": stay.confirmation_code,
        "status": stay.status,
        "check_in_date": stay.check_in_date,
        "check_out_date": stay.check_out_date,
        "room_id": stay.room_id,
        "room_number": stay.room.room_number if stay.room else None,
        "notes": stay.notes,
    }


def quick_profile(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    offset: int = 0,
    limit: int = 5,
) -> dict[str, Any]:
    """BRM §2.5: quick guest profile with paginated stays and per-status breakdown.

    Backward compatible: ``last_stays`` keeps the same shape (most recent stays,
    paginated via ``offset``/``limit``). Adds ``observations`` and a
    ``stays_by_status`` breakdown (previas / futuras / canceladas / no_show)
    plus ``total_stays`` for the "Mostrar más" pagination.
    """
    guest = _get_guest(db, hotel_id, guest_id)

    base_query = (
        active_reservations(db, hotel_id)
        .filter(Reservation.guest_id == guest_id)
        .order_by(Reservation.check_out_date.desc(), Reservation.id.desc())
    )

    total_stays = base_query.count()

    page_offset = max(int(offset or 0), 0)
    page_limit = max(int(limit if limit is not None else 5), 0)
    page = base_query.offset(page_offset).limit(page_limit).all()

    today = hotel_today(db, hotel_id)
    previas: list[dict[str, Any]] = []
    futuras: list[dict[str, Any]] = []
    canceladas: list[dict[str, Any]] = []
    no_show: list[dict[str, Any]] = []

    for stay in base_query.all():
        serialized = _serialize_stay(stay)
        if stay.status == ReservationStatusEnum.CANCELLED:
            canceladas.append(serialized)
        elif stay.status == ReservationStatusEnum.NO_SHOW:
            no_show.append(serialized)
        elif stay.check_out_date is not None and stay.check_out_date <= today:
            previas.append(serialized)
        else:
            futuras.append(serialized)

    return {
        "guest": guest,
        "observations": guest.observations,
        "active_tags": list_active_tags(db, hotel_id=hotel_id, guest_id=guest_id),
        "last_stays": [_serialize_stay(stay) for stay in page],
        "total_stays": total_stays,
        "offset": page_offset,
        "limit": page_limit,
        "stays_by_status": {
            "previas": previas,
            "futuras": futuras,
            "canceladas": canceladas,
            "no_show": no_show,
        },
    }


@audited_change(table_name="guest_tags", action=AuditActionEnum.CREATE)
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


@audited_change(table_name="guest_tags", action=AuditActionEnum.STATUS_CHANGE)
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


@audited_change(table_name="guests", action=AuditActionEnum.UPDATE)
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
