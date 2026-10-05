from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.reservation import ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    change_reservation_dates,
    extend_reservation_stay,
)
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    mark_reservation_no_show,
)


def _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms, *, code_dates=None):
    check_in, check_out = code_dates or (date.today() + timedelta(days=7), date.today() + timedelta(days=9))
    return create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=check_in,
            check_out_date=check_out,
        ),
        hotel_id=1,
    )


def _completed_transaction(db, reservation, amount="50.00"):
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=Decimal(amount),
        currency=reservation.currency_code or "ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.COMPLETED,
    )
    db.add(tx)
    db.flush()
    return tx


def test_no_show_can_be_marked_without_auto_charge(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    assert db.query(Transaction).count() == 0

    mark_reservation_no_show(
        db,
        reservation,
        hotel_id=1,
        client_version=reservation.version,
        notes="Guest did not arrive",
    )

    assert reservation.status == ReservationStatusEnum.NO_SHOW
    assert reservation.no_show_policy_applied.value == "none"
    assert db.query(Transaction).count() == 0


def test_date_change_without_payments_cancels_and_recreates(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    changed_check_in = date.today() + timedelta(days=11)
    changed_check_out = date.today() + timedelta(days=13)

    result = change_reservation_dates(
        db,
        reservation=reservation,
        hotel_id=1,
        check_in_date=changed_check_in,
        check_out_date=changed_check_out,
        client_version=reservation.version,
        manager_authorized=False,
        reason="Guest requested different dates",
    )

    assert result.recreated is True
    assert result.original_reservation.id == reservation.id
    assert result.original_reservation.status == ReservationStatusEnum.CANCELLED
    assert result.reservation.id != reservation.id
    assert result.reservation.check_in_date == changed_check_in
    assert result.reservation.check_out_date == changed_check_out


def test_date_change_with_payments_requires_manager_and_preserves_history(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    pricing_state = (
        reservation.total_amount,
        reservation.subtotal_amount,
        reservation.tax_amount,
        reservation.fee_amount,
        reservation.commission_amount,
        reservation.net_amount,
        reservation.currency_code,
        reservation.pricing_snapshot,
    )
    tx = _completed_transaction(db, reservation)
    changed_check_in = date.today() + timedelta(days=11)
    changed_check_out = date.today() + timedelta(days=13)

    with pytest.raises(ReservationOperationsError, match="requiere gerente"):
        change_reservation_dates(
            db,
            reservation=reservation,
            hotel_id=1,
            check_in_date=changed_check_in,
            check_out_date=changed_check_out,
            client_version=reservation.version,
            manager_authorized=False,
        )

    result = change_reservation_dates(
        db,
        reservation=reservation,
        hotel_id=1,
        check_in_date=changed_check_in,
        check_out_date=changed_check_out,
        client_version=reservation.version,
        manager_authorized=True,
        pricing_mode="keep_current_total",
    )

    assert result.recreated is False
    assert result.reservation.id == reservation.id
    assert reservation.check_in_date == changed_check_in
    assert (
        reservation.total_amount,
        reservation.subtotal_amount,
        reservation.tax_amount,
        reservation.fee_amount,
        reservation.commission_amount,
        reservation.net_amount,
        reservation.currency_code,
        reservation.pricing_snapshot,
    ) == pricing_state
    assert db.get(Transaction, tx.id).reservation_id == reservation.id
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1


def test_paid_date_change_refreshes_analytics_facts_once(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    monkeypatch,
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    payment = _completed_transaction(db, reservation)

    from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily
    from app.services.analytics_facts import refresh_fact_reservation_daily, refresh_fact_room_occupancy_daily

    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date
    changed_check_in = date.today() + timedelta(days=11)
    changed_check_out = date.today() + timedelta(days=13)
    refresh_date_from = min(original_check_in, changed_check_in)
    refresh_date_to = max(original_check_out, changed_check_out)
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=refresh_date_from,
        date_to=refresh_date_to,
    )
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=refresh_date_from,
        date_to=refresh_date_to,
    )

    from app.services import analytics_facts, reservation_operations_service

    original_touch = analytics_facts.touch_reservation_fact_window
    calls = []

    def record_touch(*args, **kwargs):
        calls.append(kwargs.copy())
        return original_touch(*args, **kwargs)

    monkeypatch.setattr(analytics_facts, "touch_reservation_fact_window", record_touch)
    monkeypatch.setattr(reservation_operations_service, "touch_reservation_fact_window", record_touch)

    result = change_reservation_dates(
        db,
        reservation=reservation,
        hotel_id=1,
        check_in_date=changed_check_in,
        check_out_date=changed_check_out,
        client_version=reservation.version,
        manager_authorized=True,
        pricing_mode="keep_current_total",
    )

    assert result.recreated is False
    assert len(calls) == 1
    assert calls[0]["reservation_id"] == reservation.id
    assert calls[0]["date_from"] == refresh_date_from
    assert calls[0]["date_to"] == refresh_date_to
    assert db.get(Transaction, payment.id).status == TransactionStatusEnum.COMPLETED

    reservation_facts = (
        db.query(FactReservationDaily)
        .filter_by(hotel_id=hotel_config.id, reservation_id=reservation.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    new_stay_dates = [changed_check_in + timedelta(days=offset) for offset in range(2)]
    assert [fact.stay_date for fact in reservation_facts] == new_stay_dates
    assert sum((fact.revenue_gross_ars for fact in reservation_facts), Decimal("0")) == Decimal(
        str(reservation.total_amount)
    )
    assert sum((fact.revenue_net_ars for fact in reservation_facts), Decimal("0")) == Decimal(
        str(reservation.net_amount)
    )

    room_facts = {
        fact.stay_date: fact
        for fact in db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_config.id,
            FactRoomOccupancyDaily.room_id == reservation.room_id,
            FactRoomOccupancyDaily.stay_date.between(refresh_date_from, refresh_date_to),
        )
        .all()
    }
    old_stay_dates = [original_check_in + timedelta(days=offset) for offset in range(2)]
    assert all(room_facts[stay_date].is_occupied is False for stay_date in old_stay_dates)
    assert all(room_facts[stay_date].reservation_id is None for stay_date in old_stay_dates)
    assert all(room_facts[stay_date].status_at_night.value == "available" for stay_date in old_stay_dates)
    assert all(room_facts[stay_date].is_occupied is True for stay_date in new_stay_dates)
    assert all(room_facts[stay_date].reservation_id == reservation.id for stay_date in new_stay_dates)


def test_extension_requires_payment_or_link_action(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    new_checkout_date = date.today() + timedelta(days=10)
    reservation.status = ReservationStatusEnum.FULLY_PAID
    reservation.amount_paid = reservation.total_amount
    db.flush()

    with pytest.raises(ReservationOperationsError, match="requiere generar link"):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=1,
            new_checkout_date=new_checkout_date,
            client_version=reservation.version,
            pricing_mode="current_rate",
            payment_action="payment_link",
        )

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=1,
        new_checkout_date=new_checkout_date,
        client_version=reservation.version,
        pricing_mode="current_rate",
        payment_action="payment_link",
        payment_link=PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
        ),
        notes="Guest extends one night",
    )

    assert reservation.check_out_date == new_checkout_date
    assert result.extension_amount == Decimal("100.00")
    assert result.payment_link is not None
    assert result.payment_link.reservation_id == reservation.id


def test_extension_rejects_refund_as_immediate_payment_without_mutating_reservation(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    reservation.status = ReservationStatusEnum.FULLY_PAID
    reservation.amount_paid = reservation.total_amount
    db.flush()
    old_checkout = reservation.check_out_date
    old_total = reservation.total_amount
    old_transaction_count = db.query(Transaction).filter_by(reservation_id=reservation.id).count()

    with pytest.raises(ReservationOperationsError, match="No se permiten devoluciones"):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=1,
            new_checkout_date=old_checkout + timedelta(days=1),
            client_version=reservation.version,
            pricing_mode="original_average",
            payment_action="immediate_payment",
            immediate_payment=PaymentRequest(
                reservation_id=reservation.id,
                amount=100,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.REFUND,
            ),
        )

    assert reservation.check_out_date == old_checkout
    assert reservation.total_amount == old_total
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == old_transaction_count


def test_reservation_lifecycle_optimistic_lock_conflict(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)

    with pytest.raises(ReservationError, match="modified concurrently"):
        mark_reservation_no_show(
            db,
            reservation,
            hotel_id=1,
            client_version=reservation.version + 1,
        )
