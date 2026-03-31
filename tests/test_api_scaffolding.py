from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.models.guest import Guest
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    """Spin up the real FastAPI app against an in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Route init_db to our ephemeral engine
    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as client:
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_rooms_crud_smoke(api_client):
    client, SessionLocal = api_client

    # Seed a category for room creation
    with SessionLocal() as db:
        cat = RoomCategory(
            name="Demo Standard",
            code="STD_DEMO",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add(cat)
        db.commit()
        db.refresh(cat)
        category_id = cat.id

    create_resp = client.post(
        "/api/rooms/",
        json={"room_number": "101", "floor": 1, "category_id": category_id, "status": RoomStatusEnum.AVAILABLE.value},
    )
    assert create_resp.status_code == 201, create_resp.text
    room_id = create_resp.json()["id"]

    # Placeholder availability works without params
    avail = client.get("/api/rooms/availability")
    assert avail.status_code == 200
    assert avail.json()["status"] == "placeholder"

    update_resp = client.patch(f"/api/rooms/{room_id}", json={"notes": "Sea view"})
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["notes"] == "Sea view"

    delete_resp = client.delete(f"/api/rooms/{room_id}")
    assert delete_resp.status_code == 204, delete_resp.text

    list_resp = client.get("/api/rooms/")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_room_status_and_category_fetch(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        cat = RoomCategory(
            name="Status Cat",
            code="STAT_CAT",
            base_price_per_night=90.0,
            max_occupancy=2,
        )
        db.add(cat)
        db.flush()
        room = Room(room_number="401", floor=4, category_id=cat.id, status=RoomStatusEnum.AVAILABLE)
        db.add(room)
        db.commit()
        db.refresh(cat)
        db.refresh(room)
        cat_id, room_id = cat.id, room.id

    cat_resp = client.get(f"/api/rooms/categories/{cat_id}")
    assert cat_resp.status_code == 200
    assert cat_resp.json()["code"] == "STAT_CAT"

    status_resp = client.patch(f"/api/rooms/{room_id}/status", json={"status": RoomStatusEnum.MAINTENANCE.value, "notes": "Deep clean"})
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["room"]["id"] == room_id
    assert body["room"]["status"] == RoomStatusEnum.MAINTENANCE.value
    assert body["room"]["notes"] == "Deep clean"
    assert "reallocation" in body

def test_bookings_basic_flow(api_client):
    client, SessionLocal = api_client
    today = date.today()
    checkout = today + timedelta(days=2)

    # Seed prerequisites
    with SessionLocal() as db:
        cat = RoomCategory(
            name="Suite",
            code="STE",
            base_price_per_night=200.0,
            max_occupancy=3,
        )
        guest = Guest(first_name="Test", last_name="Guest", email="guest@example.com")
        db.add_all([cat, guest])
        db.flush()
        room = Room(room_number="201", floor=2, category_id=cat.id, status=RoomStatusEnum.AVAILABLE)
        db.add(room)
        db.commit()
        db.refresh(cat)
        db.refresh(room)
        db.refresh(guest)
        payload = {
            "guest_id": guest.id,
            "category_id": cat.id,
            "room_id": room.id,
            "check_in_date": today.isoformat(),
            "check_out_date": checkout.isoformat(),
            "num_adults": 2,
        }

    # Placeholder availability
    avail = client.get("/api/bookings/availability")
    assert avail.status_code == 200
    assert avail.json()["status"] == "placeholder"

    create = client.post("/api/bookings/", json=payload)
    assert create.status_code == 201, create.text
    booking_id = create.json()["id"]

    listing = client.get("/api/bookings/")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    delete = client.delete(f"/api/bookings/{booking_id}")
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    listing_after = client.get("/api/bookings/")
    assert listing_after.status_code == 200
    assert listing_after.json() == []


def test_booking_status_and_overlap(api_client):
    client, SessionLocal = api_client
    start = date(2026, 4, 1)
    end = start + timedelta(days=2)  # 2 nights

    with SessionLocal() as db:
        cat = RoomCategory(
            name="Standard API",
            code="STD_API",
            base_price_per_night=120.0,
            max_occupancy=2,
        )
        guest = Guest(first_name="API", last_name="Tester", email="api@test.com")
        room1 = Room(room_number="301", floor=3, category_id=1, status=RoomStatusEnum.AVAILABLE)
        room2 = Room(room_number="302", floor=3, category_id=1, status=RoomStatusEnum.AVAILABLE)
        db.add_all([cat, guest])
        db.flush()
        room1.category_id = cat.id
        room2.category_id = cat.id
        db.add_all([room1, room2])
        db.commit()
        db.refresh(cat)
        db.refresh(guest)
        db.refresh(room1)
        db.refresh(room2)
        cat_id, guest_id, room1_id, room2_id = cat.id, guest.id, room1.id, room2.id

    quote = client.get(
        "/api/bookings/price-quote",
        params={"category_id": cat_id, "check_in_date": start.isoformat(), "check_out_date": end.isoformat()},
    )
    assert quote.status_code == 200
    payload = quote.json()
    assert payload["nights"] == 2
    assert payload["total_amount"] == 240.0
    assert payload["deposit_amount"] == pytest.approx(72.0)

    base_payload = {
        "guest_id": guest_id,
        "category_id": cat_id,
        "check_in_date": start.isoformat(),
        "check_out_date": end.isoformat(),
        "num_adults": 2,
    }
    create1 = client.post("/api/bookings/", json=base_payload | {"room_id": room1_id})
    assert create1.status_code == 201
    booking1_id = create1.json()["id"]
    assert create1.json()["balance_due"] == pytest.approx(240.0)

    # Overlap on same room should fail
    overlap = client.post("/api/bookings/", json=base_payload | {"room_id": room1_id})
    assert overlap.status_code == 400

    # Use second room for status flow
    create2 = client.post("/api/bookings/", json=base_payload | {"room_id": room2_id})
    assert create2.status_code == 201
    booking2_id = create2.json()["id"]

    # Cancel booking1
    cancel = client.post(f"/api/bookings/{booking1_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == ReservationStatusEnum.CANCELLED.value

    # Mark booking2 as fully paid and perform check-in/out
    with SessionLocal() as db:
        res = db.query(Reservation).filter(Reservation.id == booking2_id).first()
        res.status = ReservationStatusEnum.FULLY_PAID
        db.commit()

    checkin = client.post(f"/api/bookings/{booking2_id}/checkin")
    assert checkin.status_code == 200
    assert checkin.json()["status"] == ReservationStatusEnum.CHECKED_IN.value

    checkout_resp = client.post(f"/api/bookings/{booking2_id}/checkout")
    assert checkout_resp.status_code == 200
    assert checkout_resp.json()["status"] == ReservationStatusEnum.CHECKED_OUT.value
