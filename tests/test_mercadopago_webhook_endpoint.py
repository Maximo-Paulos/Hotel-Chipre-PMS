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
import app.services.payment_webhook_service as payment_webhook_service
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
from app.services.payment_webhook_service import RetryablePaymentWebhookError

WEBHOOK_SECRET = "qa-mp-webhook-secret"
_REAL_MP_FETCH = payment_webhook_service.fetch_mercadopago_payment


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

    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    patched_settings = get_settings().model_copy(update={"MERCADOPAGO_WEBHOOK_SECRET": WEBHOOK_SECRET})
    monkeypatch.setattr("app.api.payment_links.get_settings", lambda: patched_settings)

    # The route now verifies provider-originated notifications against the
    # hotel's Mercado Pago account before posting a ledger transaction. Keep
    # this HTTP journey fully deterministic by replacing that provider read;
    # the endpoint still exercises the signature, reference and idempotency
    # boundaries without opening a real Mercado Pago connection.
    def fake_provider_fetch(_db, _hotel_id, payment_id):
        is_rejected = "rejected" in str(payment_id)
        return {
            "id": payment_id,
            "status": "rejected" if is_rejected else "approved",
            "transaction_amount": 90.0,
            "currency_id": "ARS",
            "external_reference": getattr(fastapi_app.state, "webhook_expected_external_reference", None),
        }

    monkeypatch.setattr(
        "app.services.payment_webhook_service.fetch_mercadopago_payment",
        fake_provider_fetch,
    )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        get_settings.cache_clear()
        db.close()
        engine.dispose()


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True, enable_mercado_pago=True))
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
    # The webhook journey only needs a signed external_reference; it does not
    # require creating a real Mercado Pago checkout preference.
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
        idempotency_key=f"webhook-link-{hotel_id}-{reservation_id}-{amount}",
    )
    db.commit()
    db.refresh(link)
    return link


def _sign(data_id: str, request_id: str) -> str:
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _post_webhook(
    client,
    *,
    external_reference: str,
    data_id: str,
    webhook_id: str | None,
    status: str,
    amount: str,
    event_id: str | None = None,
    body_payment_id: str | None = None,
    nested_external_reference: str | None = None,
    status_detail: str | None = None,
    event_action: str | None = "payment.updated",
    request_id: str = "req-qa-1",
    bad_signature: bool = False,
):
    fastapi_app.state.webhook_expected_external_reference = external_reference
    if bad_signature:
        ts = str(int(datetime.now(timezone.utc).timestamp()))
        signature = f"ts={ts},v1=deadbeef"
    else:
        signature = _sign(data_id, request_id)
    params = {"external_reference": external_reference, "data.id": data_id}
    if webhook_id is not None:
        params["webhook_id"] = webhook_id
    payload = {
        "status": status,
        "amount": amount,
        "currency": "ARS",
        "data": {"id": body_payment_id or data_id},
        "type": "payment",
    }
    if nested_external_reference is not None:
        payload["data"]["external_reference"] = nested_external_reference
    if status_detail is not None:
        payload["status_detail"] = status_detail
    if event_action is not None:
        payload["action"] = event_action
    if body_payment_id is not None:
        payload["payment_id"] = body_payment_id
    if event_id is not None:
        payload["id"] = event_id
    return client.post(
        "/api/payment-links/mercadopago/webhook",
        params=params,
        json=payload,
        headers={"x-signature": signature, "x-request-id": request_id},
    )


def test_approved_webhook_completes_transaction_and_updates_reservation(client_with_db, monkeypatch):
    tenant_context_hotel_ids = []
    monkeypatch.setattr(
        payment_webhook_service,
        "set_tenant_hotel_context",
        lambda _db, hotel_id: tenant_context_hotel_ids.append(hotel_id),
    )
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
    assert tenant_context_hotel_ids == [1]

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


def test_retryable_provider_failure_returns_503_without_persisting_then_redelivery_is_idempotent(
    client_with_db, monkeypatch
):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-RETRYABLE-PROVIDER")
    link = _create_link(db, 1, reservation.id, "90.00")
    payment_id = "mp-pay-transient-1"
    webhook_id = "mp-hook-transient-1"

    def fail_provider_fetch(_db, _hotel_id, _payment_id):
        raise RetryablePaymentWebhookError("synthetic provider timeout")

    monkeypatch.setattr(payment_webhook_service, "fetch_mercadopago_payment", fail_provider_fetch)

    failed_delivery = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=payment_id,
        webhook_id=webhook_id,
        status="approved",
        amount="90.00",
        request_id="req-transient-failure",
    )

    assert failed_delivery.status_code == 503, failed_delivery.text
    assert failed_delivery.json() == {
        "detail": "No se pudo verificar el pago temporalmente; el webhook puede reintentarse."
    }
    assert db.query(Payment).filter(Payment.reservation_id == reservation.id).count() == 0
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
    assert db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.hotel_id == 1).count() == 0

    def successful_provider_fetch(_db, _hotel_id, provider_payment_id):
        return {
            "id": provider_payment_id,
            "status": "approved",
            "transaction_amount": 90.0,
            "currency_id": "ARS",
            "external_reference": link.external_reference,
        }

    monkeypatch.setattr(payment_webhook_service, "fetch_mercadopago_payment", successful_provider_fetch)
    successful_redelivery = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=payment_id,
        webhook_id=webhook_id,
        status="approved",
        amount="90.00",
        request_id="req-transient-retry",
    )
    duplicate_redelivery = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=payment_id,
        webhook_id=webhook_id,
        status="approved",
        amount="90.00",
        request_id="req-transient-duplicate",
    )

    assert successful_redelivery.status_code == 200, successful_redelivery.text
    assert successful_redelivery.json()["duplicate"] is False
    assert duplicate_redelivery.status_code == 200, duplicate_redelivery.text
    assert duplicate_redelivery.json()["duplicate"] is True
    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("90.00")
    assert db.query(Payment).filter(Payment.reservation_id == reservation.id).count() == 1
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
    assert db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.hotel_id == 1).count() == 1


def test_outbound_disabled_route_rejects_unverified_payment(client_with_db, monkeypatch):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-OUTBOUND-DISABLED")
    link = _create_link(db, 1, reservation.id, "90.00")
    monkeypatch.setattr(payment_webhook_service, "fetch_mercadopago_payment", _REAL_MP_FETCH)
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    response = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id="mp-payment-outbound-disabled",
        webhook_id="mp-event-outbound-disabled",
        status="approved",
        amount="90.00",
    )

    assert response.status_code == 503, response.text
    assert response.json() == {
        "detail": "No se pudo verificar el pago temporalmente; el webhook puede reintentarse."
    }
    assert db.query(Payment).filter(Payment.reservation_id == reservation.id).count() == 0
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0
    assert db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.hotel_id == 1).count() == 0


def test_event_and_payment_ids_remain_distinct_and_replays_are_idempotent(client_with_db, monkeypatch):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-DISTINCT-IDS")
    link = _create_link(db, 1, reservation.id, "90.00")
    event_id = "mp-event-distinct-1"
    signed_payment_id = "mp-payment-signed-1"
    body_payment_id = "mp-payment-body-untrusted"
    fetched_payment_ids = []

    def fake_provider_fetch(_db, _hotel_id, payment_id):
        fetched_payment_ids.append(payment_id)
        return {
            "id": payment_id,
            "status": "approved",
            "transaction_amount": 90.0,
            "currency_id": "ARS",
            "external_reference": link.external_reference,
        }

    monkeypatch.setattr(payment_webhook_service, "fetch_mercadopago_payment", fake_provider_fetch)

    first = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=signed_payment_id,
        webhook_id=None,
        event_id=event_id,
        body_payment_id=body_payment_id,
        status="approved",
        amount="90.00",
        request_id="req-distinct-1",
    )
    # An explicit notification ID wins over the body event ID.
    second = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=signed_payment_id,
        webhook_id="mp-webhook-explicit-1",
        event_id=event_id,
        body_payment_id=body_payment_id,
        status="approved",
        amount="90.00",
        request_id="req-distinct-2",
    )
    replay = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=signed_payment_id,
        webhook_id="mp-webhook-explicit-1",
        event_id=event_id,
        body_payment_id=body_payment_id,
        status="approved",
        amount="90.00",
        request_id="req-distinct-3",
    )
    fallback = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=signed_payment_id,
        webhook_id=None,
        status="approved",
        amount="90.00",
        request_id="req-distinct-4",
    )

    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is False
    assert replay.status_code == 200, replay.text
    assert replay.json()["duplicate"] is True
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["duplicate"] is False

    assert fetched_payment_ids == [signed_payment_id, signed_payment_id, signed_payment_id]
    payment = db.query(Payment).filter(Payment.reservation_id == reservation.id).one()
    assert payment.external_payment_id == signed_payment_id
    events = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.payment_id == payment.id).all()
    assert {event.webhook_id for event in events} == {event_id, "mp-webhook-explicit-1", signed_payment_id}
    assert next(event for event in events if event.webhook_id == event_id).raw_payload["id"] == event_id
    assert next(event for event in events if event.webhook_id == event_id).raw_payload["data"]["id"] == signed_payment_id

    transactions = db.query(Transaction).filter(Transaction.reservation_id == reservation.id).all()
    assert len(transactions) == 1
    assert transactions[0].idempotency_key == f"mercado_pago:{signed_payment_id}:completed"


def test_webhook_audit_replaces_nested_reference_and_drops_untrusted_free_text(client_with_db, monkeypatch):
    client, db = client_with_db
    reservation = _reservation(db, 1, "MP-WH-NESTED-PII")
    link = _create_link(db, 1, reservation.id, "90.00")
    sensitive_marker = "SYNTHETIC_NESTED_PII_MARKER"
    event_id = "mp-event-nested-privacy-1"
    payment_id = "mp-payment-nested-privacy-1"
    captured_payload = {}
    original_ingest = payment_webhook_service.ingest_webhook

    def capture_ingest(*args, **kwargs):
        captured_payload.update(kwargs["payload"])
        return original_ingest(*args, **kwargs)

    monkeypatch.setattr("app.api.payment_links.ingest_webhook", capture_ingest)

    response = _post_webhook(
        client,
        external_reference=link.external_reference,
        data_id=payment_id,
        webhook_id="operator@example.com",
        event_id=event_id,
        nested_external_reference=sensitive_marker,
        status_detail=sensitive_marker,
        event_action=sensitive_marker,
        status="approved",
        amount="90.00",
        request_id="req-nested-privacy-1",
    )

    assert response.status_code == 200, response.text
    assert captured_payload["data"]["external_reference"] == link.external_reference
    assert captured_payload["data"]["id"] == payment_id
    assert captured_payload["payment_id"] == payment_id
    payment = db.query(Payment).filter(Payment.reservation_id == reservation.id).one()
    event = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.payment_id == payment.id).one()
    transaction = db.query(Transaction).filter(Transaction.reservation_id == reservation.id).one()

    assert event.webhook_id == event_id
    assert event.event_type == "payment"
    assert event.raw_payload["external_reference"] == link.external_reference
    assert event.raw_payload["data"] == {"id": payment_id}
    assert "action" not in event.raw_payload
    assert "status" not in event.raw_payload
    assert "status_detail" not in event.raw_payload
    assert "amount" not in event.raw_payload
    assert "transaction_amount" not in event.raw_payload
    assert "currency" not in event.raw_payload
    assert "collector_id" not in event.raw_payload
    assert sensitive_marker not in str(event.raw_payload)
    assert "operator@example.com" not in str(event.raw_payload)
    assert payment.status == "completed"
    assert payment.amount == Decimal("90.00")
    assert payment.gateway_response["status"] == "approved"
    assert payment.gateway_response["transaction_amount"] == 90.0
    persisted = str([payment.gateway_response, event.raw_payload, transaction.gateway_response])
    assert sensitive_marker not in persisted


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
