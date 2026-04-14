from __future__ import annotations

from datetime import date

from app.models.commercial import SellableProduct
from app.models.guest import Guest
from app.models.ota_core import OTAProvider, OTAReservationLink, OTAReservationLifecycleEnum
from app.models.operations import ReservationAdjustmentKindEnum
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.services.reservation_action_service import (
    clear_reservation_manual_review,
    get_reservation_operations_summary,
    list_pending_reservation_actions,
    resolve_external_channel_follow_up,
)
from app.services.reservation_operations_service import rebook_ota_reservation_as_direct


def test_operations_summary_tracks_ota_rebook_and_direct_collection(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED_ACTIONS",
        name="Doble compartida acciones",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    original = Reservation(
        confirmation_code="OPS-ACTIONS-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-actions-1",
        num_adults=2,
        num_children=0,
    )
    db.add(original)
    db.flush()

    provider = OTAProvider(code="booking", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    db.add(
        OTAReservationLink(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            reservation_id=original.id,
            external_reservation_id="booking-actions-1",
            provider_state=OTAReservationLifecycleEnum.CONFIRMED,
            sync_status="linked",
        )
    )
    db.flush()

    result = rebook_ota_reservation_as_direct(
        db,
        reservation=original,
        hotel_id=hotel_config.id,
        target_category_id=sample_categories[1].id,
        discount_pct=10.0,
        notes="Upgrade mostrado en inbox operativo",
    )
    db.commit()

    original_summary = get_reservation_operations_summary(db, hotel_id=hotel_config.id, reservation_id=original.id)
    original_codes = {item["code"] for item in original_summary["pending_actions"]}
    assert "resolve_external_channel" in original_codes
    assert "resolve_adjustment_external_action" in original_codes
    assert original_summary["ota_link"]["provider_state"] == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED.value
    assert original_summary["open_adjustments"][0]["kind"] == ReservationAdjustmentKindEnum.OTA_CANCEL_AND_REBOOK.value

    new_summary = get_reservation_operations_summary(db, hotel_id=hotel_config.id, reservation_id=result.new_reservation.id)
    new_codes = {item["code"] for item in new_summary["pending_actions"]}
    assert "collect_from_guest" in new_codes
    assert "resolve_adjustment_external_action" in new_codes
    assert new_summary["financial_summary"]["recommended_next_action"] == "collect_from_guest"
    assert new_summary["payment_collection_model"] == "hotel_collect"


def test_pending_actions_list_is_hotel_scoped_and_sorted_by_priority(
    db,
    hotel_config,
    sample_categories,
    sample_guest,
    sample_categories_hotel2,
    sample_rooms_hotel2,
):
    guest_h2 = Guest(first_name="Ana", last_name="Hotel2", hotel_id=2)
    db.add(guest_h2)
    db.flush()

    reservation_h1 = Reservation(
        confirmation_code="H1-ACTION",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 10),
        check_out_date=date(2026, 9, 12),
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
        requires_manual_review=True,
        allocation_status="manual_review",
        payment_collection_model="hotel_collect",
        settlement_status="pending_hotel_collection",
    )
    db.add(reservation_h1)
    db.flush()

    db.add(
        Reservation(
            confirmation_code="H2-ACTION",
            hotel_id=2,
            guest_id=guest_h2.id,
            room_id=sample_rooms_hotel2[0].id,
            category_id=sample_categories_hotel2[0].id,
            check_in_date=date(2026, 9, 10),
            check_out_date=date(2026, 9, 12),
            total_amount=150.0,
            subtotal_amount=150.0,
            net_amount=150.0,
            amount_paid=0.0,
            deposit_amount=30.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            source=ReservationSourceEnum.DIRECT,
            num_adults=2,
            num_children=0,
            payment_collection_model="hotel_collect",
            settlement_status="pending_hotel_collection",
        )
    )
    db.commit()

    actions = list_pending_reservation_actions(db, hotel_id=hotel_config.id)
    assert actions
    assert {item["reservation_id"] for item in actions} == {reservation_h1.id}
    assert actions[0]["priority"] == "critical"
    assert actions[0]["code"] in {"manual_review_required", "allocation_follow_up"}


def test_resolve_external_channel_follow_up_closes_adjustments_and_ota_link(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED_ACTIONS_RESOLVE",
        name="Doble compartida acciones resolve",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    original = Reservation(
        confirmation_code="OPS-ACTIONS-RESOLVE",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 9, 20),
        check_out_date=date(2026, 9, 22),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-actions-resolve",
        num_adults=2,
        num_children=0,
    )
    db.add(original)
    db.flush()

    provider = OTAProvider(code="booking_resolve", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=original.id,
        external_reservation_id="booking-actions-resolve",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
    )
    db.add(link)
    db.flush()

    rebook_ota_reservation_as_direct(
        db,
        reservation=original,
        hotel_id=hotel_config.id,
        target_category_id=sample_categories[1].id,
        discount_pct=10.0,
        notes="Upgrade a resolver externamente",
    )
    db.flush()

    response = resolve_external_channel_follow_up(
        db,
        hotel_id=hotel_config.id,
        reservation_id=original.id,
        resolved_by_user_id=77,
        notes="Cancelado manualmente en Booking",
    )
    db.commit()

    db.refresh(original)
    db.refresh(link)
    assert response["changed_adjustments"] >= 1
    assert response["ota_link_resolved"] is True
    assert original.settlement_status == "resolved"
    assert link.provider_state == OTAReservationLifecycleEnum.CANCELLED
    assert link.sync_status == "resolved"


def test_clear_manual_review_resets_flag_and_keeps_unassigned_if_needed(
    db,
    hotel_config,
    sample_categories,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="OPS-CLEAR-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 25),
        check_out_date=date(2026, 9, 27),
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
        requires_manual_review=True,
        allocation_status="manual_review",
    )
    db.add(reservation)
    db.flush()

    response = clear_reservation_manual_review(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        reviewed_by_user_id=55,
        notes="Validado por recepcion",
    )
    db.commit()

    db.refresh(reservation)
    assert response["requires_manual_review"] is False
    assert reservation.requires_manual_review is False
    assert reservation.allocation_status == "unassigned"
