from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import event

from app.models.commercial import SellableProduct
from app.models.guest import Guest
from app.models.ota_core import OTAProvider, OTAReservationLink, OTAReservationLifecycleEnum
from app.models.operations import (
    BillingAdjustment,
    BillingAdjustmentTypeEnum,
    ReservationAdjustment,
    ReservationAdjustmentKindEnum,
    ReservationAdjustmentStatusEnum,
)
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


def _mk_reservation(db, *, code, guest_id, category_id, hotel_id=1, room_id=None, **overrides):
    fields = dict(
        confirmation_code=code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 3),
        total_amount=0.0,
        subtotal_amount=0.0,
        net_amount=0.0,
        amount_paid=0.0,
        deposit_amount=0.0,
        currency_code="ARS",
        status=ReservationStatusEnum.CHECKED_OUT,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
        allocation_status="assigned",
        settlement_status="not_applicable",
        payment_collection_model="hotel_collect",
        requires_manual_review=False,
    )
    fields.update(overrides)
    reservation = Reservation(**fields)
    db.add(reservation)
    return reservation


def _count_queries(db, fn):
    engine = db.get_bind()
    counts = [0]

    def _count_query(*_args, **_kwargs):
        counts[0] += 1

    event.listen(engine, "before_cursor_execute", _count_query)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _count_query)
    return counts[0], result


def test_pending_actions_query_count_scales_with_candidates_not_total_reservations(
    db, hotel_config, sample_categories, sample_guest,
):
    """The real N+1 this fix targets: query count must track the number of
    reservations that could actually generate an action, not the hotel's
    total reservation history. Proven differentially -- adding 100 more
    fully-settled, checked-out reservations (none of which can ever produce
    an action) must not measurably move the query count."""
    category_id = sample_categories[0].id

    def _seed(clean_count):
        for i in range(clean_count):
            _mk_reservation(db, code=f"CLEAN-{i}", guest_id=sample_guest.id, category_id=category_id)
        for i in range(5):
            _mk_reservation(
                db,
                code=f"TRIGGER-{i}",
                guest_id=sample_guest.id,
                category_id=category_id,
                status=ReservationStatusEnum.PENDING,
                requires_manual_review=True,
            )
        db.commit()

    _seed(20)
    small_count, small_actions = _count_queries(db, lambda: list_pending_reservation_actions(db, hotel_id=1, limit=20))

    for r in db.query(Reservation).filter(Reservation.confirmation_code.like("CLEAN-%")).all():
        db.delete(r)
    for r in db.query(Reservation).filter(Reservation.confirmation_code.like("TRIGGER-%")).all():
        db.delete(r)
    db.commit()

    _seed(120)
    large_count, large_actions = _count_queries(db, lambda: list_pending_reservation_actions(db, hotel_id=1, limit=20))

    trigger_ids = {r.id for r in db.query(Reservation).filter(Reservation.confirmation_code.like("TRIGGER-%")).all()}
    assert {a["reservation_id"] for a in large_actions} == trigger_ids
    assert len(small_actions) == len(large_actions)

    # 6x more "clean" reservations (20 -> 120) must not move the query count:
    # it's driven by the 5 real candidates, not by the hotel's history size.
    assert large_count <= small_count + 5, (
        f"query count scaled with total reservations, not candidates: {small_count} -> {large_count}"
    )


def test_pending_actions_prefilter_matches_unfiltered_scan_for_every_trigger_type(
    db, hotel_config, sample_categories, sample_guest,
):
    """Every distinct way `_build_pending_actions` can produce an action must
    still surface after the SQL-level prefilter, including ones that fire on
    a *terminal* (cancelled/checked_out) reservation -- the prefilter is not
    allowed to assume terminal status means "no possible action"."""
    category_id = sample_categories[0].id

    manual_review = _mk_reservation(
        db, code="TRIG-MANUAL-REVIEW", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.PENDING, requires_manual_review=True,
    )
    unassigned_room = _mk_reservation(
        db, code="TRIG-UNASSIGNED", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.PENDING, room_id=None, allocation_status="unassigned",
    )
    cancelled_ota = _mk_reservation(
        db, code="TRIG-CANCELLED-OTA", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.CANCELLED, source=ReservationSourceEnum.BOOKING,
    )
    settlement_problem_checked_out = _mk_reservation(
        db, code="TRIG-SETTLEMENT-CHECKEDOUT", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.CHECKED_OUT, settlement_status="pending_hotel_action",
    )
    await_settlement = _mk_reservation(
        db, code="TRIG-AWAIT-SETTLEMENT", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.FULLY_PAID, payment_collection_model="ota_prepaid",
        settlement_status="pending",
    )
    collect_from_guest = _mk_reservation(
        db, code="TRIG-COLLECT", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.PENDING, total_amount=100.0, amount_paid=0.0,
    )
    collect_via_billing_adjustment_checked_out = _mk_reservation(
        db, code="TRIG-BILLING-ADJ", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.CHECKED_OUT, total_amount=100.0, amount_paid=100.0,
    )
    financial_gap_checked_out = _mk_reservation(
        db, code="TRIG-FIN-GAP", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.CHECKED_OUT, total_amount=100.0, amount_paid=100.0,
    )
    adjustment_pending_checked_out = _mk_reservation(
        db, code="TRIG-ADJ-PENDING", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.CHECKED_OUT,
    )
    out_of_window_manual_review = _mk_reservation(
        db, code="TRIG-OUT-OF-WINDOW", guest_id=sample_guest.id, category_id=category_id,
        status=ReservationStatusEnum.PENDING, requires_manual_review=True,
        check_in_date=date(2026, 1, 1), check_out_date=date(2026, 1, 3),
    )
    for i in range(20):
        _mk_reservation(db, code=f"CLEAN-{i}", guest_id=sample_guest.id, category_id=category_id)
    db.flush()

    provider = OTAProvider(code="prefilter_test", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    db.add(
        OTAReservationLink(
            hotel_id=1,
            provider_id=provider.id,
            reservation_id=cancelled_ota.id,
            external_reservation_id="prefilter-cancelled-ota",
            provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
            sync_status="manual_resolution_required",
        )
    )
    db.add(
        BillingAdjustment(
            hotel_id=1,
            reservation_id=collect_via_billing_adjustment_checked_out.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=25.0,
            total_amount=25.0,
        )
    )
    db.add(
        ReservationAdjustment(
            hotel_id=1,
            reservation_id=adjustment_pending_checked_out.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
            reason_code="prefilter_test",
            request_source="hotel",
        )
    )
    db.commit()
    # Financial reconciliation gap: amount_paid materialized without a matching
    # completed Transaction (legacy-import style drift), on a checked-out stay.
    db.refresh(financial_gap_checked_out)
    assert financial_gap_checked_out.amount_paid == 100.0

    def _old_unfiltered_scan(db, *, hotel_id):
        """Reference behaviour: what today's code (before this fix) computes --
        every reservation gets a full summary, no SQL-level prefilter."""
        all_ids = [
            r.id for r in db.query(Reservation).filter(Reservation.hotel_id == hotel_id).all()
        ]
        found = []
        for reservation_id in all_ids:
            summary = get_reservation_operations_summary(db, hotel_id=hotel_id, reservation_id=reservation_id)
            found.extend((item["reservation_id"], item["action_key"]) for item in summary["pending_actions"])
        return set(found)

    old_all = _old_unfiltered_scan(db, hotel_id=1)
    new_result = list_pending_reservation_actions(db, hotel_id=1, limit=250)
    new_keys = {(item["reservation_id"], item["action_key"]) for item in new_result}

    expected_triggers = {
        manual_review.id,
        unassigned_room.id,
        cancelled_ota.id,
        settlement_problem_checked_out.id,
        await_settlement.id,
        collect_from_guest.id,
        collect_via_billing_adjustment_checked_out.id,
        financial_gap_checked_out.id,
        adjustment_pending_checked_out.id,
    }
    old_in_window = {(rid, key) for (rid, key) in old_all if rid != out_of_window_manual_review.id}

    # The new, prefiltered result must be an exact match against the old
    # unfiltered scan for every in-window reservation -- no real action lost.
    assert new_keys == old_in_window
    assert {rid for rid, _ in new_keys} & expected_triggers == expected_triggers
    # Clean reservations never produced an action, in either version.
    clean_ids = {r.id for r in db.query(Reservation).filter(Reservation.confirmation_code.like("CLEAN-%")).all()}
    assert not (clean_ids & {rid for rid, _ in new_keys})

    # Intentional, plan-authorized behaviour change: the date window
    # (check_out_date >= today - 1 day) drops old candidates the unfiltered
    # scan would still report. Document it explicitly rather than silently.
    assert (out_of_window_manual_review.id, "manual_review_required") in old_all
    assert out_of_window_manual_review.id not in {rid for rid, _ in new_keys}
