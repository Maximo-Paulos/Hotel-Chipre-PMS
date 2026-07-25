"""GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that
the frontend actually calls (see frontend/src/api/reservations.ts). The
Reservations page disables the "Crear" button until this quote succeeds
(quoteQuery.data.quote_token), for every role that can reach /reservas --
including receptionist, since that page has no per-role gate at all.

The endpoint's role allow-list was owner/co_owner/manager/housekeeping,
omitting receptionist entirely. That silently disabled reservation creation
for front-desk staff: the single most common daily task for that role.
"""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import bookings as bookings_api
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
        f"sqlite:///{tmp_path / 'bookings_api_roles.db'}",
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
    app.include_router(bookings_api.router)

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


def test_receptionist_can_get_price_quote(client):
    test_client, app, hotel_id, category_id = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=2)
    response = test_client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": category_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["quote_token"]
