from __future__ import annotations

from datetime import date

from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.daily_rate import DailyRate
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
    # FastAPI >=0.137 wraps included routers in `_IncludedRouter`; `app.routes` is
    # no longer a flat list of `APIRoute`, so we walk it with `iter_route_contexts`
    # (the helper FastAPI itself uses for this purpose, see fastapi/openapi/utils.py).
    paths = {
        context.path
        for context in iter_route_contexts(fastapi_app.routes)
        if isinstance(context.original_route, APIRoute)
    }
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
        # Rate calendar is pricing config -- manager's default matrix does not
        # grant reports:financial:view.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
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


def test_rate_payment_options_only_exposes_enabled_methods():
    client, db, engine = _build_client()
    try:
        _seed_hotel(db, 1, "H1")
        config = db.get(HotelConfiguration, 1)
        config.enable_cash = True
        config.enable_bank_transfer = True
        config.enable_debit_card = False
        config.enable_credit_card = False
        config.enable_mercado_pago = False
        config.enable_paypal = False
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        response = client.get("/api/rates/payment-method-options")

        assert response.status_code == 200, response.text
        assert response.json() == {
            "enable_cash": True,
            "enable_bank_transfer": True,
            "enable_debit_card": False,
            "enable_credit_card": False,
            "enable_mercado_pago": False,
            "enable_paypal": False,
        }
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


def test_legacy_rate_write_endpoints_require_reviewable_drafts():
    client, db, engine = _build_client()
    try:
        category = _seed_hotel(db, 1, "DRAFTS")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        requests = [
            ("post", f"/api/rates/category/{category.id}/daily", {"date": "2026-05-07", "price": 110}),
            ("post", f"/api/rates/category/{category.id}/bulk", {"from_date": "2026-05-07", "to_date": "2026-05-08", "price": 110}),
            ("post", f"/api/rates/category/{category.id}/bulk-field", {"from_date": "2026-05-07", "to_date": "2026-05-08", "field": "price", "mode": "set", "value": 110}),
            ("post", "/api/rates/periods", {"category_id": category.id, "name": "Nueva", "start_date": "2026-05-07", "end_date": "2026-05-08", "price_per_night": 110}),
            ("patch", "/api/rates/periods/1", {"price_per_night": 120}),
            ("delete", "/api/rates/periods/1", None),
            ("post", "/api/rates/periods/1/apply", None),
        ]

        for method, path, body in requests:
            response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
            assert response.status_code == 409, (method, path, response.text)
            assert "rate-change-drafts" in response.json()["detail"]

        assert db.query(DailyRate).filter_by(hotel_id=1, category_id=category.id).count() == 0
        from app.models.daily_rate import PricePeriod

        assert db.query(PricePeriod).filter_by(hotel_id=1, category_id=category.id).count() == 0
    finally:
        _cleanup_client(db, engine)
