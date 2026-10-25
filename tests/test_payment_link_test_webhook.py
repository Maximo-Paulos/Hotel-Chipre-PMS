from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.payment_link_test import PaymentLinkTest
from app.services import payment_link_test_service
import app.services.payment_webhook_service as payment_webhook_service
from app.services.payment_webhook_service import RetryablePaymentWebhookError

WEBHOOK_SECRET = "synthetic-mp-test-webhook-secret"
PAYMENT_ID = "synthetic-provider-payment-12"
REFERENCE = "mp-test-12-0123456789abcdef01"
DECOY_REFERENCE = "mp-test-12-fedcba987654321001"
INITIAL_RESPONSE = {"fixture": "unchanged-until-provider-verification"}


@pytest.fixture
def webhook_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    fetches: list[tuple[int, str]] = []
    provider_response = {
        "id": PAYMENT_ID,
        "external_reference": REFERENCE,
        "status": "approved",
        "status_detail": "accredited",
        "transaction_amount": 42.0,
        "currency_id": "ARS",
        "date_approved": "2026-10-22T14:00:00Z",
        "date_last_updated": "2026-10-22T14:01:00Z",
        "transaction_amount_refunded": 0.0,
        "payer": {
            "id": "synthetic-payer-id",
            "email": "synthetic-payer@example.test",
            "identification": {"type": "DNI", "number": "synthetic-id"},
        },
        "metadata": {"internal_marker": "must-not-persist"},
        "additional_info": {"items": [{"title": "private description"}]},
    }

    def override_get_db():
        yield db

    def fetch_payment(_db, hotel_id, external_payment_id, *, commit_before_network=False):
        if commit_before_network:
            _db.commit()
        fetches.append((hotel_id, external_payment_id))
        return dict(provider_response)

    monkeypatch.setattr(
        "app.api.payment_link_tests.get_settings",
        lambda: SimpleNamespace(MERCADOPAGO_WEBHOOK_SECRET=WEBHOOK_SECRET),
    )
    monkeypatch.setattr("app.api.payment_link_tests.require_inbound_provider_events", lambda _provider: None)
    monkeypatch.setattr(
        payment_link_test_service, "require_inbound_provider_events", lambda _provider: None
    )
    monkeypatch.setattr(
        payment_link_test_service,
        "set_tenant_hotel_context",
        lambda _db, _hotel_id: None,
    )
    monkeypatch.setattr("app.api.payment_link_tests.fetch_mercadopago_payment", fetch_payment)
    fastapi_app.dependency_overrides[get_db] = override_get_db

    db.add(HotelConfiguration(id=12, hotel_name="Synthetic webhook hotel", subscription_active=True))
    db.flush()
    for reference in (REFERENCE, DECOY_REFERENCE):
        db.add(
            PaymentLinkTest(
                hotel_id=12,
                provider="mercadopago",
                recipient_email="synthetic@example.test",
                amount=42.0,
                currency="ARS",
                description="Synthetic payment test",
                external_reference=reference,
                status="pending",
                external_status="preference_created",
                gateway_response=dict(INITIAL_RESPONSE),
            )
        )
    db.commit()

    client = TestClient(fastapi_app)
    try:
        yield client, db, provider_response, fetches
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _signature(data_id: str, request_id: str) -> str:
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={timestamp},v1={digest}"


def _post(client, *, reference: str, body: dict):
    request_id = "synthetic-request-12"
    return client.post(
        "/api/payment-link-tests/mercadopago/webhook",
        params={"external_reference": reference, "data.id": PAYMENT_ID},
        json=body,
        headers={"x-signature": _signature(PAYMENT_ID, request_id), "x-request-id": request_id},
    )


def test_unsigned_reference_status_and_money_do_not_override_provider_payment(webhook_client):
    client, db, provider_response, fetches = webhook_client
    response = _post(
        client,
        reference=REFERENCE,
        body={
            "external_reference": DECOY_REFERENCE,
            "status": "rejected",
            "transaction_amount": 0.01,
            "currency_id": "USD",
            "data": {"id": PAYMENT_ID},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
    assert fetches == [(12, PAYMENT_ID)]
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    assert record.status == "approved"
    assert record.external_status == "accredited"
    assert record.external_payment_id == PAYMENT_ID
    assert record.gateway_response == {
        "id": PAYMENT_ID,
        "external_reference": REFERENCE,
        "status": "approved",
        "status_detail": "accredited",
        "transaction_amount": 42.0,
        "currency_id": "ARS",
        "date_approved": "2026-10-22T14:00:00Z",
        "date_last_updated": "2026-10-22T14:01:00Z",
        "transaction_amount_refunded": 0.0,
    }
    assert not {"payer", "metadata", "additional_info"} & set(record.gateway_response)


def test_provider_amount_matches_cents_sent_for_payment_link_test(webhook_client):
    client, db, _provider_response, _fetches = webhook_client
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    record.amount = 42.004
    db.commit()

    response = _post(
        client,
        reference=REFERENCE,
        body={"status": "rejected", "transaction_amount": 42.004, "currency_id": "ARS"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
    db.refresh(record)
    assert record.status == "approved"
    assert record.amount == pytest.approx(42.004)


def test_older_provider_snapshot_cannot_regress_a_newer_payment_state(webhook_client):
    client, db, provider_response, _fetches = webhook_client
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    record.status = "refunded"
    record.external_status = "refunded"
    record.external_payment_id = PAYMENT_ID
    record.refunded_amount = 42.0
    record.refunded_at = datetime(2026, 10, 22, 14, 2, tzinfo=timezone.utc)
    record.gateway_response = {
        **provider_response,
        "status": "refunded",
        "date_last_updated": "2026-10-22T14:02:00Z",
        "transaction_amount_refunded": 42.0,
    }
    db.commit()

    provider_response["status"] = "approved"
    provider_response["status_detail"] = "accredited"
    provider_response["date_last_updated"] = "2026-10-22T14:01:00Z"
    provider_response["transaction_amount_refunded"] = 0.0
    response = _post(client, reference=REFERENCE, body={"data": {"id": PAYMENT_ID}})

    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "refunded"
    db.refresh(record)
    assert record.status == "refunded"
    assert record.refunded_amount == pytest.approx(42.0)
    assert record.refunded_at.replace(tzinfo=timezone.utc) == datetime(
        2026, 10, 22, 14, 2, tzinfo=timezone.utc
    )
    assert record.gateway_response["date_last_updated"] == "2026-10-22T14:02:00Z"


def test_unknown_provider_status_preserves_state_and_records_diagnostic(webhook_client):
    client, db, provider_response, _fetches = webhook_client
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    record.status = "approved"
    record.external_status = "accredited"
    record.external_payment_id = PAYMENT_ID
    record.paid_at = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    record.gateway_response = {
        **provider_response,
        "date_last_updated": "2026-10-22T14:00:00Z",
    }
    db.commit()
    provider_response["status"] = "provider_status_added_later"
    provider_response["status_detail"] = "new_status_detail"
    provider_response["date_last_updated"] = "2026-10-22T14:02:00Z"

    response = _post(client, reference=REFERENCE, body={"data": {"id": PAYMENT_ID}})

    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "approved"
    db.refresh(record)
    assert record.status == "approved"
    assert record.external_status == "provider_status_added_later"
    assert record.last_error == "Mercado Pago devolvio un estado de pago no reconocido."
    assert record.gateway_response["status"] == "provider_status_added_later"
    assert record.paid_at.replace(tzinfo=timezone.utc) == datetime(
        2026, 10, 22, 14, 0, tzinfo=timezone.utc
    )


def test_retryable_provider_fetch_failure_returns_503(webhook_client, monkeypatch):
    client, db, _provider_response, _fetches = webhook_client

    def fail_fetch(*_args, **_kwargs):
        raise RetryablePaymentWebhookError("provider timeout")

    monkeypatch.setattr("app.api.payment_link_tests.fetch_mercadopago_payment", fail_fetch)
    response = _post(client, reference=REFERENCE, body={"data": {"id": PAYMENT_ID}})

    assert response.status_code == 503, response.text
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    assert record.status == "pending"


def test_provider_rate_limit_is_retryable_and_releases_transaction(webhook_client, monkeypatch):
    _client, db, _provider_response, _fetches = webhook_client
    db.execute(text("SELECT 1"))
    assert db.in_transaction()

    monkeypatch.setattr(
        payment_webhook_service,
        "require_external_connections",
        lambda _operation: None,
    )
    monkeypatch.setattr(
        "app.services.integration_service.get_connection_payload",
        lambda _db, _hotel_id, _provider: {"access_token": "synthetic-access-token"},
    )

    def rate_limited_request(_operation, _request, _url, **_kwargs):
        assert not db.in_transaction()
        return SimpleNamespace(ok=False, status_code=429)

    monkeypatch.setattr(payment_webhook_service, "observed_http_call", rate_limited_request)
    with pytest.raises(RetryablePaymentWebhookError):
        payment_webhook_service.fetch_mercadopago_payment(
            db,
            12,
            PAYMENT_ID,
            commit_before_network=True,
        )


def test_unsigned_reference_cannot_redirect_signed_payment_to_another_test_record(webhook_client):
    client, db, _provider_response, fetches = webhook_client
    response = _post(
        client,
        reference=DECOY_REFERENCE,
        body={"status": "approved", "transaction_amount": 42.0, "currency_id": "ARS"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "error"
    assert fetches == [(12, PAYMENT_ID)]
    for record in db.query(PaymentLinkTest).order_by(PaymentLinkTest.external_reference).all():
        assert record.status == "pending"
        assert record.external_status == "preference_created"
        assert record.external_payment_id is None
        assert record.gateway_response == INITIAL_RESPONSE
        assert record.last_checked_at is None
        assert record.paid_at is None
        assert record.refunded_at is None
        assert record.cancelled_at is None


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("id", "different-provider-payment"),
        ("external_reference", DECOY_REFERENCE),
        ("transaction_amount", 41.99),
        ("currency_id", "USD"),
    ],
)
def test_mismatched_canonical_provider_data_does_not_change_test_row(
    webhook_client, field, tampered_value
):
    client, db, provider_response, _fetches = webhook_client
    provider_response[field] = tampered_value
    response = _post(
        client,
        reference=REFERENCE,
        body={"status": "approved", "transaction_amount": 42.0, "currency_id": "ARS"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "error"
    record = db.query(PaymentLinkTest).filter_by(external_reference=REFERENCE).one()
    assert record.status == "pending"
    assert record.external_status == "preference_created"
    assert record.external_payment_id is None
    assert record.gateway_response == INITIAL_RESPONSE
    assert record.last_checked_at is None
    assert record.paid_at is None
    assert record.refunded_at is None
    assert record.cancelled_at is None
