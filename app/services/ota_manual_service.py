"""Manual OTA reservation workflows.

Sprint 1 does not rely on live channel-manager sync, so manual OTA operations
must be tenant-scoped, deduplicated, and auditable.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.schemas.ota_manual import ManualOTAReservationCreate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    transition_reservation_status,
    update_reservation_fields,
)
from app.services.waitlist_service import promote_from_waitlist


class OTAManualReservationError(Exception):
    """Raised when a manual OTA operation violates business rules."""


_OTA_CHANNELS = {
    "booking": (ReservationSourceEnum.BOOKING, ReservationChannelCodeEnum.BOOKING),
    "booking.com": (ReservationSourceEnum.BOOKING, ReservationChannelCodeEnum.BOOKING),
    "expedia": (ReservationSourceEnum.EXPEDIA, ReservationChannelCodeEnum.EXPEDIA),
    "despegar": (ReservationSourceEnum.OTHER_OTA, ReservationChannelCodeEnum.DESPEGAR),
    "other_ota": (ReservationSourceEnum.OTHER_OTA, ReservationChannelCodeEnum.OTHER_OTA),
}

_NO_GUARANTEE_MODELS = {
    "hotel_collect",
    "no_guarantee",
    "ota_no_guarantee",
    "unknown",
}


def create_or_update_manual_ota_reservation(
    db: Session,
    *,
    hotel_id: int,
    data: ManualOTAReservationCreate,
    actor_user_id: int | None = None,
) -> Reservation:
    channel = _normalize_required(data.channel, "channel").lower()
    external_id = _normalize_required(data.external_id, "external_id")
    source, channel_code = _source_for_channel(channel)

    existing = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.source_provider_code == channel,
            Reservation.external_id == external_id,
        )
        .first()
    )
    if existing is not None:
        return _update_existing_manual_ota_reservation(
            db,
            reservation=existing,
            data=data,
            channel=channel,
            external_id=external_id,
            channel_code=channel_code,
            actor_user_id=actor_user_id,
        )

    create_data = ReservationCreate(
        guest_id=data.guest_id,
        category_id=data.category_id,
        room_id=data.room_id,
        sellable_product_id=data.sellable_product_id,
        rate_plan_id=data.rate_plan_id,
        tax_policy_id=data.tax_policy_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        num_adults=data.num_adults,
        num_children=data.num_children,
        notes=data.notes,
        arrival_time_hint=data.arrival_time_hint,
        reservation_comment=data.reservation_comment,
        source=source,
        external_id=external_id,
        pricing_channel_code=data.pricing_channel_code or channel,
        guest_scope=data.guest_scope,
        target_currency=data.target_currency,
        total_amount=data.total_amount,
    )
    try:
        reservation = create_reservation(db, create_data, hotel_id=hotel_id)
    except ReservationError as exc:
        raise OTAManualReservationError(str(exc)) from exc

    reservation.source = source
    reservation.channel_code = channel_code
    reservation.source_provider_code = channel
    reservation.external_id = external_id
    reservation.external_confirmation_code = _clean(data.external_confirmation_code)
    reservation.payment_collection_model = _clean(data.payment_collection_model) or "hotel_collect"
    reservation.settlement_status = _clean(data.settlement_status) or "pending"
    _apply_manual_amounts(reservation, data)
    _audit(
        db,
        hotel_id=hotel_id,
        user_id=actor_user_id,
        action="ota.manual_reservation.created",
        reservation=reservation,
        details={
            "channel": channel,
            "external_id": external_id,
            "created": True,
        },
    )
    db.flush()
    return reservation


def release_no_guarantee(
    db: Session,
    *,
    reservation: Reservation,
    actor_user_id: int | None = None,
    reason: str | None = None,
) -> Reservation:
    if not reservation.source_provider_code or not reservation.external_id:
        raise OTAManualReservationError("Only OTA reservations can be internally released")
    if Decimal(str(reservation.amount_paid or 0)) > Decimal("0"):
        raise OTAManualReservationError("OTA reservation has payments and cannot be released as no-guarantee")
    collection_model = _clean(reservation.payment_collection_model) or "unknown"
    if collection_model not in _NO_GUARANTEE_MODELS:
        raise OTAManualReservationError("OTA reservation has a payment guarantee")
    if reservation.status in (
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
    ):
        raise OTAManualReservationError(f"Cannot release OTA reservation from status '{reservation.status.value}'")

    try:
        transition_reservation_status(
            db,
            reservation,
            ReservationStatusEnum.CANCELLED,
            hotel_id=reservation.hotel_id,
            reason_code="ota_no_guarantee_internal_release",
            notes=reason,
            changed_by_user_id=_existing_user_id(db, actor_user_id),
        )
    except ReservationError as exc:
        raise OTAManualReservationError(str(exc)) from exc
    reservation.allocation_status = "internally_released"
    reservation.settlement_status = "internal_release_no_guarantee"
    reservation.requires_manual_review = False
    reservation.version = (reservation.version or 0) + 1
    _attempt_waitlist_promotion_after_release(
        db,
        reservation=reservation,
        actor_user_id=actor_user_id,
    )
    _audit(
        db,
        hotel_id=reservation.hotel_id,
        user_id=actor_user_id,
        action="ota.no_guarantee.internal_release",
        reservation=reservation,
        details={
            "channel": reservation.source_provider_code,
            "external_id": reservation.external_id,
            "reason": reason,
            "provider_cancel_called": False,
        },
    )
    db.flush()
    return reservation


def _attempt_waitlist_promotion_after_release(
    db: Session,
    *,
    reservation: Reservation,
    actor_user_id: int | None,
) -> None:
    entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.hotel_id == reservation.hotel_id,
            WaitlistEntry.category_id == reservation.category_id,
            WaitlistEntry.check_in_date == reservation.check_in_date,
            WaitlistEntry.check_out_date == reservation.check_out_date,
            WaitlistEntry.status == WaitlistStatusEnum.WAITING,
        )
        .order_by(WaitlistEntry.priority.asc(), WaitlistEntry.created_at.asc(), WaitlistEntry.id.asc())
        .first()
    )
    if entry is None:
        _audit_waitlist_promotion(
            db,
            reservation=reservation,
            user_id=actor_user_id,
            details={"outcome": "no_candidate"},
        )
        return

    try:
        with db.begin_nested():
            promoted_entry, promoted_reservation = promote_from_waitlist(
                db,
                reservation.hotel_id,
                entry.id,
                room_id=reservation.room_id,
                notes=f"Promoted after OTA no-guarantee release {reservation.id}",
            )
    except Exception as exc:
        _audit_waitlist_promotion(
            db,
            reservation=reservation,
            user_id=actor_user_id,
            details={
                "outcome": "failed",
                "waitlist_entry_id": entry.id,
                "error": str(exc),
            },
        )
        return

    _audit_waitlist_promotion(
        db,
        reservation=reservation,
        user_id=actor_user_id,
        details={
            "outcome": "promoted",
            "waitlist_entry_id": promoted_entry.id,
            "promoted_reservation_id": promoted_reservation.id,
        },
    )


def _update_existing_manual_ota_reservation(
    db: Session,
    *,
    reservation: Reservation,
    data: ManualOTAReservationCreate,
    channel: str,
    external_id: str,
    channel_code: ReservationChannelCodeEnum,
    actor_user_id: int | None,
) -> Reservation:
    before = _reservation_snapshot(reservation)
    try:
        update_reservation_fields(
            db,
            reservation,
            ReservationUpdate(
                room_id=data.room_id,
                check_in_date=data.check_in_date,
                check_out_date=data.check_out_date,
                num_adults=data.num_adults,
                num_children=data.num_children,
                notes=data.notes,
                arrival_time_hint=data.arrival_time_hint,
                reservation_comment=data.reservation_comment,
            ),
            reservation.hotel_id,
            changed_by_user_id=actor_user_id,
            room_move_reason_code="manual_ota_update",
            room_move_notes="Manual OTA duplicate update",
            client_version=data.client_version,
        )
    except ReservationError as exc:
        raise OTAManualReservationError(str(exc)) from exc

    reservation.channel_code = channel_code
    reservation.source_provider_code = channel
    reservation.external_id = external_id
    reservation.external_confirmation_code = _clean(data.external_confirmation_code)
    reservation.payment_collection_model = _clean(data.payment_collection_model) or reservation.payment_collection_model
    if data.settlement_status is not None:
        reservation.settlement_status = _clean(data.settlement_status) or reservation.settlement_status
    _apply_manual_amounts(reservation, data)
    _audit(
        db,
        hotel_id=reservation.hotel_id,
        user_id=actor_user_id,
        action="ota.manual_reservation.updated",
        reservation=reservation,
        details={
            "channel": channel,
            "external_id": external_id,
            "created": False,
            "before": before,
            "after": _reservation_snapshot(reservation),
        },
    )
    db.flush()
    return reservation


def _source_for_channel(channel: str) -> tuple[ReservationSourceEnum, ReservationChannelCodeEnum]:
    return _OTA_CHANNELS.get(channel, (ReservationSourceEnum.OTHER_OTA, ReservationChannelCodeEnum.OTHER_OTA))


def _normalize_required(value: str | None, field_name: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise OTAManualReservationError(f"{field_name} is required for manual OTA reservations")
    return cleaned


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _apply_manual_amounts(reservation: Reservation, data: ManualOTAReservationCreate) -> None:
    if data.total_amount is not None:
        reservation.total_amount = data.total_amount
        reservation.subtotal_amount = data.total_amount
        reservation.net_amount = data.total_amount
    # Two independently-typed prices the receptionist can quote the guest
    # ("cuánto en pesos" / "cuánto en dólares") -- NOT a conversion of one
    # into the other, and NOT the canonical billing amount (that stays
    # total_amount/currency_code above, untouched by these two fields).
    if data.quoted_amount_ars is not None:
        reservation.quoted_amount_ars = data.quoted_amount_ars
    if data.quoted_amount_usd is not None:
        reservation.quoted_amount_usd = data.quoted_amount_usd
    if data.target_currency:
        # Labels the reservation with the currency the operator entered the
        # total in. This does NOT run a live FX conversion (that mechanism is
        # rate_plan + OTACurrencyRate-only, see reservation_service.py) -- it
        # just prevents a USD total from being silently mislabeled as ARS.
        reservation.currency_code = data.target_currency.strip().upper()
    if data.amount_paid is not None:
        reservation.amount_paid = data.amount_paid


def _reservation_snapshot(reservation: Reservation) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "check_in_date": str(reservation.check_in_date),
        "check_out_date": str(reservation.check_out_date),
        "room_id": reservation.room_id,
        "guest_id": reservation.guest_id,
        "notes": reservation.notes,
        "arrival_time_hint": reservation.arrival_time_hint,
        "reservation_comment": reservation.reservation_comment,
        "source_provider_code": reservation.source_provider_code,
        "external_id": reservation.external_id,
        "status": reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status),
        "version": reservation.version,
    }


def _audit(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    action: str,
    reservation: Reservation,
    details: dict[str, Any],
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action=action,
            resource_type="reservation",
            resource_id=str(reservation.id),
            details=json.dumps(details, sort_keys=True, default=str),
        )
    )


def _audit_waitlist_promotion(
    db: Session,
    *,
    reservation: Reservation,
    user_id: int | None,
    details: dict[str, Any],
) -> None:
    _audit(
        db,
        hotel_id=reservation.hotel_id,
        user_id=user_id,
        action="ota.no_guarantee.waitlist_promotion",
        reservation=reservation,
        details=details,
    )


def _existing_user_id(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None
    return user_id if db.get(User, user_id) is not None else None
