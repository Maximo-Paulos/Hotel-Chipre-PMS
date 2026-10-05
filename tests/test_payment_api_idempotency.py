import pytest

from app.models.transaction import Transaction
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_RECORD_PRIOR_RECEIPT,
    set_override,
)

from tests.test_payment_links_api import _reservation, client_with_db


def test_cash_charge_without_open_cash_session_is_blocked_not_a_crash(client_with_db):
    # A cash charge with no caja open must be rejected with a clear 4xx (the
    # cash-register guard's CashRegisterError previously escaped process_payment
    # uncaught, crashing the request as an unhandled 500 instead of blocking it).
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-PAY-NO-CAJA")
    payload = {
        "reservation_id": reservation.id,
        "amount": 30.0,
        "payment_method": "cash",
        "transaction_type": "deposit",
    }
    headers = {"Idempotency-Key": "direct-payment-no-cash-session"}

    response = client.post("/api/payments/", json=payload, headers=headers)

    assert response.status_code == 400, response.text
    assert "cash session" in response.json()["detail"].lower()


@pytest.mark.parametrize("method", ["mercado_pago", "paypal"])
def test_direct_payment_rejects_external_provider_methods_without_gateway_evidence(client_with_db, method):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, f"API-PAY-{method.upper()}")
    payload = {
        "reservation_id": reservation.id,
        "amount": 30.0,
        "payment_method": method,
        "transaction_type": "deposit",
    }

    response_without_key = client.post("/api/payments/", json=payload)
    assert response_without_key.status_code == 422

    headers = {"Idempotency-Key": f"direct-{method}-payment-001"}
    first = client.post("/api/payments/", json=payload, headers=headers)
    retry = client.post("/api/payments/", json=payload, headers=headers)

    for response in (first, retry):
        assert response.status_code == 400, response.text
        assert "requieren una respuesta verificada" in response.json()["detail"].lower()
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
    db.refresh(reservation)
    assert reservation.amount_paid == 0


@pytest.mark.parametrize("method", ["mercado_pago", "paypal"])
def test_rejected_external_payment_does_not_consume_key_for_manual_transfer(client_with_db, method):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, f"API-PAY-KEY-REUSE-{method.upper()}")
    headers = {"Idempotency-Key": f"gateway-key-reuse-{method}-001"}
    external_payload = {
        "reservation_id": reservation.id,
        "amount": 30.0,
        "payment_method": method,
        "transaction_type": "deposit",
    }

    rejected = client.post("/api/payments/", json=external_payload, headers=headers)
    assert rejected.status_code == 400, rejected.text
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0

    allowed_payload = {
        **external_payload,
        "payment_method": "bank_transfer",
        "manual_reference": f"BANK-KEY-REUSE-{method.upper()}-001",
    }
    accepted = client.post("/api/payments/", json=allowed_payload, headers=headers)
    retry = client.post("/api/payments/", json=allowed_payload, headers=headers)

    assert accepted.status_code == 201, accepted.text
    assert retry.status_code == 201, retry.text
    assert accepted.json()["status"] == "completed"
    assert retry.json()["id"] == accepted.json()["id"]
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
    db.refresh(reservation)
    assert reservation.amount_paid == 30


def test_manual_bank_transfer_payment_reuses_idempotent_transaction(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-PAY-BANK-TRANSFER-IDEMPOTENT")
    payload = {
        "reservation_id": reservation.id,
        "amount": 30.0,
        "payment_method": "bank_transfer",
        "transaction_type": "deposit",
        "manual_reference": "BANK-TRANSFER-IDEMPOTENT-001",
    }
    headers = {"Idempotency-Key": "manual-bank-transfer-idempotent-001"}

    first = client.post("/api/payments/", json=payload, headers=headers)
    retry = client.post("/api/payments/", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert first.json()["status"] == "completed"
    assert retry.json()["id"] == first.json()["id"]
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
    db.refresh(reservation)
    assert reservation.amount_paid == 30


def test_external_provider_payment_still_requires_cash_operation_permission(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-PAY-PROVIDER-DENIED")
    set_override(db, 1, "receptionist", PERMISSION_CASH_OPERATE, False, user_id=1)
    db.commit()

    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": reservation.id,
            "amount": 30.0,
            "payment_method": "paypal",
            "transaction_type": "deposit",
        },
        headers={"Idempotency-Key": "external-provider-denied-001"},
    )

    assert response.status_code == 403
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0


def test_prior_cash_receipt_requires_its_specific_permission(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-PAY-PRIOR-RECEIPT-DENIED")
    set_override(db, 1, "receptionist", PERMISSION_CASH_RECORD_PRIOR_RECEIPT, False, user_id=1)
    db.commit()

    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": reservation.id,
            "amount": 30.0,
            "payment_method": "cash",
            "transaction_type": "deposit",
            "collected_before": True,
            "collected_on": "2020-01-01",
            "prior_receipt_note": "Previously collected before being entered in the PMS",
        },
        headers={"Idempotency-Key": "prior-receipt-specific-permission-001"},
    )

    assert response.status_code == 403
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0


def test_manual_payment_cannot_write_for_another_hotel(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 2, "API-PAY-CROSS-HOTEL")

    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": reservation.id,
            "amount": 30.0,
            "payment_method": "bank_transfer",
            "transaction_type": "deposit",
            "manual_reference": "BANK-CROSS-HOTEL-001",
        },
        headers={"Idempotency-Key": "manual-cross-hotel-001"},
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Reservation not found"
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
