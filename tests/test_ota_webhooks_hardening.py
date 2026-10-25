from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.config import get_settings
from app.database import Base, get_db
from app.models.hotel_config import HotelConfiguration
from app.models.ota import OTAReservationMapping
from app.models.ota_core import OTAReservationLink
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.encryption import get_encryption_fernet
from app.services.ota_service import (
    OTAIntegrationService,
    OTAError,
    OTAProcessingError,
    OTA_CONFLICT_ERROR_MESSAGE,
    OTA_PROCESSING_ERROR_MESSAGE,
    _ota_reconciliation_payload_projection,
)


@pytest.fixture(autouse=True)
def _provide_fresh_fx_quotes_for_reservations(monkeypatch):
    def quote(currency: str, market: str = "oficial"):
        return {
            "moneda": currency,
            "casa": market if currency == "USD" else "oficial",
            "compra": 1000.0,
            "venta": 1100.0,
            "fechaActualizacion": datetime.now(timezone.utc).isoformat(),
        }

    monkeypatch.setattr("app.services.pricing_policy_service.get_conversion_quote_sync", quote)


@pytest.fixture(autouse=True)
def _enable_mocked_inbound_events(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="function")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("ota-hardening-db")
    return f"sqlite:///{(db_dir / 'ota.sqlite').as_posix()}"


@pytest.fixture(scope="function")
def engine(db_url: str):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(engine) -> sessionmaker:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(engine, db_url: str, monkeypatch: pytest.MonkeyPatch):
    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db(db_url)
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db(db_url))

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()


def _seed_hotel(db, hotel_id: int, room_type_code: str) -> tuple[str, str]:
    db.add(HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", owner_email=f"owner{hotel_id}@test.local", subscription_active=True))
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=room_type_code,
        base_price_per_night=100.0 + hotel_id,
        max_occupancy=2,
        description=f"Category {room_type_code} for hotel {hotel_id}",
    )
    db.add(category)
    db.flush()

    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()

    booking_secret = f"booking-secret-{hotel_id}"
    expedia_secret = f"expedia-secret-{hotel_id}"
    despegar_secret = f"despegar-secret-{hotel_id}"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="booking",
        webhook_secret=booking_secret,
        external_property_id=f"booking-{hotel_id}",
    )
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="expedia",
        webhook_secret=expedia_secret,
        external_property_id=f"expedia-{hotel_id}",
    )
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="despegar",
        webhook_secret=despegar_secret,
        external_property_id=f"despegar-{hotel_id}",
    )
    return booking_secret, expedia_secret, despegar_secret


def _assert_ota_payload_storage(
    db,
    mapping: OTAReservationMapping,
    payload: dict,
    *,
    required_projection_fields: set[str],
) -> None:
    projected_payload = json.loads(mapping.raw_payload or "{}")
    assert required_projection_fields <= projected_payload.keys()
    serialized_projection = json.dumps(projected_payload, sort_keys=True)

    for sensitive_value in ("Jane Doe", "jane@example.com", "Ana", "Lopez", "ana@example.com", "Luis", "Diaz", "luis@example.com"):
        assert sensitive_value not in serialized_projection

    link = db.query(OTAReservationLink).filter_by(
        hotel_id=mapping.hotel_id,
        external_reservation_id=mapping.ota_reservation_id,
    ).one()
    assert link.raw_payload_encrypted
    assert not link.raw_payload_encrypted.startswith("{")
    assert json.loads(
        get_encryption_fernet().decrypt(link.raw_payload_encrypted.encode("ascii")).decode("utf-8")
    ) == payload


def test_booking_webhook_scopes_by_hotel_and_secret(client: TestClient, db, monkeypatch):
    tenant_context_hotel_ids = []
    monkeypatch.setattr(
        "app.services.ota_service.set_tenant_hotel_context",
        lambda _db, hotel_id: tenant_context_hotel_ids.append(hotel_id),
    )
    booking_secret_1, _, _ = _seed_hotel(db, 1, "STD_DBL")
    booking_secret_2, _, _ = _seed_hotel(db, 2, "STD_DBL")
    db.commit()

    payload = {
        "reservation_id": "BKG-2001",
        "guest_name": "Jane Doe",
        "guest_email": "jane@example.com",
        "checkin": "2026-04-10",
        "checkout": "2026-04-12",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 320.0,
        "currency": "ARS",
        "property_id": "booking-2",
    }

    response = client.post(f"/api/webhooks/booking/2/{booking_secret_2}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert tenant_context_hotel_ids == [2, 2]

    db.expire_all()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=2,
        ota_name="booking",
        ota_reservation_id="BKG-2001",
    ).one()
    assert mapping.hotel_id == 2
    assert mapping.reservation is not None
    assert mapping.reservation.hotel_id == 2
    assert mapping.reservation.room is not None
    assert mapping.reservation.room.hotel_id == 2
    _assert_ota_payload_storage(
        db,
        mapping,
        payload,
        required_projection_fields={
            "reservation_id",
            "property_id",
            "checkin",
            "checkout",
            "room_type",
            "total_price",
            "currency",
        },
    )

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="booking",
        ota_reservation_id="BKG-2001",
    ).count() == 0


def test_expedia_webhook_scopes_by_hotel_and_secret(client: TestClient, db):
    _, expedia_secret_1, _ = _seed_hotel(db, 1, "STD_DBL")
    _, expedia_secret_2, _ = _seed_hotel(db, 2, "STD_DBL")
    db.commit()

    payload = {
        "booking_id": "EXP-2002",
        "guest": {"first_name": "Ana", "last_name": "Lopez", "email": "ana@example.com"},
        "stay": {"checkin": "2026-04-15", "checkout": "2026-04-17"},
        "room_type_id": "STD_DBL",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {"total": 280.0, "currency": "ARS"},
        "property_id": "expedia-1",
    }

    response = client.post(f"/api/webhooks/expedia/1/{expedia_secret_1}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    db.expire_all()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="expedia",
        ota_reservation_id="EXP-2002",
    ).one()
    assert mapping.hotel_id == 1
    assert mapping.reservation is not None
    assert mapping.reservation.hotel_id == 1
    assert mapping.reservation.room is not None
    assert mapping.reservation.room.hotel_id == 1
    _assert_ota_payload_storage(
        db,
        mapping,
        payload,
        required_projection_fields={"booking_id", "stay", "room_type_id", "occupancy", "pricing"},
    )

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=2,
        ota_name="expedia",
        ota_reservation_id="EXP-2002",
    ).count() == 0


def test_ota_webhook_rejects_invalid_secret(client: TestClient, db):
    _seed_hotel(db, 1, "STD_DBL")
    db.commit()

    payload = {
        "reservation_id": "BKG-2999",
        "guest_name": "Invalid Secret",
        "guest_email": "invalid@example.com",
        "checkin": "2026-04-20",
        "checkout": "2026-04-22",
        "room_type": "STD_DBL",
        "num_adults": 1,
        "num_children": 0,
        "total_price": 150.0,
        "currency": "ARS",
        "property_id": "booking-1",
    }

    response = client.post("/api/webhooks/booking/1/not-the-secret", json=payload)
    assert response.status_code == 401
    assert db.query(OTAReservationMapping).count() == 0


def test_despegar_webhook_scopes_by_hotel_and_secret(client: TestClient, db):
    _, _, despegar_secret_1 = _seed_hotel(db, 1, "STD_DBL")
    _, _, despegar_secret_2 = _seed_hotel(db, 2, "STD_DBL")
    db.commit()

    payload = {
        "reservation_id": "DSP-2003",
        "confirmation_code": "DSP-CNF-2003",
        "guest": {"first_name": "Luis", "last_name": "Diaz", "email": "luis@example.com"},
        "stay": {"checkin": "2026-04-18", "checkout": "2026-04-20"},
        "product_code": "STD_DBL",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {"total": 310.0, "currency": "USD"},
        "property_id": "despegar-2",
    }

    response = client.post(f"/api/webhooks/despegar/2/{despegar_secret_2}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    db.expire_all()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=2,
        ota_name="despegar",
        ota_reservation_id="DSP-2003",
    ).one()
    assert mapping.hotel_id == 2
    assert mapping.reservation is not None
    assert mapping.reservation.hotel_id == 2
    assert mapping.reservation.room is not None
    assert mapping.reservation.room.hotel_id == 2
    _assert_ota_payload_storage(
        db,
        mapping,
        payload,
        required_projection_fields={
            "reservation_id",
            "confirmation_code",
            "stay",
            "product_code",
            "occupancy",
            "pricing",
        },
    )

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="despegar",
        ota_reservation_id="DSP-2003",
    ).count() == 0


def test_reconciliation_projection_rejects_pii_shaped_values_under_allowed_keys():
    payload = {
        "reservation_id": "guest@example.com",
        "confirmation_code": "Jane Doe",
        "booking_id": "ABC",
        "event": "reservation.modified",
        "event_type": "reservation_updated",
        "status": "Ana Lopez",
        "checkin": "guest@example.com",
        "check_out_date": "2026-04-12",
        "room_type": "Private Guest",
        "product_code": "DELUXE",
        "num_adults": "jane@example.com",
        "children": 0,
        "total_price": "Luis Diaz",
        "currency": "ARS",
        "stay": {
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
            "guest_email": "nested@example.com",
        },
        "occupancy": {"adults": 2, "children": "Guest Name"},
        "pricing": {
            "total": 120.0,
            "currency": "ARS",
            "commission": {"total": 5.0},
        },
        "commission": 5.0,
        "guest_email": "guest@example.com",
    }

    projected = _ota_reconciliation_payload_projection(payload)
    serialized = json.dumps(projected, sort_keys=True)

    assert projected["event"] == "reservation.modified"
    assert projected["event_type"] == "reservation_updated"
    assert projected["booking_id"] == "ABC"
    assert projected["product_code"] == "DELUXE"
    assert projected["check_out_date"] == "2026-04-12"
    assert projected["children"] == 0
    assert projected["stay"] == {"checkin": "2026-04-10", "checkout": "2026-04-12"}
    assert projected["occupancy"] == {"adults": 2}
    assert projected["pricing"] == {
        "total": 120.0,
        "currency": "ARS",
        "commission": {"total": 5.0},
    }
    assert projected["commission"] == 5.0
    for sensitive_value in (
        "guest@example.com",
        "Jane Doe",
        "Ana Lopez",
        "Luis Diaz",
        "Private Guest",
        "jane@example.com",
        "Guest Name",
        "nested@example.com",
    ):
        assert sensitive_value not in serialized
    assert not {
        "reservation_id",
        "confirmation_code",
        "status",
        "checkin",
        "room_type",
        "num_adults",
    }.intersection(projected)


def test_ota_service_marks_unexpected_error_safely_before_caller_transaction_decision(db, monkeypatch):
    booking_secret, _, _ = _seed_hotel(db, 1, "STD_DBL")
    payload = {
        "reservation_id": "BKG-5001",
        "guest_name": "Private Guest",
        "guest_email": "private@example.com",
        "checkin": "2026-04-10",
        "checkout": "2026-04-12",
        "room_type": "STD_DBL",
        "num_adults": 1,
        "num_children": 0,
        "total_price": 150.0,
        "currency": "ARS",
        "property_id": "booking-1",
    }

    def fail_materialization(*_args, **_kwargs):
        raise RuntimeError("internal SQL detail private@example.com")

    monkeypatch.setattr(
        OTAIntegrationService,
        "_materialize_incoming_reservation",
        staticmethod(fail_materialization),
    )

    with pytest.raises(OTAProcessingError) as error:
        OTAIntegrationService.process_booking_webhook(db, 1, booking_secret, payload)

    assert str(error.value) == OTA_PROCESSING_ERROR_MESSAGE
    # This service-level check commits to inspect its safe error state. The HTTP
    # handler deliberately rolls the transaction back, as verified below.
    db.commit()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="booking",
        ota_reservation_id="BKG-5001",
    ).one()
    assert mapping.error_message == OTA_PROCESSING_ERROR_MESSAGE
    assert "internal SQL detail" not in mapping.error_message
    assert "private@example.com" not in (mapping.raw_payload or "")


def test_ota_webhook_returns_generic_500_for_unexpected_processing_error(client, db, monkeypatch):
    booking_secret, _, _ = _seed_hotel(db, 1, "STD_DBL")
    db.commit()

    def fail_materialization(*_args, **_kwargs):
        raise RuntimeError("internal SQL detail private@example.com")

    monkeypatch.setattr(
        OTAIntegrationService,
        "_materialize_incoming_reservation",
        staticmethod(fail_materialization),
    )

    response = client.post(
        f"/api/webhooks/booking/1/{booking_secret}",
        json={
            "reservation_id": "BKG-5002",
            "guest_name": "Private Guest",
            "guest_email": "private@example.com",
            "checkin": "2026-04-10",
            "checkout": "2026-04-12",
            "room_type": "STD_DBL",
            "num_adults": 1,
            "num_children": 0,
            "total_price": 150.0,
            "currency": "ARS",
            "property_id": "booking-1",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": OTA_PROCESSING_ERROR_MESSAGE}
    assert "internal SQL detail" not in response.text
    assert "private@example.com" not in response.text
    assert db.query(OTAReservationMapping).filter_by(ota_reservation_id="BKG-5002").count() == 0


def test_ota_webhook_hides_room_and_reservation_details_from_conflict_response(client, db, monkeypatch):
    booking_secret, _, _ = _seed_hotel(db, 1, "STD_DBL")
    db.commit()
    internal_details = "OVERBOOKING: reservation BKG-PRIVATE room 402"

    def fail_with_conflict(*_args, **_kwargs):
        raise OTAError(internal_details)

    monkeypatch.setattr(
        OTAIntegrationService,
        "process_booking_webhook",
        staticmethod(fail_with_conflict),
    )
    response = client.post(
        f"/api/webhooks/booking/1/{booking_secret}",
        json={"reservation_id": "BKG-PRIVATE"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": OTA_CONFLICT_ERROR_MESSAGE}
    assert "BKG-PRIVATE" not in response.text
    assert "402" not in response.text
