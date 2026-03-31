"""
FastAPI routes for Booking management (thin layer over Reservation).
Provides basic CRUD plus a simple availability placeholder.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import (
    ReservationError,
    check_room_availability,
    create_reservation,
    find_available_rooms,
)

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


def _booking_to_read(res: Reservation) -> BookingRead:
    """Ensure computed fields land in the response."""
    return BookingRead.model_validate(res)


@router.get("/availability")
def availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
):
    """
    Lightweight availability placeholder. When all parameters are provided,
    it returns real available room ids; otherwise it returns a helpful message.
    """
    if not (category_id and check_in_date and check_out_date):
        return {
            "status": "placeholder",
            "available_rooms": [],
            "message": "Provide category_id, check_in_date, and check_out_date to check availability.",
        }
    available = find_available_rooms(db, category_id, check_in_date, check_out_date)
    return {
        "status": "ok",
        "available_rooms": [room.id for room in available],
        "count": len(available),
    }


@router.get("/", response_model=list[BookingRead])
def list_bookings(db: Session = Depends(get_db)):
    bookings = db.query(Reservation).order_by(Reservation.check_in_date).all()
    return [_booking_to_read(r) for r in bookings]


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    # Reuse the existing ReservationCreate schema to drive business logic
    reservation_payload = ReservationCreate(**payload.model_dump())
    try:
        booking = create_reservation(db, reservation_payload)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Reservation).filter(Reservation.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_to_read(booking)


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking(booking_id: int, payload: BookingUpdate, db: Session = Depends(get_db)):
    booking = db.query(Reservation).filter(Reservation.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    data = payload.model_dump(exclude_unset=True)

    # Validate optional category change
    if "category_id" in data and data["category_id"] is not None:
        category = db.query(RoomCategory).filter(RoomCategory.id == data["category_id"]).first()
        if not category:
            raise HTTPException(status_code=400, detail="Category not found")
        booking.category_id = data["category_id"]

    # Handle room change
    if "room_id" in data and data["room_id"] is not None:
        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            raise HTTPException(status_code=400, detail="Room not found")
        if room.category_id != booking.category_id:
            raise HTTPException(status_code=400, detail="Room does not belong to the booking category")
        if not check_room_availability(db, room.id, booking.check_in_date, booking.check_out_date, exclude_reservation_id=booking.id):
            raise HTTPException(status_code=400, detail="Room is not available for the current dates")
        booking.room_id = room.id

    # Handle date adjustments
    if "check_in_date" in data or "check_out_date" in data:
        new_ci = data.get("check_in_date", booking.check_in_date)
        new_co = data.get("check_out_date", booking.check_out_date)
        if new_co <= new_ci:
            raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")
        if booking.room_id and not check_room_availability(db, booking.room_id, new_ci, new_co, exclude_reservation_id=booking.id):
            raise HTTPException(status_code=400, detail="Room is not available for the new dates")
        booking.check_in_date = new_ci
        booking.check_out_date = new_co

    for field in ("num_adults", "num_children", "notes"):
        if field in data:
            setattr(booking, field, data[field])

    if "status" in data and data["status"]:
        if not booking.can_transition_to(data["status"]):
            raise HTTPException(status_code=400, detail=f"Invalid status transition to {data['status'].value}")
        booking.status = data["status"]

    db.commit()
    db.refresh(booking)
    return _booking_to_read(booking)


@router.delete("/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Reservation).filter(Reservation.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # Avoid deleting checked-in/checked-out bookings to preserve history
    if booking.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
        raise HTTPException(status_code=400, detail="Cannot delete an active/finished booking")
    db.delete(booking)
    db.commit()
    return {"deleted": True, "id": booking_id}
