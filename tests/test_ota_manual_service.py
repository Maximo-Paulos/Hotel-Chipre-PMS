from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.waitlist import WaitlistStatusEnum
from app.schemas.ota_manual import ManualOTAReservationCreate
from app.schemas.waitlist import WaitlistEntryCreate
from app.services.ota_manual_service import (
    OTAManualReservationError,
    create_or_update_manual_ota_reservation,
    release_no_guarantee,
)
from app.services.ota_service import OTAIntegrationService
from app.services.waitlist_service import add_to_waitlist


def _seed_hotel(db, *, hotel_id: int, suffix: str = ""):
    db.add(
        HotelConfiguration(
            id=hotel_id,
            hotel_name=f"Hotel {hotel_id}",
            subscription_active=True,
        )
    )
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {suffix or hotel_id}",
        code=f"STD{suffix or hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name=f"Guest{hotel_id}",
        last_name="OTA",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"DOC-{hotel_id}",
        email=f"guest{hotel_id}@test.local",
        terms_accepted=True,
    )
    db.add_all([room, guest])
    db.flush()
    return category, room, guest


def _manual_payload(*, guest_id: int, category_id: int, room_id: int, channel: str = "booking", external_id: str = "BKG-1"):
    return ManualOTAReservationCreate(
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        num_adults=2,
        num_children=0,
        channel=channel,
        external_id=external_id,
        external_confirmation_code=f"CONF-{external_id}",
        notes="manual ota",
        payment_collection_model="hotel_collect",
        total_amount=250,
    )


def test_manual_ota_requires_channel_and_external_id(db):
    category, room, guest = _seed_hotel(db, hotel_id=1)

    with pytest.raises(OTAManualReservationError, match="channel"):
        create_or_update_manual_ota_reservation(
            db,
            hotel_id=1,
            data=_manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id, channel=" "),
            actor_user_id=7,
        )

    with pytest.raises(OTAManualReservationError, match="external_id"):
        create_or_update_manual_ota_reservation(
            db,
            hotel_id=1,
            data=_manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id, external_id=" "),
            actor_user_id=7,
        )


def test_duplicate_channel_external_id_updates_existing_reservation_and_audits(db):
    category, room, guest = _seed_hotel(db, hotel_id=1)
    first = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id, external_id="BKG-DUP"),
        actor_user_id=7,
    )
    db.flush()

    second_payload = _manual_payload(
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        external_id="BKG-DUP",
    )
    second_payload.check_out_date = date(2026, 7, 4)
    second_payload.notes = "updated manual ota"
    second = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=second_payload,
        actor_user_id=8,
    )
    db.flush()

    assert second.id == first.id
    assert db.query(Reservation).filter_by(hotel_id=1, source_provider_code="booking", external_id="BKG-DUP").count() == 1
    assert second.check_out_date == date(2026, 7, 4)
    assert second.notes == "updated manual ota"
    assert second.version == 1

    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="ota.manual_reservation.updated",
        resource_type="reservation",
        resource_id=str(first.id),
    ).one()
    assert audit.user_id == 8
    assert "BKG-DUP" in audit.details


def test_manual_ota_total_amount_and_currency_label_applied(db):
    """B4: the manual OTA form lets the receptionist type a total + currency
    that don't come from any rate plan. fx_rate_snapshot is a real schema
    field on the response (ReservationRead.fx_rate_snapshot) but stays None
    here on purpose -- this hotel has no rate_plan/OTACurrencyRate configured
    for this category, so there is no live conversion rate to report, and
    this function must not fabricate one. currency_code must still reflect
    what the operator typed so the amount isn't silently mislabeled."""
    category, room, guest = _seed_hotel(db, hotel_id=1)
    payload = _manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id, external_id="BKG-USD")
    payload.target_currency = "usd"

    reservation = create_or_update_manual_ota_reservation(db, hotel_id=1, data=payload, actor_user_id=7)
    db.flush()

    assert reservation.total_amount == 250
    assert reservation.currency_code == "USD"
    assert reservation.fx_rate_snapshot is None

    # The frontend reads fx_rate_snapshot straight off the manual-ota response
    # body (POST /api/reservations/manual-ota uses response_model=ReservationRead,
    # see app/api/reservations.py). Confirm the field really is part of that
    # schema so the UI isn't assuming a key that doesn't exist -- it's None
    # here (no rate_plan/OTACurrencyRate configured), not absent.
    from app.api.reservations import _to_read

    body = _to_read(reservation).model_dump()
    assert "fx_rate_snapshot" in body
    assert body["fx_rate_snapshot"] is None
    assert body["currency_code"] == "USD"

    # Correcting the currency on a duplicate submission (update path) must
    # also relabel it -- not just the initial create path.
    updated_payload = _manual_payload(
        guest_id=guest.id, category_id=category.id, room_id=room.id, external_id="BKG-USD"
    )
    updated_payload.target_currency = "ars"
    updated_payload.total_amount = 300
    updated = create_or_update_manual_ota_reservation(db, hotel_id=1, data=updated_payload, actor_user_id=7)
    db.flush()

    assert updated.id == reservation.id
    assert updated.total_amount == 300
    assert updated.currency_code == "ARS"


def test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(db):
    """Root-cause repro for the owner's report: a category with a RatePlan
    that is only priced for the "direct" sales channel. Loading a manual
    Booking.com reservation with an explicit total_amount must NOT go
    through the rate-plan quoting engine at all -- the operator already
    typed the negotiated price, so a channel-scope policy restriction that
    would legitimately reject an auto-quote must not block this manual
    load."""
    from app.models.commercial import RatePlan, RatePlanPrice, SellableProduct

    category, room, guest = _seed_hotel(db, hotel_id=1)
    product = SellableProduct(
        hotel_id=1,
        primary_room_category_id=category.id,
        code="STD_DIRECT_ONLY",
        name="Standard directa only",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    rate_plan = RatePlan(
        hotel_id=1,
        sellable_product_id=product.id,
        code="DIRECT-ONLY",
        name="Solo canal directo",
        currency_code="ARS",
        is_active=True,
    )
    db.add(rate_plan)
    db.flush()
    db.add(
        RatePlanPrice(
            hotel_id=1,
            rate_plan_id=rate_plan.id,
            sales_channel_code="direct",
            occupancy=2,
            currency_code="ARS",
            base_amount=120.0,
            tax_inclusive=False,
        )
    )
    db.flush()

    # Confirm the auto-quote path really is blocked for the "booking"
    # channel by this policy restriction (sanity check for the hypothesis,
    # not the bug itself).
    from app.services.pricing_policy_service import PricingPolicyError, quote_rate_plan_stay

    with pytest.raises(PricingPolicyError, match="sales channel"):
        quote_rate_plan_stay(
            db,
            hotel_id=1,
            rate_plan_id=rate_plan.id,
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 3),
            occupancy=2,
            channel_code="booking",
        )

    payload = _manual_payload(
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        channel="booking",
        external_id="BKG-DIRECT-ONLY",
    )
    payload.total_amount = Decimal("250.00")

    reservation = create_or_update_manual_ota_reservation(db, hotel_id=1, data=payload, actor_user_id=7)
    db.flush()

    assert reservation.total_amount == 250
    assert reservation.status == ReservationStatusEnum.PENDING


def test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(db, monkeypatch):
    category, room, guest = _seed_hotel(db, hotel_id=1)
    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id),
        actor_user_id=7,
    )
    db.flush()

    def fail_provider_cancel(*args, **kwargs):
        raise AssertionError("provider cancel API must not be called")

    monkeypatch.setattr(OTAIntegrationService, "cancel_reservation", fail_provider_cancel, raising=False)

    released = release_no_guarantee(
        db,
        reservation=reservation,
        actor_user_id=9,
        reason="guest did not confirm arrival",
    )
    db.flush()

    assert released.status == ReservationStatusEnum.CANCELLED
    assert released.allocation_status == "internally_released"
    assert released.settlement_status == "internal_release_no_guarantee"
    assert db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="ota.no_guarantee.internal_release",
        resource_type="reservation",
        resource_id=str(reservation.id),
    ).count() == 1


def test_release_no_guarantee_promotes_compatible_waitlist_entry(db):
    category, room, ota_guest = _seed_hotel(db, hotel_id=1)
    waitlist_guest = Guest(
        hotel_id=1,
        first_name="Waiting",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number="WAIT-1",
        email="waiting@test.local",
        terms_accepted=True,
    )
    db.add(waitlist_guest)
    db.flush()
    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(guest_id=ota_guest.id, category_id=category.id, room_id=room.id),
        actor_user_id=7,
    )
    entry = add_to_waitlist(
        db,
        1,
        WaitlistEntryCreate(
            guest_id=waitlist_guest.id,
            category_id=category.id,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            num_adults=2,
            num_children=0,
            priority=10,
        ),
    )
    db.flush()

    released = release_no_guarantee(
        db,
        reservation=reservation,
        actor_user_id=9,
        reason="guest did not confirm arrival",
    )
    db.flush()

    assert released.status == ReservationStatusEnum.CANCELLED
    assert entry.status == WaitlistStatusEnum.PROMOTED
    assert entry.promoted_reservation_id is not None
    promoted = db.get(Reservation, entry.promoted_reservation_id)
    assert promoted is not None
    assert promoted.hotel_id == 1
    assert promoted.guest_id == waitlist_guest.id
    assert promoted.room_id == room.id
    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="ota.no_guarantee.waitlist_promotion",
        resource_type="reservation",
        resource_id=str(reservation.id),
    ).one()
    assert '"outcome": "promoted"' in audit.details
    assert str(entry.id) in audit.details


def test_release_no_guarantee_without_waitlist_still_succeeds(db):
    category, room, guest = _seed_hotel(db, hotel_id=1)
    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(guest_id=guest.id, category_id=category.id, room_id=room.id),
        actor_user_id=7,
    )
    db.flush()

    released = release_no_guarantee(
        db,
        reservation=reservation,
        actor_user_id=9,
        reason="guest did not confirm arrival",
    )
    db.flush()

    assert released.status == ReservationStatusEnum.CANCELLED
    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="ota.no_guarantee.waitlist_promotion",
        resource_type="reservation",
        resource_id=str(reservation.id),
    ).one()
    assert '"outcome": "no_candidate"' in audit.details


def test_deprecated_ota_webhook_routes_return_410():
    client = TestClient(main_module.app)
    for path in ("/api/webhooks/booking", "/api/webhooks/expedia", "/api/webhooks/despegar"):
        response = client.post(path, json={"hotel_id": 1})
        assert response.status_code == 410


def test_manual_ota_cross_hotel_isolation(db):
    category1, room1, guest1 = _seed_hotel(db, hotel_id=1, suffix="H1")
    category2, room2, guest2 = _seed_hotel(db, hotel_id=2, suffix="H2")

    reservation1 = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(guest_id=guest1.id, category_id=category1.id, room_id=room1.id, external_id="OTA-SAME"),
        actor_user_id=1,
    )
    reservation2 = create_or_update_manual_ota_reservation(
        db,
        hotel_id=2,
        data=_manual_payload(guest_id=guest2.id, category_id=category2.id, room_id=room2.id, external_id="OTA-SAME"),
        actor_user_id=2,
    )
    db.flush()

    assert reservation1.id != reservation2.id
    assert db.query(Reservation).filter_by(source_provider_code="booking", external_id="OTA-SAME").count() == 2
    assert db.query(Reservation).filter_by(hotel_id=1, source_provider_code="booking", external_id="OTA-SAME").one().id == reservation1.id
    assert db.query(Reservation).filter_by(hotel_id=2, source_provider_code="booking", external_id="OTA-SAME").one().id == reservation2.id
