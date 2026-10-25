"""Real PostgreSQL concurrency coverage for payment-link test callbacks."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.payment_link_test import PaymentLinkTest
from app.services import payment_link_test_service
from app.services.payment_link_test_service import refresh_mercadopago_payment_link_test_by_reference
from app.services.tenant_context import set_tenant_hotel_context


def test_older_callback_snapshot_cannot_replace_newer_state_across_postgres_sessions(
    pg_engine, monkeypatch
):
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    external_reference = f"mp-test-{hotel_id}-{uuid4().hex[:18]}"
    payment_id = f"synthetic-payment-{hotel_id}"
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(
            HotelConfiguration(
                id=hotel_id,
                hotel_name=f"Synthetic PaymentLinkTest {hotel_id}",
                subscription_active=True,
            )
        )
        seed.flush()
        seed.add(
            PaymentLinkTest(
                hotel_id=hotel_id,
                provider="mercadopago",
                recipient_email="synthetic@example.test",
                amount=42.0,
                currency="ARS",
                description="Synthetic payment test",
                external_reference=external_reference,
                status="pending",
                external_status="preference_created",
            )
        )
        seed.commit()
    finally:
        seed.close()

    monkeypatch.setattr(
        payment_link_test_service,
        "require_inbound_provider_events",
        lambda _provider: None,
    )
    older_fetch_started = Event()
    newer_snapshot_committed = Event()

    snapshots = {
        "older": {
            "id": payment_id,
            "external_reference": external_reference,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": 42.0,
            "currency_id": "ARS",
            "date_last_updated": "2026-10-22T14:01:00Z",
            "transaction_amount_refunded": 0.0,
        },
        "newer": {
            "id": payment_id,
            "external_reference": external_reference,
            "status": "refunded",
            "status_detail": "refunded",
            "transaction_amount": 42.0,
            "currency_id": "ARS",
            "date_last_updated": "2026-10-22T14:02:00Z",
            "transaction_amount_refunded": 42.0,
        },
    }

    def invoke(label: str) -> str:
        session = session_factory()
        session.info["payment_link_snapshot_label"] = label

        def fetch_payment(db, _hotel_id, _payment_id):
            # Mirror the endpoint's transaction release before provider I/O.
            db.commit()
            if label == "older":
                older_fetch_started.set()
                if not newer_snapshot_committed.wait(timeout=15):
                    raise TimeoutError("newer callback did not commit in time")
            return snapshots[label]

        try:
            record = refresh_mercadopago_payment_link_test_by_reference(
                session,
                external_reference,
                hotel_id=hotel_id,
                external_payment_id=payment_id,
                payment_fetcher=fetch_payment,
            )
            assert record is not None
            status_after_apply = record.status
            session.commit()
            if label == "newer":
                newer_snapshot_committed.set()
            return status_after_apply
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="payment-link-test-race") as executor:
        older_future = executor.submit(invoke, "older")
        assert older_fetch_started.wait(timeout=10), "older provider snapshot did not start"
        newer_future = executor.submit(invoke, "newer")
        assert newer_future.result(timeout=20) == "refunded"
        assert older_future.result(timeout=20) == "refunded"

    check = session_factory()
    try:
        set_tenant_hotel_context(check, hotel_id)
        record = check.query(PaymentLinkTest).filter_by(external_reference=external_reference).one()
        assert record.status == "refunded"
        assert record.external_payment_id == payment_id
        assert record.gateway_response["date_last_updated"] == "2026-10-22T14:02:00Z"
        assert record.refunded_amount == pytest.approx(42.0)
        assert record.refunded_at.replace(tzinfo=timezone.utc) == datetime(
            2026, 10, 22, 14, 2, tzinfo=timezone.utc
        )
    finally:
        check.close()
