from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User


@pytest.fixture
def blocks_client(monkeypatch: pytest.MonkeyPatch):
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

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    auth_state = {"hotel_id": 1, "user_id": 11, "role": "manager"}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="manager@example.com",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner1@example.com", subscription_active=True),
                HotelConfiguration(id=2, owner_email="owner2@example.com", subscription_active=True),
                User(id=11, email="manager@example.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal, auth_state

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_room(db, *, hotel_id: int, room_number: str) -> Room:
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number=room_number,
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def test_create_room_block_public_api(blocks_client):
    client, SessionLocal, _ = blocks_client
    with SessionLocal() as db:
        room = _seed_room(db, hotel_id=1, room_number="101")
        room_id = room.id

    response = client.post(
        f"/api/rooms/{room_id}/blocks",
        json={"start_date": "2026-07-01", "end_date": "2026-07-03", "reason": "Pipe repair"},
    )

    assert response.status_code == 201, response.text
    assert response.json() == {"blocked": True, "moved_reservations": [], "conflicts": []}


def test_list_room_blocks_public_api(blocks_client):
    client, SessionLocal, _ = blocks_client
    with SessionLocal() as db:
        room = _seed_room(db, hotel_id=1, room_number="102")
        room_id = room.id

    create = client.post(
        f"/api/rooms/{room_id}/blocks",
        json={"start_date": "2026-08-01", "end_date": "2026-08-01", "reason": "Deep clean"},
    )
    assert create.status_code == 201, create.text

    response = client.get(f"/api/rooms/{room_id}/blocks")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["room_id"] == room_id
    assert payload[0]["start_date"] == "2026-08-01"
    assert payload[0]["end_date"] == "2026-08-01"
    assert payload[0]["reason"] == "Deep clean"
    assert payload[0]["is_active"] is True


def test_release_room_block_public_api(blocks_client):
    client, SessionLocal, _ = blocks_client
    with SessionLocal() as db:
        room = _seed_room(db, hotel_id=1, room_number="103")
        room_id = room.id

    create = client.post(
        f"/api/rooms/{room_id}/blocks",
        json={"start_date": "2026-09-01", "end_date": "2026-09-02", "reason": "Maintenance"},
    )
    assert create.status_code == 201, create.text
    listed = client.get(f"/api/rooms/{room_id}/blocks")
    block_id = listed.json()[0]["id"]

    release = client.delete(f"/api/blocks/{block_id}")

    assert release.status_code == 200, release.text
    assert release.json() == {"released": True, "moved_reservations": []}
    assert client.get(f"/api/rooms/{room_id}/blocks").json() == []


def test_room_blocks_public_api_is_hotel_scoped(blocks_client):
    client, SessionLocal, auth_state = blocks_client
    with SessionLocal() as db:
        room_1 = _seed_room(db, hotel_id=1, room_number="104")
        room_2 = _seed_room(db, hotel_id=2, room_number="204")
        room_1_id = room_1.id
        room_2_id = room_2.id

    create = client.post(
        f"/api/rooms/{room_1_id}/blocks",
        json={"start_date": "2026-10-01", "end_date": "2026-10-02", "reason": "Owner hold"},
    )
    assert create.status_code == 201, create.text

    auth_state["hotel_id"] = 2
    own_hotel_listing = client.get(f"/api/rooms/{room_2_id}/blocks")
    hidden_foreign_room = client.get(f"/api/rooms/{room_1_id}/blocks")

    assert own_hotel_listing.status_code == 200, own_hotel_listing.text
    assert own_hotel_listing.json() == []
    assert hidden_foreign_room.status_code == 404
