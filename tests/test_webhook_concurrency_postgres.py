"""Two-session idempotency regressions for inbound payment and OTA webhooks.

These tests intentionally require the repository's explicitly isolated local
PostgreSQL fixture. SQLite cannot exercise transaction-scoped advisory locks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Event, Lock
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.services.payment_webhook_service as payment_webhook_service
from app.config import get_settings
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.ota import OTAReservationMapping, OTAWebhookCredential
from app.models.ota_core import OTAReservationLink
from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import Transaction
from app.services.ota_service import OTAIntegrationService
from app.services.payment_webhook_service import ingest_webhook
from app.services.tenant_context import set_tenant_hotel_context


@pytest.fixture(autouse=True)
def _enable_synthetic_inbound_webhooks(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _hotel_id() -> int:
    return 80_000_000 + uuid4().int % 10_000_000


def _race_two_sessions(
    pg_engine,
    monkeypatch,
    *,
    hotel_id: int,
    lock_owner,
    lock_name: str,
    lock_is_static: bool = False,
    matches_lock,
    operation,
):
    """Hold the first real PostgreSQL lock until the second session is waiting."""
    owner_has_lock = Event()
    waiter_attempted_lock = Event()
    release_owner = Event()
    claim_guard = Lock()
    owner_claimed = False
    original_lock = getattr(lock_owner, lock_name)

    def observed_lock(*args, **kwargs):
        nonlocal owner_claimed
        session = args[0]
        selected = matches_lock(*args, **kwargs)
        label = session.info.get("_webhook_race_label")
        if not selected:
            return original_lock(*args, **kwargs)
        if label == "second":
            waiter_attempted_lock.set()
            return original_lock(*args, **kwargs)

        with claim_guard:
            should_hold = label == "first" and not owner_claimed
            if should_hold:
                owner_claimed = True
        original_lock(*args, **kwargs)
        if should_hold:
            owner_has_lock.set()
            if not release_owner.wait(timeout=15):
                raise TimeoutError("timed out waiting to release the PostgreSQL webhook lock")

    replacement = staticmethod(observed_lock) if lock_is_static else observed_lock
    monkeypatch.setattr(lock_owner, lock_name, replacement)
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def invoke(label: str):
        session = session_factory()
        session.info["_webhook_race_label"] = label
        try:
            set_tenant_hotel_context(session, hotel_id)
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": f"webhook-race-{label}"},
            )
            result = operation(session, label)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def wait_until_second_is_blocked() -> None:
        deadline = monotonic() + 8
        while monotonic() < deadline:
            with pg_engine.connect() as connection:
                waiting = connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = 'webhook-race-second' "
                        "AND wait_event_type = 'Lock' AND wait_event = 'advisory'"
                    )
                ).scalar_one()
            if waiting:
                return
            sleep(0.025)
        pytest.fail("the second PostgreSQL session did not wait on the advisory lock")

    second_future = None
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="webhook-race") as executor:
        first_future = executor.submit(invoke, "first")
        try:
            assert owner_has_lock.wait(timeout=10), "the first session did not acquire its advisory lock"
            second_future = executor.submit(invoke, "second")
            assert waiter_attempted_lock.wait(timeout=10), "the second session did not reach the advisory lock"
            wait_until_second_is_blocked()
        finally:
            release_owner.set()

        first_result = first_future.result(timeout=20)
        assert second_future is not None
        second_result = second_future.result(timeout=20)

    return first_result, second_result


def _seed_payment_target(pg_engine, hotel_id: int) -> int:
    session = sessionmaker(bind=pg_engine)()
    try:
        set_tenant_hotel_context(session, hotel_id)
        session.add(
            HotelConfiguration(
                id=hotel_id,
                hotel_name=f"Synthetic webhook {hotel_id}",
                subscription_active=True,
                enable_mercado_pago=True,
            )
        )
        session.flush()
        guest = Guest(first_name="Synthetic", last_name="Payment Guest", hotel_id=hotel_id)
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Webhook Room {hotel_id}",
            code=f"WH{hotel_id}",
            base_price_per_night=100,
            max_occupancy=2,
        )
        session.add_all([guest, category])
        session.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"WH-{hotel_id}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=30),
            check_out_date=date.today() + timedelta(days=33),
            total_amount=Decimal("300.00"),
            deposit_amount=Decimal("90.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
        )
        session.add(reservation)
        session.flush()
        link = PaymentLink(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            provider="mercado_pago",
            link_code=f"plink-{hotel_id}",
            requested_amount=Decimal("100.00"),
            collected_amount=Decimal("0.00"),
            currency="ARS",
            recipient_email="synthetic@example.test",
            status="pending",
            execution_mode="provider",
            payable=True,
            external_checkout_url=f"https://mp.test/checkout/{hotel_id}",
            external_reference=f"synthetic-ref-{hotel_id}",
        )
        session.add(link)
        session.commit()
        return link.id
    finally:
        session.close()


def test_same_payment_webhook_is_idempotent_under_two_postgres_sessions(pg_engine, monkeypatch):
    hotel_id = _hotel_id()
    link_id = _seed_payment_target(pg_engine, hotel_id)
    webhook_id = f"synthetic-hook-{hotel_id}"
    payment_id = f"synthetic-payment-{hotel_id}"
    payload = {
        "payment_id": payment_id,
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }
    def matches_lock(*_args, **kwargs):
        return kwargs.get("scope") == "event" and kwargs.get("identifier") == webhook_id

    def operation(session, _label):
        return ingest_webhook(
            session,
            hotel_id=hotel_id,
            provider="mercado_pago",
            webhook_id=webhook_id,
            payload=payload,
            payment_link_id=link_id,
            provider_fetcher=lambda *_args: {
                "id": payment_id,
                "external_reference": f"synthetic-ref-{hotel_id}",
                "transaction_amount": "100.00",
                "currency_id": "ARS",
                "status": "approved",
            },
        )

    results = _race_two_sessions(
        pg_engine,
        monkeypatch,
        hotel_id=hotel_id,
        lock_owner=payment_webhook_service,
        lock_name="_acquire_postgres_webhook_lock",
        matches_lock=matches_lock,
        operation=operation,
    )

    assert [result["duplicate"] for result in results] == [False, True]
    assert results[0]["event_id"] == results[1]["event_id"]
    check = sessionmaker(bind=pg_engine)()
    try:
        set_tenant_hotel_context(check, hotel_id)
        assert check.query(PaymentWebhookEvent).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(Payment).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(Transaction).filter_by(hotel_id=hotel_id).count() == 1
    finally:
        check.close()


def test_distinct_payment_events_share_one_payment_and_transaction_under_postgres_lock(pg_engine, monkeypatch):
    hotel_id = _hotel_id()
    link_id = _seed_payment_target(pg_engine, hotel_id)
    payment_id = f"synthetic-payment-{hotel_id}"
    def matches_lock(*_args, **kwargs):
        return kwargs.get("scope") == "payment" and kwargs.get("identifier") == payment_id

    def operation(session, label):
        return ingest_webhook(
            session,
            hotel_id=hotel_id,
            provider="mercado_pago",
            webhook_id=f"synthetic-hook-{label}-{hotel_id}",
            payload={
                "payment_id": payment_id,
                "status": "approved",
                "amount": "100.00",
                "currency": "ARS",
            },
            payment_link_id=link_id,
            provider_fetcher=lambda *_args: {
                "id": payment_id,
                "external_reference": f"synthetic-ref-{hotel_id}",
                "transaction_amount": "100.00",
                "currency_id": "ARS",
                "status": "approved",
            },
        )

    results = _race_two_sessions(
        pg_engine,
        monkeypatch,
        hotel_id=hotel_id,
        lock_owner=payment_webhook_service,
        lock_name="_acquire_postgres_webhook_lock",
        matches_lock=matches_lock,
        operation=operation,
    )

    assert all(result["duplicate"] is False for result in results)
    check = sessionmaker(bind=pg_engine)()
    try:
        set_tenant_hotel_context(check, hotel_id)
        assert check.query(PaymentWebhookEvent).filter_by(hotel_id=hotel_id).count() == 2
        assert check.query(Payment).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(Transaction).filter_by(hotel_id=hotel_id).count() == 1
        link = check.query(PaymentLink).filter_by(hotel_id=hotel_id).one()
        assert link.collected_amount == Decimal("100.00")
    finally:
        check.close()


def test_same_ota_reservation_is_materialized_once_under_two_postgres_sessions(pg_engine, monkeypatch):
    hotel_id = _hotel_id()
    secret = f"synthetic-booking-secret-{hotel_id}"
    external_id = f"synthetic-booking-{hotel_id}"
    property_id = f"booking-{hotel_id}"
    session = sessionmaker(bind=pg_engine)()
    try:
        set_tenant_hotel_context(session, hotel_id)
        session.add(
            HotelConfiguration(
                id=hotel_id,
                hotel_name=f"Synthetic OTA {hotel_id}",
                subscription_active=True,
                deposit_policy_configured=True,
                enable_booking_sync=True,
            )
        )
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Booking Room {hotel_id}",
            code=f"BK{hotel_id}",
            base_price_per_night=100,
            max_occupancy=2,
        )
        session.add(category)
        session.flush()
        session.add(
            Room(
                hotel_id=hotel_id,
                room_number="101",
                floor=1,
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE,
                is_active=True,
            )
        )
        OTAIntegrationService.upsert_webhook_credential(
            session,
            hotel_id=hotel_id,
            provider="booking",
            webhook_secret=secret,
            external_property_id=property_id,
        )
        session.commit()
    finally:
        session.close()

    def matches_lock(*_args, **kwargs):
        return kwargs.get("external_reservation_id") == external_id

    def operation(session, _label):
        mapping = OTAIntegrationService.process_booking_webhook(
            session,
            hotel_id,
            secret,
            {
                "reservation_id": external_id,
                "guest_name": "Synthetic Guest",
                "guest_email": f"guest-{hotel_id}@example.test",
                "checkin": (date.today() + timedelta(days=30)).isoformat(),
                "checkout": (date.today() + timedelta(days=32)).isoformat(),
                "room_type": f"BK{hotel_id}",
                "num_adults": 2,
                "num_children": 0,
                "total_price": 200.0,
                "currency": "ARS",
                "property_id": property_id,
            },
        )
        return {"mapping_id": mapping.id, "reservation_id": mapping.reservation_id}

    results = _race_two_sessions(
        pg_engine,
        monkeypatch,
        hotel_id=hotel_id,
        lock_owner=OTAIntegrationService,
        lock_name="_lock_inbound_reservation_identity",
        lock_is_static=True,
        matches_lock=matches_lock,
        operation=operation,
    )

    assert results[0] == results[1]
    check = sessionmaker(bind=pg_engine)()
    try:
        set_tenant_hotel_context(check, hotel_id)
        assert check.query(OTAReservationMapping).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(OTAReservationLink).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(Reservation).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(Guest).filter_by(hotel_id=hotel_id).count() == 1
        assert check.query(OTAWebhookCredential).filter_by(hotel_id=hotel_id).count() == 1
    finally:
        check.close()
