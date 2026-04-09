"""
FastAPI routes for Booking management (thin layer over Reservation).
Provides basic CRUD plus a simple availability placeholder.
"""
from datetime import date, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.schemas.booking import BookingCreate, BookingRead, BookingUpdate
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import (
    ReservationError,
    check_room_availability,
    create_reservation,
    find_available_rooms,
    transition_reservation_status,
    compute_reservation_pricing,
)
from app.services.checkin_service import perform_checkin, perform_checkout, CheckInError

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


def _require_demo_mode():
    if os.getenv("DEMO_MODE", "").lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=403,
            detail="Demo mode is disabled. Set DEMO_MODE=true to use this endpoint.",
        )


def _booking_to_read(res: Reservation) -> BookingRead:
    """Ensure computed fields land in the response."""
    result = BookingRead.model_validate(res)
    result.balance_due = res.balance_due
    result.nights = res.nights
    result.additional_guests = [
        {
            "id": g.id,
            "first_name": g.first_name,
            "last_name": g.last_name,
            "document_type": g.document_type,
            "document_number": g.document_number,
        }
        for g in res.additional_guests
    ]
    return result


@router.get("/availability")
def availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
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
    available = find_available_rooms(
        db,
        category_id,
        check_in_date,
        check_out_date,
        hotel_id=context.hotel_id,
    )
    return {
        "status": "ok",
        "available_rooms": [room.id for room in available],
        "count": len(available),
    }


@router.get("/price-quote")
def price_quote(
    category_id: int,
    check_in_date: date,
    check_out_date: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    """
    Calculate pricing for a potential booking without persisting it.
    Uses CategoryPricing (cash) when present, otherwise the base category price.
    """
    try:
        nights, nightly_rate, total_amount, deposit_amount = compute_reservation_pricing(
            db, category_id, check_in_date, check_out_date, hotel_id=context.hotel_id
        )
        return {
            "status": "ok",
            "nights": nights,
            "nightly_rate": nightly_rate,
            "total_amount": total_amount,
            "deposit_amount": deposit_amount,
        }
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[BookingRead])
def list_bookings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    bookings = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == context.hotel_id)
        .order_by(Reservation.check_in_date)
        .all()
    )
    return [_booking_to_read(r) for r in bookings]


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    # Reuse the existing ReservationCreate schema to drive business logic
    reservation_payload = ReservationCreate(**payload.model_dump())
    try:
        booking = create_reservation(db, reservation_payload, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    booking = db.query(Reservation).filter(Reservation.id == booking_id, Reservation.hotel_id == context.hotel_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_to_read(booking)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    booking = db.query(Reservation).filter(Reservation.id == booking_id, Reservation.hotel_id == context.hotel_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        raise HTTPException(status_code=400, detail="Cannot cancel a booking that is already checked-in or checked-out")
    if booking.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(status_code=400, detail="Booking is already cancelled")
    try:
        transition_reservation_status(db, booking, ReservationStatusEnum.CANCELLED, context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/checkin", response_model=BookingRead)
def checkin_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    try:
        booking = perform_checkin(db, booking_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/checkout", response_model=BookingRead)
def checkout_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    try:
        booking = perform_checkout(db, booking_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(booking)
        return _booking_to_read(booking)
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{booking_id}", response_model=BookingRead)
def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    booking = db.query(Reservation).filter(Reservation.id == booking_id, Reservation.hotel_id == context.hotel_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    data = payload.model_dump(exclude_unset=True)
    new_category_id = data.get("category_id", booking.category_id)
    new_ci = data.get("check_in_date", booking.check_in_date)
    new_co = data.get("check_out_date", booking.check_out_date)

    # Validate category existence
    category = db.query(RoomCategory).filter(RoomCategory.id == new_category_id, RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")

    # Validate dates
    if new_co <= new_ci:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")

    # Validate existing room still matches category
    if booking.room_id is not None and booking.category_id != new_category_id:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        if room and room.category_id != new_category_id:
            raise HTTPException(status_code=400, detail="Existing room does not belong to the new category; change room first")

    # Handle room change
        if "room_id" in data and data["room_id"] is not None:
            room = db.query(Room).filter(Room.id == data["room_id"], Room.hotel_id == context.hotel_id).first()
            if not room:
                raise HTTPException(status_code=400, detail="Room not found")
            if room.category_id != new_category_id:
                raise HTTPException(status_code=400, detail="Room does not belong to the booking category")
            if not check_room_availability(
                db,
                room.id,
                new_ci,
                new_co,
                hotel_id=context.hotel_id,
                exclude_reservation_id=booking.id,
            ):
                raise HTTPException(status_code=400, detail="Room is not available for the requested dates")
            booking.room_id = room.id

    # Validate current room availability with new dates
    if booking.room_id and not check_room_availability(
        db,
        booking.room_id,
        new_ci,
        new_co,
        hotel_id=context.hotel_id,
        exclude_reservation_id=booking.id,
    ):
        raise HTTPException(status_code=400, detail="Room is not available for the new dates")

    booking.category_id = new_category_id
    booking.check_in_date = new_ci
    booking.check_out_date = new_co

    # Recalculate totals when dates or category change
    if {"check_in_date", "check_out_date", "category_id"} & data.keys():
        try:
            _, _, total_amount, deposit_amount = compute_reservation_pricing(
                db,
                new_category_id,
                new_ci,
                new_co,
                hotel_id=context.hotel_id,
            )
            booking.total_amount = total_amount
            booking.deposit_amount = deposit_amount
        except ReservationError as e:
            raise HTTPException(status_code=400, detail=str(e))

    for field in ("num_adults", "num_children", "notes"):
        if field in data:
            setattr(booking, field, data[field])

    if "status" in data and data["status"]:
        try:
            transition_reservation_status(db, booking, data["status"], context.hotel_id)
        except ReservationError as e:
            raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(booking)
    return _booking_to_read(booking)


@router.post("/demo-seed")
def seed_demo_bookings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Quickly seed demo bookings (requires DEMO_MODE=true)."""
    _require_demo_mode()
    today = date.today()

    category = db.query(RoomCategory).filter(RoomCategory.hotel_id == context.hotel_id).first()
    if not category:
        category = RoomCategory(
            hotel_id=context.hotel_id,
            name="Demo Category",
            code="DEMO",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add(category)
        db.flush()

    rooms = db.query(Room).filter(Room.category_id == category.id, Room.hotel_id == context.hotel_id).all()
    if not rooms:
        rooms = [
            Room(hotel_id=context.hotel_id, room_number="D1", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE),
            Room(hotel_id=context.hotel_id, room_number="D2", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE),
        ]
        db.add_all(rooms)
        db.flush()

    guest = db.query(Guest).filter(Guest.hotel_id == context.hotel_id).first()
    if not guest:
        guest = Guest(first_name="Demo", last_name="Guest", email="demo@example.com", hotel_id=context.hotel_id)
        db.add(guest)
        db.flush()

    created_ids: list[int] = []
    for idx, room in enumerate(rooms[:2]):
        ci = today + timedelta(days=idx * 3)
        co = ci + timedelta(days=2)
        payload = ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=ci,
            check_out_date=co,
            num_adults=2,
        )
        try:
            res = create_reservation(db, payload, hotel_id=context.hotel_id)
            created_ids.append(res.id)
        except ReservationError:
            continue

    db.commit()
    return {"status": "ok", "created": len(created_ids), "booking_ids": created_ids}


@router.delete("/{booking_id}")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    booking = db.query(Reservation).filter(Reservation.id == booking_id, Reservation.hotel_id == context.hotel_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # Avoid deleting checked-in/checked-out bookings to preserve history
    if booking.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
        raise HTTPException(status_code=400, detail="Cannot delete an active/finished booking")
    db.delete(booking)
    db.commit()
    return {"deleted": True, "id": booking_id}
