from __future__ import annotations

import pytest
from datetime import date

from app.models.allocation import LLMFeedbackEvent, ManualOverrideReason
from app.models.commercial import FxPolicy, ProductRoomCompatibility, RatePlan, RatePlanPrice, SellableProduct, TaxPolicy, TaxRule
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTACommissionRule, OTACurrencyRate, OTAProvider, OTAReservationLink, OTAReservationLifecycleEnum
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.allocation_runtime_service import run_persisted_allocation
from app.services.reservation_operations_service import preview_ota_rebook_as_direct, rebook_ota_reservation_as_direct


def _seed_commercial_setup(db, hotel_id: int, source_category_id: int, target_category_id: int):
    product = SellableProduct(
        hotel_id=hotel_id,
        primary_room_category_id=target_category_id,
        code="DBL_PRIVATE",
        name="Doble privada",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    rate_plan = RatePlan(
        hotel_id=hotel_id,
        sellable_product_id=product.id,
        code="FLEX-UPG",
        name="Flexible upgrade",
        currency_code="ARS",
        is_active=True,
    )
    db.add(rate_plan)
    db.flush()

    db.add(
        RatePlanPrice(
            hotel_id=hotel_id,
            rate_plan_id=rate_plan.id,
            sales_channel_code="booking",
            occupancy=2,
            currency_code="ARS",
            base_amount=150.0,
            tax_inclusive=False,
        )
    )

    tax_policy = TaxPolicy(
        hotel_id=hotel_id,
        code="ARG",
        name="Argentina",
        taxes_included=False,
        apply_vat_by_default=False,
        foreign_guest_tax_exempt=True,
        is_active=True,
    )
    db.add(tax_policy)
    db.flush()

    db.add(
        TaxRule(
            hotel_id=hotel_id,
            tax_policy_id=tax_policy.id,
            channel_code="booking",
            guest_scope="local",
            tax_code="VAT",
            tax_name="IVA",
            tax_type="percentage",
            amount=21.0,
            priority=10,
        )
    )

    provider = OTAProvider(code="booking", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()

    db.add(
        OTACommissionRule(
            hotel_id=hotel_id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            commission_pct=15.0,
            payout_model="agency",
        )
    )

    fx_policy = FxPolicy(
        hotel_id=hotel_id,
        code="LOCAL",
        name="Local",
        base_currency="ARS",
        preferred_source="official",
        preferred_side="sell",
        spread_pct=0.0,
        is_active=True,
    )
    db.add(fx_policy)
    db.flush()
    return product, rate_plan, tax_policy, fx_policy


def test_rebook_ota_reservation_as_direct_creates_adjustment_and_direct_booking(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble compartida",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    original = Reservation(
        confirmation_code="OTA-REBOOK-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-123",
        num_adults=2,
        num_children=0,
    )
    db.add(original)
    db.flush()
    provider = OTAProvider(code="booking", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=original.id,
        external_reservation_id="booking-123",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
    )
    db.add(link)
    db.flush()

    result = rebook_ota_reservation_as_direct(
        db,
        reservation=original,
        hotel_id=hotel_config.id,
        target_category_id=sample_categories[1].id,
        discount_pct=10.0,
        notes="Upgrade a categoria superior",
    )
    db.commit()

    assert result.original_reservation.status == ReservationStatusEnum.CANCELLED
    assert result.new_reservation.source == ReservationSourceEnum.DIRECT
    assert result.new_reservation.category_id == sample_categories[1].id
    assert result.adjustment.resulting_reservation_id == result.new_reservation.id
    assert result.billing_adjustment is not None
    assert result.billing_adjustment.total_amount > 0
    assert result.adjustment.ota_reservation_link_id == link.id
    assert result.original_reservation.settlement_status == "manual_resolution_required"
    assert result.new_reservation.payment_collection_model == "hotel_collect"
    assert result.new_reservation.settlement_status == "pending_hotel_collection"
    db.refresh(link)
    assert link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
    assert link.sync_status == "manual_resolution_required"
    override = db.query(ManualOverrideReason).filter_by(reservation_id=original.id, override_type="ota_rebook_direct").one()
    feedback = db.query(LLMFeedbackEvent).filter_by(reservation_id=original.id, event_type="manual_override").one()
    assert override.reason_code == "ota_rebook_direct"
    assert feedback.manual_override_reason_id == override.id


def test_preview_ota_rebook_as_direct_uses_commercial_quote(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    _legacy_product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble compartida",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(_legacy_product)
    db.flush()

    _, target_rate_plan, target_tax_policy, _ = _seed_commercial_setup(
        db,
        hotel_id=hotel_config.id,
        source_category_id=sample_categories[0].id,
        target_category_id=sample_categories[1].id,
    )

    original = Reservation(
        confirmation_code="OTA-PREVIEW-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 7, 10),
        check_out_date=date(2026, 7, 12),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-555",
        num_adults=2,
        num_children=0,
    )
    db.add(original)
    db.flush()

    preview = preview_ota_rebook_as_direct(
        db,
        reservation=original,
        hotel_id=hotel_config.id,
        target_category_id=sample_categories[1].id,
        target_rate_plan_id=target_rate_plan.id,
        target_tax_policy_id=target_tax_policy.id,
        pricing_channel_code="booking",
        guest_scope="local",
        discount_pct=10.0,
    )

    assert preview.pricing_source == "commercial_quote"
    assert preview.target_rate_plan_id == target_rate_plan.id
    assert preview.quoted_total_amount == 326.7
    assert preview.tax_amount == 56.7
    assert preview.amount_delta == 126.7
    assert preview.deposit_amount == 98.01


def test_rebook_ota_reservation_as_direct_persists_commercial_fields(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    _legacy_product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED_2",
        name="Doble compartida 2",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(_legacy_product)
    db.flush()

    target_product, target_rate_plan, target_tax_policy, _ = _seed_commercial_setup(
        db,
        hotel_id=hotel_config.id,
        source_category_id=sample_categories[0].id,
        target_category_id=sample_categories[1].id,
    )

    original = Reservation(
        confirmation_code="OTA-REBOOK-2",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 7, 15),
        check_out_date=date(2026, 7, 17),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-777",
        num_adults=2,
        num_children=0,
    )
    db.add(original)
    db.flush()

    result = rebook_ota_reservation_as_direct(
        db,
        reservation=original,
        hotel_id=hotel_config.id,
        target_category_id=sample_categories[1].id,
        target_rate_plan_id=target_rate_plan.id,
        target_tax_policy_id=target_tax_policy.id,
        pricing_channel_code="booking",
        guest_scope="local",
        discount_pct=10.0,
        notes="Upgrade con cotizacion comercial",
    )
    db.commit()

    assert result.preview.pricing_source == "commercial_quote"
    assert result.new_reservation.sellable_product_id == target_product.id
    assert result.new_reservation.rate_plan_id == target_rate_plan.id
    assert result.new_reservation.tax_policy_id == target_tax_policy.id
    assert float(result.new_reservation.total_amount) == pytest.approx(326.7)
    assert float(result.new_reservation.tax_amount) == pytest.approx(56.7)
    assert float(result.new_reservation.deposit_amount) == pytest.approx(98.01)
    assert result.billing_adjustment is not None
    assert float(result.billing_adjustment.total_amount) == pytest.approx(126.7)


def test_run_persisted_allocation_assigns_rooms_and_persists_run(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    second_guest = sample_guest.__class__(
        hotel_id=hotel_config.id,
        first_name="Laura",
        last_name="Segundo",
        terms_accepted=True,
    )
    db.add(second_guest)
    db.flush()

    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="STD_BASE",
        name="Standard base",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()
    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[0].id,
            compatibility_kind="exact",
            priority=1,
        )
    )
    db.flush()

    reservation_a = Reservation(
        confirmation_code="ALLOC-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    reservation_b = Reservation(
        confirmation_code="ALLOC-2",
        hotel_id=hotel_config.id,
        guest_id=second_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 4),
        total_amount=300.0,
        subtotal_amount=300.0,
        net_amount=300.0,
        amount_paid=0.0,
        deposit_amount=90.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add_all([reservation_a, reservation_b])
    db.flush()

    persisted = run_persisted_allocation(
        db,
        hotel_id=hotel_config.id,
        trigger_type="test",
        apply=True,
        horizon_start=date(2026, 8, 1),
        horizon_end=date(2026, 8, 10),
    )
    db.commit()

    db.refresh(reservation_a)
    db.refresh(reservation_b)
    assert persisted.run.status.value == "succeeded"
    assert reservation_a.room_id is not None
    assert reservation_b.room_id is not None
    assert reservation_a.room_id != reservation_b.room_id
    assert reservation_a.allocation_status == "assigned"
    assert reservation_b.allocation_status == "assigned"


def test_move_reservation_room_creates_feedback_trace(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 10),
        check_out_date=date(2026, 8, 12),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=0.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import move_reservation_room

    move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=sample_rooms[1].id,
        hotel_id=hotel_config.id,
        moved_by_user_id=None,
        reason_code="guest_preference",
        notes="Prefiere otra orientacion",
    )
    db.commit()

    override = db.query(ManualOverrideReason).filter_by(reservation_id=reservation.id, override_type="room_move").one()
    feedback = db.query(LLMFeedbackEvent).filter_by(reservation_id=reservation.id, event_type="manual_override").one()
    assert override.reason_code == "guest_preference"
    assert override.created_by_user_id is None
    assert feedback.manual_override_reason_id == override.id


def test_move_reservation_room_creates_manual_audit_event(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-AUDIT",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 13),
        check_out_date=date(2026, 8, 15),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=0.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.models.operations import RoomMoveEvent
    from app.services.reservation_operations_service import move_reservation_room

    previous_room_id = sample_rooms[0].id
    new_room_id = sample_rooms[1].id
    result = move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=new_room_id,
        hotel_id=hotel_config.id,
        moved_by_user_id=None,
        reason_code="guest_preference",
        notes="Prefiere otra orientacion",
    )
    db.commit()

    persisted_event = db.get(RoomMoveEvent, result.event.id)
    assert persisted_event.from_room_id == previous_room_id
    assert persisted_event.to_room_id == new_room_id
    assert persisted_event.trigger_event == "manual"
    assert persisted_event.reason_code == "guest_preference"


def test_move_reservation_room_updates_room_status_for_checked_in_reservation(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    """Room.status is a persisted column, not derived from reservations --
    a checked-in guest's room move must flip old/new Room.status explicitly
    (bug: previously left the old room OCCUPIED and the new one untouched)."""
    from_room = sample_rooms[0]
    to_room = sample_rooms[1]
    from_room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    reservation = Reservation(
        confirmation_code="ROOM-MOVE-STATUS",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=from_room.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 16),
        check_out_date=date(2026, 8, 18),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=120.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.CHECKED_IN,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import move_reservation_room

    move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=to_room.id,
        hotel_id=hotel_config.id,
        moved_by_user_id=None,
        reason_code="guest_preference",
        notes="Cambio de habitacion con huesped alojado",
        origin_room_disposition="cleaning",
    )
    db.commit()

    db.refresh(from_room)
    db.refresh(to_room)
    assert to_room.status == RoomStatusEnum.OCCUPIED
    assert from_room.status == RoomStatusEnum.CLEANING


def test_checked_in_room_move_requires_explicit_origin_disposition(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    from app.services.reservation_operations_service import ReservationOperationsError, move_reservation_room

    from_room = sample_rooms[0]
    to_room = sample_rooms[1]
    from_room.status = RoomStatusEnum.OCCUPIED
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-DISPOSITION-REQUIRED",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=from_room.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 19),
        check_out_date=date(2026, 8, 21),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=120.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.CHECKED_IN,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    with pytest.raises(ReservationOperationsError, match="elegir el estado"):
        move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=to_room.id,
            hotel_id=hotel_config.id,
            reason_code="guest_preference",
        )

    assert reservation.room_id == from_room.id
    assert from_room.status == RoomStatusEnum.OCCUPIED
    assert to_room.status == RoomStatusEnum.AVAILABLE


def test_checked_in_room_move_persists_non_cleaning_disposition_and_note(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    from app.models.operations import RoomMoveEvent
    from app.services.reservation_operations_service import ReservationOperationsError, move_reservation_room

    from_room = sample_rooms[0]
    to_room = sample_rooms[1]
    from_room.status = RoomStatusEnum.OCCUPIED
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-DISPOSITION-NOTE",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=from_room.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 22),
        check_out_date=date(2026, 8, 24),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=120.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.CHECKED_IN,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    with pytest.raises(ReservationOperationsError, match="justificaci\u00f3n"):
        move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=to_room.id,
            hotel_id=hotel_config.id,
            reason_code="guest_preference",
            origin_room_disposition="maintenance",
        )

    result = move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=to_room.id,
        hotel_id=hotel_config.id,
        reason_code="guest_preference",
        notes="El huésped usó parcialmente la habitación y reportó una falla.",
        origin_room_disposition="maintenance",
        origin_room_disposition_note="El huésped usó parcialmente la habitación y reportó una falla.",
    )
    db.commit()
    persisted_event = db.get(RoomMoveEvent, result.event.id)

    assert from_room.status == RoomStatusEnum.MAINTENANCE
    assert to_room.status == RoomStatusEnum.OCCUPIED
    assert result.origin_room_status_before == RoomStatusEnum.OCCUPIED.value
    assert result.origin_room_status_after == RoomStatusEnum.MAINTENANCE.value
    assert persisted_event.origin_room_disposition == "maintenance"
    assert persisted_event.origin_room_disposition_note.startswith("El huésped")


def test_move_reservation_room_ignores_status_for_non_checked_in_reservation(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    from_room = sample_rooms[0]
    to_room = sample_rooms[1]

    reservation = Reservation(
        confirmation_code="ROOM-MOVE-STATUS-PENDING",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=from_room.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 20),
        check_out_date=date(2026, 8, 22),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=0.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import move_reservation_room

    result = move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=to_room.id,
        hotel_id=hotel_config.id,
        moved_by_user_id=None,
        reason_code="guest_preference",
        notes="Reserva futura sin huesped alojado",
    )
    db.commit()

    db.refresh(from_room)
    db.refresh(to_room)
    assert from_room.status == RoomStatusEnum.AVAILABLE
    assert to_room.status == RoomStatusEnum.AVAILABLE
    assert result.event.origin_room_disposition is None


def test_create_grouped_room_move_updates_room_status_for_checked_in_reservation(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    from app.models.operations import RoomMoveTypeEnum
    from app.services.room_movement_group_service import create_grouped_room_move

    from_room = sample_rooms[0]
    to_room = sample_rooms[1]
    from_room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    reservation = Reservation(
        confirmation_code="GROUPED-MOVE-STATUS",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=from_room.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 24),
        check_out_date=date(2026, 8, 26),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=120.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.CHECKED_IN,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    create_grouped_room_move(
        db,
        hotel_id=hotel_config.id,
        reservation=reservation,
        to_room=to_room,
        trigger_reason="extension_conflict",
        reason_code="extension_conflict_equivalent",
        reason_note="Movida agrupada con huesped alojado",
        move_type=RoomMoveTypeEnum.AUTO_ASSIGNMENT,
        trigger_event="extension_conflict",
    )
    db.commit()

    db.refresh(from_room)
    db.refresh(to_room)
    assert to_room.status == RoomStatusEnum.OCCUPIED
    assert from_room.status == RoomStatusEnum.CLEANING


def test_move_reservation_room_requires_reason_code(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-REASON",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 8, 20),
        check_out_date=date(2026, 8, 22),
        total_amount=120.0,
        subtotal_amount=120.0,
        net_amount=120.0,
        amount_paid=0.0,
        deposit_amount=36.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import ReservationOperationsError, move_reservation_room

    with pytest.raises(ReservationOperationsError, match="reason_code"):
        move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=sample_rooms[1].id,
            hotel_id=hotel_config.id,
            reason_code=" ",
        )


# ── B5: room move across categories must revalidate capacity and gate repricing ──


def test_move_reservation_room_rejects_capacity_overflow_across_categories(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    single_category = RoomCategory(
        hotel_id=hotel_config.id,
        name="Single",
        code="SGL_B5",
        base_price_per_night=80.0,
        max_occupancy=1,
    )
    db.add(single_category)
    db.flush()
    single_room = Room(
        room_number="501",
        floor=5,
        category_id=single_category.id,
        hotel_id=hotel_config.id,
    )
    db.add(single_room)
    db.flush()

    reservation = Reservation(
        confirmation_code="ROOM-MOVE-CAPACITY",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import ReservationOperationsError, move_reservation_room

    with pytest.raises(ReservationOperationsError, match="hasta 1"):
        move_reservation_room(
            db,
            reservation=reservation,
            to_room_id=single_room.id,
            hotel_id=hotel_config.id,
            reason_code="guest_preference",
        )
    db.refresh(reservation)
    assert reservation.room_id == sample_rooms[0].id
    assert reservation.category_id == sample_categories[0].id


def test_move_reservation_room_keep_price_action_does_not_change_total_but_returns_quote(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-KEEP",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,  # STD_DBL, 100/night
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 5),
        check_out_date=date(2026, 9, 7),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import move_reservation_room

    superior_room = sample_rooms[20]  # SUP_DBL, 150/night
    result = move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=superior_room.id,
        hotel_id=hotel_config.id,
        reason_code="upgrade",
        price_action="keep",
    )
    db.commit()
    db.refresh(reservation)

    assert reservation.room_id == superior_room.id
    assert reservation.category_id == sample_categories[1].id
    assert float(reservation.total_amount) == 200.0  # untouched, "keep" never applies money
    assert result.category_changed is True
    assert result.price_action == "keep"
    assert float(result.previous_total_amount) == 200.0
    assert float(result.quoted_total_amount) == 300.0  # 2 nights * 150
    assert float(result.amount_delta) == 100.0


def test_move_reservation_room_reprice_updates_total_amount(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="ROOM-MOVE-REPRICE",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,  # STD_DBL, 100/night
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 9),
        check_out_date=date(2026, 9, 11),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    from app.services.reservation_operations_service import move_reservation_room

    superior_room = sample_rooms[21]  # SUP_DBL, 150/night
    result = move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=superior_room.id,
        hotel_id=hotel_config.id,
        reason_code="upgrade",
        price_action="reprice",
    )
    db.commit()
    db.refresh(reservation)

    assert reservation.room_id == superior_room.id
    assert float(reservation.total_amount) == 300.0  # 2 nights * 150, applied
    assert result.price_action == "reprice"
    assert float(result.quoted_total_amount) == 300.0
    assert float(result.amount_delta) == 100.0
