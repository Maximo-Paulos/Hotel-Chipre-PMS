"""Hotel-scoped WhatsApp bot booking hooks."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationChannelCodeEnum, ReservationSourceEnum
from app.models.room import RoomCategory
from app.schemas.reservation import ReservationCreate
from app.schemas.whatsapp_hooks import (
    WhatsAppPaymentConfirmation,
    WhatsAppPaymentLinkCreate,
    WhatsAppReservationCreate,
)
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.payment_webhook_service import PaymentWebhookError, ingest_webhook
from app.services.reservation_service import (
    ReservationError,
    compute_reservation_pricing,
    create_reservation as reservation_create,
    find_available_rooms,
)


class WhatsAppBookingError(Exception):
    pass


def availability_lookup(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    check_in_date: date,
    check_out_date: date,
) -> dict[str, Any]:
    try:
        available = find_available_rooms(
            db,
            category_id,
            check_in_date,
            check_out_date,
            hotel_id=hotel_id,
        )
    except ReservationError as exc:
        raise WhatsAppBookingError(str(exc)) from exc
    return {
        "status": "ok",
        "category_id": category_id,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "available_room_ids": [room.id for room in available],
        "count": len(available),
    }


def price_quote(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    check_in_date: date,
    check_out_date: date,
) -> dict[str, Any]:
    try:
        nights, nightly_rate, total_amount, deposit_amount = compute_reservation_pricing(
            db,
            category_id,
            check_in_date,
            check_out_date,
            hotel_id=hotel_id,
            pricing_channel_code="whatsapp",
        )
    except ReservationError as exc:
        raise WhatsAppBookingError(str(exc)) from exc
    return {
        "status": "ok",
        "category_id": category_id,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "nights": nights,
        "nightly_rate": nightly_rate,
        "total_amount": total_amount,
        "deposit_amount": deposit_amount,
        "currency": "ARS",
    }


def options_with_prices(
    db: Session,
    *,
    hotel_id: int,
    check_in_date: date,
    check_out_date: date,
) -> dict[str, Any]:
    categories = (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == hotel_id)
        .order_by(RoomCategory.name.asc(), RoomCategory.id.asc())
        .all()
    )
    options: list[dict[str, Any]] = []
    for category in categories:
        try:
            availability = availability_lookup(
                db,
                hotel_id=hotel_id,
                category_id=category.id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
            )
            if availability["count"] <= 0:
                continue
            quote = price_quote(
                db,
                hotel_id=hotel_id,
                category_id=category.id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
            )
        except WhatsAppBookingError:
            continue
        options.append(
            {
                "category_id": category.id,
                "category_name": category.name,
                "category_code": category.code,
                "available_room_ids": availability["available_room_ids"],
                "count": availability["count"],
                "nights": quote["nights"],
                "nightly_rate": quote["nightly_rate"],
                "total_amount": quote["total_amount"],
                "deposit_amount": quote["deposit_amount"],
                "currency": quote["currency"],
            }
        )
    return {
        "status": "ok",
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "options": options,
    }


def create_reservation(
    db: Session,
    *,
    hotel_id: int,
    payload: WhatsAppReservationCreate,
) -> Reservation:
    reservation_payload = ReservationCreate(
        **payload.model_dump(),
        source=ReservationSourceEnum.DIRECT,
        pricing_channel_code="whatsapp",
    )
    try:
        reservation = reservation_create(db, reservation_payload, hotel_id=hotel_id)
    except ReservationError as exc:
        raise WhatsAppBookingError(str(exc)) from exc
    reservation.channel_code = ReservationChannelCodeEnum.WHATSAPP
    reservation.source_provider_code = "whatsapp"
    db.flush()
    return reservation


def generate_payment_link(db: Session, *, hotel_id: int, payload: WhatsAppPaymentLinkCreate):
    try:
        link = create_link(db, hotel_id, payload.to_payment_link_create())
    except PaymentLinkError as exc:
        raise WhatsAppBookingError(str(exc)) from exc
    link.sent_via_whatsapp = True
    db.flush()
    return link


def handle_payment_confirmation(
    db: Session,
    *,
    hotel_id: int,
    payload: WhatsAppPaymentConfirmation,
) -> dict[str, Any]:
    webhook_payload = {
        **payload.raw_payload,
        "webhook_id": payload.webhook_id,
        "payment_id": payload.payment_id,
        "status": payload.status,
        "amount": str(payload.amount),
        "currency": payload.currency,
    }
    try:
        return ingest_webhook(
            db,
            hotel_id=hotel_id,
            provider=payload.provider,
            webhook_id=payload.webhook_id,
            payload=webhook_payload,
            payment_link_id=payload.payment_link_id,
        )
    except PaymentWebhookError as exc:
        raise WhatsAppBookingError(str(exc)) from exc
