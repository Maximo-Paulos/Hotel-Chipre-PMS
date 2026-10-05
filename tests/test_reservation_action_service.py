from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import event

import app.services.reservation_action_service as reservation_action_service
from app.models.commercial import SellableProduct
from app.models.company import Company
from app.models.guest import Guest
from app.models.ota_core import OTAProvider, OTAReservationLink, OTAReservationLifecycleEnum
from app.models.operations import (
    BillingAdjustment,
    BillingAdjustmentTypeEnum,
    ReservationAdjustment,
    ReservationAdjustmentKindEnum,
    ReservationAdjustmentStatusEnum,
    RoomMoveEvent,
    RoomMoveTypeEnum,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.services.financial_ledger import completed_paid_amounts_by_reservation
from app.services.reservation_action_service import (
    _candidate_reservation_ids,
    clear_reservation_manual_review,
    get_reservation_operations_summary,
    list_pending_reservation_actions,
    resolve_external_channel_follow_up,
)
from app.services.reservation_operations_service import rebook_ota_reservation_as_direct


# Reservation dates are anchored to "today" instead of literal calendar dates:
# list_pending_reservation_actions() only considers stays whose check-out is
# within _ACTIVE_WINDOW_DAYS of the hotel's today, so fixed dates silently stop
# matching once the real date moves past them. The +/-2 day span absorbs any
# one-day drift between date.today() and the hotel timezone's today.
_IN_WINDOW_CHECK_IN = date.today()
_IN_WINDOW_CHECK_OUT = date.today() + timedelta(days=2)

# Deliberately outside the active window: the regression for pruning stale
# active reservations.
_STALE_CHECK_IN = date.today() - timedelta(days=400)
_STALE_CHECK_OUT = date.today() - timedelta(days=398)


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
        check_in_date=_IN_WINDOW_CHECK_IN,
        check_out_date=_IN_WINDOW_CHECK_OUT,
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
        check_in_date=_IN_WINDOW_CHECK_IN,
        check_out_date=_IN_WINDOW_CHECK_OUT,
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
            check_in_date=_IN_WINDOW_CHECK_IN,
            check_out_date=_IN_WINDOW_CHECK_OUT,
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
        check_in_date=_IN_WINDOW_CHECK_IN,
        check_out_date=_IN_WINDOW_CHECK_OUT,
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
        check_in_date=_IN_WINDOW_CHECK_IN,
        check_out_date=_IN_WINDOW_CHECK_OUT,
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
        # Keep the generic fixtures inside the service's active window. The
        # explicit January fixture below remains the regression for pruning
        # stale active reservations.
        check_in_date=date.today() - timedelta(days=1),
        check_out_date=date.today() + timedelta(days=1),
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


def test_completed_paid_amounts_group_net_completed_transactions_and_scope_hotel(
    db, hotel_config, sample_categories, sample_categories_hotel2, sample_guest,
):
    reservation = _mk_reservation(
        db,
        code="LEDGER-GROUPED-1",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
    )
    another_reservation = _mk_reservation(
        db,
        code="LEDGER-GROUPED-2",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
    )
    foreign_guest = Guest(
        first_name="Other",
        last_name="Hotel",
        email="other-hotel-ledger@example.test",
        terms_accepted=False,
        hotel_id=2,
    )
    db.add(foreign_guest)
    db.flush()
    foreign_reservation = _mk_reservation(
        db,
        code="LEDGER-GROUPED-FOREIGN",
        guest_id=foreign_guest.id,
        category_id=sample_categories_hotel2[0].id,
        hotel_id=2,
    )
    db.flush()
    db.add_all(
        [
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("100.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("12.34"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.REFUND,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("7.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.DEPOSIT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.PENDING,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=another_reservation.id,
                amount=Decimal("50.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.DEPOSIT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=2,
                reservation_id=foreign_reservation.id,
                amount=Decimal("900.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
        ]
    )
    db.flush()

    captured_sql: list[str] = []

    def _capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "from transactions" in statement.lower():
            captured_sql.append(statement.lower())

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _capture_sql)
    try:
        totals = completed_paid_amounts_by_reservation(
            db,
            hotel_config.id,
            [reservation.id, another_reservation.id, foreign_reservation.id],
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture_sql)

    assert totals == {
        reservation.id: Decimal("87.66"),
        another_reservation.id: Decimal("50.00"),
    }
    assert len(captured_sql) == 1
    assert "sum(" in captured_sql[0]
    assert "group by transactions.reservation_id" in captured_sql[0]


def test_pending_action_adjustment_batch_omits_rows_that_cannot_create_actions(
    db, hotel_config, sample_categories, sample_categories_hotel2, sample_guest,
):
    candidate = _mk_reservation(
        db,
        code="ADJUSTMENT-CANDIDATE",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
    )
    source = _mk_reservation(
        db,
        code="ADJUSTMENT-SOURCE",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
    )
    db.flush()
    actionable = [
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.DRAFT,
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=source.id,
            resulting_reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.APPLIED,
            external_resolution_status="manual_resolution_required",
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.FAILED,
            external_resolution_status="pending_hotel_action",
        ),
    ]
    inactive = [
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.APPLIED,
            external_resolution_status="resolved",
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.CANCELLED,
            external_resolution_status="review_cancellation",
        ),
        ReservationAdjustment(
            hotel_id=2,
            reservation_id=candidate.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
        ),
    ]
    db.add_all(actionable + inactive)
    db.flush()

    grouped = reservation_action_service._related_adjustments_by_reservation(
        db,
        hotel_id=hotel_config.id,
        reservation_ids=[candidate.id],
    )

    assert {row.id for row in grouped[candidate.id]} == {row.id for row in actionable}
    assert not reservation_action_service._related_adjustments_by_reservation(
        db,
        hotel_id=hotel_config.id,
        reservation_ids=[],
    )


def test_cancelled_reservation_never_offers_collection_action(
    db, hotel_config, sample_categories, sample_guest,
):
    cancelled = _mk_reservation(
        db,
        code="CANCELLED-UNPAID",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
        status=ReservationStatusEnum.CANCELLED,
        source=ReservationSourceEnum.DIRECT,
        payment_collection_model="hotel_collect",
        total_amount=100.0,
        amount_paid=0.0,
    )
    active = _mk_reservation(
        db,
        code="ACTIVE-UNPAID",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        payment_collection_model="hotel_collect",
        total_amount=100.0,
        amount_paid=0.0,
    )
    db.commit()

    cancelled_summary = get_reservation_operations_summary(
        db, hotel_id=hotel_config.id, reservation_id=cancelled.id,
    )
    active_summary = get_reservation_operations_summary(
        db, hotel_id=hotel_config.id, reservation_id=active.id,
    )
    actions = list_pending_reservation_actions(db, hotel_id=hotel_config.id, limit=50)
    collection_actions = [action for action in actions if action["code"] == "collect_from_guest"]

    assert all(action["code"] != "collect_from_guest" for action in cancelled_summary["pending_actions"])
    assert cancelled_summary["financial_summary"]["recommended_next_action"] is None
    assert active_summary["financial_summary"]["recommended_next_action"] == "collect_from_guest"
    assert {action["reservation_id"] for action in collection_actions} == {active.id}


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


def _legacy_operations_summary_reference(db, *, hotel_id, reservation_id):
    """Reproduce the pre-batch detail assembly for an exact JSON comparison."""
    reservation = reservation_action_service._get_reservation_or_error(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation_id,
    )
    financial_summary = reservation_action_service.get_reservation_financial_summary(
        db,
        hotel_id,
        reservation.id,
    )
    if (
        reservation.status == ReservationStatusEnum.CANCELLED
        and financial_summary.get("recommended_next_action") == "collect_from_guest"
    ):
        financial_summary["recommended_next_action"] = None
    ota_link = reservation_action_service._get_latest_ota_link(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
    )
    adjustments = reservation_action_service._get_related_adjustments(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
    )
    latest_room_move = reservation_action_service._get_latest_room_move(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
    )
    pending_actions = reservation_action_service._build_pending_actions(
        reservation=reservation,
        ota_link=ota_link,
        related_adjustments=adjustments,
        financial_summary=financial_summary,
    )
    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "source": reservation.source.value,
        "source_provider_code": reservation.source_provider_code,
        "allocation_status": reservation.allocation_status,
        "requires_manual_review": reservation.requires_manual_review,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "pending_action_count": len(pending_actions),
        "pending_actions": pending_actions,
        "financial_summary": financial_summary,
        "ota_link": reservation_action_service._serialize_ota_link(ota_link),
        "open_adjustments": [reservation_action_service._serialize_adjustment(row) for row in adjustments],
        "latest_room_move": reservation_action_service._serialize_room_move(latest_room_move),
    }


def test_latest_ota_links_batch_returns_one_tie_broken_row_without_joined_relationships(
    db,
    hotel_config,
    sample_categories,
    sample_guest,
):
    reservation = _mk_reservation(
        db,
        code="OTA-LATEST-BATCH",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
        status=ReservationStatusEnum.PENDING,
    )
    provider = OTAProvider(
        code="ota-latest-batch",
        name="OTA latest batch",
        auth_type="api_key",
        security_model="shared_secret",
    )
    db.add(provider)
    db.flush()

    same_timestamp = datetime(2026, 1, 2, tzinfo=timezone.utc)
    older_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ota-latest-old",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    earlier_tied_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ota-latest-tie-earlier-id",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
        updated_at=same_timestamp,
    )
    db.add_all([older_link, earlier_tied_link])
    db.flush()
    latest_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ota-latest-tie-later-id",
        provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        sync_status="manual_resolution_required",
        updated_at=same_timestamp,
    )
    db.add(latest_link)
    db.flush()
    hotel_id = hotel_config.id
    reservation_id = reservation.id
    earlier_tied_link_id = earlier_tied_link.id
    latest_link_id = latest_link.id
    db.commit()

    captured_sql: list[str] = []

    def _capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        captured_sql.append(statement.lower())

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _capture_sql)
    try:
        latest_by_reservation = reservation_action_service._latest_ota_links_by_reservation(
            db,
            hotel_id=hotel_id,
            reservation_ids=[reservation_id],
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture_sql)

    assert latest_link_id > earlier_tied_link_id
    assert len(latest_by_reservation) == 1
    assert latest_by_reservation[reservation_id].id == latest_link_id
    assert len(captured_sql) == 1
    assert "row_number() over" in captured_sql[0]
    assert "ranked_ota_links.latest_rank" in captured_sql[0]
    assert "left outer join" not in captured_sql[0]


def test_operations_summary_batches_related_reads_with_exact_json_parity(
    db,
    hotel_config,
    sample_categories,
    sample_categories_hotel2,
    sample_rooms,
    sample_guest,
):
    reservation = _mk_reservation(
        db,
        code="OPS-BATCH-OTA",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="ops-batch-ota-1",
        payment_collection_model="ota_prepaid",
        settlement_status="pending",
        total_amount=Decimal("120.00"),
        amount_paid=Decimal("110.00"),
        external_paid_amount=Decimal("30.00"),
        external_paid_currency="ARS",
        external_paid_confirmed=True,
    )
    db.flush()

    db.add_all(
        [
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("100.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("20.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.REFUND,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("7.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.FAILED,
            ),
        ]
    )
    db.add_all(
        [
            BillingAdjustment(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
                amount=Decimal("10.00"),
                total_amount=Decimal("10.00"),
            ),
            BillingAdjustment(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                adjustment_type=BillingAdjustmentTypeEnum.CREDIT,
                amount=Decimal("-5.00"),
                total_amount=Decimal("-5.00"),
            ),
        ]
    )

    provider = OTAProvider(
        code="ops-batch-ota",
        name="OTA operaciones batch",
        auth_type="api_key",
        security_model="shared_secret",
    )
    db.add(provider)
    db.flush()
    older_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ops-batch-old",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    latest_link_candidate = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ops-batch-latest-candidate",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    latest_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="ops-batch-latest",
        provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        sync_status="manual_resolution_required",
        error_message="synthetic latest status",
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    cross_hotel_link = OTAReservationLink(
        hotel_id=2,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id="foreign-hotel-link",
        provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        sync_status="manual_resolution_required",
        updated_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    db.add_all([older_link, latest_link_candidate, latest_link, cross_hotel_link])

    adjustment_source = _mk_reservation(
        db,
        code="OPS-BATCH-ADJUSTMENT-SOURCE",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
    )
    db.flush()
    adjustment_rows = [
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            kind=ReservationAdjustmentKindEnum.UPGRADE,
            status=ReservationAdjustmentStatusEnum.APPLIED,
            reason_code="old-applied",
            request_source="hotel",
            notes="older source adjustment",
            requested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=adjustment_source.id,
            resulting_reservation_id=reservation.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.DRAFT,
            reason_code="resulting-reservation",
            request_source="hotel",
            notes="newer incoming adjustment",
            requested_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            kind=ReservationAdjustmentKindEnum.REFUND,
            status=ReservationAdjustmentStatusEnum.PENDING,
            reason_code="newest-source",
            request_source="hotel",
            notes="newest source adjustment",
            requested_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]
    adjustment_rows.append(
        ReservationAdjustment(
            hotel_id=2,
            reservation_id=reservation.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
            reason_code="cross-hotel-adjustment",
            request_source="hotel",
        )
    )
    db.add_all(adjustment_rows)

    room_moves = [
        RoomMoveEvent(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            from_room_id=sample_rooms[0].id,
            to_room_id=sample_rooms[1].id,
            move_type=RoomMoveTypeEnum.MANUAL_MOVE,
            reason_code="older-move",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        RoomMoveEvent(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            from_room_id=sample_rooms[0].id,
            to_room_id=sample_rooms[1].id,
            move_type=RoomMoveTypeEnum.UPGRADE,
            reason_code="latest-move",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
    ]
    room_moves.append(
        RoomMoveEvent(
            hotel_id=2,
            reservation_id=reservation.id,
            from_room_id=sample_rooms[0].id,
            to_room_id=sample_rooms[1].id,
            move_type=RoomMoveTypeEnum.MAINTENANCE_RELOCATION,
            reason_code="cross-hotel-move",
            occurred_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.add_all(room_moves)
    db.commit()

    legacy_query_count, expected = _count_queries(
        db,
        lambda: _legacy_operations_summary_reference(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
        ),
    )
    optimized_query_count, actual = _count_queries(
        db,
        lambda: get_reservation_operations_summary(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
        ),
    )

    assert actual == expected
    assert actual["ota_link"]["id"] == latest_link.id
    assert [row["reason_code"] for row in actual["open_adjustments"]] == [
        "newest-source",
        "resulting-reservation",
        "old-applied",
    ]
    assert actual["latest_room_move"]["reason_code"] == "latest-move"
    assert all(row["reason_code"] != "cross-hotel-adjustment" for row in actual["open_adjustments"])
    assert actual["financial_summary"]["hotel_received_amount"] == Decimal("80.00")
    assert actual["financial_summary"]["ota_prepaid_amount"] == Decimal("30.00")
    assert optimized_query_count <= legacy_query_count - 2, (
        "batching OTA link, adjustment history, and latest room move should save at least two round trips; "
        f"legacy={legacy_query_count}, optimized={optimized_query_count}"
    )


def test_operations_summary_keeps_company_deferred_financial_view_unchanged(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Empresa diferida summary",
        display_name="Empresa diferida summary",
        payment_deferred=True,
    )
    db.add(company)
    db.flush()
    reservation = _mk_reservation(
        db,
        code="OPS-BATCH-DEFERRED",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        status=ReservationStatusEnum.PENDING,
        company_id=company.id,
        total_amount=Decimal("900.00"),
        amount_paid=Decimal("100.00"),
    )
    db.flush()
    db.add(
        Transaction(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            amount=Decimal("100.00"),
            currency="ARS",
            transaction_type=TransactionTypeEnum.DEPOSIT,
            payment_method=PaymentMethodEnum.CASH,
            status=TransactionStatusEnum.COMPLETED,
        )
    )
    db.add(
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
            reason_code="deferred-company-adjustment",
            request_source="hotel",
        )
    )
    db.commit()

    expected = _legacy_operations_summary_reference(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
    )
    actual = get_reservation_operations_summary(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
    )

    assert actual == expected
    assert actual["financial_summary"]["company_billing_deferred"] is True
    assert actual["financial_summary"]["total_amount"] is None
    assert actual["financial_summary"]["amount_paid"] is None
    assert actual["financial_summary"]["transactions"] == []
    assert actual["open_adjustments"][0]["reason_code"] == "deferred-company-adjustment"


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


def test_pending_actions_batch_query_count_is_constant_for_five_vs_twenty_five_candidates(
    db, hotel_config, sample_categories, sample_rooms, sample_guest,
):
    category_id = sample_categories[0].id
    room_id = sample_rooms[0].id

    def _seed(start, count):
        for index in range(start, start + count):
            _mk_reservation(
                db,
                code=f"BATCH-{index}",
                guest_id=sample_guest.id,
                category_id=category_id,
                hotel_id=hotel_config.id,
                room_id=room_id,
                status=ReservationStatusEnum.PENDING,
                requires_manual_review=True,
                allocation_status="assigned",
            )
        db.commit()

    _seed(0, 5)
    five_count, five_actions = _count_queries(
        db,
        lambda: list_pending_reservation_actions(db, hotel_id=hotel_config.id, limit=100),
    )
    _seed(5, 20)
    twenty_five_count, twenty_five_actions = _count_queries(
        db,
        lambda: list_pending_reservation_actions(db, hotel_id=hotel_config.id, limit=100),
    )

    assert len(five_actions) == 5
    assert len(twenty_five_actions) == 25
    assert twenty_five_count == five_count, (
        f"batch query count grew with candidates: {five_count} -> {twenty_five_count}"
    )


def test_pending_actions_batch_matches_complete_detail_summary_output(
    db, hotel_config, sample_categories, sample_rooms, sample_guest,
):
    category_id = sample_categories[0].id
    room_id = sample_rooms[0].id

    direct_paid_and_refunded = _mk_reservation(
        db,
        code="BATCH-DIRECT-REFUND",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("75.00"),
        allocation_status="assigned",
    )
    db.flush()
    db.add_all(
        [
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=direct_paid_and_refunded.id,
                amount=Decimal("100.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=direct_paid_and_refunded.id,
                amount=Decimal("25.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.REFUND,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            # Failed/pending transaction history disables the legacy amount_paid fallback.
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=direct_paid_and_refunded.id,
                amount=Decimal("1.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.DEPOSIT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.FAILED,
            ),
        ]
    )

    ota_reservation = _mk_reservation(
        db,
        code="BATCH-OTA-CANCELLED",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.CANCELLED,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="batch-ota-cancelled",
        payment_collection_model="ota_prepaid",
        settlement_status="unknown",
        external_paid_amount=Decimal("40.00"),
        external_paid_currency="USD",  # Mismatched currency must remain excluded.
        external_paid_confirmed=True,
    )

    adjustment_source = _mk_reservation(
        db,
        code="BATCH-ADJUSTMENT-SOURCE",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.CHECKED_OUT,
        allocation_status="assigned",
    )
    adjustment_result = _mk_reservation(
        db,
        code="BATCH-ADJUSTMENT-RESULT",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.CHECKED_OUT,
        allocation_status="assigned",
    )

    deferred_company = Company(
        hotel_id=hotel_config.id,
        legal_name="Empresa diferida batch",
        display_name="Empresa diferida batch",
        payment_deferred=True,
    )
    db.add(deferred_company)
    db.flush()
    deferred_reservation = _mk_reservation(
        db,
        code="BATCH-DEFERRED-COMPANY",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.PENDING,
        allocation_status="assigned",
        payment_collection_model="hotel_collect",
        total_amount=Decimal("120.00"),
        amount_paid=Decimal("0.00"),
        company_id=deferred_company.id,
    )

    gap_at_threshold = _mk_reservation(
        db,
        code="BATCH-GAP-001",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.CHECKED_OUT,
        allocation_status="assigned",
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
    )
    gap_above_threshold = _mk_reservation(
        db,
        code="BATCH-GAP-002",
        guest_id=sample_guest.id,
        category_id=category_id,
        hotel_id=hotel_config.id,
        room_id=room_id,
        status=ReservationStatusEnum.CHECKED_OUT,
        allocation_status="assigned",
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
    )
    db.flush()
    db.add_all(
        [
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=gap_at_threshold.id,
                amount=Decimal("99.99"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=gap_above_threshold.id,
                amount=Decimal("99.98"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.COMPLETED,
            ),
        ]
    )
    provider = OTAProvider(
        code="batch-action-ota",
        name="Batch action OTA",
        auth_type="api_key",
        security_model="shared_secret",
    )
    db.add(provider)
    db.flush()
    older_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=ota_reservation.id,
        external_reservation_id="batch-ota-old",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="linked",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    latest_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        reservation_id=ota_reservation.id,
        external_reservation_id="batch-ota-latest",
        provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        sync_status="manual_resolution_required",
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db.add_all([older_link, latest_link])
    db.add(
        ReservationAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=adjustment_source.id,
            resulting_reservation_id=adjustment_result.id,
            kind=ReservationAdjustmentKindEnum.OTHER,
            status=ReservationAdjustmentStatusEnum.PENDING,
            reason_code="batch_resulting_reservation",
            request_source="hotel",
            external_resolution_status="pending_hotel_action",
        )
    )
    db.add(
        BillingAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=direct_paid_and_refunded.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=Decimal("10.00"),
            total_amount=Decimal("10.00"),
        )
    )
    db.commit()

    candidate_ids = _candidate_reservation_ids(db, hotel_id=hotel_config.id)
    expected = []
    for reservation_id in candidate_ids:
        detail = get_reservation_operations_summary(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation_id,
        )
        expected.extend(detail["pending_actions"])
    expected.sort(
        key=lambda item: (
            -{"critical": 4, "high": 3, "medium": 2, "low": 1}.get(item["priority"], 0),
            item["check_in_date"],
            item["reservation_id"],
            item["action_key"],
        )
    )

    actual = list_pending_reservation_actions(db, hotel_id=hotel_config.id, limit=250)
    assert actual == expected
    assert any(
        item["reservation_id"] == adjustment_result.id
        and item["reference_type"] == "reservation_adjustment"
        for item in actual
    )
    assert any(
        item["reservation_id"] == ota_reservation.id
        and item["reference_id"] == latest_link.id
        for item in actual
    )
    assert not any(
        item["reservation_id"] == gap_at_threshold.id
        and item["code"] == "financial_reconciliation_gap"
        for item in actual
    )
    assert any(
        item["reservation_id"] == gap_above_threshold.id
        and item["code"] == "financial_reconciliation_gap"
        for item in actual
    )
    assert not any(
        item["reservation_id"] == deferred_reservation.id
        and item["code"] in {"collect_from_guest", "financial_reconciliation_gap"}
        for item in actual
    )


def test_pending_actions_failed_and_pending_history_does_not_credit_legacy_paid_amount(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = _mk_reservation(
        db,
        code="BATCH-FAILED-HISTORY-LEGACY-PAID",
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        hotel_id=hotel_config.id,
        room_id=sample_rooms[0].id,
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
        payment_collection_model="hotel_collect",
        allocation_status="assigned",
    )
    db.flush()
    db.add_all(
        [
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("100.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.DEPOSIT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.FAILED,
            ),
            Transaction(
                hotel_id=hotel_config.id,
                reservation_id=reservation.id,
                amount=Decimal("100.00"),
                currency="ARS",
                transaction_type=TransactionTypeEnum.DEPOSIT,
                payment_method=PaymentMethodEnum.CASH,
                status=TransactionStatusEnum.PENDING,
            ),
        ]
    )
    db.commit()

    expected = get_reservation_operations_summary(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
    )["pending_actions"]
    actual = [
        action
        for action in list_pending_reservation_actions(db, hotel_id=hotel_config.id, limit=100)
        if action["reservation_id"] == reservation.id
    ]

    assert {action["action_key"]: action for action in actual} == {
        action["action_key"]: action for action in expected
    }
    assert {action["code"] for action in actual} == {
        "collect_from_guest",
        "financial_reconciliation_gap",
    }


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
        check_in_date=_STALE_CHECK_IN, check_out_date=_STALE_CHECK_OUT,
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
