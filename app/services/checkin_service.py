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
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.operations import BillingAdjustment
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.services.reservation_service import (
    ReservationError,
    _active_reservations_without_hotel,
    active_reservations,
    transition_reservation_status,
)
from app.services.jurisdiction_profile import compute_missing_guest_fields
from app.models.room import Room, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.models.company import Company
from app.models.company_document import CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum
from app.models.security_audit_log import SecurityAuditLog
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.services.timezones import hotel_today
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.services.guest_restriction_service import record_restriction_override, validate_no_active_restriction


logger = logging.getLogger(__name__)


class CheckInError(Exception):
    """Custom exception for check-in validation errors."""
    pass


def _notify_reservation_event(db: Session, *, hotel_id: int, reservation: Reservation, event_type: str, title: str) -> None:
    """Durable, per-recipient notification counterpart to the status
    transition below. Best-effort: never blocks or rolls back check-in/out."""
    try:
        from app.models.notification import NotificationSeverityEnum
        from app.services.notification_service import enqueue_notifications_for_event
        from app.services.permission_service import ROLE_CODES

        enqueue_notifications_for_event(
            db,
            hotel_id=hotel_id,
            event_type=event_type,
            dedupe_key=f"{event_type}:{reservation.id}",
            title=title,
            severity=NotificationSeverityEnum.INFO,
            entity_type="reservation",
            entity_id=reservation.id,
            payload={"reservation_id": reservation.id, "status": reservation.status.value if reservation.status else None},
            recipient_roles=list(ROLE_CODES),
        )
    except Exception as exc:
        logger.error(
            "checkin.notify_failed",
            extra={"hotel_id": hotel_id, "reservation_id": reservation.id, "error_type": type(exc).__name__},
        )


def _resolve_jurisdiction_code(config: HotelConfiguration | None) -> str:
    if not config:
        return "AR"
    return str(config.jurisdiction_code or "AR").strip().upper()


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
            raise CheckInError("Se requiere el hotel para validar el check-in.")
        hotel_id = config_or_hotel
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()

    return compute_missing_guest_fields(
        guest,
        jurisdiction_code=_resolve_jurisdiction_code(config),
        require_document=bool(config.require_document_for_checkin) if config else False,
        require_terms=bool(config.require_terms_acceptance) if config else False,
    )


def _load_reservation(db: Session, reservation_id: int, hotel_id: int | None) -> tuple[Reservation, int]:
    reservation_q = (
        active_reservations(db, hotel_id)
        if hotel_id is not None
        else _active_reservations_without_hotel(db)
    ).filter(Reservation.id == reservation_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"No se encontró la reserva {reservation_id}.")

    resolved_hotel_id = reservation.hotel_id or hotel_id
    if resolved_hotel_id is None:
        raise CheckInError("Se requiere el hotel para realizar el check-in.")
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
            f"No se puede realizar el check-in: el huésped tiene una marca activa de 'prohibido_alojar'{note}. "
            "Se requiere una autorización de un gerente para continuar."
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
            f"No se puede realizar el check-in: faltan datos obligatorios del huésped: {'; '.join(validation_errors)}"
        )


def _validate_checkin_window_and_payment(db: Session, reservation: Reservation, hotel_id: int) -> None:
    today = hotel_today(db, hotel_id)
    if reservation.check_in_date > today:
        raise CheckInError(
            f"No se puede realizar el check-in antes de la fecha de llegada de la reserva ({reservation.check_in_date.isoformat()})."
        )
    if reservation.check_out_date <= today:
        raise CheckInError(
            f"No se puede realizar el check-in después de la fecha de salida de la reserva ({reservation.check_out_date.isoformat()}); primero extendé la estadía."
        )

    if (
        Decimal(str(reservation.external_paid_amount or 0)) > Decimal("0.00")
        and not reservation.external_paid_confirmed
    ):
        raise CheckInError(
            "No se puede realizar el check-in: un gerente debe confirmar el pago anticipado importado de la OTA e indicar su referencia."
        )

    company = None
    if reservation.company_id is not None:
        company = (
            db.query(Company)
            .filter(Company.id == reservation.company_id, Company.hotel_id == hotel_id)
            .one_or_none()
        )
        if company is None:
            raise CheckInError("No se puede realizar el check-in: la empresa asociada a la reserva no está disponible.")

        documents_query = db.query(CompanyDocument).filter(
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.reservation_id == reservation.id,
            CompanyDocument.company_id == company.id,
            CompanyDocument.deleted_at.is_(None),
            CompanyDocument.stored_object_id.isnot(None),
        )
        if company.requires_voucher:
            voucher_exists = documents_query.filter(
                CompanyDocument.doc_type == CompanyDocumentTypeEnum.VOUCHER_PDF,
            ).first()
            if voucher_exists is None:
                raise CheckInError("No se puede realizar el check-in: esta empresa requiere que se cargue el comprobante de la reserva.")
        if company.requires_signature:
            signed_document_exists = documents_query.filter(
                CompanyDocument.status == CompanyDocumentStatusEnum.SIGNED,
                (CompanyDocument.doc_type == CompanyDocumentTypeEnum.SIGNATURE_REQUIRED)
                | CompanyDocument.requires_signature.is_(True),
            ).first()
            if signed_document_exists is None:
                raise CheckInError("No se puede realizar el check-in: esta empresa requiere un documento firmado de la reserva.")

        # Invoice-after-stay is a per-company exception to the hotel's
        # full-payment default. Any nightly extras remain collectible and
        # visible in the operational ledger, but unpaid nights are review-only.
        if company.payment_deferred:
            return

    config = db.get(HotelConfiguration, hotel_id)
    policy = getattr(config, "checkin_payment_policy", "total") if config else "total"
    if policy not in {"deposit", "total", "free"}:
        raise CheckInError("No se puede realizar el check-in: la política de pago del hotel no es válida.")
    if policy == "free":
        return

    paid = Decimal(str(paid_amount_with_legacy_fallback(db, hotel_id, reservation)))
    if policy == "total":
        required = Decimal(str(reservation.total_amount or 0))
        requirement_name = "el importe total de la reserva"
    else:
        required = Decimal(str(reservation.deposit_amount or 0))
        requirement_name = "la seña configurada"
    if paid + Decimal("0.01") < required:
        raise CheckInError(
            f"No se puede realizar el check-in: primero debe abonarse {requirement_name}. "
            f"Importe requerido: ${required:.2f}; abonado: ${paid:.2f}."
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
    2. Verify the hotel's payment policy and arrival date
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
    allowed_pre_checkin = {
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.PRE_CHECK_IN,
    }
    if reservation.status not in allowed_pre_checkin:
        raise CheckInError(
            f"No se puede realizar el check-in: la reserva está en estado '{reservation.status.value}'. "
            "La reserva no está en un estado válido previo a la llegada."
        )
    _validate_checkin_window_and_payment(db, reservation, hotel_id)

    # Load guest
    guest = db.query(Guest).filter(Guest.id == reservation.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise CheckInError("No se encontró el registro del huésped asociado a esta reserva.")

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
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.checked_in",
        title=f"Reservation {reservation.confirmation_code} checked in",
    )

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
    from a state allowed by the hotel's payment policy.
    """
    reservation, hotel_id = _load_reservation(db, reservation_id, hotel_id)

    if reservation.status not in {
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
    }:
        raise CheckInError(
            f"No se puede iniciar el pre check-in: la reserva está en estado '{reservation.status.value}'. "
            "La reserva no está en un estado válido previo a la llegada."
        )
    _validate_checkin_window_and_payment(db, reservation, hotel_id)

    guest = db.query(Guest).filter(Guest.id == reservation.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise CheckInError("No se encontró el registro del huésped asociado a esta reserva.")

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
    reservation_q = (
        active_reservations(db, hotel_id)
        if hotel_id is not None
        else _active_reservations_without_hotel(db)
    ).filter(Reservation.id == reservation_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"No se encontró la reserva {reservation_id}.")

    hotel_id = reservation.hotel_id or hotel_id
    if hotel_id is None:
        raise CheckInError("Se requiere el hotel para realizar el check-out.")
    reservation.hotel_id = hotel_id

    if reservation.status != ReservationStatusEnum.CHECKED_IN:
        raise CheckInError(
            f"No se puede realizar el check-out: la reserva está en estado '{reservation.status.value}'. "
            "Debe estar en estado 'checked_in'."
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
            room.housekeeping_status = RoomHousekeepingStatusEnum.DIRTY

    db.flush()
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.checked_out",
        title=f"Reservation {reservation.confirmation_code} checked out",
    )

    return reservation
