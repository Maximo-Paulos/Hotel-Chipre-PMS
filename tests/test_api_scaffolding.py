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
