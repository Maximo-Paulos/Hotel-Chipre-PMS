"""Public booking-engine API authenticated only with hotel API keys."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditActionEnum
from app.dependencies.api_key_auth import PublicAPIContext, require_web_engine_api_context
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationSourceEnum,
)
from app.models.room import RoomCategory
from app.schemas.hotel_api_key import (
    PublicAvailabilityResponse,
    PublicCategoryRead,
    PublicPaymentLinkCreate,
    PublicPaymentLinkRead,
    PublicRateQuote,
    PublicReservationCreate,
    PublicReservationRead,
    PublicReservationStatusRead,
)
from app.schemas.reservation import ReservationCreate
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.reservation_service import (
    ReservationError,
    active_reservations,
    compute_reservation_pricing,
    create_reservation,
    find_available_rooms,
)
from app.services.reservation_quote_service import build_reservation_quote
from app.services import audit_log_service


router = APIRouter(prefix="/api/public/booking", tags=["Public Booking"])


@router.get("/availability", response_model=PublicAvailabilityResponse)
def public_availability(
    category_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
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
    context: PublicAPIContext = Depends(require_web_engine_api_context),
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
    occupancy: int = Query(1, gt=0),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
):
    try:
        return build_reservation_quote(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            pricing_channel_code="website_direct",
            occupancy=occupancy,
        )
    except (ReservationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reservations", response_model=PublicReservationRead, status_code=status.HTTP_201_CREATED)
def public_create_reservation(
    payload: PublicReservationCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
):
    if not payload.quote_token:
        raise HTTPException(status_code=400, detail="Se requiere una cotización vigente para crear la reserva.")
    data = payload.model_dump()
    data["source"] = ReservationSourceEnum.DIRECT
    data["pricing_channel_code"] = "website_direct"
    reservation_payload = ReservationCreate(**data)
    try:
        reservation = create_reservation(db, reservation_payload, hotel_id=context.hotel_id)
        reservation.channel_code = ReservationChannelCodeEnum.WEBSITE_DIRECT
        reservation.source_provider_code = "website_direct"
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=None,
            payload_after={
                **(audit_log_service.model_snapshot(reservation) or {}),
                "source": "public_api",
            },
        )
        db.commit()
        db.refresh(reservation)
        return reservation
    except ReservationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _derive_payment_status(reservation: Reservation) -> str:
    """Coarse payment status derived from amounts (no sensitive detail)."""
    from decimal import Decimal

    def _d(value) -> Decimal:
        return Decimal(str(value)) if value is not None else Decimal("0")

    paid = _d(reservation.amount_paid)
    total = _d(reservation.total_amount)
    if paid <= Decimal("0"):
        return "unpaid"
    if paid >= total:
        return "paid"
    return "partially_paid"


def _serialize_reservation_status(reservation: Reservation) -> PublicReservationStatusRead:
    return PublicReservationStatusRead(
        id=reservation.id,
        confirmation_code=reservation.confirmation_code,
        status=getattr(reservation.status, "value", reservation.status),
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        arrival_time_hint=reservation.arrival_time_hint,
        total_amount=reservation.total_amount,
        amount_paid=reservation.amount_paid,
        balance_due=reservation.balance_due,
        currency_code=reservation.currency_code,
        payment_status=_derive_payment_status(reservation),
        settlement_status=reservation.settlement_status,
    )


@router.get("/reservations/by-code/{confirmation_code}", response_model=PublicReservationStatusRead)
def public_reservation_status_by_code(
    confirmation_code: str,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
):
    """Read-only reservation/payment status by confirmation code (v72 §16).

    Scoped to the API key's hotel; codes belonging to other hotels return 404.
    """
    reservation = (
        active_reservations(db, context.hotel_id)
        .filter(Reservation.confirmation_code == confirmation_code)
        .first()
    )
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return _serialize_reservation_status(reservation)


@router.get("/reservations/{reservation_id}", response_model=PublicReservationStatusRead)
def public_reservation_status(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
):
    """Read-only reservation/payment status by id (v72 §16).

    Scoped to the API key's hotel; reservations belonging to other hotels
    return 404 so cross-hotel existence is never leaked.
    """
    reservation = (
        active_reservations(db, context.hotel_id)
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return _serialize_reservation_status(reservation)


@router.post("/payment-link", response_model=PublicPaymentLinkRead, status_code=status.HTTP_201_CREATED)
@router.post("/payment-links", response_model=PublicPaymentLinkRead, status_code=status.HTTP_201_CREATED)
def public_create_payment_link(
    payload: PublicPaymentLinkCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(require_web_engine_api_context),
):
    try:
        link = create_link(db, context.hotel_id, payload.to_payment_link_create())
        db.commit()
        db.refresh(link)
        return link
    except PaymentLinkError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
