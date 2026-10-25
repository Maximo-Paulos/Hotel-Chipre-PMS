"""Authorization and API contract checks for FX-credit cash refunds."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user_mfa import UserMfaSecret
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.cash_register_service import open_session
from app.services.permission_service import PERMISSION_PAYMENT_REFUND
from tests.test_payment_links_api import _reservation, client_with_db


def _step_up_header(ctx):
    ticket = create_action_step_up_ticket(
        user_id=1,
        hotel_id=ctx["hotel_id"],
        token_version=0,
        permission_code=PERMISSION_PAYMENT_REFUND,
        method="POST",
        path="/api/payments/",
    )
    return {"X-Action-Step-Up-Ticket": ticket}


def test_credit_refund_requires_refund_permission_step_up_and_cash_session(client_with_db):
    client, db, ctx = client_with_db
    db.add(UserMfaSecret(user_id=1, encrypted_secret="unused-test-ciphertext", status="active"))
    reservation = _reservation(db, 1, "FX-CREDIT-REFUND-API")
    source = Transaction(
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        currency="ARS",
        tender_amount=Decimal("33.00"),
        tender_currency="ARS",
        rounding_credit_amount=Decimal("3.00"),
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CREDIT_CARD,
        status=TransactionStatusEnum.COMPLETED,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(source)
    db.flush()
    open_session(db, hotel_id=1, opened_by_user_id=1, opening_balance=0, currency_code="ARS")

    payload = {
        "reservation_id": reservation.id,
        "amount": "1.00",
        "payment_method": "cash",
        "transaction_type": "refund",
        "refund_component": "rounding_credit",
        "refund_of_transaction_id": source.id,
        "refund_reason": "Devolución manual aprobada",
        "currency": "ARS",
    }
    headers = {"Idempotency-Key": "fx-credit-refund-api-001"}

    receptionist = client.post("/api/payments/", json=payload, headers=headers)
    assert receptionist.status_code == 403

    ctx["role"] = "manager"
    missing_step_up = client.post("/api/payments/", json=payload, headers=headers)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["permission_code"] == PERMISSION_PAYMENT_REFUND

    action_headers = {**headers, **_step_up_header(ctx)}
    refunded = client.post("/api/payments/", json=payload, headers=action_headers)
    assert refunded.status_code == 201, refunded.text
    assert refunded.json()["amount"] == 0
    assert refunded.json()["tender_amount"] == 1
    assert refunded.json()["refund_component"] == "rounding_credit"
    assert Decimal(refunded.json()["credit_refund_amount"]) == Decimal("1.00")

    replay = client.post(
        "/api/payments/",
        json=payload,
        headers={**headers, **_step_up_header(ctx)},
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == refunded.json()["id"]
    assert db.query(Transaction).filter_by(refund_of_transaction_id=source.id).count() == 1
