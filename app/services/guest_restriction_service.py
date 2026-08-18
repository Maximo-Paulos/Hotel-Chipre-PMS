"""
GuestRestriction service — formal, hotel-scoped guest lodging-prohibition
lifecycle (create / list-active / resolve) plus the shared revalidation gate
reused by reservation create/update, check-in, and price-quote so a guest
newly restricted mid-flow can never slip through a stale quote or a request
that started before the restriction existed.

The restriction's `reason`/`detail` are private, internal-only context: they
are never included in domain events or HTTP error bodies. They may be
recorded in SecurityAuditLog rows, which are internal security records, not
guest- or public-facing.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.guest_restriction import GuestRestriction, GuestRestrictionStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.services.domain_events import RealtimeEventsUnavailable, publish_domain_event
from app.services.permission_service import PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, resolve as resolve_permission

logger = logging.getLogger(__name__)

_INACTIVE_RESERVATION_STATUSES = {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW}


class GuestRestrictionServiceError(Exception):
    """Base class for guest restriction domain errors."""


class GuestRestrictionNotFoundError(GuestRestrictionServiceError):
    pass


class GuestRestrictionConflictError(GuestRestrictionServiceError):
    pass


class GuestProhibitedError(GuestRestrictionServiceError):
    """Raised when a guest has an active restriction and no valid override
    was supplied. Never carries `reason`/`detail` in its message."""

    code = "GUEST_PROHIBITED"

    def __init__(self, restriction_id: int):
        self.restriction_id = restriction_id
        super().__init__("Guest has an active lodging restriction")


class RestrictionOverridePermissionError(GuestRestrictionServiceError):
    def __init__(self):
        super().__init__("No tenes permisos para autorizar esta excepcion")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_active_guest_restrictions(db: Session, *, hotel_id: int, guest_id: int) -> list[GuestRestriction]:
    """Active, non-expired restrictions for a guest, tenant-scoped."""
    now = _now()
    return (
        db.query(GuestRestriction)
        .filter(
            GuestRestriction.hotel_id == hotel_id,
            GuestRestriction.guest_id == guest_id,
            GuestRestriction.status == GuestRestrictionStatusEnum.ACTIVE,
            or_(GuestRestriction.valid_until.is_(None), GuestRestriction.valid_until > now),
        )
        .order_by(GuestRestriction.id)
        .all()
    )


def _flag_future_active_reservations(db: Session, *, hotel_id: int, guest_id: int) -> None:
    """Mark every future, non-cancelled/non-no-show reservation for this
    guest for manual review. Past reservations are left untouched."""
    today = date.today()
    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.guest_id == guest_id,
            Reservation.check_in_date >= today,
            ~Reservation.status.in_(_INACTIVE_RESERVATION_STATUSES),
        )
        .all()
    )
    for reservation in reservations:
        reservation.requires_manual_review = True


def _publish_restriction_created(*, hotel_id: int, guest_id: int, restriction: GuestRestriction, actor_user_id: Optional[int]) -> None:
    """Best-effort realtime signal. `reason`/`detail` are deliberately
    excluded from the payload -- only identifiers and status travel here."""
    try:
        publish_domain_event(
            hotel_id=hotel_id,
            domain="guests",
            event_type="guest.restriction.created",
            payload={
                "guest_id": guest_id,
                "restriction_id": restriction.id,
                "user_id": actor_user_id,
                "status": restriction.status.value,
            },
        )
    except RealtimeEventsUnavailable:
        logger.warning("guest_restriction.realtime_unavailable", extra={"hotel_id": hotel_id})
    except Exception:
        logger.exception("guest_restriction.publish_failed", extra={"hotel_id": hotel_id})


def create_guest_restriction(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    reason: str,
    detail: Optional[str] = None,
    valid_until: Optional[datetime] = None,
    created_by_user_id: Optional[int] = None,
    legacy_guest_tag_id: Optional[int] = None,
) -> GuestRestriction:
    restriction = GuestRestriction(
        hotel_id=hotel_id,
        guest_id=guest_id,
        status=GuestRestrictionStatusEnum.ACTIVE,
        reason=reason,
        detail=detail,
        valid_until=valid_until,
        created_by_user_id=created_by_user_id,
        legacy_guest_tag_id=legacy_guest_tag_id,
    )
    db.add(restriction)
    db.flush()

    _flag_future_active_reservations(db, hotel_id=hotel_id, guest_id=guest_id)
    db.flush()

    _publish_restriction_created(
        hotel_id=hotel_id, guest_id=guest_id, restriction=restriction, actor_user_id=created_by_user_id
    )
    return restriction


def resolve_guest_restriction(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    restriction_id: int,
    resolved_by_user_id: Optional[int] = None,
    resolution_note: Optional[str] = None,
) -> GuestRestriction:
    restriction = (
        db.query(GuestRestriction)
        .filter(
            GuestRestriction.id == restriction_id,
            GuestRestriction.hotel_id == hotel_id,
            GuestRestriction.guest_id == guest_id,
        )
        .one_or_none()
    )
    if restriction is None:
        raise GuestRestrictionNotFoundError("Guest restriction not found")
    if restriction.status == GuestRestrictionStatusEnum.RESOLVED:
        raise GuestRestrictionConflictError("Guest restriction already resolved")

    restriction.status = GuestRestrictionStatusEnum.RESOLVED
    restriction.resolved_by_user_id = resolved_by_user_id
    restriction.resolved_at = _now()
    restriction.resolution_note = resolution_note
    db.flush()
    return restriction


def record_restriction_override(
    db: Session,
    *,
    hotel_id: int,
    actor_user_id: Optional[int],
    restriction: GuestRestriction,
    reason: str,
    reservation_id: Optional[int] = None,
    operation: Optional[str] = None,
) -> None:
    """Audit an already-authorized override. Callers must only invoke this
    after `validate_no_active_restriction` returned a restriction (i.e. the
    override was already verified as matching + permitted)."""
    details = {
        "actor_user_id": actor_user_id,
        "override_reason": reason,
        "restriction_id": restriction.id,
        "overridden_at": _now().isoformat(),
        "restriction_snapshot": {
            "reason": restriction.reason,
            "detail": restriction.detail,
        },
    }
    if reservation_id is not None:
        details["reservation_id"] = reservation_id
    if operation is not None:
        details["operation"] = operation

    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action="guest.restriction.override",
            resource_type="guest_restriction",
            resource_id=str(restriction.id),
            details=json.dumps(details, sort_keys=True, default=str),
        )
    )
    db.flush()


def validate_no_active_restriction(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    restriction_override: Optional[GuestRestrictionOverrideRequest],
    actor_user_id: Optional[int],
    actor_role: Optional[str],
) -> Optional[GuestRestriction]:
    """Revalidate that the guest has no active restriction blocking the
    in-flight mutation.

    Returns the restriction that was validly overridden (the caller should
    call `record_restriction_override` once the mutation it guards has been
    persisted), or None when there is nothing active to block.

    Raises GuestProhibitedError when a restriction is active and no matching
    override was supplied, or RestrictionOverridePermissionError when the
    override matches but the actor lacks the override permission.
    """
    active = get_active_guest_restrictions(db, hotel_id=hotel_id, guest_id=guest_id)
    if not active:
        return None

    restriction = active[0]
    if restriction_override is None or restriction_override.restriction_id != restriction.id:
        raise GuestProhibitedError(restriction.id)

    if not resolve_permission(
        db, hotel_id, actor_role, PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, user_id=actor_user_id
    ):
        raise RestrictionOverridePermissionError()

    return restriction
