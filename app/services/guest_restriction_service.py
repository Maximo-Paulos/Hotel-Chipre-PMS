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
from app.models.notification import NotificationSeverityEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.services.domain_events import RealtimeEventsUnavailable, publish_domain_event
from app.services.permission_service import (
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    ROLE_CODES,
    resolve as resolve_permission,
)
from app.services.reservation_service import active_reservations

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
        active_reservations(db, hotel_id)
        .filter(
            Reservation.guest_id == guest_id,
            Reservation.check_in_date >= today,
            ~Reservation.status.in_(_INACTIVE_RESERVATION_STATUSES),
        )
        .all()
    )
    for reservation in reservations:
        reservation.requires_manual_review = True


def _publish_restriction_event(
    *, hotel_id: int, guest_id: int, restriction: GuestRestriction, actor_user_id: Optional[int], event_type: str,
) -> None:
    """Best-effort realtime signal. `reason`/`detail` are deliberately
    excluded from the payload -- only identifiers and status travel here."""
    try:
        publish_domain_event(
            hotel_id=hotel_id,
            domain="guests",
            event_type=event_type,
            payload={
                "guest_id": guest_id,
                "restriction_id": restriction.id,
                "user_id": actor_user_id,
                "status": restriction.status.value,
            },
        )
    except RealtimeEventsUnavailable:
        logger.warning("guest_restriction.realtime_unavailable", extra={"hotel_id": hotel_id})
    except Exception as exc:
        logger.error("guest_restriction.publish_failed", extra={"hotel_id": hotel_id, "error_type": type(exc).__name__})


def _publish_restriction_created(*, hotel_id: int, guest_id: int, restriction: GuestRestriction, actor_user_id: Optional[int]) -> None:
    _publish_restriction_event(
        hotel_id=hotel_id, guest_id=guest_id, restriction=restriction, actor_user_id=actor_user_id,
        event_type="guest.restriction.created",
    )


def _notify_restriction_event(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    restriction: GuestRestriction,
    event_type: str,
    title: str,
) -> None:
    """Durable, per-recipient notification counterpart to the realtime-only
    `publish_domain_event` above. Never carries `reason`/`detail`; the
    notification only signals that something changed and where to look."""
    try:
        from app.services.notification_service import enqueue_notifications_for_event

        enqueue_notifications_for_event(
            db,
            hotel_id=hotel_id,
            event_type=event_type,
            dedupe_key=f"{event_type}:{restriction.id}",
            title=title,
            severity=NotificationSeverityEnum.WARNING,
            entity_type="guest_restriction",
            entity_id=restriction.id,
            payload={"guest_id": guest_id, "restriction_id": restriction.id, "status": restriction.status.value},
            recipient_roles=list(ROLE_CODES),
        )
    except Exception as exc:
        logger.error("guest_restriction.notify_failed", extra={"hotel_id": hotel_id, "error_type": type(exc).__name__})


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
    _notify_restriction_event(
        db, hotel_id=hotel_id, guest_id=guest_id, restriction=restriction,
        event_type="guest.restriction.created", title="New guest lodging restriction created",
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
    _publish_restriction_event(
        hotel_id=hotel_id, guest_id=guest_id, restriction=restriction, actor_user_id=resolved_by_user_id,
        event_type="guest.restriction.resolved",
    )
    _notify_restriction_event(
        db, hotel_id=hotel_id, guest_id=guest_id, restriction=restriction,
        event_type="guest.restriction.resolved", title="Guest lodging restriction resolved",
    )
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
    _publish_restriction_event(
        hotel_id=hotel_id, guest_id=restriction.guest_id, restriction=restriction, actor_user_id=actor_user_id,
        event_type="guest.restriction.overridden",
    )
    _notify_restriction_event(
        db, hotel_id=hotel_id, guest_id=restriction.guest_id, restriction=restriction,
        event_type="guest.restriction.overridden", title="Guest lodging restriction overridden",
    )


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
