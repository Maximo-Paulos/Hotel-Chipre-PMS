"""PostgreSQL regression for OTA cancellation racing with check-in."""
from __future__ import annotations

import threading
import time
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.services.ota_service as ota_service_module
from app.config import get_settings
from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily
from app.models.audit_log import AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.ota import (
    OTAReservationMapping,
    OTASyncStatusEnum,
    OTAWebhookCredential,
)
from app.models.ota_core import OTAReservationLifecycleEnum, OTAReservationLink
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.services.checkin_service import _load_reservation
from app.services.ota_service import OTAError, OTAIntegrationService
from app.services.reservation_service import (
    lock_reservation_version,
    transition_reservation_status,
)
from app.services.tenant_context import set_tenant_hotel_context


@pytest.fixture(autouse=True)
def _enable_mocked_inbound_events(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _booking_cancel_payload(
    external_id: str,
    property_id: str,
    *,
    event: str = "reservation.cancelled",
    checkout_date: date | None = None,
) -> dict[str, object]:
    today = date.today()
    return {
        "reservation_id": external_id,
        "guest_name": "Synthetic Guest",
        "checkin": (today - timedelta(days=1)).isoformat(),
        "checkout": (checkout_date or today + timedelta(days=1)).isoformat(),
        "room_type": "SYNTHETIC",
        "num_adults": 1,
        "num_children": 0,
        "total_price": 200.0,
        "currency": "ARS",
        "property_id": property_id,
        "event": event,
    }


def _wait_for_blocking_backend(pg_engine, backend_pid: int, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    with pg_engine.connect() as monitor:
        while time.monotonic() < deadline:
            blockers = monitor.execute(
                text("SELECT pg_blocking_pids(:backend_pid)"),
                {"backend_pid": backend_pid},
            ).scalar_one()
            if blockers:
                return True
            time.sleep(0.01)
    return False


def test_ota_cancellation_waits_for_checkin_and_uses_committed_status(pg_engine, monkeypatch):
    """Cancellation waits for check-in's reservation lock, then requires review."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 100_000_000 + uuid4().int % 100_000_000
    external_id = f"PG-OTA-CHECKIN-{suffix}"
    property_id = f"PG-PROPERTY-{suffix}"
    webhook_secret = f"synthetic-booking-secret-{suffix}"
    reservation_id: int | None = None
    payment_link_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic OTA check-in race {suffix}")
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic {suffix}",
            code=f"C{suffix[:8]}",
            base_price_per_night=Decimal("100.00"),
            variable_cost_per_night=Decimal("10.00"),
            max_occupancy=2,
        )
        seed.add(hotel)
        seed.flush()
        seed.add_all([guest, category])
        seed.flush()

        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"OTA-CI-{suffix}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today() + timedelta(days=1),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            amount_paid=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
            external_id=external_id,
            source_provider_code="booking",
        )
        seed.add(reservation)
        seed.flush()
        OTAIntegrationService.upsert_webhook_credential(
            seed,
            hotel_id,
            provider="booking",
            webhook_secret=webhook_secret,
            external_property_id=property_id,
        )
        seed.add_all(
            [
                OTAReservationMapping(
                    hotel_id=hotel_id,
                    reservation_id=reservation.id,
                    ota_name="booking",
                    ota_reservation_id=external_id,
                    ota_guest_name="Synthetic Guest",
                    sync_status=OTASyncStatusEnum.SYNCED,
                ),
                PaymentLink(
                    hotel_id=hotel_id,
                    reservation_id=reservation.id,
                    link_code=f"PG{suffix}",
                    requested_amount=Decimal("50.00"),
                    currency="ARS",
                    status="active",
                    execution_mode="local_only",
                    payable=False,
                    recipient_email="synthetic@example.invalid",
                    recipient_name="Synthetic Guest",
                ),
            ]
        )
        seed.commit()
        reservation_id = reservation.id
        payment_link_id = (
            seed.query(PaymentLink)
            .filter(PaymentLink.hotel_id == hotel_id, PaymentLink.reservation_id == reservation_id)
            .one()
            .id
        )
    finally:
        seed.close()

    checkin_session = session_factory()
    worker_thread: threading.Thread | None = None
    try:
        set_tenant_hotel_context(checkin_session, hotel_id)
        checked_in, resolved_hotel_id = _load_reservation(checkin_session, reservation_id, hotel_id)
        assert resolved_hotel_id == hotel_id
        transition_reservation_status(
            checkin_session,
            checked_in,
            ReservationStatusEnum.CHECKED_IN,
            hotel_id=hotel_id,
        )
        checkin_session.flush()

        lock_attempted = threading.Event()
        backend_pid_ready = threading.Event()
        worker_backend_pid: list[int] = []
        worker_result: dict[str, object] = {}
        worker_errors: list[Exception] = []
        snapshot_statuses: list[ReservationStatusEnum] = []
        original_lock_query = ota_service_module.lock_query
        original_snapshot = ota_service_module.audit_log_service.model_snapshot

        def signal_reservation_lock(query, model):
            if model is Reservation:
                lock_attempted.set()
            return original_lock_query(query, model)

        def record_reservation_snapshot(instance):
            if instance is not None and instance.id == reservation_id:
                snapshot_statuses.append(instance.status)
            return original_snapshot(instance)

        monkeypatch.setattr(ota_service_module, "lock_query", signal_reservation_lock)
        monkeypatch.setattr(
            ota_service_module.audit_log_service,
            "model_snapshot",
            record_reservation_snapshot,
        )

        def process_cancel_webhook() -> None:
            try:
                with session_factory() as webhook_session:
                    set_tenant_hotel_context(webhook_session, hotel_id)
                    backend_pid = webhook_session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    worker_backend_pid.append(int(backend_pid))
                    backend_pid_ready.set()
                    webhook_session.execute(text("SET LOCAL lock_timeout = '10s'"))
                    result = OTAIntegrationService.process_booking_webhook(
                        webhook_session,
                        hotel_id,
                        webhook_secret,
                        _booking_cancel_payload(external_id, property_id),
                    )
                    webhook_session.commit()
                    worker_result["sync_status"] = result.sync_status
                    worker_result["error_message"] = result.error_message
            except Exception as exc:  # noqa: BLE001 - surface worker failures in the test thread
                worker_errors.append(exc)

        worker_thread = threading.Thread(target=process_cancel_webhook, daemon=True)
        worker_thread.start()
        try:
            assert backend_pid_ready.wait(timeout=5), "webhook session did not start"
            assert lock_attempted.wait(timeout=5), "cancellation did not lock the reservation"
            assert _wait_for_blocking_backend(pg_engine, worker_backend_pid[0]), (
                "webhook did not wait on the check-in transaction's reservation lock"
            )
        finally:
            checkin_session.commit()

        worker_thread.join(timeout=10)
        assert not worker_thread.is_alive(), "webhook did not finish after check-in committed"
        if worker_errors:
            raise worker_errors[0]

        assert worker_result["sync_status"] == OTASyncStatusEnum.CONFLICT
        assert "manual resolution required" in str(worker_result["error_message"]).lower()
        assert snapshot_statuses
        assert snapshot_statuses[0] == ReservationStatusEnum.CHECKED_IN

        with session_factory() as verification:
            set_tenant_hotel_context(verification, hotel_id)
            persisted_reservation = verification.query(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.hotel_id == hotel_id,
            ).one()
            persisted_mapping = verification.query(OTAReservationMapping).filter(
                OTAReservationMapping.hotel_id == hotel_id,
                OTAReservationMapping.reservation_id == reservation_id,
            ).one()
            persisted_payment_link = verification.query(PaymentLink).filter(
                PaymentLink.hotel_id == hotel_id,
                PaymentLink.id == payment_link_id,
            ).one()
            foundation_link = verification.query(OTAReservationLink).filter_by(
                hotel_id=hotel_id,
                external_reservation_id=external_id,
            ).one()

            assert persisted_reservation.status == ReservationStatusEnum.CHECKED_IN
            assert persisted_reservation.requires_manual_review is True
            assert persisted_reservation.settlement_status == "manual_resolution_required"
            assert persisted_mapping.sync_status == OTASyncStatusEnum.CONFLICT
            assert persisted_payment_link.status == "active"
            assert persisted_payment_link.payable is False
            assert foundation_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
    finally:
        if checkin_session.in_transaction():
            checkin_session.rollback()
        checkin_session.close()
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=2)

        with session_factory.begin() as cleanup:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(OTAReservationLink).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(OTAReservationMapping).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(PaymentLink).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(FactReservationDaily).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(FactRoomOccupancyDaily).filter_by(hotel_id=hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(AuditLog).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(Guest).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)


def test_ota_modification_locks_reservation_before_room_after_extension(pg_engine, monkeypatch):
    """A modification waits for an extension's reservation lock before room selection."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 200_000_000 + uuid4().int % 100_000_000
    external_id = f"PG-OTA-EXTENSION-{suffix}"
    property_id = f"PG-PROPERTY-{suffix}"
    webhook_secret = f"synthetic-booking-secret-{suffix}"
    reservation_id: int | None = None
    room_id: int | None = None
    category_id: int | None = None
    initial_checkout = date.today() + timedelta(days=1)
    extension_checkout = date.today() + timedelta(days=2)
    ota_checkout = date.today() + timedelta(days=3)

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic OTA extension race {suffix}")
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic {suffix}",
            code=f"S{suffix[:8]}",
            base_price_per_night=Decimal("100.00"),
            variable_cost_per_night=Decimal("10.00"),
            max_occupancy=2,
        )
        seed.add(hotel)
        seed.flush()
        seed.add_all([guest, category])
        seed.flush()
        room = Room(hotel_id=hotel_id, room_number=f"{suffix[:4]}", category_id=category.id)
        seed.add(room)
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"OTA-EXT-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=initial_checkout,
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            amount_paid=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
            external_id=external_id,
            source_provider_code="booking",
        )
        seed.add(reservation)
        seed.flush()
        OTAIntegrationService.upsert_webhook_credential(
            seed,
            hotel_id,
            provider="booking",
            webhook_secret=webhook_secret,
            external_property_id=property_id,
        )
        seed.add(
            OTAReservationMapping(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                ota_name="booking",
                ota_reservation_id=external_id,
                ota_guest_name="Synthetic Guest",
                sync_status=OTASyncStatusEnum.SYNCED,
            )
        )
        seed.commit()
        reservation_id = reservation.id
        room_id = room.id
        category_id = category.id
    finally:
        seed.close()

    extension_session = session_factory()
    worker_thread: threading.Thread | None = None
    try:
        set_tenant_hotel_context(extension_session, hotel_id)
        extension_reservation = extension_session.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.hotel_id == hotel_id,
        ).one()
        # Mirror the extension service's lock order: reservation, then room.
        lock_reservation_version(
            extension_session,
            extension_reservation,
            hotel_id=hotel_id,
            client_version=extension_reservation.version,
        )
        extension_room = extension_session.query(Room).filter(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
        ).with_for_update(of=Room).one()
        assert extension_room.id == room_id
        extension_reservation.check_out_date = extension_checkout
        extension_reservation.version += 1
        extension_session.flush()

        lock_attempted = threading.Event()
        backend_pid_ready = threading.Event()
        room_selection_started = threading.Event()
        worker_backend_pid: list[int] = []
        worker_result: dict[str, object] = {}
        worker_errors: list[Exception] = []
        snapshot_checkouts: list[date] = []
        original_lock_query = ota_service_module.lock_query
        original_snapshot = ota_service_module.audit_log_service.model_snapshot
        original_select_room = OTAIntegrationService._select_room_for_normalized_reservation

        def signal_reservation_lock(query, model):
            if model is Reservation:
                lock_attempted.set()
            return original_lock_query(query, model)

        def record_reservation_snapshot(instance):
            if instance is not None and instance.id == reservation_id:
                snapshot_checkouts.append(instance.check_out_date)
            return original_snapshot(instance)

        def signal_room_selection(db, **kwargs):
            room_selection_started.set()
            return original_select_room(db, **kwargs)

        monkeypatch.setattr(ota_service_module, "lock_query", signal_reservation_lock)
        monkeypatch.setattr(
            ota_service_module.audit_log_service,
            "model_snapshot",
            record_reservation_snapshot,
        )
        monkeypatch.setattr(
            OTAIntegrationService,
            "_resolve_commercial_context",
            lambda db, **kwargs: (None, None, [category]),
        )
        monkeypatch.setattr(
            OTAIntegrationService,
            "_select_room_for_normalized_reservation",
            signal_room_selection,
        )

        def process_modified_webhook() -> None:
            try:
                with session_factory() as webhook_session:
                    set_tenant_hotel_context(webhook_session, hotel_id)
                    backend_pid = webhook_session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                    worker_backend_pid.append(int(backend_pid))
                    backend_pid_ready.set()
                    webhook_session.execute(text("SET LOCAL lock_timeout = '10s'"))
                    result = OTAIntegrationService.process_booking_webhook(
                        webhook_session,
                        hotel_id,
                        webhook_secret,
                        _booking_cancel_payload(
                            external_id,
                            property_id,
                            event="reservation.modified",
                            checkout_date=ota_checkout,
                        ),
                    )
                    webhook_session.commit()
                    worker_result["sync_status"] = result.sync_status
            except Exception as exc:  # noqa: BLE001 - surface worker failures in the test thread
                worker_errors.append(exc)

        worker_thread = threading.Thread(target=process_modified_webhook, daemon=True)
        worker_thread.start()
        try:
            assert backend_pid_ready.wait(timeout=5), "webhook session did not start"
            assert lock_attempted.wait(timeout=5), "modification did not lock the reservation"
            assert _wait_for_blocking_backend(pg_engine, worker_backend_pid[0]), (
                "webhook did not wait on the extension transaction's reservation lock"
            )
            assert not room_selection_started.is_set(), (
                "OTA modification reached room selection before the extension released Reservation"
            )
        finally:
            extension_session.commit()

        worker_thread.join(timeout=10)
        assert not worker_thread.is_alive(), "webhook did not finish after extension committed"
        if worker_errors:
            raise worker_errors[0]

        assert room_selection_started.is_set(), "modification never reached room selection after waiting"
        assert worker_result["sync_status"] == OTASyncStatusEnum.SYNCED
        assert snapshot_checkouts[0] == extension_checkout
        assert snapshot_checkouts[-1] == ota_checkout
        with session_factory() as verification:
            set_tenant_hotel_context(verification, hotel_id)
            persisted_reservation = verification.query(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.hotel_id == hotel_id,
            ).one()
            assert persisted_reservation.check_out_date == ota_checkout
    finally:
        if extension_session.in_transaction():
            extension_session.rollback()
        extension_session.close()
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=2)

        with session_factory.begin() as cleanup:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(OTAReservationLink).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(OTAReservationMapping).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(FactReservationDaily).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(FactRoomOccupancyDaily).filter_by(hotel_id=hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(AuditLog).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            if room_id is not None:
                cleanup.query(Room).filter(Room.id == room_id, Room.hotel_id == hotel_id).delete(
                    synchronize_session=False
                )
            if category_id is not None:
                cleanup.query(RoomCategory).filter(
                    RoomCategory.id == category_id,
                    RoomCategory.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            cleanup.query(Guest).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)


def test_ota_cancellation_does_not_follow_cross_hotel_reservation_mapping(pg_engine):
    """A stale cross-tenant mapping cannot make cancellation mutate another hotel's stay."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 300_000_000 + uuid4().int % 100_000_000
    foreign_hotel_id = hotel_id + 100_000_001
    external_id = f"PG-OTA-FOREIGN-{suffix}"
    property_id = f"PG-PROPERTY-{suffix}"
    webhook_secret = f"synthetic-booking-secret-{suffix}"
    reservation_id: int | None = None

    seed = session_factory()
    try:
        seed.add_all(
            [
                HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic OTA tenant A {suffix}"),
                HotelConfiguration(id=foreign_hotel_id, hotel_name=f"Synthetic OTA tenant B {suffix}"),
            ]
        )
        seed.flush()
        set_tenant_hotel_context(seed, foreign_hotel_id)
        guest = Guest(hotel_id=foreign_hotel_id, first_name="Synthetic", last_name="Foreign")
        seed.add(guest)
        seed.flush()
        category = RoomCategory(
            hotel_id=foreign_hotel_id,
            name=f"Synthetic Foreign {suffix}",
            code=f"F{suffix[:8]}",
            base_price_per_night=Decimal("100.00"),
            variable_cost_per_night=Decimal("10.00"),
            max_occupancy=2,
        )
        seed.add(category)
        seed.flush()
        reservation = Reservation(
            hotel_id=foreign_hotel_id,
            confirmation_code=f"OTA-FOREIGN-{suffix}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today() + timedelta(days=1),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
            external_id=external_id,
            source_provider_code="booking",
        )
        seed.add(reservation)
        seed.flush()

        set_tenant_hotel_context(seed, hotel_id)
        OTAIntegrationService.upsert_webhook_credential(
            seed,
            hotel_id,
            provider="booking",
            webhook_secret=webhook_secret,
            external_property_id=property_id,
        )
        seed.add(
            OTAReservationMapping(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                ota_name="booking",
                ota_reservation_id=external_id,
                ota_guest_name="Synthetic Foreign",
                sync_status=OTASyncStatusEnum.SYNCED,
            )
        )
        seed.commit()
        reservation_id = reservation.id
    finally:
        seed.close()

    try:
        with session_factory() as webhook_session:
            set_tenant_hotel_context(webhook_session, hotel_id)
            with pytest.raises(OTAError, match="no está disponible para este hotel"):
                OTAIntegrationService.process_booking_webhook(
                    webhook_session,
                    hotel_id,
                    webhook_secret,
                    _booking_cancel_payload(external_id, property_id),
                )
            webhook_session.rollback()

        with session_factory() as verification:
            set_tenant_hotel_context(verification, foreign_hotel_id)
            reservation = verification.query(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.hotel_id == foreign_hotel_id,
            ).one()
            assert reservation.status == ReservationStatusEnum.FULLY_PAID
    finally:
        with session_factory.begin() as cleanup:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(OTAReservationMapping).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(OTAWebhookCredential).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            set_tenant_hotel_context(cleanup, foreign_hotel_id)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == foreign_hotel_id,
                ).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter_by(hotel_id=foreign_hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(Guest).filter_by(hotel_id=foreign_hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter_by(id=foreign_hotel_id).delete(synchronize_session=False)
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
