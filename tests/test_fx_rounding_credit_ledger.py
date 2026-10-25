"""Focused tests for exact FX settlement, cash change and historical refunds."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.pricing import CategoryPricing
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services import payment_service as payment_service_module
from app.services.cash_register_service import CashMovement, open_session
from app.services.payment_service import (
    PaymentError,
    PaymentNotFoundError,
    get_reservation_financial_summary,
    process_payment,
)
from app.services.reservation_service import create_reservation


@pytest.fixture(autouse=True)
def ensure_category_pricing_table(db_engine):
    CategoryPricing.__table__.create(bind=db_engine, checkfirst=True)
    yield


def _reservation(db, guest, categories, hotel_config, *, total="200.00"):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=categories[0].id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
        ),
        hotel_id=hotel_config.id,
    )
    reservation.total_amount = Decimal(total)
    reservation.deposit_amount = (Decimal(total) * Decimal("0.30")).quantize(Decimal("0.01"))
    reservation.currency_code = "ARS"
    db.flush()
    return reservation


def _open_cash(db, hotel_id, currency="USD"):
    open_session(
        db,
        hotel_id=hotel_id,
        opened_by_user_id=None,
        opening_balance=0,
        currency_code=currency,
    )


def _mock_usd_to_ars_quote(monkeypatch):
    def quote(_db, *, amount, **_kwargs):
        return amount * 3.0, 3.0, {
            "from_currency": "USD",
            "to_currency": "ARS",
            "source": "deterministic-test-quote",
        }

    monkeypatch.setattr(payment_service_module, "_convert_amount", quote)


def _legacy_rounding_credit_payment(db, reservation):
    """Seed a historical payment row so the old credit-refund path stays covered."""
    source = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=Decimal("200.00"),
        currency="ARS",
        tender_amount=Decimal("67.00"),
        tender_currency="USD",
        rounding_credit_amount=Decimal("0.33"),
        gross_amount=Decimal("67.00"),
        fx_rate_snapshot=Decimal("0.33335"),
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.COMPLETED,
        description="Historical FX rounding credit",
    )
    db.add(source)
    db.flush()
    reservation.amount_paid = Decimal("200.00")
    db.flush()
    return source


@pytest.mark.parametrize(
    ("policy", "tender", "transaction_type", "expected_applied", "expected_due"),
    [
        ("exact", "66.66", TransactionTypeEnum.PARTIAL_PAYMENT, "199.98", "0.02"),
        ("round_up", "66.66", TransactionTypeEnum.PARTIAL_PAYMENT, "199.98", "0.02"),
        ("nearest_ten", "66.66", TransactionTypeEnum.PARTIAL_PAYMENT, "199.98", "0.02"),
        ("round_down", "66.00", TransactionTypeEnum.PARTIAL_PAYMENT, "198.00", "2.00"),
        ("keep_remainder", "66.66", TransactionTypeEnum.PARTIAL_PAYMENT, "199.98", "0.02"),
    ],
)
def test_configured_rounding_never_changes_exact_fx_principal_or_issues_credit(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    policy,
    tender,
    transaction_type,
    expected_applied,
    expected_due,
):
    reservation = _reservation(db, sample_guest, sample_categories, hotel_config)
    hotel_config.fx_rounding_policy = policy
    _open_cash(db, hotel_config.id)
    _mock_usd_to_ars_quote(monkeypatch)

    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=tender,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=transaction_type,
            currency="USD",
        ),
        hotel_id=hotel_config.id,
    )
    db.flush()
    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)

    assert Decimal(str(transaction.amount)) == Decimal(expected_applied)
    assert Decimal(str(transaction.rounding_credit_amount)) == Decimal("0.00")
    assert Decimal(str(summary["operational_balance_due"])) == Decimal(expected_due)
    assert reservation.amount_paid == Decimal(expected_applied)
    assert summary["rounding_credit_by_currency"] == []


@pytest.mark.parametrize(
    ("policy", "tender"),
    [
        ("exact", "67.00"),
        ("round_up", "68.00"),
        ("nearest_ten", "80.00"),
        ("keep_remainder", "67.00"),
    ],
)
def test_arbitrary_fx_overpayment_is_rejected_even_when_rounding_is_configured(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    policy,
    tender,
):
    reservation = _reservation(db, sample_guest, sample_categories, hotel_config)
    hotel_config.fx_rounding_policy = policy
    _open_cash(db, hotel_config.id)
    _mock_usd_to_ars_quote(monkeypatch)

    with pytest.raises(PaymentError, match="supera el saldo pendiente"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=tender,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                currency="USD",
            ),
            hotel_id=hotel_config.id,
        )

    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert reservation.amount_paid == 0


def test_same_currency_payment_remains_exact_under_fx_rounding_policy(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        total="200.40",
    )
    hotel_config.fx_rounding_policy = "round_up"
    _open_cash(db, hotel_config.id, currency="ARS")

    with pytest.raises(PaymentError, match="supera el saldo pendiente"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount="201.00",
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                currency="ARS",
            ),
            hotel_id=hotel_config.id,
        )

    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="200.40",
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            currency="ARS",
        ),
        hotel_id=hotel_config.id,
    )

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert Decimal(str(transaction.amount)) == Decimal("200.40")
    assert Decimal(str(transaction.fx_rate_snapshot)) == Decimal("1.0")
    assert Decimal(str(transaction.rounding_credit_amount)) == Decimal("0.00")
    assert reservation.amount_paid == Decimal("200.40")
    assert summary["operational_balance_due"] == Decimal("0.00")
    assert summary["rounding_credit_by_currency"] == []


def test_fx_payment_does_not_collect_a_tender_cent_that_exceeds_balance(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        total="84600.00",
    )
    hotel_config.fx_rounding_policy = "exact"
    _open_cash(db, hotel_config.id)

    def quote(_db, *, amount, **_kwargs):
        return amount * 4470.0, 4470.0, {
            "from_currency": "USD",
            "to_currency": "ARS",
            "source": "deterministic-test-quote",
        }

    monkeypatch.setattr(payment_service_module, "_convert_amount", quote)
    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="18.92",
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency="USD",
        ),
        hotel_id=hotel_config.id,
    )

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert Decimal(str(transaction.tender_amount)) == Decimal("18.92")
    assert Decimal(str(transaction.amount)) == Decimal("84572.40")
    assert Decimal(str(transaction.rounding_credit_amount)) == Decimal("0.00")
    assert reservation.amount_paid == Decimal("84572.40")
    assert summary["operational_balance_due"] == Decimal("27.60")
    assert summary["rounding_credit_by_currency"] == []


@pytest.mark.parametrize(
    ("tip_amount", "expected_change"),
    [("0.00", "0.60"), ("0.60", "0.00")],
)
def test_exact_fx_cash_over_tender_records_change_or_explicit_tip_without_credit(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    tip_amount,
    expected_change,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        total="84600.00",
    )
    hotel_config.fx_rounding_policy = "exact"
    _open_cash(db, hotel_config.id, currency="USD")

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
    idempotency_key = f"exact-fx-cash-change-{tip_amount}"
    transaction = process_payment(
        db,
        request,
        hotel_id=hotel_config.id,
        idempotency_key=idempotency_key,
    )
    replay = process_payment(
        db,
        request,
        hotel_id=hotel_config.id,
        idempotency_key=idempotency_key,
    )
    movement = db.query(CashMovement).filter_by(transaction_id=transaction.id).one()
    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)

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


@pytest.mark.parametrize(
    "payment_method",
    [PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.BANK_TRANSFER],
)
def test_fx_rounding_policy_keeps_card_and_transfer_at_exact_converted_amount(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    payment_method,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        total="84600.00",
    )
    hotel_config.fx_rounding_policy = "round_up"
    hotel_config.enable_bank_transfer = True

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
            external_payment_id="test-card-capture",
            external_status="approved",
        )
        if payment_method == PaymentMethodEnum.CREDIT_CARD
        else None
    )
    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="56.40",
            payment_method=payment_method,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            currency="USD",
        ),
        hotel_id=hotel_config.id,
        gateway_response=gateway_response,
        manual_confirmation=payment_method == PaymentMethodEnum.BANK_TRANSFER,
        apply_surcharge=False,
    )

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert Decimal(str(transaction.tender_amount)) == Decimal("56.40")
    assert Decimal(str(transaction.amount)) == Decimal("84600.00")
    assert Decimal(str(transaction.rounding_credit_amount)) == Decimal("0.00")
    assert transaction.cash_received_amount is None
    assert reservation.amount_paid == Decimal("84600.00")
    assert summary["operational_balance_due"] == Decimal("0.00")
    assert summary["rounding_credit_by_currency"] == []


@pytest.mark.parametrize(
    "payment_method",
    [PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.BANK_TRANSFER],
)
def test_fx_rounding_policy_rejects_rounded_up_card_and_transfer_amounts(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
    payment_method,
):
    reservation = _reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        total="84600.00",
    )
    hotel_config.fx_rounding_policy = "round_up"
    hotel_config.enable_bank_transfer = True

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
            external_payment_id="test-card-capture",
            external_status="approved",
        )
        if payment_method == PaymentMethodEnum.CREDIT_CARD
        else None
    )
    with pytest.raises(PaymentError, match="supera el saldo pendiente"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount="57.00",
                payment_method=payment_method,
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
                currency="USD",
            ),
            hotel_id=hotel_config.id,
            gateway_response=gateway_response,
            manual_confirmation=payment_method == PaymentMethodEnum.BANK_TRANSFER,
            apply_surcharge=False,
        )

    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert reservation.amount_paid == 0


def test_credit_refunds_are_idempotent_partial_and_full_without_reducing_reservation_payment(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    reservation = _reservation(db, sample_guest, sample_categories, hotel_config)
    hotel_config.fx_rounding_policy = "round_up"
    _open_cash(db, hotel_config.id)
    _mock_usd_to_ars_quote(monkeypatch)
    source = _legacy_rounding_credit_payment(db, reservation)

    partial_request = PaymentRequest(
        reservation_id=reservation.id,
        amount="0.10",
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.REFUND,
        refund_component="rounding_credit",
        refund_of_transaction_id=source.id,
        refund_reason="Devolución manual del crédito cambiario",
        currency="USD",
    )
    partial_refund = process_payment(
        db,
        partial_request,
        hotel_id=hotel_config.id,
        idempotency_key="fx-credit-refund-partial-001",
    )
    replay = process_payment(
        db,
        partial_request,
        hotel_id=hotel_config.id,
        idempotency_key="fx-credit-refund-partial-001",
    )
    assert replay.id == partial_refund.id
    assert Decimal(str(partial_refund.amount)) == Decimal("0.00")
    assert Decimal(str(partial_refund.credit_refund_amount)) == Decimal("0.10")
    assert partial_refund.refund_component == "rounding_credit"
    assert db.query(CashMovement).filter_by(transaction_id=partial_refund.id).one().amount == Decimal("0.10")
    assert reservation.amount_paid == Decimal("200.00")

    full_refund = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="0.23",
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.REFUND,
            refund_component="rounding_credit",
            refund_of_transaction_id=source.id,
            refund_reason="Devolución del crédito restante",
            currency="USD",
        ),
        hotel_id=hotel_config.id,
        idempotency_key="fx-credit-refund-full-001",
    )
    db.flush()

    assert full_refund.amount == Decimal("0.00")
    assert db.query(CashMovement).filter_by(transaction_id=full_refund.id).one().amount == Decimal("0.23")
    assert reservation.amount_paid == Decimal("200.00")
    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert summary["operational_balance_due"] == Decimal("0.00")
    assert summary["hotel_received_amount"] == Decimal("200.00")
    assert summary["rounding_credit_by_currency"] == [
        {
            "currency_code": "USD",
            "issued_amount": Decimal("0.33"),
            "refunded_amount": Decimal("0.33"),
            "open_amount": Decimal("0.00"),
        }
    ]
    assert summary["rounding_credit_sources"] == [
        {
            "source_transaction_id": source.id,
            "currency_code": "USD",
            "issued_amount": Decimal("0.33"),
            "refunded_amount": Decimal("0.33"),
            "open_amount": Decimal("0.00"),
        }
    ]
    with pytest.raises(PaymentError, match="crédito cambiario disponible"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount="0.01",
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.REFUND,
                refund_component="rounding_credit",
                refund_of_transaction_id=source.id,
                refund_reason="Intento de exceder el crédito",
                currency="USD",
            ),
            hotel_id=hotel_config.id,
        )


def test_principal_refund_uses_net_tender_and_does_not_also_refund_credit(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    reservation = _reservation(db, sample_guest, sample_categories, hotel_config)
    hotel_config.fx_rounding_policy = "round_up"
    _open_cash(db, hotel_config.id)
    _mock_usd_to_ars_quote(monkeypatch)
    source = _legacy_rounding_credit_payment(db, reservation)

    principal_refund = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount="66.67",
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.REFUND,
            refund_of_transaction_id=source.id,
            refund_reason="Devolución manual del pago principal",
            currency="USD",
        ),
        hotel_id=hotel_config.id,
    )

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert Decimal(str(principal_refund.amount)) == Decimal("200.00")
    assert Decimal(str(principal_refund.tender_amount)) == Decimal("66.67")
    assert principal_refund.refund_component == "payment"
    assert reservation.amount_paid == Decimal("0.00")
    assert summary["rounding_credit_by_currency"] == [
        {
            "currency_code": "USD",
            "issued_amount": Decimal("0.33"),
            "refunded_amount": Decimal("0.00"),
            "open_amount": Decimal("0.33"),
        }
    ]


def test_rounding_credit_refund_cannot_cross_hotel_scope(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
    monkeypatch,
):
    reservation = _reservation(db, sample_guest, sample_categories, hotel_config)
    hotel_config.fx_rounding_policy = "round_up"
    _open_cash(db, hotel_config.id)
    _mock_usd_to_ars_quote(monkeypatch)
    source = _legacy_rounding_credit_payment(db, reservation)

    with pytest.raises(PaymentNotFoundError):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount="0.10",
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.REFUND,
                refund_component="rounding_credit",
                refund_of_transaction_id=source.id,
                refund_reason="Intento entre hoteles",
                currency="USD",
            ),
            hotel_id=2,
        )

    assert db.query(Transaction).filter_by(refund_of_transaction_id=source.id).count() == 0
