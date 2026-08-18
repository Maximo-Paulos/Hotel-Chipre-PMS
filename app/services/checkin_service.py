"""
Check-in Service.
Manages the deep guest check-in flow:
  1. Validates all required guest data (document, terms acceptance, etc.)
  2. Ensures reservation is fully_paid (or pre_check_in) before check-in
  3. Blocks check-in if guest has an active prohibido_alojar tag (v72 §2.7)
  4. Records actual check-in time
  5. Transitions status to checked_in
  6. Also handles check-out flow
"""
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.operations import BillingAdjustment
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.services.reservation_service import transition_reservation_status, ReservationError
from app.services.jurisdiction_profile import compute_missing_guest_fields
from app.models.room import Room, RoomStatusEnum
from app.services.guest_profile import get_guest_profile, validate_primary_guest_record
from app.models.security_audit_log import SecurityAuditLog
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.services.guest_restriction_service import record_restriction_override, validate_no_active_restriction


class CheckInError(Exception):
    """Custom exception for check-in validation errors."""
    pass


def _resolve_jurisdiction_code(config: HotelConfiguration | None) -> str:
    if not config:
        return "AR"
    extra_policies = config.get_extra_policies()
    return str(extra_policies.get("jurisdiction_code") or "AR").strip().upper()


def validate_guest_for_checkin(
    db: Session,
    guest: Guest,
    config_or_hotel: HotelConfiguration | int | None = None,
    reservation: Reservation | None = None,
) -> list[str]:
    """
    Validate that a guest has all required data for check-in.
    Returns a list of missing field descriptions (empty = valid).
    """
    config: HotelConfiguration | None
    if isinstance(config_or_hotel, HotelConfiguration):
        config = config_or_hotel
        hotel_id = config.id
    else:
        if config_or_hotel is None:
            raise CheckInError("hotel_id is required for check-in validation")
        hotel_id = config_or_hotel
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()

    return compute_missing_guest_fields(
        guest,
        jurisdiction_code=_resolve_jurisdiction_code(config),
        require_document=bool(config.require_document_for_checkin) if config else False,
        require_terms=bool(config.require_terms_acceptance) if config else False,
    )


def _load_reservation(db: Session, reservation_id: int, hotel_id: int | None) -> tuple[Reservation, int]:
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    resolved_hotel_id = reservation.hotel_id or hotel_id
    if resolved_hotel_id is None:
        raise CheckInError("hotel_id is required for check-in")
    reservation.hotel_id = resolved_hotel_id
    return reservation, resolved_hotel_id


def _guard_prohibido(
    db: Session,
    hotel_id: int,
    guest: Guest,
    reservation: Reservation,
    *,
    override_prohibido: bool,
    override_user_id: int | None,
) -> None:
    # v72 §2.7 — block check-in if guest has an active prohibido_alojar tag
    prohibido_tag = (
        db.query(GuestTag)
        .filter(
            GuestTag.hotel_id == hotel_id,
            GuestTag.guest_id == guest.id,
            GuestTag.tag_type == GuestTagTypeEnum.PROHIBIDO_ALOJAR,
            or_(GuestTag.expires_at.is_(None), GuestTag.expires_at > datetime.now(timezone.utc)),
        )
        .first()
    )
    if prohibido_tag and override_prohibido:
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=override_user_id,
                action="checkin.prohibido_override",
                resource_type="reservation",
                resource_id=str(reservation.id),
                details=json.dumps(
                    {
                        "guest_id": guest.id,
                        "guest_tag_id": prohibido_tag.id,
                        "tag_note": prohibido_tag.note,
                        "overridden_by_user_id": override_user_id,
                    },
                    sort_keys=True,
                ),
            )
        )
    if prohibido_tag and not override_prohibido:
        note = f" ({prohibido_tag.note})" if prohibido_tag.note else ""
        raise CheckInError(
            f"Check-in blocked — guest has an active 'prohibido_alojar' tag{note}. "
            "An authorized override by a manager is required."
        )


def _apply_guest_patch_and_validate(
    db: Session,
    guest: Guest,
    hotel_id: int,
    reservation: Reservation,
    guest_patch: dict | None,
) -> None:
    """B3.4: apply the guest data captured at the check-in desk (if any) before
    validating — same transaction, so the receptionist completes and checks in
    in a single request instead of hitting a 400 with no way to fix it."""
    if guest_patch:
        for key, value in guest_patch.items():
            setattr(guest, key, value)
        db.flush()

    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    validation_errors = validate_guest_for_checkin(db, guest, config or hotel_id, reservation=reservation)
    if validation_errors:
        raise CheckInError(
            f"Check-in blocked — missing required guest data: {'; '.join(validation_errors)}"
        )


def perform_checkin(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
    *,
    override_prohibido: bool = False,
    override_user_id: int | None = None,
    guest_patch: dict | None = None,
    restriction_override: GuestRestrictionOverrideRequest | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
) -> Reservation:
    """
    Full check-in process:
    1. Load reservation with guest data
    2. Verify reservation is in 'fully_paid' or 'pre_check_in' status
    3. Apply any captured guest data, then validate guest identity documents
    4. Transition to checked_in
    5. Record actual check-in timestamp

    Raises CheckInError with descriptive messages on failure. Raises
    GuestProhibitedError / RestrictionOverridePermissionError (from
    app.services.guest_restriction_service) when the formal GuestRestriction
    gate blocks the check-in -- distinct from the legacy prohibido_alojar
    tag gate in `_guard_prohibido`.
    """
    reservation, hotel_id = _load_reservation(db, reservation_id, hotel_id)
    ledger_paid = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    ledger_balance = max(Decimal("0"), Decimal(str(reservation.total_amount or 0)) - ledger_paid)

    # Must be fully_paid or pre_check_in to check in
    allowed_pre_checkin = {ReservationStatusEnum.FULLY_PAID, ReservationStatusEnum.PRE_CHECK_IN}
    if reservation.status not in allowed_pre_checkin:
        raise CheckInError(
            f"Cannot check in: reservation status is '{reservation.status.value}'. "
            f"Must be 'fully_paid' or 'pre_check_in'. Outstanding balance: ${ledger_balance:.2f}"
        )

    # Load guest
    guest = db.query(Guest).filter(Guest.id == reservation.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise CheckInError("Guest record not found for this reservation")

    overridden_restriction = validate_no_active_restriction(
        db,
        hotel_id=hotel_id,
        guest_id=guest.id,
        restriction_override=restriction_override,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    if overridden_restriction is not None:
        record_restriction_override(
            db,
            hotel_id=hotel_id,
            actor_user_id=actor_user_id,
            restriction=overridden_restriction,
            reason=restriction_override.reason,
            reservation_id=reservation.id,
            operation="checkin",
        )

    _guard_prohibido(
        db, hotel_id, guest, reservation,
        override_prohibido=override_prohibido, override_user_id=override_user_id,
    )
    _apply_guest_patch_and_validate(db, guest, hotel_id, reservation, guest_patch)

    # All validations passed — perform check-in
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_IN, hotel_id)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_in = datetime.now(timezone.utc)
    # Mark room as occupied for housekeeping dashboard
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id).first()
        if room:
            room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    return reservation


def perform_partial_checkin(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
    *,
    override_prohibido: bool = False,
    override_user_id: int | None = None,
    guest_patch: dict | None = None,
) -> Reservation:
    """
    B3.1: writes the 'pre_check_in' state (v72 §7.2 — "docs loaded, awaiting
    room entry"). Since PRE_CHECK_IN means the guest's data is already on
    file, this shares the same guest-patch + validation gate as the final
    check-in; only the target status and timestamp differ. Only reachable
    from 'fully_paid' (see VALID_TRANSITIONS).
    """
    reservation, hotel_id = _load_reservation(db, reservation_id, hotel_id)

    if reservation.status != ReservationStatusEnum.FULLY_PAID:
        raise CheckInError(
            f"Cannot start partial check-in: reservation status is '{reservation.status.value}'. "
            "Must be 'fully_paid'."
        )

    guest = db.query(Guest).filter(Guest.id == reservation.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise CheckInError("Guest record not found for this reservation")

    _guard_prohibido(
        db, hotel_id, guest, reservation,
        override_prohibido=override_prohibido, override_user_id=override_user_id,
    )
    _apply_guest_patch_and_validate(db, guest, hotel_id, reservation, guest_patch)

    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.PRE_CHECK_IN, hotel_id)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.pre_check_in_at = datetime.now(timezone.utc)
    db.flush()

    return reservation


def perform_checkout(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
    *,
    force: bool = False,
) -> Reservation:
    """
    Check-out process:
    1. Verify reservation is in 'checked_in' status
    2. Verify no outstanding balance (optional: allow checkout with balance)
    3. Transition to checked_out
    4. Record actual check-out timestamp
    """
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    hotel_id = reservation.hotel_id or hotel_id
    if hotel_id is None:
        raise CheckInError("hotel_id is required for check-out")
    reservation.hotel_id = hotel_id

    if reservation.status != ReservationStatusEnum.CHECKED_IN:
        raise CheckInError(
            f"Cannot check out: reservation status is '{reservation.status.value}'. "
            f"Must be 'checked_in'."
        )

    billing_adjustments = (
        db.query(BillingAdjustment)
        .filter(
            BillingAdjustment.reservation_id == reservation_id,
            BillingAdjustment.hotel_id == hotel_id,
        )
        .order_by(BillingAdjustment.effective_at, BillingAdjustment.id)
        .all()
    )
    billing_adjustment_total = Decimal(str(round(sum(adj.total_amount for adj in billing_adjustments), 2)))
    d_total = Decimal(str(reservation.total_amount or 0))
    d_paid = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    operational_total = d_total + billing_adjustment_total
    operational_balance_due = max(Decimal("0"), operational_total - d_paid)
    if operational_balance_due > Decimal("0.01") and not force:
        raise CheckInError(
            f"No se puede hacer check-out: la reserva tiene un saldo pendiente de ${operational_balance_due:.2f}. "
            "Cobrá el saldo o forzá el check-out."
        )

    # Transition
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_OUT, hotel_id)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_out = datetime.now(timezone.utc)
    
    # Mark room for cleaning
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id).first()
        if room:
            room.status = RoomStatusEnum.CLEANING
            
    db.flush()

    return reservation
