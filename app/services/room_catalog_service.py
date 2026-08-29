"""Canonical room category and room catalog write operations."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.onboarding import RoomInput
from app.schemas.room import RoomCategoryCreate, RoomCreate
from app.services.analytics_service import record_hotel_audit_event
from app.services.subscription_service import ensure_room_within_limit


def create_category(db: Session, *, hotel_id: int, data: RoomCategoryCreate, actor_user_id: int | None = None) -> RoomCategory:
    category = RoomCategory(**data.model_dump(), hotel_id=hotel_id)
    db.add(category)
    db.flush()
    if actor_user_id is not None:
        record_hotel_audit_event(
            db,
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action_code="analytics.variable_cost.updated",
            entity_type="room_category",
            entity_id=category.id,
            after={"room_category_id": category.id, "variable_cost_per_night": float(category.variable_cost_per_night or 0)},
        )
    return category


def create_room(db: Session, *, hotel_id: int, data: RoomCreate, actor_user_id: int | None = None) -> Room:
    ensure_room_within_limit(db, hotel_id)
    room = Room(**data.model_dump(), hotel_id=hotel_id)
    db.add(room)
    db.flush()
    return room


def upsert_categories(db: Session, *, hotel_id: int, categories: Iterable[RoomCategoryCreate]) -> tuple[int, int]:
    existing = {c.code.lower(): c for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).all()}
    created = updated = 0
    for payload in categories:
        data = payload.model_dump()
        current = existing.get(data["code"].lower())
        if current is None:
            current = create_category(db, hotel_id=hotel_id, data=payload)
            existing[data["code"].lower()] = current
            created += 1
        else:
            for field, value in data.items():
                setattr(current, field, value)
            updated += 1
    db.flush()
    return created, updated


def upsert_rooms(db: Session, *, hotel_id: int, rooms: Iterable[RoomInput]) -> tuple[int, int]:
    payloads = list(rooms)
    categories = {c.code.lower(): c for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).all()}
    missing_codes = sorted({r.category_code.lower() for r in payloads if r.category_code.lower() not in categories})
    if missing_codes:
        raise ValueError(f"Missing categories for codes: {', '.join(missing_codes)}")

    existing = {r.room_number: r for r in db.query(Room).filter(Room.hotel_id == hotel_id).all()}
    created = updated = 0
    for payload in payloads:
        category_id = categories[payload.category_code.lower()].id
        current = existing.get(payload.room_number)
        if current is None:
            current = create_room(
                db,
                hotel_id=hotel_id,
                data=RoomCreate(
                    room_number=payload.room_number,
                    floor=payload.floor,
                    category_id=category_id,
                    status=RoomStatusEnum.AVAILABLE,
                ),
            )
            existing[payload.room_number] = current
            created += 1
        else:
            current.floor = payload.floor
            current.category_id = category_id
            current.is_active = True
            if current.status is None:
                current.status = RoomStatusEnum.AVAILABLE.value
            updated += 1
    db.flush()
    return created, updated
