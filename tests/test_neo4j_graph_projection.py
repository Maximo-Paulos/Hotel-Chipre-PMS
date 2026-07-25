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
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.graph_projection import (
    ASSIGNMENT_CYPHER,
    project_company_link,
    project_reservation_assignment,
    project_room_movement,
)


@pytest.fixture
def graph_api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.graph_projection.get_neo4j_driver", lambda: None)
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

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True),
                User(id=1, email="owner@test.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_neo4j_off_create_and_move_reservation_still_write_postgres(graph_api_client):
    client, SessionLocal = graph_api_client
    with SessionLocal() as db:
        guest = Guest(first_name="Graph", last_name="Guest", hotel_id=1)
        category = RoomCategory(
            hotel_id=1,
            name="Graph Standard",
            code="GRAPH_STD",
            base_price_per_night=100,
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        room_one = Room(
            hotel_id=1,
            room_number="701",
            floor=7,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
        )
        room_two = Room(
            hotel_id=1,
            room_number="702",
            floor=7,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add_all([room_one, room_two])
        db.commit()
        guest_id = guest.id
        category_id = category.id
        room_one_id = room_one.id
        room_two_id = room_two.id

    quote_response = client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": category_id,
            "check_in_date": "2026-10-01",
            "check_out_date": "2026-10-03",
            "num_adults": 1,
            "num_children": 0,
        },
    )
    assert quote_response.status_code == 200, quote_response.text

    create_response = client.post(
        "/api/reservations/",
        json={
            "guest_id": guest_id,
            "category_id": category_id,
            "room_id": room_one_id,
            "check_in_date": "2026-10-01",
            "check_out_date": "2026-10-03",
            "num_adults": 1,
            "quote_token": quote_response.json()["quote_token"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    reservation_id = create_response.json()["id"]
    assert create_response.json()["room_id"] == room_one_id

    move_response = client.post(
        f"/api/reservations/{reservation_id}/room-move",
        json={"to_room_id": room_two_id, "reason_code": "guest_request", "notes": "quiet room"},
    )
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["reservation"]["room_id"] == room_two_id

    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        assert reservation.room_id == room_two_id
        assert reservation.category_id == category_id


def test_project_functions_noop_when_neo4j_driver_is_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.graph_projection.get_neo4j_driver", lambda: None)

    project_reservation_assignment(1, 2, 3, 4, "pending")
    project_room_movement(1, 2, 3, 4, 5)
    project_company_link(1, 6, 2)


def test_assignment_projection_cypher_merge_shape(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, dict]] = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cypher, parameters):
            calls.append((cypher, parameters))

    class FakeDriver:
        def session(self):
            return FakeSession()

    monkeypatch.setattr("app.services.graph_projection.get_neo4j_driver", lambda: FakeDriver())

    project_reservation_assignment(1, 2, 3, 4, "pending")

    assert calls == [
        (
            ASSIGNMENT_CYPHER,
            {
                "hotel_id": 1,
                "reservation_id": 2,
                "room_id": 3,
                "guest_id": 4,
                "status": "pending",
            },
        )
    ]
    cypher = calls[0][0]
    assert "MERGE (reservation:Reservation" in cypher
    assert "MERGE (room:Room" in cypher
    assert "MERGE (guest:Guest" in cypher
    assert "MERGE (reservation)-[:ASSIGNED_TO]->(room)" in cypher
    assert "MERGE (guest)-[:HAS_RESERVATION]->(reservation)" in cypher
