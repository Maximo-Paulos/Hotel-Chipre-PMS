"""Reception needs to read room data to build reservations (room picker,
availability check, reservation details). Regression for a gap where the
`receptionist` role could not call GET /api/rooms or GET /api/rooms/availability
at all, which silently emptied the room picker on the Reservations page for
front-desk staff -- a core, everyday task for that role.
"""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import rooms as rooms_api
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory


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
        f"sqlite:///{tmp_path / 'rooms_api_roles.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    app = FastAPI()
    app.include_router(rooms_api.router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    hotel_id = 1
    session.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    session.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name="QA-Standard",
        code="QASTD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    session.add(category)
    session.flush()
    session.add(Room(hotel_id=hotel_id, room_number="QA-101", floor=1, category_id=category.id))
    session.commit()

    with TestClient(app) as test_client:
        yield test_client, app, hotel_id, category.id
    app.dependency_overrides.clear()
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_receptionist_can_list_rooms(client):
    test_client, app, hotel_id, _category_id = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

    response = test_client.get("/api/rooms/")

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_receptionist_can_check_room_availability(client):
    test_client, app, hotel_id, category_id = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=2)
    response = test_client.get(
        "/api/rooms/availability",
        params={
            "category_id": category_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
