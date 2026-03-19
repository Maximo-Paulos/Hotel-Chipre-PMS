"""
FastAPI routes for Room management + Housekeeping.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.pricing import CategoryPricing
from app.schemas.room import RoomCreate, RoomRead, RoomCategoryCreate, RoomCategoryRead, CategoryPricingSchema, CategoryPricingRead

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


class RoomStatusUpdate(BaseModel):
    status: RoomStatusEnum
    notes: Optional[str] = None


@router.post("/categories", response_model=RoomCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(data: RoomCategoryCreate, db: Session = Depends(get_db)):
    category = RoomCategory(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[RoomCategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return db.query(RoomCategory).all()


@router.get("/categories/pricing/all", response_model=list[CategoryPricingRead])
def get_all_category_pricing(db: Session = Depends(get_db)):
    return db.query(CategoryPricing).all()


@router.get("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def get_category_pricing(category_id: int, db: Session = Depends(get_db)):
    pricing = db.query(CategoryPricing).filter(CategoryPricing.category_id == category_id).first()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config not found")
    return pricing


@router.post("/categories/{category_id}/pricing", response_model=CategoryPricingSchema)
def update_category_pricing(category_id: int, data: CategoryPricingSchema, db: Session = Depends(get_db)):
    category = db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
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
def create_room(data: RoomCreate, db: Session = Depends(get_db)):
    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    room = Room(**data.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/", response_model=list[RoomRead])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).all()


@router.get("/{room_id}", response_model=RoomRead)
def get_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/{room_id}/status")
def update_room_status(room_id: int, data: RoomStatusUpdate, db: Session = Depends(get_db)):
    """Update room status for housekeeping. When a room is set to cleaning/maintenance/blocked,
    any reservations assigned to it are automatically relocated by the allocation engine."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    old_status = room.status
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
            res_slots, room_slots = build_slots_from_db(db)
            if res_slots:
                result = run_allocation(res_slots, room_slots)
                updated = apply_allocation_result(db, result)
                db.commit()
                realloc_result = {
                    "moved": len(result.moved_reservations),
                    "unassigned": len(result.unassigned_reservations),
                    "unassigned_ids": result.unassigned_reservations,
                }
        except Exception as e:
            realloc_result = {"error": str(e)}
    
    return {
        "id": room.id, 
        "room_number": room.room_number, 
        "status": room.status.value, 
        "notes": room.notes,
        "reallocation": realloc_result,
    }


class RoomCategoryUpdate(BaseModel):
    category_id: int

@router.patch("/{room_id}/category")
def update_room_category(room_id: int, data: RoomCategoryUpdate, db: Session = Depends(get_db)):
    """Update the category of a specific room."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Target category does not exist")

    room.category_id = data.category_id
    db.commit()
    db.refresh(room)
    return room


@router.post("/reallocate")
def trigger_reallocation(db: Session = Depends(get_db)):
    """Manually trigger the allocation engine to optimally redistribute all reservations.
    This maximizes availability and profitability by packing rooms tightly and
    relocating reservations away from cleaning/maintenance rooms.
    Returns unassigned reservations (to be shown in yellow in the UI)."""
    from app.services.allocation_engine import build_slots_from_db, run_allocation, apply_allocation_result, AllocationError
    
    try:
        res_slots, room_slots = build_slots_from_db(db)
        if not res_slots:
            return {"status": "ok", "message": "No active reservations to reallocate", "moved": 0, "unassigned": []}
        
        result = run_allocation(res_slots, room_slots)
        updated = apply_allocation_result(db, result)
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/housekeeping/summary")
def housekeeping_summary(db: Session = Depends(get_db)):
    """Get housekeeping overview: how many rooms in each status."""
    rooms = db.query(Room).all()
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
    checked_in_res = db.query(Reservation).filter(Reservation.status == ReservationStatusEnum.CHECKED_IN).all()
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
