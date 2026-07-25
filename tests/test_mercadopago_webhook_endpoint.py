"""HTTP-level Mercado Pago webhook journey.

Exercises the real route (/api/payment-links/mercadopago/webhook) end to end:
signature verification, resolving the signed external_reference, and the
ledger effects of an approved/rejected/duplicate delivery -- not just the
service-layer helpers already covered in test_payment_webhook_service.py and
test_mercadopago_webhook_signature.py.

Uses a synthetic HMAC-signed payload built with the same manifest algorithm
Mercado Pago uses, posted to the local TestClient. No real Mercado Pago
network call, no real webhook.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import Payment, PaymentWebhookEvent
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction, TransactionStatusEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.services.payment_link_service import create_link

WEBHOOK_SECRET = "qa-mp-webhook-secret"


@pytest.fixture
def client_with_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(hotel_id=1, user_id=1, user_email="manager@test.com", user_role="manager", is_verified=True)

    from app.config import get_settings

    patched_settings = get_settings().model_copy(update={"MERCADOPAGO_WEBHOOK_SECRET": WEBHOOK_SECRET})
    monkeypatch.setattr("app.api.payment_links.get_settings", lambda: patched_settings)

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name="Webhook", last_name="Endpoint", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Webhook Endpoint Room {hotel_id}",
        code=f"WHE{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 4),
        total_amount=Decimal("300.00"),
        deposit_amount=Decimal("90.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.commit()
    return reservation


def _fake_gateway(db, hotel_id, link):
    # ponytail: no real MP network call -- webhook journey only needs the
    # signed external_reference to exist, not a real checkout preference.
    return {"checkout_url": f"https://mp.test/checkout/{link.link_code}", "preference_id": "pref-qa", "raw": {}}


def _create_link(db, hotel_id: int, reservation_id: int, amount: str):
    link = create_link(
        db,
        hotel_id,
        PaymentLinkCreate(
            reservation_id=reservation_id,
            requested_amount=Decimal(amount),
            recipient_email="qa-webhook@example.com",
        ),
        mp_gateway=_fake_gateway,
    )
    db.commit()
    db.refresh(link)
    return link


def _sign(data_id: str, request_id: str) -> str:
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _post_webhook(client, *, external_reference: str, data_id: str, webhook_id: str, status: str, amount: str,
                   request_id: str = "req-qa-1", bad_signature: bool = False):
    if bad_signature:
        ts = str(int(datetime.now(timezone.utc).timestamp()))
        signature = f"ts={ts},v1=deadbeef"
    else:
        signature = _sign(data_id, request_id)
    return client.post(
        "/api/payment-links/mercadopago/webhook",
        params={"external_reference": external_reference, "data.id": data_id, "webhook_id": webhook_id},
        json={"status": status, "amount": amount, "currency": "ARS", "data": {"id": data_id}},
        headers={"x-signature": signature, "x-request-id": request_id},
    )


def test_approved_webhook_completes_transaction_and_updates_reservation(client_with_db):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-APPROVED")
    link = _create_link(db, 1, reservation.id, "90.00")

    response = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-pay-approved-1",
        webhook_id="mp-pay-approved-1",
        status="approved",
        amount="90.00",
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["duplicate"] is False

    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("90.00")
    assert reservation.status == ReservationStatusEnum.DEPOSIT_PAID
    txs = db.query(Transaction).filter(Transaction.reservation_id == reservation.id).all()
    assert len(txs) == 1
    assert txs[0].status == TransactionStatusEnum.COMPLETED


def test_rejected_webhook_records_payment_without_completing_a_transaction(client_with_db):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-REJECTED")
    link = _create_link(db, 1, reservation.id, "90.00")

    response = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-pay-rejected-1",
        webhook_id="mp-pay-rejected-1",
        status="rejected",
        amount="90.00",
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"

    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("0.00")
    assert reservation.status == ReservationStatusEnum.PENDING
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
    payment = db.query(Payment).filter(Payment.reservation_id == reservation.id).one()
    assert payment.status == "failed"


def test_duplicate_webhook_delivery_does_not_double_charge(client_with_db):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-RETRY")
    link = _create_link(db, 1, reservation.id, "90.00")

    first = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-pay-retry-1",
        webhook_id="mp-pay-retry-1",
        status="approved",
        amount="90.00",
    )
    second = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-pay-retry-1",
        webhook_id="mp-pay-retry-1",
        status="approved",
        amount="90.00",
    )

    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True

    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("90.00")
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
    assert db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.hotel_id == 1).count() == 1


def test_webhook_with_invalid_signature_is_rejected_and_changes_nothing(client_with_db):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-BADSIG")
    link = _create_link(db, 1, reservation.id, "90.00")

    response = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-pay-badsig-1",
        webhook_id="mp-pay-badsig-1",
        status="approved",
        amount="90.00",
        bad_signature=True,
    )

    assert response.status_code == 401, response.text
    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("0.00")
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
    assert db.query(Payment).filter(Payment.reservation_id == reservation.id).count() == 0
