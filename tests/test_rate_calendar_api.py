from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.rate_calendar import RateCalendarResponse


def _override_auth(hotel_id: int, role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=1,
            user_email="owner@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _build_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _cleanup_client(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _seed_hotel(db, hotel_id: int, suffix: str) -> RoomCategory:
    db.add(
        HotelConfiguration(
            id=hotel_id,
            owner_email=f"owner-{suffix}@test.com",
            subscription_active=True,
            default_currency="ARS",
        )
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {suffix}",
        code=f"STD_{suffix}",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    db.add(
        Room(
            hotel_id=hotel_id,
            room_number=f"{suffix}-101",
            floor=1,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
    )
    db.commit()
    return category


def test_endpoint_is_registered():
    paths = {route.path for route in fastapi_app.routes}
    assert "/api/rate-calendar/daily" in paths


def test_endpoint_requires_authentication():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "H1")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category.id, "date_from": "2026-05-01", "date_to": "2026-05-01"},
        )
        assert response.status_code == 401
    finally:
        _cleanup_client(db, engine)


def test_endpoint_rejects_forbidden_role():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category.id, "date_from": "2026-05-01", "date_to": "2026-05-01"},
        )
        assert response.status_code == 403
    finally:
        _cleanup_client(db, engine)


def test_unknown_category_returns_404():
    client, db, engine = _build_client()
    try:
        _seed_hotel(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": 9999, "date_from": "2026-05-01", "date_to": "2026-05-01"},
        )
        assert response.status_code == 404
    finally:
        _cleanup_client(db, engine)


def test_date_to_before_date_from_returns_422():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category.id, "date_from": "2026-05-02", "date_to": "2026-05-01"},
        )
        assert response.status_code == 422
    finally:
        _cleanup_client(db, engine)


def test_range_longer_than_366_days_returns_422():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category.id, "date_from": "2026-01-01", "date_to": "2027-01-03"},
        )
        assert response.status_code == 422
    finally:
        _cleanup_client(db, engine)


def test_success_returns_expected_schema():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category.id, "date_from": "2026-05-01", "date_to": "2026-05-02"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        parsed = RateCalendarResponse.model_validate(payload)
        assert parsed.meta.category_id == category.id
        assert len(parsed.days) == 2
        assert [channel.provider_code for channel in parsed.days[0].channels] == ["direct", "booking", "expedia"]
    finally:
        _cleanup_client(db, engine)


def test_multi_hotel_isolation_returns_404_for_foreign_category():
    client, db, engine = _build_client()
    try:
        _seed_hotel(db, 1, "H1")
        category_h2 = _seed_hotel(db, 2, "H2")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        response = client.get(
            "/api/rate-calendar/daily",
            params={"category_id": category_h2.id, "date_from": "2026-05-01", "date_to": "2026-05-01"},
        )
        assert response.status_code == 404
    finally:
        _cleanup_client(db, engine)
