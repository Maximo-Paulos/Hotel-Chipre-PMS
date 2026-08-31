"""
FastAPI routes for Booking management (thin layer over Reservation).
Provides basic CRUD plus a simple availability placeholder.
"""
from datetime import date, datetime, timedelta, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.timezones import hotel_today
from app.dependencies.auth import AuthContext, require_permission, require_roles
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.audit_log import AuditActionEnum
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
from app.services.reservation_quote_service import build_reservation_quote
from app.services.checkin_service import perform_checkin, perform_checkout, CheckInError
from app.services.guest_restriction_service import GuestProhibitedError, get_active_guest_restrictions
from app.services.graph_projection import project_company_link, project_reservation_assignment
from app.services import audit_log_service
from app.services.permission_service import PERMISSION_RESERVATION_CREATE

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
    result.balance_due = float(res.balance_due)
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


def _project_booking_graph(hotel_id: int, booking: Reservation) -> None:
    project_reservation_assignment(
        hotel_id,
        booking.id,
        booking.room_id,
        booking.guest_id,
        booking.status,
    )
    if booking.company_id is not None:
        project_company_link(hotel_id, booking.company_id, booking.id)


@router.get("/availability")
def availability(
    category_id: int | None = None,
    check_in_date: date | None = None,
    check_out_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    guest_id: int | None = None,
    company_id: int | None = None,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int = Query(1, gt=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    """
    Calculate pricing for a potential booking without persisting it.
    Uses the canonical daily/seasonal rate resolver and then the category base price.
    """
    if guest_id is not None:
        active = get_active_guest_restrictions(db, hotel_id=context.hotel_id, guest_id=guest_id)
        if active:
            error = GuestProhibitedError(active[0].id)
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error), "restriction_id": error.restriction_id},
            )
    try:
        return build_reservation_quote(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            sellable_product_id=sellable_product_id,
            rate_plan_id=rate_plan_id,
            tax_policy_id=tax_policy_id,
            pricing_channel_code=pricing_channel_code,
            pricing_payment_method=pricing_payment_method,
            guest_scope=guest_scope,
            target_currency=target_currency,
            occupancy=occupancy,
            guest_id=guest_id,
            company_id=company_id,
        )
    except (ReservationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[BookingRead])
def list_bookings(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    bookings = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == context.hotel_id, Reservation.deleted_at.is_(None))
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
        _project_booking_graph(context.hotel_id, booking)
        return _booking_to_read(booking)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    booking = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_to_read(booking)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    booking = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .first()
    )
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    booking = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .first()
    )
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
        room = (
            db.query(Room)
            .filter(Room.id == booking.room_id, Room.hotel_id == context.hotel_id)
            .first()
        )
        if room and room.category_id != new_category_id:
            raise HTTPException(status_code=400, detail="Existing room does not belong to the new category; change room first")

    # Handle room change
    if "room_id" in data and data["room_id"] is not None:
        room = (
            db.query(Room)
            .filter(
                Room.id == data["room_id"],
                Room.hotel_id == context.hotel_id,
                Room.deleted_at.is_(None),
            )
            .first()
        )
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
    today = hotel_today(db, context.hotel_id)

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

    rooms = (
        db.query(Room)
        .filter(
            Room.category_id == category.id,
            Room.hotel_id == context.hotel_id,
            Room.deleted_at.is_(None),
        )
        .all()
    )
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
    booking = (
        db.query(Reservation)
        .filter(
            Reservation.id == booking_id,
            Reservation.hotel_id == context.hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    # Avoid deleting checked-in/checked-out bookings to preserve history
    if booking.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
        raise HTTPException(status_code=400, detail="Cannot delete an active/finished booking")
    before = audit_log_service.model_snapshot(booking)
    booking.deleted_at = datetime.now(timezone.utc)
    booking.deleted_by_user_id = context.user_id
    db.commit()
    db.refresh(booking)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="reservations",
        record_id=booking.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(booking),
    )
    return {"deleted": True, "id": booking_id}
