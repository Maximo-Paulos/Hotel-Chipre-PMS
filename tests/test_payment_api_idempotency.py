from app.models.transaction import Transaction

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


def test_direct_payment_requires_and_reuses_idempotency_key(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-PAY-1")
    payload = {
        "reservation_id": reservation.id,
        "amount": 30.0,
        "payment_method": "mercado_pago",
        "transaction_type": "deposit",
    }

    missing_key = client.post("/api/payments/", json=payload)
    assert missing_key.status_code == 422

    headers = {"Idempotency-Key": "direct-payment-001"}
    first = client.post("/api/payments/", json=payload, headers=headers)
    second = client.post("/api/payments/", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
