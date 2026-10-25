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
from datetime import UTC, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, lazyload

from app.models.company import Company
from app.models.company_document import (
    CompanyDocument,
    CompanyDocumentStatusEnum,
    CompanyDocumentTypeEnum,
)
from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment
from app.models.reservation import (
    Reservation,
    ReservationStatusEnum,
    reservation_additional_guests,
)
from app.models.reservation_guest_arrival import ReservationGuestArrival
from app.models.room import Room, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.services.company_reservation_terms import (
    effective_company_terms,
    get_company_terms_review_state,
)
from app.services.guest_restriction_service import (
    record_restriction_override,
    validate_no_active_restriction,
)
from app.services.housekeeping_checklist_policy import (
    open_housekeeping_checklist_exists,
)
from app.services.housekeeping_checklist_service import create_checkout_checklist
from app.services.jurisdiction_profile import (
    UnsupportedJurisdictionError,
    compute_missing_guest_fields,
)
from app.services.reservation_service import (
    ReservationError,
    _active_reservations_without_hotel,
    active_reservations,
    transition_reservation_status,
)
from app.services.room_block_service import room_has_active_block
from app.services.room_state_service import RoomStateTransitionError, mutate_room_state
from app.services.row_locks import lock_query
from app.services.timezones import hotel_business_now, hotel_today

logger = logging.getLogger(__name__)


class CheckInError(Exception):
    """Custom exception for check-in validation errors."""
    pass


class CheckInConflictError(CheckInError):
    """A concurrent room operation requires the operator to retry check-in."""


class CheckOutConflictError(CheckInError):
    """A concurrent room operation requires the operator to retry checkout."""


def _is_postgres_lock_not_available(error: OperationalError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None)
    sqlstate = (
        getattr(original, "sqlstate", None)
        or getattr(original, "pgcode", None)
        or getattr(diagnostic, "sqlstate", None)
    )
    return sqlstate == "55P03"


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

    try:
        return compute_missing_guest_fields(
            guest,
            jurisdiction_code=_resolve_jurisdiction_code(config),
            require_document=bool(config.require_document_for_checkin) if config else False,
            require_terms=bool(config.require_terms_acceptance) if config else False,
        )
    except UnsupportedJurisdictionError as exc:
        # Fail closed: do not apply Argentina's document rules silently to a
        # hotel configured for an unsupported jurisdiction.
        return [f"{exc} Revisá la configuración del hotel antes del check-in."]


def _load_reservation(db: Session, reservation_id: int, hotel_id: int | None) -> tuple[Reservation, int]:
    reservation_q = (
        active_reservations(db, hotel_id)
        if hotel_id is not None
        else _active_reservations_without_hotel(db)
    ).filter(Reservation.id == reservation_id)
    # Refresh and lock the reservation before reading its assigned room. This
    # serializes check-in with room moves and checkout, whose lock order is
    # reservation then room. Preserve intentional in-session edits while the
    # lock query refreshes stale database state; never autoflush them here.
    with db.no_autoflush:
        reservation = reservation_q.first()
        if reservation is None:
            raise CheckInError(f"No se encontró la reserva {reservation_id}.")

        reservation_state = sa_inspect(reservation)
        staged_values = {
            attribute.key: getattr(reservation, attribute.key)
            for attribute in reservation_state.mapper.column_attrs
            if attribute.key != "hotel_id"
            and reservation_state.attrs[attribute.key].history.has_changes()
        }
        reservation = lock_query(reservation_q.populate_existing(), Reservation).first()
        if reservation is None:
            raise CheckInError(f"No se encontró la reserva {reservation_id}.")
        for attribute_name, value in staged_values.items():
            setattr(reservation, attribute_name, value)

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
        # Lock the hotel policy and company profile after the reservation lock.
        # Company/config updates serialize against the first arrival so the
        # guest cannot check in using a stale voucher/signature/payment rule.
        hotel_config_query = (
            db.query(HotelConfiguration)
            .filter(HotelConfiguration.id == hotel_id)
            .populate_existing()
        )
        lock_query(hotel_config_query, HotelConfiguration).one_or_none()
        company_query = (
            db.query(Company)
            .filter(Company.id == reservation.company_id, Company.hotel_id == hotel_id)
            .populate_existing()
        )
        company = (
            lock_query(company_query, Company)
            .one_or_none()
        )
        if company is None:
            raise CheckInError("No se puede realizar el check-in: la empresa asociada a la reserva no está disponible.")

        try:
            company_terms_state = get_company_terms_review_state(
                db,
                reservation,
                hotel_id=hotel_id,
                company=company,
            )
        except ValueError as exc:
            raise CheckInError(f"No se puede validar las condiciones de empresa: {exc}") from exc
        if company_terms_state["blocks_checkin"]:
            raise CheckInError(
                "No se puede realizar el check-in: las condiciones de empresa cambiaron o no tienen una copia histórica. "
                "Gerencia debe revisar esta reserva antes de alojar al huésped."
            )
        company_terms = effective_company_terms(company, reservation)

        documents_query = db.query(CompanyDocument).filter(
            CompanyDocument.hotel_id == hotel_id,
            CompanyDocument.reservation_id == reservation.id,
            CompanyDocument.company_id == company.id,
            CompanyDocument.deleted_at.is_(None),
            CompanyDocument.stored_object_id.isnot(None),
        )
        if company_terms["requires_voucher"]:
            voucher_exists = documents_query.filter(
                CompanyDocument.doc_type == CompanyDocumentTypeEnum.VOUCHER_PDF,
            ).first()
            if voucher_exists is None:
                raise CheckInError("No se puede realizar el check-in: esta empresa requiere que se cargue el comprobante de la reserva.")
        if company_terms["requires_signature"]:
            signature_required_documents = documents_query.filter(
                (CompanyDocument.doc_type == CompanyDocumentTypeEnum.SIGNATURE_REQUIRED)
                | CompanyDocument.requires_signature.is_(True),
            )
            if signature_required_documents.first() is None:
                raise CheckInError("No se puede realizar el check-in: esta empresa requiere un documento firmado de la reserva.")
            unsigned_required_document = signature_required_documents.filter(
                CompanyDocument.status != CompanyDocumentStatusEnum.SIGNED,
            ).first()
            if unsigned_required_document is not None:
                raise CheckInError(
                    "No se puede realizar el check-in: todos los documentos que requieren firma deben estar firmados."
                )

        # Invoice-after-stay is a per-company exception to the hotel's
        # full-payment default. Any nightly extras remain collectible and
        # visible in the operational ledger, but unpaid nights are review-only.
        if company_terms["payment_deferred"]:
            return

    paid = Decimal(str(paid_amount_with_legacy_fallback(db, hotel_id, reservation)))
    required = Decimal(str(reservation.total_amount or 0))
    if paid + Decimal("0.01") < required:
        raise CheckInError(
            "No se puede realizar el check-in: primero debe abonarse el importe total de la reserva. "
            f"Importe requerido: ${required:.2f}; abonado: ${paid:.2f}."
        )


def _load_ready_room_for_checkin(db: Session, reservation: Reservation, hotel_id: int) -> Room:
    """Lock and validate the reservation's assigned room before lodging guests."""
    if reservation.room_id is None:
        raise CheckInError(
            "No se puede realizar el check-in: asigná una habitación activa del hotel antes de alojar al huésped."
        )

    # Target the Room row explicitly because Room.category is joined eagerly;
    # PostgreSQL cannot apply an untargeted FOR UPDATE across that outer join.
    # Reservation.room is also joined eagerly, so refresh an already-loaded
    # identity after waiting for the lock instead of validating stale state.
    try:
        room = (
            db.query(Room)
            .filter(
                Room.id == reservation.room_id,
                Room.hotel_id == hotel_id,
                Room.is_active.is_(True),
                Room.deleted_at.is_(None),
            )
            .populate_existing()
            .with_for_update(of=Room, nowait=True)
            .first()
        )
    except OperationalError as exc:
        if not _is_postgres_lock_not_available(exc):
            raise
        raise CheckInConflictError(
            "Otra operación está modificando la habitación asignada. Revisá su estado y reintentá el check-in."
        ) from exc
    if room is None:
        # Keep the response generic so it does not reveal whether a foreign
        # hotel's room id exists.
        raise CheckInError(
            "No se puede realizar el check-in: asigná una habitación activa del hotel antes de alojar al huésped."
        )
    if room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=room.id,
        start_date=reservation.check_in_date,
        end_date=reservation.check_out_date,
    ):
        raise CheckInError(
            "No se puede realizar el check-in: la habitación asignada tiene un bloqueo activo para las fechas de la estadía."
        )
    if open_housekeeping_checklist_exists(db, hotel_id=hotel_id, room_id=room.id):
        raise CheckInError(
            "No se puede realizar el check-in: primero debe completarse el checklist de limpieza de la habitación."
        )
    if room.status != RoomStatusEnum.AVAILABLE:
        raise CheckInError(
            "No se puede realizar el check-in: la habitación asignada debe estar disponible."
        )
    if room.housekeeping_status not in {
        RoomHousekeepingStatusEnum.CLEAN,
        RoomHousekeepingStatusEnum.INSPECTED,
    }:
        raise CheckInError(
            "No se puede realizar el check-in: la habitación asignada debe estar limpia o inspeccionada."
        )
    return room


def _load_occupied_room_for_guest_arrival(db: Session, reservation: Reservation, hotel_id: int) -> Room:
    """Lock the room for later arrivals without re-running the first-entry gate."""
    if reservation.room_id is None:
        raise CheckInError("No se puede registrar la llegada: la reserva no tiene una habitación asignada.")
    try:
        room = (
            db.query(Room)
            .filter(
                Room.id == reservation.room_id,
                Room.hotel_id == hotel_id,
                Room.is_active.is_(True),
                Room.deleted_at.is_(None),
            )
            .populate_existing()
            .with_for_update(of=Room, nowait=True)
            .first()
        )
    except OperationalError as exc:
        if not _is_postgres_lock_not_available(exc):
            raise
        raise CheckInConflictError(
            "Otra operación está modificando la habitación asignada. Revisá su estado y reintentá el check-in."
        ) from exc
    if room is None:
        raise CheckInError("No se puede registrar la llegada: la habitación asignada no está disponible.")
    if room.status != RoomStatusEnum.OCCUPIED:
        raise CheckInError(
            "No se puede registrar otra llegada: la habitación asignada no figura como ocupada. Revisá su estado."
        )
    return room


def _reservation_guests(db: Session, reservation: Reservation, hotel_id: int) -> list[Guest]:
    """Return only guest profiles linked to this tenant-scoped reservation."""
    linked_ids = {
        row[0]
        for row in db.query(reservation_additional_guests.c.guest_id)
        .filter(reservation_additional_guests.c.reservation_id == reservation.id)
        .all()
    }
    linked_ids.add(reservation.guest_id)
    return (
        db.query(Guest)
        .filter(Guest.hotel_id == hotel_id, Guest.id.in_(linked_ids))
        .order_by(Guest.id)
        .all()
    )


def _checkin_status_policy(db: Session, reservation: Reservation, hotel_id: int) -> str:
    allowed = {"partial_checkin", "checked_in_on_first_guest"}
    policy = reservation.checkin_reservation_status_policy_snapshot
    if policy is None:
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
        policy = getattr(config, "checkin_reservation_status_policy", None) or "partial_checkin"
    if policy not in allowed:
        raise CheckInError("La política de estado del check-in no es válida. Revisá la configuración del hotel.")
    return policy


def _arrival_projection(arrival: ReservationGuestArrival, guest: Guest, actor: User | None) -> dict:
    arrived_at = arrival.arrived_at
    # SQLite returns naive values for DateTime(timezone=True); normalize both
    # database dialects so retries preserve an identical UTC API timestamp.
    arrived_at = (
        arrived_at.replace(tzinfo=UTC)
        if arrived_at.tzinfo is None
        else arrived_at.astimezone(UTC)
    )
    return {
        "id": arrival.id,
        "guest_id": arrival.guest_id,
        "guest_name": guest.full_name,
        "arrived_at": arrived_at,
        "actor_user_id": arrival.actor_user_id,
        "actor_display_name": actor.display_name if actor else None,
        "actor_role": arrival.actor_role,
    }


def _guest_arrival_summary(db: Session, reservation: Reservation, hotel_id: int) -> dict:
    guests = _reservation_guests(db, reservation, hotel_id)
    arrivals = (
        db.query(ReservationGuestArrival, Guest, User)
        .join(
            Guest,
            (Guest.id == ReservationGuestArrival.guest_id)
            & (Guest.hotel_id == ReservationGuestArrival.hotel_id),
        )
        .outerjoin(User, User.id == ReservationGuestArrival.actor_user_id)
        .filter(
            ReservationGuestArrival.hotel_id == hotel_id,
            ReservationGuestArrival.reservation_id == reservation.id,
        )
        .order_by(ReservationGuestArrival.arrived_at, ReservationGuestArrival.id)
        .all()
    )
    expected_count = max(1, int(reservation.num_adults or 0) + int(reservation.num_children or 0))
    return {
        "reservation_id": reservation.id,
        "reservation_status": reservation.status,
        "status_policy": _checkin_status_policy(db, reservation, hotel_id),
        "expected_guest_count": expected_count,
        "registered_guest_count": len(guests),
        "arrived_guest_count": len(arrivals),
        "missing_profile_count": max(0, expected_count - len(guests)),
        "arrivals": [
            _arrival_projection(arrival, guest, actor)
            for arrival, guest, actor in arrivals
        ],
    }


def list_guest_arrivals(db: Session, reservation_id: int, *, hotel_id: int) -> dict:
    """Tenant-scoped read model for the per-person arrival panel."""
    reservation = active_reservations(db, hotel_id).filter(Reservation.id == reservation_id).first()
    if reservation is None:
        raise CheckInError(f"No se encontró la reserva {reservation_id}.")
    return _guest_arrival_summary(db, reservation, hotel_id)


def perform_guest_checkin(
    db: Session,
    reservation_id: int,
    guest_id: int,
    hotel_id: int | None = None,
    *,
    override_prohibido: bool = False,
    override_user_id: int | None = None,
    guest_patch: dict | None = None,
    restriction_override: GuestRestrictionOverrideRequest | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
) -> tuple[Reservation, dict, bool]:
    """Record one guest's arrival with a stable, append-only idempotency key.

    The reservation lock serializes companions, checkout and allocation. Only
    the first arrival transitions the room to occupied; every guest gets their
    own immutable actor/time record. No payment or balance field is touched.
    """
    reservation, hotel_id = _load_reservation(db, reservation_id, hotel_id)

    # Replays return the original event even after checkout. This makes a lost
    # HTTP response safe to retry without adding another arrival.
    existing = (
        db.query(ReservationGuestArrival, Guest, User)
        .join(
            Guest,
            (Guest.id == ReservationGuestArrival.guest_id)
            & (Guest.hotel_id == ReservationGuestArrival.hotel_id),
        )
        .outerjoin(User, User.id == ReservationGuestArrival.actor_user_id)
        .filter(
            ReservationGuestArrival.hotel_id == hotel_id,
            ReservationGuestArrival.reservation_id == reservation.id,
            ReservationGuestArrival.guest_id == guest_id,
        )
        .one_or_none()
    )
    if existing is not None:
        return reservation, _guest_arrival_summary(db, reservation, hotel_id), True

    participants = _reservation_guests(db, reservation, hotel_id)
    guest = next((item for item in participants if item.id == guest_id), None)
    if guest is None:
        # Do not reveal if a guessed profile belongs to another hotel.
        raise CheckInError("El huésped no está registrado en esta reserva.")

    allowed_before_arrival = {
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.PRE_CHECK_IN,
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
    }
    if reservation.status not in allowed_before_arrival:
        raise CheckInError(
            f"No se puede registrar la llegada: la reserva está en estado '{reservation.status.value}'."
        )

    prior_arrivals = (
        db.query(ReservationGuestArrival.id)
        .filter(
            ReservationGuestArrival.hotel_id == hotel_id,
            ReservationGuestArrival.reservation_id == reservation.id,
        )
        .count()
    )
    first_arrival = prior_arrivals == 0
    policy = _checkin_status_policy(db, reservation, hotel_id)

    if first_arrival:
        _validate_checkin_window_and_payment(db, reservation, hotel_id)
        room = _load_ready_room_for_checkin(db, reservation, hotel_id)
    else:
        room = _load_occupied_room_for_guest_arrival(db, reservation, hotel_id)

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
        db,
        hotel_id,
        guest,
        reservation,
        override_prohibido=override_prohibido,
        override_user_id=override_user_id,
    )
    _apply_guest_patch_and_validate(db, guest, hotel_id, reservation, guest_patch)

    arrived_at = hotel_business_now(db, hotel_id)
    arrival = ReservationGuestArrival(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        guest_id=guest.id,
        arrived_at=arrived_at,
        actor_user_id=actor_user_id,
        actor_role=(actor_role or "system")[:40],
    )
    db.add(arrival)
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action="reservation.guest_checked_in",
            resource_type="reservation_guest_arrival",
            resource_id=f"{reservation.id}:{guest.id}",
            details=json.dumps(
                {
                    "reservation_id": reservation.id,
                    "guest_id": guest.id,
                    "actor_role": actor_role or "system",
                    "arrived_at": arrived_at.isoformat(),
                },
                sort_keys=True,
            ),
        )
    )

    if first_arrival:
        reservation.checkin_reservation_status_policy_snapshot = policy
        reservation.actual_check_in = arrived_at
        try:
            mutate_room_state(
                db,
                room=room,
                hotel_id=hotel_id,
                status=RoomStatusEnum.OCCUPIED,
                actor_user_id=actor_user_id,
            )
        except RoomStateTransitionError as exc:
            raise CheckInError(str(exc)) from exc

    db.flush()
    arrived_count = prior_arrivals + 1
    expected_count = max(1, int(reservation.num_adults or 0) + int(reservation.num_children or 0))
    party_complete = arrived_count >= expected_count and len(participants) >= expected_count

    target_status: ReservationStatusEnum | None = None
    if first_arrival and policy == "checked_in_on_first_guest":
        target_status = ReservationStatusEnum.CHECKED_IN
    elif policy == "partial_checkin" and party_complete:
        target_status = ReservationStatusEnum.CHECKED_IN
    elif reservation.status in {
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.PRE_CHECK_IN,
    }:
        target_status = ReservationStatusEnum.PARTIAL_CHECK_IN

    if target_status is not None and reservation.status != target_status:
        try:
            transition_reservation_status(
                db,
                reservation,
                target_status,
                hotel_id,
                changed_by_user_id=actor_user_id,
            )
        except ReservationError as exc:
            raise CheckInError(str(exc)) from exc

    db.flush()
    event_type = (
        "reservation.checked_in"
        if target_status == ReservationStatusEnum.CHECKED_IN
        else "reservation.partial_checkin"
        if first_arrival
        else "reservation.guest_arrived"
    )
    if first_arrival or target_status == ReservationStatusEnum.CHECKED_IN:
        _notify_reservation_event(
            db,
            hotel_id=hotel_id,
            reservation=reservation,
            event_type=event_type,
            title=f"Reservation {reservation.confirmation_code} guest arrival registered",
        )

    return reservation, _guest_arrival_summary(db, reservation, hotel_id), False


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
    primary_guest_id = (
        active_reservations(db, hotel_id)
        if hotel_id is not None
        else _active_reservations_without_hotel(db)
    ).filter(Reservation.id == reservation_id).with_entities(Reservation.guest_id).scalar()
    if primary_guest_id is None:
        raise CheckInError(f"No se encontró la reserva {reservation_id}.")
    reservation, _summary, _already_recorded = perform_guest_checkin(
        db,
        reservation_id,
        # The existing reservation-level endpoint continues to mean that its
        # primary guest arrived; it now shares the per-person ledger and gates.
        guest_id=primary_guest_id,
        hotel_id=hotel_id,
        override_prohibido=override_prohibido,
        override_user_id=override_user_id,
        guest_patch=guest_patch,
        restriction_override=restriction_override,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
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

    reservation.pre_check_in_at = hotel_business_now(db, hotel_id)
    db.flush()

    return reservation


def perform_checkout(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
    *,
    force: bool = False,
    actor_user_id: int | None = None,
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

    # Lock and read only the fields used by the checkout gate. Refreshing the
    # whole ORM row would discard unrelated in-transaction edits such as an
    # actual_check_in timestamp set immediately before calling this service.
    with db.no_autoflush:
        locked_state = (
            reservation_q.with_entities(
                Reservation.status,
                Reservation.hotel_id,
                Reservation.room_id,
            )
            .with_for_update(of=Reservation)
            .first()
        )
    if locked_state is None:
        raise CheckInError(f"No se encontró la reserva {reservation_id}.")

    reservation.status, locked_hotel_id, reservation.room_id = locked_state
    hotel_id = locked_hotel_id or hotel_id
    reservation.hotel_id = hotel_id

    if reservation.status not in {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
    }:
        raise CheckInError(
            f"No se puede realizar el check-out: la reserva está en estado '{reservation.status.value}'. "
            "La reserva debe estar checked_in o partial_checkin y tener al menos un huésped alojado."
        )

    if reservation.room_id is None:
        raise CheckInError("No se puede realizar el check-out: la reserva no tiene una habitación asignada.")

    # The reservation lock serializes checkout attempts for this stay. The room
    # lock then serializes the transition with check-in, checklist, and status
    # operations that mutate the same physical room.
    room = _lock_room_for_checkout(db, reservation=reservation, hotel_id=hotel_id)

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
        deferred_company_exists = False
        if reservation.company_id is not None:
            deferred_company_exists = (
                db.query(Company.id)
                .filter(
                    Company.id == reservation.company_id,
                    Company.hotel_id == hotel_id,
                    Company.payment_deferred.is_(True),
                )
                .first()
                is not None
            )
        if not deferred_company_exists:
            raise CheckInError(
                f"No se puede hacer check-out: la reserva tiene un saldo pendiente de ${operational_balance_due:.2f}. "
                "Cobrá el saldo o forzá el check-out."
            )

    # Transition
    try:
        transition_reservation_status(
            db,
            reservation,
            ReservationStatusEnum.CHECKED_OUT,
            hotel_id,
            changed_by_user_id=actor_user_id,
        )
    except ReservationError as e:
        raise CheckInError(str(e))

    checkout_at = hotel_business_now(db, hotel_id)
    reservation.actual_check_out = checkout_at
    config = db.get(HotelConfiguration, hotel_id)
    timezone_name = config.hotel_timezone if config else "UTC"
    try:
        hotel_timezone = ZoneInfo(timezone_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        hotel_timezone = ZoneInfo("UTC")

    actual_check_in = reservation.actual_check_in
    if actual_check_in is None:
        actual_check_in = datetime.combine(reservation.check_in_date, datetime.min.time(), tzinfo=hotel_timezone)
    elif actual_check_in.tzinfo is None:
        # PostgreSQL's legacy timestamp column is timezone-naive but stores UTC.
        actual_check_in = actual_check_in.replace(tzinfo=timezone.utc)
    reservation.used_nights = max(
        0,
        (checkout_at.astimezone(hotel_timezone).date() - actual_check_in.astimezone(hotel_timezone).date()).days,
    )
    
    # Only the normal occupied state transitions into cleaning. Preserve an
    # operational maintenance/blocking state if it was applied during the stay.
    create_checkout_checklist(
        db,
        hotel_id=hotel_id,
        room_id=room.id,
        reservation_id=reservation.id,
        actor_user_id=actor_user_id,
    )
    try:
        mutate_room_state(
            db,
            room=room,
            hotel_id=hotel_id,
            status=RoomStatusEnum.CLEANING if room.status == RoomStatusEnum.OCCUPIED else None,
            housekeeping_status=RoomHousekeepingStatusEnum.DIRTY,
            actor_user_id=actor_user_id,
        )
    except RoomStateTransitionError as exc:
        raise CheckInError(str(exc)) from exc

    db.flush()
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.checked_out",
        title=f"Reservation {reservation.confirmation_code} checked out",
    )

    return reservation


def _lock_room_for_checkout(db: Session, *, reservation: Reservation, hotel_id: int) -> Room:
    """Lock the assigned room without waiting while holding the reservation lock."""
    try:
        room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id)
            .populate_existing()
            # Room.reservations is select-in loaded by default. Do not refresh the
            # checkout Reservation as a side effect of locking its Room.
            .options(lazyload(Room.reservations))
            .with_for_update(of=Room, nowait=True)
            .one_or_none()
        )
    except OperationalError as exc:
        if not _is_postgres_lock_not_available(exc):
            raise
        raise CheckOutConflictError(
            "Otra operación está modificando la habitación asignada. Revisá su estado y reintentá el check-out."
        ) from exc
    if room is None:
        raise CheckInError("No se puede realizar el check-out: la habitación asignada no está disponible.")
    return room
