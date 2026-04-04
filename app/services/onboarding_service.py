"""
Onboarding service layer.

Responsible for tracking completion of required steps and producing a status
structure that the API and dashboard gating can use.
"""
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.onboarding import OnboardingState
from app.models.room import RoomCategory, Room, RoomStatusEnum
from app.schemas.onboarding import OwnerPayload, RoomInput, StaffMember
from app.schemas.room import RoomCategoryCreate


class OnboardingError(Exception):
    """Raised when onboarding preconditions are not met."""


def resolve_hotel_id(db: Session, provided: Optional[int] = None) -> int:
    """Return the current hotel id; requires explicit selection."""
    if provided is None:
        raise OnboardingError("hotel_id is required")
    config = db.get(HotelConfiguration, provided)
    if not config:
        # Create minimal configuration on the fly for new hotels during onboarding
        config = HotelConfiguration(id=provided)
        db.add(config)
        db.flush()
    return provided


def get_or_create_state(db: Session, hotel_id: int) -> OnboardingState:
    state = db.query(OnboardingState).filter(OnboardingState.hotel_id == hotel_id).first()
    if not state:
        state = OnboardingState(hotel_id=hotel_id)
        db.add(state)
        db.flush()
    return state


def _status_from_state(db: Session, state: OnboardingState) -> dict:
    staff_list = state.get_staff()
    categories_count = db.query(RoomCategory).filter(RoomCategory.hotel_id == state.hotel_id).count()
    rooms_count = db.query(Room).filter(Room.hotel_id == state.hotel_id).count()

    owner_done = bool(state.owner_name and state.owner_email)
    categories_done = categories_count > 0
    rooms_done = rooms_count > 0
    staff_done = len(staff_list) > 0

    steps = {
        "owner": owner_done,
        "categories": categories_done,
        "rooms": rooms_done,
        "staff": staff_done,
        "finish": state.finished,
    }
    completed = all([owner_done, categories_done, rooms_done, staff_done, state.finished])

    missing_steps = [name for name, done in steps.items() if not done]

    status = {
        "hotel_id": state.hotel_id,
        "completed": completed,
        "steps": steps,
        "missing_steps": missing_steps,
        "counts": {
            "categories": categories_count,
            "rooms": rooms_count,
            "staff": len(staff_list),
        },
    }
    if owner_done:
        status["owner"] = {
            "name": state.owner_name,
            "email": state.owner_email,
            "phone": state.owner_phone,
            "role": state.owner_role,
        }
    else:
        status["owner"] = None
    return status


def get_status(db: Session, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    return _status_from_state(db, state)


def set_owner(db: Session, payload: OwnerPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    state.owner_name = payload.name
    state.owner_email = payload.email
    state.owner_phone = payload.phone
    state.owner_role = payload.role
    db.flush()
    return _status_from_state(db, state)


def upsert_categories(
    db: Session,
    categories: Iterable[RoomCategoryCreate],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    existing = {
        c.code.lower(): c
        for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hid).all()
    }
    created = 0
    updated = 0
    for cat in categories:
        data = cat.model_dump()
        code_key = data["code"].lower()
        if code_key in existing:
            obj = existing[code_key]
            for field, value in data.items():
                setattr(obj, field, value)
            updated += 1
        else:
            obj = RoomCategory(hotel_id=hid, **data)
            db.add(obj)
            created += 1
    db.flush()

    status = _status_from_state(db, state)
    status["created"] = created
    status["updated"] = updated
    return status


def upsert_rooms(
    db: Session,
    rooms: Iterable[RoomInput],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    categories = {
        c.code.lower(): c
        for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hid).all()
    }
    missing_codes = sorted({r.category_code.lower() for r in rooms if r.category_code.lower() not in categories})
    if missing_codes:
        raise OnboardingError(f"Missing categories for codes: {', '.join(missing_codes)}")

    existing_rooms = {
        r.room_number: r
        for r in db.query(Room).filter(Room.hotel_id == hid).all()
    }
    created = 0
    updated = 0

    for room_payload in rooms:
        code_key = room_payload.category_code.lower()
        category_id = categories[code_key].id
        if room_payload.room_number in existing_rooms:
            room = existing_rooms[room_payload.room_number]
            room.floor = room_payload.floor
            room.category_id = category_id
            room.is_active = True
            if room.status is None:
                room.status = RoomStatusEnum.AVAILABLE
            updated += 1
        else:
            room = Room(
                hotel_id=hid,
                room_number=room_payload.room_number,
                floor=room_payload.floor,
                category_id=category_id,
                status=RoomStatusEnum.AVAILABLE,
            )
            db.add(room)
            created += 1

    db.flush()
    status = _status_from_state(db, state)
    status["created"] = created
    status["updated"] = updated
    return status


def store_staff(
    db: Session,
    staff: Iterable[StaffMember],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    staff_list = [member.model_dump() for member in staff]
    state.set_staff(staff_list)
    db.flush()
    return _status_from_state(db, state)


def finish_onboarding(db: Session, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    status = _status_from_state(db, state)

    required_steps = ["owner", "categories", "rooms", "staff"]
    missing = [step for step in required_steps if not status["steps"].get(step)]
    if missing:
        raise OnboardingError(f"Missing required onboarding steps: {', '.join(missing)}")

    state.finished = True
    db.flush()
    return _status_from_state(db, state)

