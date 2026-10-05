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
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.room import Room, RoomCategory
from app.services.permission_service import ROLE_HOUSEKEEPING, create_custom_role


def _override_auth(hotel_id: int, role: str, *, base_role: str | None = None):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=123,
            user_email=f"{role}@example.com",
            user_role=role,
            base_role=base_role,
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
    session.add(Room(
        hotel_id=hotel_id,
        room_number="QA-101",
        floor=1,
        category_id=category.id,
        notes="Guest identity and payment note",
    ))
    session.commit()

    with TestClient(app) as test_client:
        yield test_client, app, hotel_id, category.id, session
    app.dependency_overrides.clear()
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_receptionist_can_list_rooms_without_loading_reservations(client):
    test_client, app, hotel_id, _category_id, db = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        response = test_client.get("/api/rooms/")
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert not any("from reservations" in statement for statement in statements)


def test_receptionist_can_check_room_availability(client):
    test_client, app, hotel_id, category_id, _db = client
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


def test_receptionist_can_list_room_categories(client):
    """GET /api/rooms/categories feeds the category picker on both the
    Reservations page (useCategories -> listCategories) and the Waitlist
    page (listRoomCategories). Both are reachable by receptionist per the
    nav role matrix, so the endpoint must not 403 for that role -- a
    receptionist who cannot list categories cannot create a reservation
    or a waitlist entry, both core front-desk tasks.
    """
    test_client, app, hotel_id, category_id, _db = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

    response = test_client.get("/api/rooms/categories")

    assert response.status_code == 200, response.text
    assert any(cat["id"] == category_id for cat in response.json())


def test_room_category_rates_are_batched_and_keep_daily_period_and_base_precedence(
    client, monkeypatch
):
    test_client, app, hotel_id, base_category_id, db = client
    app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")
    today = date(2026, 10, 5)
    monkeypatch.setattr(rooms_api, "local_today", lambda _timezone: today)

    daily_category = RoomCategory(
        hotel_id=hotel_id,
        name="QA-Daily",
        code="QADAILY",
        base_price_per_night=150,
        max_occupancy=2,
    )
    period_category = RoomCategory(
        hotel_id=hotel_id,
        name="QA-Period",
        code="QAPERIOD",
        base_price_per_night=160,
        max_occupancy=2,
    )
    db.add_all([daily_category, period_category])
    db.flush()
    db.add_all(
        [
            DailyRate(
                hotel_id=hotel_id,
                category_id=daily_category.id,
                date=today,
                price=275,
            ),
            PricePeriod(
                hotel_id=hotel_id,
                category_id=daily_category.id,
                name="QA daily overrides period",
                start_date=today,
                end_date=today,
                price_per_night=240,
                priority=10,
            ),
            PricePeriod(
                hotel_id=hotel_id,
                category_id=period_category.id,
                name="QA low priority",
                start_date=today,
                end_date=today,
                price_per_night=210,
                priority=1,
            ),
            PricePeriod(
                hotel_id=hotel_id,
                category_id=period_category.id,
                name="QA high priority",
                start_date=today,
                end_date=today,
                price_per_night=230,
                priority=2,
            ),
        ]
    )
    db.commit()

    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        response = test_client.get("/api/rooms/categories")
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    by_id = {category["id"]: category for category in response.json()}
    assert by_id[base_category_id]["current_rate"] == 100
    assert by_id[base_category_id]["current_rate_source"] == "category_base"
    assert by_id[daily_category.id]["current_rate"] == 275
    assert by_id[daily_category.id]["current_rate_source"] == "daily_rate"
    assert by_id[period_category.id]["current_rate"] == 230
    assert by_id[period_category.id]["current_rate_source"] == "price_period"
    assert sum("from daily_rates" in statement for statement in statements) == 1
    assert sum("from price_periods" in statement for statement in statements) == 1
    assert not any("from rooms" in statement for statement in statements)


def test_custom_housekeeping_role_receives_safe_room_projection(client):
    test_client, app, hotel_id, _category_id, db = client
    custom = create_custom_role(
        db,
        hotel_id,
        name="Limpieza turno tarde",
        base_role=ROLE_HOUSEKEEPING,
        actor_user_id=None,
    )
    db.commit()
    app.dependency_overrides[get_auth_context] = _override_auth(
        hotel_id,
        custom.code,
        base_role=ROLE_HOUSEKEEPING,
    )

    response = test_client.get("/api/rooms/")

    assert response.status_code == 200, response.text
    assert response.json()[0]["room_number"] == "QA-101"
    assert "notes" not in response.json()[0]
    assert "Guest identity and payment note" not in response.text
