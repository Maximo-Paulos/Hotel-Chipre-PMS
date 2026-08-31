"""Editing a room category into a duplicate code or name must answer 409.

`room_categories` is unique on (hotel_id, code) and on (hotel_id, name). Before
this guard the IntegrityError escaped `PATCH /api/rooms/categories/{id}` as an
unhandled 500 which, being produced above the CORS middleware, reached the
browser without an Access-Control-Allow-Origin header -- so the Configuración >
Hotel page showed "Failed to fetch" instead of a readable conflict message.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import rooms as rooms_api
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory

HOTEL_ID = 1


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'category_conflict.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    session.add(HotelConfiguration(id=HOTEL_ID, subscription_active=True))
    session.flush()
    first = RoomCategory(hotel_id=HOTEL_ID, name="Doble", code="DBL", base_price_per_night=100, max_occupancy=2)
    second = RoomCategory(hotel_id=HOTEL_ID, name="Suite", code="SUI", base_price_per_night=200, max_occupancy=3)
    session.add_all([first, second])
    session.flush()
    session.add_all([
        Room(hotel_id=HOTEL_ID, room_number="101", floor=1, category_id=first.id),
        Room(hotel_id=HOTEL_ID, room_number="102", floor=1, category_id=first.id),
    ])
    session.commit()

    app = FastAPI()
    app.include_router(rooms_api.router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        hotel_id=HOTEL_ID,
        user_id=123,
        user_email="owner@example.com",
        user_role="owner",
        is_verified=True,
    )

    with TestClient(app) as test_client:
        yield test_client, second.id, session

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.parametrize("payload", [{"code": "DBL"}, {"name": "Doble"}])
def test_duplicate_category_returns_409(client, payload):
    test_client, category_id, _session = client

    response = test_client.patch(f"/api/rooms/categories/{category_id}", json=payload)

    assert response.status_code == 409, response.text
    assert "código o nombre" in response.json()["detail"]


def test_non_conflicting_edit_still_saves(client):
    test_client, category_id, _session = client

    response = test_client.patch(f"/api/rooms/categories/{category_id}", json={"base_price_per_night": 250})

    assert response.status_code == 200, response.text
    assert response.json()["base_price_per_night"] == 250


def test_duplicate_room_number_returns_409(client):
    """Same failure mode one section below on the same settings page: renaming a
    room onto an existing number must answer 409, not an unhandled 500.
    """
    test_client, _category_id, session = client
    room = session.query(Room).filter(Room.room_number == "102").one()

    response = test_client.patch(f"/api/rooms/{room.id}", json={"room_number": "101"})

    assert response.status_code == 409, response.text
    assert "número" in response.json()["detail"]
