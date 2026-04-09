"""
FastAPI routes for Room management + Housekeeping.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.pricing import CategoryPricing
from app.schemas.room import (
    RoomCreate,
    RoomRead,
    RoomCategoryCreate,
    RoomCategoryRead,
    RoomCategoryUpdate,
    CategoryPricingSchema,
    CategoryPricingRead,
    RoomUpdate,
    RoomStatusUpdateResponse,
)
from app.services.reservation_service import ReservationError, find_available_rooms
from app.dependencies.auth import get_auth_context, AuthContext, require_roles
from app.services.subscription_service import ensure_room_within_limit

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


class RoomStatusUpdate(BaseModel):
    status: RoomStatusEnum
    notes: Optional[str] = None


@router.post("/categories", response_model=RoomCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    data: RoomCategoryCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    category = RoomCategory(**data.model_dump(), hotel_id=context.hotel_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=RoomCategoryRead)
def update_category(
    category_id: int,
    data: RoomCategoryUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    category = db.query(RoomCategory).filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[RoomCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    return db.query(RoomCategory).filter(RoomCategory.hotel_id == context.hotel_id).all()


@router.get("/categories/{category_id}", response_model=RoomCategoryRead)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("/categories/pricing/all", response_model=list[CategoryPricingRead])
def get_all_category_pricing(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(RoomCategory.hotel_id == context.hotel_id)
        .all()
    )


@router.get("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def get_category_pricing(
    category_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    pricing = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config not found")
    return pricing


@router.post("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def update_category_pricing(
    category_id: int,
    data: CategoryPricingSchema,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    pricing = db.query(CategoryPricing).filter(CategoryPricing.category_id == category_id).first()
    if not pricing:
        pricing = CategoryPricing(category_id=category_id)
        db.add(pricing)
    
    for k, v in data.model_dump().items():
        setattr(pricing, k, v)
    
    db.commit()
    db.refresh(pricing)
    return pricing



@router.post("/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    # Validate room limit for the hotel's subscription
    ensure_room_within_limit(db, category.hotel_id)
    room = Room(**data.model_dump(), hotel_id=context.hotel_id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/", response_model=list[RoomRead])
def list_rooms(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    return db.query(Room).filter(Room.hotel_id == context.hotel_id).all()


@router.get("/availability")
def room_availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    """
    Simple availability helper. Returns a placeholder message if required
    parameters are missing; otherwise returns available room ids.
    """
    if not (category_id and check_in_date and check_out_date):
        return {
            "status": "placeholder",
            "available_rooms": [],
            "message": "Provide category_id, check_in_date, and check_out_date to check availability.",
        }
    try:
        available = find_available_rooms(
            db,
            category_id,
            check_in_date,
            check_out_date,
            hotel_id=context.hotel_id,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "ok",
        "count": len(available),
        "available_rooms": [room.id for room in available],
    }


@router.get("/{room_id}", response_model=RoomRead)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Generic room update (number, floor, notes, status, etc.)."""
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        category = db.query(RoomCategory).filter(RoomCategory.id == payload["category_id"], RoomCategory.hotel_id == context.hotel_id).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        room.category_id = payload["category_id"]

    # If reactivating a room, enforce plan room limit
    if payload.get("is_active") is True and room.is_active is False:
        ensure_room_within_limit(db, room.hotel_id)

    for field in ("room_number", "floor", "status", "is_active", "notes"):
        if field in payload:
            setattr(room, field, payload[field])

    # When deactivating, ensure no active reservations remain assigned
    if payload.get("is_active") is False:
        active_res = db.query(Reservation).filter(
            Reservation.room_id == room_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        ).count()
        if active_res > 0:
            raise HTTPException(status_code=400, detail="Room has active reservations and cannot be deactivated")

    db.commit()
    db.refresh(room)
    return room


@router.patch("/{room_id}/status", response_model=RoomStatusUpdateResponse)
def update_room_status(
    room_id: int,
    data: RoomStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Update room status for housekeeping. When a room is set to cleaning/maintenance/blocked,
    any reservations assigned to it are automatically relocated by the allocation engine."""
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room.status = data.status
    if data.notes is not None:
        room.notes = data.notes
    db.commit()
    db.refresh(room)
    
    # If room was moved to an unavailable state, trigger reallocation
    realloc_result = None
    if data.status in (RoomStatusEnum.CLEANING, RoomStatusEnum.MAINTENANCE, RoomStatusEnum.BLOCKED):
        from app.services.allocation_engine import build_slots_from_db, run_allocation, apply_allocation_result
        try:
            res_slots, room_slots = build_slots_from_db(db, hotel_id=context.hotel_id)
            if res_slots:
                result = run_allocation(res_slots, room_slots)
                updated = apply_allocation_result(db, result, hotel_id=context.hotel_id)
                db.commit()
                realloc_result = {
                    "moved": len(result.moved_reservations),
                    "unassigned": len(result.unassigned_reservations),
                    "unassigned_ids": result.unassigned_reservations,
                }
        except Exception as e:
            realloc_result = {"error": str(e)}
    
    return {"room": room, "reallocation": realloc_result}


class RoomCategoryAssignmentUpdate(BaseModel):
    category_id: int

@router.patch("/{room_id}/category")
def update_room_category(
    room_id: int,
    data: RoomCategoryAssignmentUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Update the category of a specific room."""
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == context.hotel_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Target category does not exist")

    room.category_id = data.category_id
    db.commit()
    db.refresh(room)
    return room


@router.post("/reallocate")
def trigger_reallocation(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Manually trigger the allocation engine to optimally redistribute all reservations.
    This maximizes availability and profitability by packing rooms tightly and
    relocating reservations away from cleaning/maintenance rooms.
    Returns unassigned reservations (to be shown in yellow in the UI)."""
    from app.services.allocation_engine import build_slots_from_db, run_allocation, apply_allocation_result, AllocationError
    
    try:
        res_slots, room_slots = build_slots_from_db(db, hotel_id=context.hotel_id)
        if not res_slots:
            return {"status": "ok", "message": "No active reservations to reallocate", "moved": 0, "unassigned": []}
        
        result = run_allocation(res_slots, room_slots)
        updated = apply_allocation_result(db, result, hotel_id=context.hotel_id)
        db.commit()
        
        return {
            "status": "ok",
            "total_reservations": len(res_slots),
            "assignments": len(result.assignments),
            "moved": result.moved_reservations,
            "moved_count": len(result.moved_reservations),
            "unassigned": result.unassigned_reservations,
            "unassigned_count": len(result.unassigned_reservations),
            "objective_value": result.objective_value,
        }
    except AllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/housekeeping/summary")
def housekeeping_summary(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    """Get housekeeping overview: how many rooms in each status."""
    rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id).all()
    summary = {
        "total": len(rooms),
        "available": 0,
        "occupied": 0,
        "maintenance": 0,
        "blocked": 0,
        "cleaning": 0,
        "rooms": [],
    }
    # Also check which rooms are actually occupied by checked-in guests
    checked_in_rooms = set()
    checked_in_res = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == context.hotel_id,
            Reservation.status == ReservationStatusEnum.CHECKED_IN,
        )
        .all()
    )
    for r in checked_in_res:
        if r.room_id:
            checked_in_rooms.add(r.room_id)

    for room in sorted(rooms, key=lambda r: r.room_number):
        is_guest_in = room.id in checked_in_rooms
        status_value = room.status.value
        summary[status_value] = summary.get(status_value, 0) + 1
        summary["rooms"].append({
            "id": room.id,
            "room_number": room.room_number,
            "floor": room.floor,
            "category_id": room.category_id,
            "status": status_value,
            "has_guest": is_guest_in,
            "notes": room.notes,
        })
    return summary


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    """Delete a room when no active reservations are attached."""
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    in_use = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.hotel_id == context.hotel_id,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
    ).count()
    if in_use > 0:
        raise HTTPException(status_code=400, detail="Room has active reservations and cannot be deleted")

    db.delete(room)
    db.commit()
    return None
