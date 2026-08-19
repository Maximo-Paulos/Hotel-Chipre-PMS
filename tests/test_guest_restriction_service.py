from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.guest_restriction import GuestRestriction, GuestRestrictionStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.guest_restriction_service import (
    GuestProhibitedError,
    GuestRestrictionConflictError,
    GuestRestrictionNotFoundError,
    RestrictionOverridePermissionError,
    create_guest_restriction,
    get_active_guest_restrictions,
    resolve_guest_restriction,
)
from app.services.guest_service import resolve_tag
from app.services.reservation_service import create_reservation, update_reservation_fields


def _seed_hotel(db, hotel_id: int, *, actor_user_id: int | None = None, role: str = "owner") -> None:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    if actor_user_id is not None:
        db.add(
            User(
                id=actor_user_id,
                email=f"actor-{hotel_id}-{actor_user_id}@example.test",
                password_hash="synthetic",
                is_verified=True,
            )
        )
        db.flush()
        db.add(HotelMembership(hotel_id=hotel_id, user_id=actor_user_id, role=role, status="active"))
    db.flush()


def _seed_guest_inventory(db, hotel_id: int, *, actor_user_id: int | None = None, role: str = "owner"):
    _seed_hotel(db, hotel_id, actor_user_id=actor_user_id, role=role)
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Synthetic",
        last_name=f"Guest {hotel_id}",
        document_type="DNI",
        document_number=f"DOC-{hotel_id}",
        phone="0000000000",
        terms_accepted=True,
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD-{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number=f"{hotel_id}-101",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return guest, category, room


def _reservation(
    *,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int | None,
    check_in_date: date,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    code: str,
) -> Reservation:
    return Reservation(
        hotel_id=hotel_id,
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=check_in_date,
        check_out_date=check_in_date + timedelta(days=2),
        num_adults=1,
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
        status=status,
        confirmation_code=code,
    )


def _create_payload(guest_id: int, category_id: int, room_id: int | None = None, **extra) -> ReservationCreate:
    return ReservationCreate(
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=date.today() + timedelta(days=30),
        check_out_date=date.today() + timedelta(days=32),
        total_amount=Decimal("200.00"),
        **extra,
    )


def test_restriction_lifecycle_distinguishes_active_expired_and_resolved(db):
    guest, _, _ = _seed_guest_inventory(db, 7101, actor_user_id=101)
    active = create_guest_restriction(
        db,
        hotel_id=7101,
        guest_id=guest.id,
        reason="Safety policy",
        detail="Internal-only detail",
        valid_until=datetime.now(timezone.utc) + timedelta(days=2),
        created_by_user_id=101,
    )
    expired = GuestRestriction(
        hotel_id=7101,
        guest_id=guest.id,
        status=GuestRestrictionStatusEnum.ACTIVE,
        reason="Expired policy",
        valid_until=datetime.now(timezone.utc) - timedelta(seconds=1),
        created_by_user_id=101,
    )
    db.add(expired)
    db.flush()

    assert [row.id for row in get_active_guest_restrictions(db, hotel_id=7101, guest_id=guest.id)] == [active.id]

    resolved = resolve_guest_restriction(
        db,
        hotel_id=7101,
        guest_id=guest.id,
        restriction_id=active.id,
        resolved_by_user_id=101,
        resolution_note="Reviewed by management",
    )
    assert resolved.status is GuestRestrictionStatusEnum.RESOLVED
    assert resolved.resolved_at is not None
    assert get_active_guest_restrictions(db, hotel_id=7101, guest_id=guest.id) == []

    with pytest.raises(GuestRestrictionConflictError):
        resolve_guest_restriction(
            db,
            hotel_id=7101,
            guest_id=guest.id,
            restriction_id=active.id,
            resolved_by_user_id=101,
        )


def test_restriction_is_tenant_scoped_for_reads_and_resolution(db):
    guest_a, _, _ = _seed_guest_inventory(db, 7111, actor_user_id=111)
    guest_b, _, _ = _seed_guest_inventory(db, 7112, actor_user_id=112)
    restriction = create_guest_restriction(
        db,
        hotel_id=7111,
        guest_id=guest_a.id,
        reason="Hotel A only",
        created_by_user_id=111,
    )

    assert get_active_guest_restrictions(db, hotel_id=7112, guest_id=guest_b.id) == []
    with pytest.raises(GuestRestrictionNotFoundError):
        resolve_guest_restriction(
            db,
            hotel_id=7112,
            guest_id=guest_b.id,
            restriction_id=restriction.id,
            resolved_by_user_id=112,
        )


def test_adding_restriction_marks_only_future_active_reservations_for_review(db):
    guest, category, room = _seed_guest_inventory(db, 7121, actor_user_id=121)
    future = _reservation(
        hotel_id=7121,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date.today() + timedelta(days=10),
        code="FUTURE-ACTIVE",
    )
    cancelled = _reservation(
        hotel_id=7121,
        guest_id=guest.id,
        category_id=category.id,
        room_id=None,
        check_in_date=date.today() + timedelta(days=12),
        status=ReservationStatusEnum.CANCELLED,
        code="FUTURE-CANCELLED",
    )
    past = _reservation(
        hotel_id=7121,
        guest_id=guest.id,
        category_id=category.id,
        room_id=None,
        check_in_date=date.today() - timedelta(days=20),
        code="PAST-ACTIVE",
    )
    db.add_all([future, cancelled, past])
    db.flush()

    create_guest_restriction(
        db,
        hotel_id=7121,
        guest_id=guest.id,
        reason="Manual review required",
        created_by_user_id=121,
    )

    assert future.requires_manual_review is True
    assert future.status is ReservationStatusEnum.PENDING
    assert cancelled.requires_manual_review is False
    assert cancelled.status is ReservationStatusEnum.CANCELLED
    assert past.requires_manual_review is False


def test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(db):
    guest, category, room = _seed_guest_inventory(db, 7131, actor_user_id=131, role="owner")
    db.commit()

    restriction = create_guest_restriction(
        db,
        hotel_id=7131,
        guest_id=guest.id,
        reason="Do not disclose",
        detail="Sensitive internal context",
        created_by_user_id=131,
    )
    db.commit()

    with pytest.raises(GuestProhibitedError) as blocked:
        create_reservation(db, _create_payload(guest.id, category.id, room.id), hotel_id=7131)
    assert blocked.value.code == "GUEST_PROHIBITED"
    assert blocked.value.restriction_id == restriction.id

    with pytest.raises(GuestProhibitedError):
        create_reservation(
            db,
            _create_payload(
                guest.id,
                category.id,
                room.id,
                restriction_override=GuestRestrictionOverrideRequest(
                    restriction_id=restriction.id + 999,
                    reason="Approved after review",
                ),
            ),
            hotel_id=7131,
            actor_user_id=131,
            actor_role="owner",
        )

    created = create_reservation(
        db,
        _create_payload(
            guest.id,
            category.id,
            room.id,
            restriction_override=GuestRestrictionOverrideRequest(
                restriction_id=restriction.id,
                reason="Approved after review",
            ),
        ),
        hotel_id=7131,
        actor_user_id=131,
        actor_role="owner",
    )
    audit = db.query(SecurityAuditLog).filter_by(action="guest.restriction.override").one()
    details = json.loads(audit.details)
    assert created.id is not None
    assert details["actor_user_id"] == 131
    assert details["override_reason"] == "Approved after review"
    assert details["restriction_id"] == restriction.id
    assert details["overridden_at"]
    assert details["restriction_snapshot"]["reason"] == "Do not disclose"


def test_receptionist_cannot_override_until_canonical_permission_is_granted(db):
    guest, category, room = _seed_guest_inventory(db, 7141, actor_user_id=141, role="receptionist")
    db.commit()
    restriction = create_guest_restriction(
        db,
        hotel_id=7141,
        guest_id=guest.id,
        reason="Manager decision required",
        created_by_user_id=141,
    )
    db.commit()

    with pytest.raises(RestrictionOverridePermissionError):
        create_reservation(
            db,
            _create_payload(
                guest.id,
                category.id,
                room.id,
                restriction_override=GuestRestrictionOverrideRequest(
                    restriction_id=restriction.id,
                    reason="Attempted override",
                ),
            ),
            hotel_id=7141,
            actor_user_id=141,
            actor_role="receptionist",
        )


def test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass(db):
    guest, category, room = _seed_guest_inventory(db, 7151, actor_user_id=151)
    reservation = _reservation(
        hotel_id=7151,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date.today() + timedelta(days=5),
        code="UPDATE-BLOCKED",
    )
    legacy_tag = GuestTag(
        hotel_id=7151,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Legacy evidence",
        created_by_user_id=151,
    )
    db.add_all([reservation, legacy_tag])
    db.flush()
    restriction = create_guest_restriction(
        db,
        hotel_id=7151,
        guest_id=guest.id,
        reason="Independent restriction",
        legacy_guest_tag_id=legacy_tag.id,
        created_by_user_id=151,
    )
    db.commit()

    resolve_tag(db, hotel_id=7151, guest_id=guest.id, tag_id=legacy_tag.id, user_id=151)
    assert restriction in get_active_guest_restrictions(db, hotel_id=7151, guest_id=guest.id)

    with pytest.raises(GuestProhibitedError):
        update_reservation_fields(
            db,
            reservation,
            ReservationUpdate(notes="This must not be persisted"),
            hotel_id=7151,
            changed_by_user_id=151,
            actor_role="owner",
        )
    assert reservation.notes is None

