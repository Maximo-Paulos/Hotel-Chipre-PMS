from app.models.transaction import Transaction

from tests.test_payment_links_api import _reservation, client_with_db


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
