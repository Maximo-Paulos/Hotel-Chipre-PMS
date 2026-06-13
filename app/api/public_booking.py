"""Public booking-engine API authenticated only with hotel API keys."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.api_key_auth import PublicAPIContext, get_public_api_context
from app.models.reservation import ReservationChannelCodeEnum, ReservationSourceEnum
from app.models.room import RoomCategory
from app.schemas.hotel_api_key import (
    PublicAvailabilityResponse,
    PublicCategoryRead,
    PublicPaymentLinkCreate,
    PublicPaymentLinkRead,
    PublicRateQuote,
    PublicReservationCreate,
    PublicReservationRead,
)
from app.schemas.reservation import ReservationCreate
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.reservation_service import (
    ReservationError,
    compute_reservation_pricing,
    create_reservation,
    find_available_rooms,
)


router = APIRouter(prefix="/api/public/booking", tags=["Public Booking"])


@router.get("/availability", response_model=PublicAvailabilityResponse)
def public_availability(
    category_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        available = find_available_rooms(
            db,
            category_id,
            check_in_date,
            check_out_date,
            hotel_id=context.hotel_id,
        )
        return {
            "status": "ok",
            "category_id": category_id,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "available_room_ids": [room.id for room in available],
            "count": len(available),
        }
    except ReservationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/categories", response_model=list[PublicCategoryRead])
@router.get("/rate/categories", response_model=list[PublicCategoryRead])
def public_categories(
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    return (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == context.hotel_id)
        .order_by(RoomCategory.name.asc(), RoomCategory.id.asc())
        .all()
    )


@router.get("/rates", response_model=PublicRateQuote)
@router.get("/rate", response_model=PublicRateQuote)
def public_rate_quote(
    category_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        nights, nightly_rate, total_amount, deposit_amount = compute_reservation_pricing(
            db,
            category_id,
            check_in_date,
            check_out_date,
            hotel_id=context.hotel_id,
            pricing_channel_code="website_direct",
        )
        return {
            "status": "ok",
            "category_id": category_id,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "nights": nights,
            "nightly_rate": nightly_rate,
            "total_amount": total_amount,
            "deposit_amount": deposit_amount,
        }
    except ReservationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reservations", response_model=PublicReservationRead, status_code=status.HTTP_201_CREATED)
def public_create_reservation(
    payload: PublicReservationCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    data = payload.model_dump()
    data["source"] = ReservationSourceEnum.DIRECT
    reservation_payload = ReservationCreate(**data)
    try:
        reservation = create_reservation(db, reservation_payload, hotel_id=context.hotel_id)
        reservation.channel_code = ReservationChannelCodeEnum.WEBSITE_DIRECT
        reservation.source_provider_code = "website_direct"
        db.commit()
        db.refresh(reservation)
        return reservation
    except ReservationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payment-link", response_model=PublicPaymentLinkRead, status_code=status.HTTP_201_CREATED)
@router.post("/payment-links", response_model=PublicPaymentLinkRead, status_code=status.HTTP_201_CREATED)
def public_create_payment_link(
    payload: PublicPaymentLinkCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        link = create_link(db, context.hotel_id, payload.to_payment_link_create())
        db.commit()
        db.refresh(link)
        return link
    except PaymentLinkError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
