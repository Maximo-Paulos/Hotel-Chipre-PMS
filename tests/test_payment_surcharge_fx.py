from datetime import date
from decimal import Decimal

import pytest

from app.models.payment import Payment
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.transaction import PaymentRequest
from app.services import payment_link_service, payment_service
from app.services.cash_register_service import open_session
from app.services.payment_link_service import create_link
from app.services.payment_service import (
    PaymentError,
    calculate_payment_surcharge,
    process_payment,
    quote_reservation_payment_surcharge,
)
from app.services.payment_webhook_service import _ensure_completed_transaction


def _reservation(db, guest, category, hotel_config, *, total="321.80", currency="ARS"):
    reservation = Reservation(
        hotel_id=hotel_config.id,
        confirmation_code=f"FXS-{hotel_config.id}-{guest.id}-{currency}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 11, 1),
        check_out_date=date(2026, 11, 2),
        total_amount=Decimal(total),
        deposit_amount=Decimal("0.00"),
        currency_code=currency,
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_fixed_surcharge_converts_from_configured_currency_to_tender_currency(
    db,
    sample_guest,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    db.add(
        PaymentSurcharge(
            hotel_id=hotel_config.id,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    def quote(_db, *, amount, from_currency, to_currency, **_kwargs):
        assert (from_currency, to_currency) == ("ARS", "USD")
        return amount * 0.02, 0.02, {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "source_quote": {"market": "blue", "side": "compra", "provider_updated_at": "2026-10-25T12:00:00Z"},
        }

    monkeypatch.setattr(payment_service, "_convert_amount", quote)
    result = calculate_payment_surcharge(
        db,
        hotel_id=hotel_config.id,
        payment_method=PaymentMethodEnum.CASH,
        base_amount=Decimal("50.00"),
        currency_code="USD",
    )

    assert result["base_amount"] == Decimal("50.00")
    assert result["surcharge_currency_code"] == "ARS"
    assert result["surcharge_amount"] == Decimal("20.00")
    assert result["final_amount"] == Decimal("70.00")
    assert result["surcharge_fx_rate"] == Decimal("0.02")
    assert result["surcharge_fx_quote_details"]["source_quote"]["market"] == "blue"
    assert result["surcharge_quote_snapshot"]["surcharge_amount"] == "20.00"


def test_fixed_cross_currency_surcharge_fails_closed_without_a_valid_quote(
    db,
    hotel_config,
    monkeypatch,
):
    db.add(
        PaymentSurcharge(
            hotel_id=hotel_config.id,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    def no_quote(*_args, **_kwargs):
        raise payment_service.PricingPolicyError("No hay una cotización FX vigente para convertir ARS a USD.")

    monkeypatch.setattr(payment_service, "_convert_amount", no_quote)
    with pytest.raises(PaymentError, match="No hay una cotización FX vigente"):
        calculate_payment_surcharge(
            db,
            hotel_id=hotel_config.id,
            payment_method=PaymentMethodEnum.CASH,
            base_amount=Decimal("50.00"),
            currency_code="USD",
        )


def test_payment_link_webhook_uses_the_saved_fixed_surcharge_quote(
    db,
    sample_guest,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    hotel_config.enable_mercado_pago = True
    hotel_config.subscription_active = True
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories[0],
        hotel_config,
        total="200.00",
        currency="USD",
    )
    db.add(
        PaymentSurcharge(
            hotel_id=hotel_config.id,
            payment_method="mercado_pago",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    def creation_quote(_db, *, amount, from_currency, to_currency, **_kwargs):
        assert (from_currency, to_currency) == ("ARS", "USD")
        return amount * 0.02, 0.02, {"source": "link_creation_quote", "applied_rate": 0.02}

    monkeypatch.setattr(payment_service, "_convert_amount", creation_quote)
    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: False)
    link = create_link(
        db,
        hotel_config.id,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="fx-guest@example.com",
            currency="USD",
        ),
    )
    assert link.requested_amount == Decimal("120.00")
    quote_snapshot = link.gateway_response["_pms_surcharge_quote"]
    assert quote_snapshot["surcharge_amount"] == "20.00"

    payment = Payment(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        payment_link_id=link.id,
        amount=Decimal("120.00"),
        currency="USD",
        provider="mercado_pago",
        external_payment_id="synthetic-approved-fx-surcharge",
        status="completed",
    )
    db.add(payment)
    db.flush()

    def quote_must_not_be_refetched(*_args, **_kwargs):
        raise AssertionError("El webhook debe respetar la cotización fijada al crear el link")

    monkeypatch.setattr(payment_service, "_convert_amount", quote_must_not_be_refetched)
    _ensure_completed_transaction(
        db,
        payment,
        "mercado_pago",
        {"status": "approved", "transaction_amount": "120.00", "currency_id": "USD"},
    )

    transaction = db.query(Transaction).filter(Transaction.reservation_id == reservation.id).one()
    assert transaction.transaction_type == TransactionTypeEnum.PARTIAL_PAYMENT
    assert transaction.amount == Decimal("100.00")
    assert transaction.fee_amount == Decimal("20.00")
    assert transaction.gross_amount == Decimal("120.00")
    assert transaction.fx_quote_details["payment_surcharge_conversion"]["source"] == "link_creation_quote"


def test_quote_chooses_maximum_tender_without_exceeding_balance_and_returns_cash_suggestion(
    db,
    sample_guest,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    hotel_config.fx_rounding_policy = "round_up"
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories[0],
        hotel_config,
        total="321.80",
        currency="ARS",
    )

    def quote(_db, *, amount, from_currency, to_currency, **_kwargs):
        assert (from_currency, to_currency) == ("USD", "ARS")
        return amount * 17.0, 17.0, {"source": "quote_max_tender", "applied_rate": 17.0}

    monkeypatch.setattr(payment_service, "_convert_amount", quote)
    result = quote_reservation_payment_surcharge(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        payment_method=PaymentMethodEnum.CASH,
        currency_code="USD",
    )

    assert result["base_amount"] == Decimal("18.92")
    assert result["applied_amount"] == Decimal("321.64")
    assert result["remaining_balance"] == Decimal("0.16")
    assert result["final_amount"] == Decimal("18.92")
    assert result["cash_tender_suggestion"] == Decimal("19")
    assert result["cash_tender_suggestion_difference"] == Decimal("0.08")

    with pytest.raises(PaymentError, match="por encima del saldo pendiente"):
        quote_reservation_payment_surcharge(
            db,
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            payment_method=PaymentMethodEnum.CASH,
            currency_code="USD",
            base_amount=Decimal("18.93"),
        )


def test_signed_payment_quote_keeps_previewed_fx_and_surcharge_when_rate_changes(
    db,
    sample_guest,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories[0],
        hotel_config,
        total="1000.00",
        currency="ARS",
    )
    db.add(
        PaymentSurcharge(
            hotel_id=hotel_config.id,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    def quote_v1(_db, *, amount, from_currency, to_currency, **_kwargs):
        rates = {("USD", "ARS"): 20.0, ("ARS", "USD"): 0.02}
        rate = rates[(from_currency, to_currency)]
        return amount * rate, rate, {
            "source": "quote_v1",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "applied_rate": rate,
        }

    monkeypatch.setattr(payment_service, "_convert_amount", quote_v1)
    quote = quote_reservation_payment_surcharge(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        payment_method=PaymentMethodEnum.CASH,
        currency_code="USD",
        base_amount=Decimal("10.00"),
    )
    assert quote["applied_amount"] == Decimal("200.00")
    assert quote["surcharge_amount"] == Decimal("20.00")
    assert quote["final_amount"] == Decimal("30.00")

    with pytest.raises(PaymentError, match="no coincide con el importe enviado"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=Decimal("10.01"),
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
                currency="USD",
                payment_quote_token=quote["payment_quote_token"],
            ),
            hotel_id=hotel_config.id,
        )

    open_session(
        db,
        hotel_id=hotel_config.id,
        opened_by_user_id=None,
        opening_balance=Decimal("0.00"),
        currency_code="USD",
    )
    db.query(PaymentSurcharge).filter_by(
        hotel_id=hotel_config.id,
        payment_method="cash",
    ).one().amount = Decimal("5000.00")

    def unexpected_requote(*_args, **_kwargs):
        raise AssertionError("El pago debe usar los importes y las tasas aceptadas en la cotización")

    monkeypatch.setattr(payment_service, "_convert_amount", unexpected_requote)
    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=Decimal("10.00"),
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency="USD",
            payment_quote_token=quote["payment_quote_token"],
        ),
        hotel_id=hotel_config.id,
    )
    db.flush()

    assert transaction.amount == Decimal("200.00")
    assert transaction.tender_amount == Decimal("10.00")
    assert transaction.tender_currency == "USD"
    assert transaction.gross_amount == Decimal("30.00")
    assert transaction.fee_amount == Decimal("20.00")
    assert transaction.fx_quote_details["source"] == "quote_v1"
    assert transaction.fx_quote_details["payment_surcharge_conversion"]["source"] == "quote_v1"
