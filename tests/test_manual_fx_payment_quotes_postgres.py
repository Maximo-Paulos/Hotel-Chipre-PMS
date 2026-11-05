"""PostgreSQL regressions for manager-approved, reservation-specific FX amounts."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

import app.models  # noqa: F401
from app.models.fx_rate_cache import FxRateCache
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.manual_fx_payment_quote import ManualFxPaymentQuote
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.models.user import User
from app.schemas.transaction import PaymentRequest
from app.services import payment_service, pricing_policy_service
from app.services.cash_register_service import CashMovement, open_session
from app.services.payment_service import (
    PaymentError,
    create_manual_fx_payment_quote,
    get_active_manual_fx_payment_quote,
    get_reservation_financial_summary,
    process_payment,
)
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_PAYMENT_FX_MANUAL_SET,
    ROLE_CO_OWNER,
    ROLE_HOUSEKEEPING,
    ROLE_MANAGER,
    ROLE_OWNER,
    ROLE_RECEPTIONIST,
)
from app.services.tenant_context import set_tenant_hotel_context


def _scenario(pg_session):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 120_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic manual FX {suffix}",
        subscription_active=True,
        fx_rounding_policy="exact",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic manual FX category {suffix}",
        code=f"MF{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="FX Guest")
    authorizer = User(
        email=f"fx-authorizer-{suffix.lower()}@example.invalid",
        password_hash="not-a-real-password-hash",
        is_active=True,
        is_verified=True,
    )
    cashier = User(
        email=f"fx-cashier-{suffix.lower()}@example.invalid",
        password_hash="not-a-real-password-hash",
        is_active=True,
        is_verified=True,
    )
    pg_session.add_all([hotel, authorizer, cashier])
    pg_session.flush()
    pg_session.add_all([category, guest])
    pg_session.flush()

    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"MFX-{suffix}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date.today() + timedelta(days=30),
        check_out_date=date.today() + timedelta(days=32),
        total_amount=Decimal("55000.00"),
        subtotal_amount=Decimal("55000.00"),
        net_amount=Decimal("55000.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    pg_session.add(reservation)
    pg_session.flush()
    open_session(
        pg_session,
        hotel_id=hotel_id,
        opened_by_user_id=cashier.id,
        opening_balance=Decimal("0.00"),
        currency_code="USD",
    )
    return hotel_id, reservation, authorizer, cashier


def _simulate_expired_fx(db, monkeypatch):
    expired_at = datetime.now(UTC) - timedelta(hours=24, seconds=1)
    db.add(
        FxRateCache(
            currency="USD",
            rate_type="oficial",
            provider_market="oficial",
            buy=Decimal("1190.00"),
            sell=Decimal("1200.00"),
            provider_updated_at=expired_at,
            observed_at=expired_at,
            cache_source="daily",
        )
    )
    db.flush()
    # Provider calls are deliberately disabled in this local outage simulation.
    # Keep the real conversion resolver in the path so it must reject the cache
    # only because its trusted observation is older than 24 hours.
    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", lambda *_args: None)


def test_only_authorized_roles_default_to_setting_manual_fx_amount():
    assert DEFAULT_MATRIX[ROLE_OWNER][PERMISSION_PAYMENT_FX_MANUAL_SET] is True
    assert DEFAULT_MATRIX[ROLE_CO_OWNER][PERMISSION_PAYMENT_FX_MANUAL_SET] is True
    assert DEFAULT_MATRIX[ROLE_MANAGER][PERMISSION_PAYMENT_FX_MANUAL_SET] is True
    assert DEFAULT_MATRIX[ROLE_RECEPTIONIST][PERMISSION_PAYMENT_FX_MANUAL_SET] is False
    assert DEFAULT_MATRIX[ROLE_HOUSEKEEPING][PERMISSION_PAYMENT_FX_MANUAL_SET] is False


def test_manual_fx_amount_is_reserved_once_then_cashier_records_that_exact_amount(
    pg_session, monkeypatch
):
    hotel_id, reservation, authorizer, cashier = _scenario(pg_session)
    _simulate_expired_fx(pg_session, monkeypatch)

    approved = create_manual_fx_payment_quote(
        pg_session,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        payment_method=PaymentMethodEnum.CASH,
        currency_code="USD",
        reservation_amount=Decimal("55000.00"),
        tender_amount=Decimal("30.00"),
        reason="API caída hace más de 24 horas; importe autorizado por gerencia.",
        actor_user_id=authorizer.id,
    )
    assert approved["manual_fx_reason"].startswith("API caída")
    assert approved["manual_fx_quote_id"] is not None
    assert approved["base_amount"] == Decimal("30.00")
    assert approved["applied_amount"] == Decimal("55000.00")

    refreshed = get_active_manual_fx_payment_quote(
        pg_session,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        payment_method=PaymentMethodEnum.CASH,
        currency_code="USD",
    )
    assert refreshed is not None
    assert refreshed["manual_fx_quote_id"] == approved["manual_fx_quote_id"]
    assert refreshed["manual_fx_reason"] == approved["manual_fx_reason"]

    request = PaymentRequest(
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        currency="USD",
        payment_quote_token=refreshed["payment_quote_token"],
        manual_fx_quote_id=refreshed["manual_fx_quote_id"],
        cash_received_amount=Decimal("30.00"),
    )
    idempotency_key = f"manual-fx-{uuid4().hex}"
    transaction = process_payment(
        pg_session,
        request,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        actor_user_id=cashier.id,
    )

    pg_session.refresh(reservation)
    manual_quote = pg_session.get(ManualFxPaymentQuote, approved["manual_fx_quote_id"])
    movement = pg_session.query(CashMovement).filter_by(transaction_id=transaction.id).one()
    assert transaction.created_by_user_id == cashier.id
    assert transaction.amount == Decimal("55000.00")
    assert transaction.currency == "ARS"
    assert transaction.tender_amount == Decimal("30.00")
    assert transaction.tender_currency == "USD"
    assert transaction.fx_quote_details["source"] == "authorized_manual_reservation_fx"
    assert transaction.fx_quote_details["manual_fx_quote_id"] == approved["manual_fx_quote_id"]
    assert transaction.fx_quote_details["manual_fx_created_by_user_id"] == authorizer.id
    assert manual_quote.consumed_transaction_id == transaction.id
    assert manual_quote.consumed_at is not None
    assert reservation.amount_paid == Decimal("55000.00")
    assert movement.amount == Decimal("30.00")
    assert get_reservation_financial_summary(pg_session, hotel_id, reservation.id)[
        "operational_balance_due"
    ] == Decimal("0.00")

    replay = process_payment(
        pg_session,
        request,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        actor_user_id=cashier.id,
    )
    assert replay.id == transaction.id
    with pytest.raises(PaymentError, match="ya fue usado o reemplazado"):
        process_payment(
            pg_session,
            request,
            hotel_id=hotel_id,
            idempotency_key=f"manual-fx-reuse-{uuid4().hex}",
            actor_user_id=cashier.id,
        )


def test_manual_fx_is_denied_while_a_current_automatic_quote_exists(pg_session, monkeypatch):
    hotel_id, reservation, authorizer, _cashier = _scenario(pg_session)
    monkeypatch.setattr(
        payment_service,
        "_payment_conversion_rate",
        lambda *_args, **_kwargs: (Decimal("1800.00"), {"source": "current_provider_quote"}),
    )

    with pytest.raises(PaymentError, match="Hay una cotización automática vigente"):
        create_manual_fx_payment_quote(
            pg_session,
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            payment_method=PaymentMethodEnum.CASH,
            currency_code="USD",
            reservation_amount=Decimal("55000.00"),
            tender_amount=Decimal("30.00"),
            reason="No corresponde reemplazar la cotización vigente.",
            actor_user_id=authorizer.id,
        )


def test_manual_fx_amount_cannot_exceed_reservation_balance_or_be_unaudited(
    pg_session, monkeypatch
):
    hotel_id, reservation, authorizer, _cashier = _scenario(pg_session)
    _simulate_expired_fx(pg_session, monkeypatch)

    with pytest.raises(PaymentError, match="supera el saldo actual"):
        create_manual_fx_payment_quote(
            pg_session,
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            payment_method=PaymentMethodEnum.CASH,
            currency_code="USD",
            reservation_amount=Decimal("55000.01"),
            tender_amount=Decimal("30.00"),
            reason="Intento de autorizar por encima del saldo.",
            actor_user_id=authorizer.id,
        )

    with pytest.raises(PaymentError, match="motivo.*obligatorio"):
        create_manual_fx_payment_quote(
            pg_session,
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            payment_method=PaymentMethodEnum.CASH,
            currency_code="USD",
            reservation_amount=Decimal("55000.00"),
            tender_amount=Decimal("30.00"),
            reason="   ",
            actor_user_id=authorizer.id,
        )
