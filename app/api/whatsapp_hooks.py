"""Public WhatsApp bot hooks authenticated only by hotel API key."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.api_key_auth import PublicAPIContext, get_public_api_context
from app.schemas.whatsapp_hooks import (
    WhatsAppAvailabilityResponse,
    WhatsAppOptionsResponse,
    WhatsAppPaymentConfirmation,
    WhatsAppPaymentConfirmationResponse,
    WhatsAppPaymentLinkCreate,
    WhatsAppPaymentLinkRead,
    WhatsAppPriceQuote,
    WhatsAppReservationCreate,
    WhatsAppReservationRead,
)
from app.services.whatsapp_booking_service import (
    WhatsAppBookingError,
    availability_lookup,
    create_reservation,
    generate_payment_link,
    handle_payment_confirmation,
    options_with_prices,
    price_quote,
)


router = APIRouter(prefix="/api/public/whatsapp", tags=["WhatsApp Hooks"])


@router.get("/availability", response_model=WhatsAppAvailabilityResponse)
def whatsapp_availability(
    category_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        return availability_lookup(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
        )
    except WhatsAppBookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/prices", response_model=WhatsAppPriceQuote)
def whatsapp_prices(
    category_id: int = Query(...),
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        return price_quote(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
        )
    except WhatsAppBookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/options", response_model=WhatsAppOptionsResponse)
@router.get("/options/prices", response_model=WhatsAppOptionsResponse)
def whatsapp_options(
    check_in_date: date = Query(...),
    check_out_date: date = Query(...),
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    return options_with_prices(
        db,
        hotel_id=context.hotel_id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
    )


@router.post("/reservations", response_model=WhatsAppReservationRead, status_code=status.HTTP_201_CREATED)
def whatsapp_create_reservation(
    payload: WhatsAppReservationCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        reservation = create_reservation(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        db.refresh(reservation)
        return reservation
    except WhatsAppBookingError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payment-links", response_model=WhatsAppPaymentLinkRead, status_code=status.HTTP_201_CREATED)
@router.post("/payment-link", response_model=WhatsAppPaymentLinkRead, status_code=status.HTTP_201_CREATED)
def whatsapp_generate_payment_link(
    payload: WhatsAppPaymentLinkCreate,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        link = generate_payment_link(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        db.refresh(link)
        return link
    except WhatsAppBookingError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payment-confirmation", response_model=WhatsAppPaymentConfirmationResponse)
@router.post("/payment-confirmations", response_model=WhatsAppPaymentConfirmationResponse)
def whatsapp_payment_confirmation(
    payload: WhatsAppPaymentConfirmation,
    db: Session = Depends(get_db),
    context: PublicAPIContext = Depends(get_public_api_context),
):
    try:
        result = handle_payment_confirmation(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        return result
    except WhatsAppBookingError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
