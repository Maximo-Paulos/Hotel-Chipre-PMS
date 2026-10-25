"""PostgreSQL coverage for exclusive provider-revocation work claims."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Event, Lock
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.services import payment_link_service
from app.services.payment_link_service import process_payment_link_revocations
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks import payment_link_revocation_tasks


def test_postgres_stale_claim_recovery_does_not_duplicate_unstarted_batch_work(
    pg_engine, monkeypatch
):
    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: True)
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(
            HotelConfiguration(
                id=hotel_id,
                hotel_name=f"Synthetic revocation {hotel_id}",
                subscription_active=True,
            )
        )
        seed.flush()
        guest = Guest(
            hotel_id=hotel_id,
            first_name="Synthetic",
            last_name="Revocation Guest",
        )
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Revocation Room {hotel_id}",
            code=f"REV{hotel_id}",
            base_price_per_night=100,
            max_occupancy=2,
        )
        seed.add_all([guest, category])
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"REV-{hotel_id}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 11, 1),
            check_out_date=date(2026, 11, 3),
            total_amount=Decimal("200.00"),
            deposit_amount=Decimal("60.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.CANCELLED,
        )
        seed.add(reservation)
        seed.flush()
        links = [
            PaymentLink(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                provider="mercado_pago",
                link_code=f"plink-{hotel_id}-{index}",
                requested_amount=Decimal("100.00"),
                collected_amount=Decimal("0.00"),
                currency="ARS",
                recipient_email="synthetic@example.test",
                status="cancelled",
                execution_mode="provider",
                payable=False,
                external_checkout_url=f"https://mp.test/checkout/{hotel_id}/{index}",
                external_reference=f"synthetic-ref-{hotel_id}-{index}",
                provider_revocation_status="pending",
                provider_revocation_attempts=0,
                gateway_response={"preference_id": f"synthetic-pref-{hotel_id}-{index}"},
            )
            for index in (1, 2)
        ]
        seed.add_all(links)
        seed.commit()
        link_ids = [link.id for link in links]
    finally:
        seed.close()

    class _MutableClock:
        current = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current.replace(tzinfo=None)
            return cls.current.astimezone(tz)

    monkeypatch.setattr(payment_link_service, "datetime", _MutableClock)
    provider_started = Event()
    release_provider = Event()
    calls_lock = Lock()
    gateway_calls: list[tuple[int, int]] = []

    def revoke_gateway(_db, _hotel_id, claimed_link):
        with calls_lock:
            gateway_calls.append((claimed_link.id, claimed_link.provider_revocation_attempts))
        if claimed_link.provider_revocation_attempts == 1 and claimed_link.id == link_ids[0]:
            provider_started.set()
            if not release_provider.wait(timeout=15):
                raise TimeoutError("timed out waiting to release synthetic provider call")
            # A late result from an expired lease must not overwrite the newer claim.
            return {"preference_expired": False}
        return {"preference_expired": True}

    def run_processor() -> dict[str, int]:
        session = session_factory()
        try:
            set_tenant_hotel_context(session, hotel_id)
            return process_payment_link_revocations(
                session,
                hotel_id,
                reservation_id=reservation.id,
                revoke_gateway=revoke_gateway,
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="revocation-claim") as executor:
        first_future = executor.submit(run_processor)
        assert provider_started.wait(timeout=10), "the first session did not claim the revocation"
        second_result = run_processor()
        # Move beyond the lease expiry while the first synthetic provider call is
        # still in flight. The second session has already drained link 2 once;
        # only link 1 may be recovered, and the late attempt-1 result is fenced.
        _MutableClock.current = datetime(2026, 10, 22, 12, 6, tzinfo=UTC)
        stale_recovery_result = run_processor()
        release_provider.set()
        first_result = first_future.result(timeout=20)

    assert second_result == {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert stale_recovery_result == {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert first_result == {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1}
    assert gateway_calls == [(link_ids[0], 1), (link_ids[1], 1), (link_ids[0], 2)]

    check = session_factory()
    try:
        set_tenant_hotel_context(check, hotel_id)
        persisted = (
            check.query(PaymentLink)
            .filter(PaymentLink.hotel_id == hotel_id, PaymentLink.id.in_(link_ids))
            .order_by(PaymentLink.id.asc())
            .all()
        )
        assert [(link.provider_revocation_status, link.provider_revocation_attempts) for link in persisted] == [
            ("succeeded", 2),
            ("succeeded", 1),
        ]
    finally:
        check.close()


def test_postgres_scheduled_task_recovers_pending_link_for_inactive_hotel(
    pg_engine, monkeypatch
):
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(
            HotelConfiguration(
                id=hotel_id,
                hotel_name=f"Synthetic inactive revocation {hotel_id}",
                subscription_active=False,
            )
        )
        seed.flush()
        guest = Guest(
            hotel_id=hotel_id,
            first_name="Synthetic",
            last_name="Inactive Revocation Guest",
        )
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Inactive Revocation Room {hotel_id}",
            code=f"INREV{hotel_id}",
            base_price_per_night=100,
            max_occupancy=2,
        )
        seed.add_all([guest, category])
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"INREV-{hotel_id}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 11, 1),
            check_out_date=date(2026, 11, 3),
            total_amount=Decimal("200.00"),
            deposit_amount=Decimal("60.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.CANCELLED,
        )
        seed.add(reservation)
        seed.flush()
        link = PaymentLink(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            provider="mercado_pago",
            link_code=f"inactive-plink-{hotel_id}",
            requested_amount=Decimal("100.00"),
            collected_amount=Decimal("0.00"),
            currency="ARS",
            recipient_email="synthetic@example.test",
            status="cancelled",
            execution_mode="provider",
            payable=False,
            external_checkout_url=f"https://mp.test/checkout/inactive/{hotel_id}",
            external_reference=f"synthetic-inactive-ref-{hotel_id}",
            provider_revocation_status="pending",
            provider_revocation_attempts=0,
            gateway_response={"preference_id": f"synthetic-inactive-pref-{hotel_id}"},
        )
        seed.add(link)
        seed.commit()
        link_id = link.id
    finally:
        seed.close()

    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: True)
    monkeypatch.setattr(
        payment_link_service,
        "_mercadopago_preference_expired",
        lambda _db, received_hotel_id, _link: {
            "preference_expired": received_hotel_id == hotel_id
        },
    )
    db = session_factory()
    try:
        result = payment_link_revocation_tasks._process_pending_revocations(
            db,
            now=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
        )
    finally:
        db.close()

    assert result["processed"] == result["succeeded"] == 1
    assert result["failed"] == 0
    assert result["attempts_used"] == 1
    check = session_factory()
    try:
        set_tenant_hotel_context(check, hotel_id)
        persisted = check.query(PaymentLink).filter_by(hotel_id=hotel_id, id=link_id).one()
        assert persisted.provider_revocation_status == "succeeded"
        assert persisted.provider_revocation_attempts == 1
    finally:
        check.close()
