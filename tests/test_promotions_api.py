from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.daily_rate import DailyRate
from app.models.hotel_config import HotelConfiguration
from app.models.room import RoomCategory


def _override_auth(hotel_id: int, role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id, user_id=1, user_email="owner@test.com",
            user_role=role, is_verified=True, permissions=set(),
        )

    return dependency


def _build_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _cleanup(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_promotion_crud_lifecycle_and_versioning():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=201, subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(201)

        create_resp = client.post(
            "/api/promotions",
            json={
                "code": "EARLY_BIRD", "name": "Early bird", "benefit_type": "percentage",
                "benefit_value": "15", "conditions": {},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        promo = create_resp.json()
        assert promo["version"] == 1

        list_resp = client.get("/api/promotions")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        update_resp = client.patch(f"/api/promotions/{promo['id']}", json={"benefit_value": "20"})
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["id"] != promo["id"]
        assert updated["version"] == 2

        # The original version is no longer in the default (active-only) listing.
        list_resp2 = client.get("/api/promotions")
        assert [row["id"] for row in list_resp2.json()] == [updated["id"]]

        deactivate_resp = client.delete(f"/api/promotions/{updated['id']}")
        assert deactivate_resp.status_code == 200
        assert deactivate_resp.json()["is_active"] is False

        reactivate_resp = client.post(f"/api/promotions/{updated['id']}/reactivate")
        assert reactivate_resp.status_code == 200
        assert reactivate_resp.json()["is_active"] is True
    finally:
        _cleanup(db, engine)


def test_promotions_are_tenant_isolated_across_hotels():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=202, subscription_active=True))
        db.add(HotelConfiguration(id=203, subscription_active=True))
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(202)
        create_resp = client.post(
            "/api/promotions",
            json={"code": "X", "name": "Hotel 202 promo", "benefit_type": "fixed", "benefit_value": "5", "conditions": {}},
        )
        assert create_resp.status_code == 201
        promo_id = create_resp.json()["id"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(203)
        # Same code is allowed in a different hotel.
        other_create = client.post(
            "/api/promotions",
            json={"code": "X", "name": "Hotel 203 promo", "benefit_type": "fixed", "benefit_value": "9", "conditions": {}},
        )
        assert other_create.status_code == 201

        get_resp = client.get(f"/api/promotions/{promo_id}")
        assert get_resp.status_code == 404
    finally:
        _cleanup(db, engine)


def test_simulate_endpoint_returns_full_breakdown_without_persisting():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=204, subscription_active=True))
        category = RoomCategory(hotel_id=204, name="Std", code="STD204", base_price_per_night=100, max_occupancy=2)
        db.add(category)
        db.flush()
        db.add(DailyRate(hotel_id=204, category_id=category.id, date=date(2026, 7, 1), price=100.0))
        db.add(DailyRate(hotel_id=204, category_id=category.id, date=date(2026, 7, 2), price=100.0))
        db.commit()
        category_id = category.id

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(204)
        client.post(
            "/api/promotions",
            json={
                "code": "SIM_PROMO", "name": "Sim promo", "benefit_type": "percentage", "benefit_value": "10",
                "conditions": {"category_id": category_id},
            },
        )

        response = client.post(
            "/api/promotions/simulate",
            json={
                "category_id": category_id,
                "check_in_date": "2026-07-01",
                "check_out_date": "2026-07-03",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["subtotal_amount"] == "180.00"
        assert len(body["promotions_applied"]) == 2

        # Nothing was persisted -- no reservation, and re-listing promotions is unaffected.
        promo_list = client.get("/api/promotions")
        assert len(promo_list.json()) == 1
    finally:
        _cleanup(db, engine)
