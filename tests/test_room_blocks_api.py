from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import room_blocks
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.permission_service import resolve


def _override_auth(hotel_id: int, role: str):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=123,
            user_email=f"{role}@example.com",
            user_role=role,
            is_verified=True,
        )

    return dependency


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'room_blocks_api.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    app = FastAPI()
    app.include_router(room_blocks.router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, session, app
    app.dependency_overrides.clear()
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_room(db, hotel_id: int = 1) -> Room:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    if db.get(User, 123) is None:
        db.add(
            User(
                id=123,
                email="user123@example.com",
                password_hash="test",
                is_active=True,
                is_verified=True,
            )
        )
    db.flush()
    return room


def test_room_block_permission_defaults(db):
    assert resolve(db, 1, "owner", "room:block") is True
    assert resolve(db, 1, "co_owner", "room:block") is True
    assert resolve(db, 1, "manager", "room:block") is True
    assert resolve(db, 1, "receptionist", "room:block") is False
    assert resolve(db, 1, "housekeeping", "room:block") is False


def test_create_and_resolve_room_block_api(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

    create_response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
            "reason_note": "Pipe repair",
        },
    )

    assert create_response.status_code == 201
    block_id = create_response.json()["id"]

    list_response = test_client.get(
        "/api/room-blocks/",
        params={"start_date": "2026-07-02", "end_date": "2026-07-04"},
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [block_id]

    resolve_response = test_client.post(f"/api/room-blocks/{block_id}/resolve")
    assert resolve_response.status_code == 200
    assert resolve_response.json()["resolved_by_user_id"] == 123


def test_receptionist_cannot_create_room_block_by_default(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")

    response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )

    assert response.status_code == 403


def test_room_block_api_is_hotel_scoped(client):
    test_client, db, app = client
    room_1 = _seed_room(db, hotel_id=1)
    _seed_room(db, hotel_id=2)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

    response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room_1.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )
    assert response.status_code == 201

    app.dependency_overrides[get_auth_context] = _override_auth(2, "manager")
    list_response = test_client.get(
        "/api/room-blocks/",
        params={"start_date": "2026-07-02", "end_date": "2026-07-04"},
    )

    assert list_response.status_code == 200
    assert list_response.json() == []
