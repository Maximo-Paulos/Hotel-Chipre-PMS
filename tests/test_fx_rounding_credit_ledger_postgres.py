"""PostgreSQL regressions for exact non-cash FX settlement amounts."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

import app.models  # noqa: F401
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services import payment_service as payment_service_module
from app.services.cash_register_service import CashMovement, open_session
from app.services.payment_service import (
    get_reservation_financial_summary,
    process_payment,
)
from app.services.tenant_context import set_tenant_hotel_context


@pytest.mark.parametrize(
    "payment_method",
    [PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.BANK_TRANSFER],
)
def test_postgres_non_cash_fx_payment_uses_exact_amount_with_round_up_policy(
    pg_session,
    monkeypatch,
    payment_method,
):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 120_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic FX rounding {suffix}",
        subscription_active=True,
        enable_credit_card=True,
        enable_bank_transfer=True,
        fx_rounding_policy="round_up",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic FX category {suffix}",
        code=f"FX{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="FX Guest")
    pg_session.add(hotel)
    pg_session.flush()
    pg_session.add_all([category, guest])
    pg_session.flush()

    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"FX-{suffix}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date.today() + timedelta(days=30),
        check_out_date=date.today() + timedelta(days=32),
        total_amount=Decimal("84600.00"),
        subtotal_amount=Decimal("84600.00"),
        net_amount=Decimal("84600.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    pg_session.add(reservation)
    pg_session.flush()

    def quote(_db, *, amount, **_kwargs):
        return amount * 1500.0, 1500.0, {
            "from_currency": "USD",
            "to_currency": "ARS",
            "source": "deterministic-test-quote",
        }

    monkeypatch.setattr(payment_service_module, "_convert_amount", quote)
    gateway_response = (
        PaymentGatewayResponse(
            success=True,
            external_payment_id=f"test-card-{suffix}",
            external_status="approved",
        )
        if payment_method == PaymentMethodEnum.CREDIT_CARD
        else None
    )
    transaction = process_payment(
        pg_session,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="56.40",
            payment_method=payment_method,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            currency="USD",
        ),
        hotel_id=hotel_id,
        gateway_response=gateway_response,
        manual_confirmation=payment_method == PaymentMethodEnum.BANK_TRANSFER,
        apply_surcharge=False,
    )

    summary = get_reservation_financial_summary(pg_session, hotel_id, reservation.id)
    assert transaction.tender_amount == Decimal("56.40")
    assert transaction.amount == Decimal("84600.00")
    assert transaction.rounding_credit_amount == Decimal("0.00")
    assert transaction.cash_received_amount is None
    assert reservation.amount_paid == Decimal("84600.00")
    assert summary["operational_balance_due"] == Decimal("0.00")
    assert summary["rounding_credit_by_currency"] == []


@pytest.mark.parametrize(
    ("tip_amount", "expected_change"),
    [("0.00", "0.60"), ("0.60", "0.00")],
)
def test_postgres_exact_fx_cash_over_tender_records_change_or_tip_without_credit(
    pg_session,
    monkeypatch,
    tip_amount,
    expected_change,
):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 120_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic exact cash FX {suffix}",
        subscription_active=True,
        fx_rounding_policy="exact",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic FX category {suffix}",
        code=f"FC{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="FX Guest")
    pg_session.add(hotel)
    pg_session.flush()
    pg_session.add_all([category, guest])
    pg_session.flush()

    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"FXC-{suffix}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date.today() + timedelta(days=30),
        check_out_date=date.today() + timedelta(days=32),
        total_amount=Decimal("84600.00"),
        subtotal_amount=Decimal("84600.00"),
        net_amount=Decimal("84600.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    pg_session.add(reservation)
    pg_session.flush()
    open_session(
        pg_session,
        hotel_id=hotel_id,
        opened_by_user_id=None,
        opening_balance=Decimal("0.00"),
        currency_code="USD",
    )

    def quote(_db, *, amount, **_kwargs):
        return amount * 1500.0, 1500.0, {
            "from_currency": "USD",
            "to_currency": "ARS",
            "source": "deterministic-test-quote",
        }

    monkeypatch.setattr(payment_service_module, "_convert_amount", quote)
    request = PaymentRequest(
        reservation_id=reservation.id,
        amount="56.40",
        cash_received_amount="57.00",
        cash_tip_amount=tip_amount,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        currency="USD",
    )
    idempotency_key = f"exact-fx-cash-{suffix}-{tip_amount}"
    transaction = process_payment(
        pg_session,
        request,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        apply_surcharge=False,
    )
    replay = process_payment(
        pg_session,
        request,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        apply_surcharge=False,
    )
    movement = pg_session.query(CashMovement).filter_by(transaction_id=transaction.id).one()
    summary = get_reservation_financial_summary(pg_session, hotel_id, reservation.id)

    assert transaction.tender_amount == Decimal("56.40")
    assert transaction.amount == Decimal("84600.00")
    assert transaction.gross_amount == Decimal("56.40")
    assert transaction.cash_received_amount == Decimal("57.00")
    assert transaction.cash_change_amount == Decimal(expected_change)
    assert transaction.cash_tip_amount == Decimal(tip_amount)
    assert transaction.rounding_credit_amount == Decimal("0.00")
    assert movement.amount == Decimal("56.40") + Decimal(tip_amount)
    assert reservation.amount_paid == Decimal("84600.00")
    assert replay.id == transaction.id
    assert summary["operational_balance_due"] == Decimal("0.00")
    assert summary["rounding_credit_by_currency"] == []
