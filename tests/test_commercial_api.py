from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.room import RoomCategory


def _get_db_override_target():
    return get_db


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


def _seed_hotel(db, hotel_id: int, suffix: str) -> list[RoomCategory]:
    db.add(
        HotelConfiguration(
            id=hotel_id,
            owner_email=f"owner-{suffix}@test.com",
            subscription_active=True,
        )
    )
    categories = [
        RoomCategory(
            hotel_id=hotel_id,
            name=f"Standard {suffix}",
            code=f"STD_{suffix}",
            base_price_per_night=100.0,
            max_occupancy=2,
        ),
        RoomCategory(
            hotel_id=hotel_id,
            name=f"Superior {suffix}",
            code=f"SUP_{suffix}",
            base_price_per_night=150.0,
            max_occupancy=3,
        ),
    ]
    db.add_all(categories)
    db.flush()
    return categories


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

    fastapi_app.dependency_overrides[_get_db_override_target()] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _cleanup_client(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_owner_can_create_and_update_commercial_configuration():
    client, db, engine = _build_client()
    try:
        categories = _seed_hotel(db, 1, "H1")
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        product_resp = client.post(
            "/api/commercial/products",
            json={
                "primary_room_category_id": categories[0].id,
                "code": "DBL_SHARED",
                "name": "Doble compartida",
                "min_occupancy": 1,
                "max_occupancy": 2,
                "compatibilities": [
                    {
                        "room_category_id": categories[0].id,
                        "compatibility_kind": "exact",
                        "priority": 1,
                        "allows_auto_assignment": True,
                    }
                ],
            },
        )
        assert product_resp.status_code == 201, product_resp.text
        product_body = product_resp.json()
        assert product_body["code"] == "DBL_SHARED"
        assert len(product_body["compatibilities"]) == 1

        product_id = product_body["id"]
        product_patch_resp = client.patch(
            f"/api/commercial/products/{product_id}",
            json={
                "name": "Doble compartida premium",
                "compatibilities": [
                    {
                        "room_category_id": categories[1].id,
                        "compatibility_kind": "upgrade",
                        "priority": 10,
                        "allows_auto_assignment": True,
                    }
                ],
            },
        )
        assert product_patch_resp.status_code == 200, product_patch_resp.text
        assert product_patch_resp.json()["compatibilities"][0]["room_category_id"] == categories[1].id

        rate_plan_resp = client.post(
            "/api/commercial/rate-plans",
            json={
                "sellable_product_id": product_id,
                "code": "FLEX",
                "name": "Flexible",
                "currency_code": "ARS",
                "prices": [
                    {
                        "sales_channel_code": "booking",
                        "occupancy": 2,
                        "currency_code": "ARS",
                        "base_amount": 50000.0,
                        "tax_inclusive": False,
                    }
                ],
            },
        )
        assert rate_plan_resp.status_code == 201, rate_plan_resp.text
        assert rate_plan_resp.json()["prices"][0]["base_amount"] == 50000.0

        tax_policy_resp = client.post(
            "/api/commercial/tax-policies",
            json={
                "code": "ARG",
                "name": "Argentina",
                "taxes_included": False,
                "apply_vat_by_default": False,
                "foreign_guest_tax_exempt": True,
                "rules": [
                    {
                        "channel_code": "booking",
                        "guest_scope": "local",
                        "tax_code": "VAT",
                        "tax_name": "IVA",
                        "tax_type": "percentage",
                        "amount": 21.0,
                    }
                ],
            },
        )
        assert tax_policy_resp.status_code == 201, tax_policy_resp.text
        assert tax_policy_resp.json()["rules"][0]["tax_code"] == "VAT"

        fx_policy_resp = client.post(
            "/api/commercial/fx-policies",
            json={
                "code": "OFFICIAL",
                "name": "Oficial venta",
                "base_currency": "ARS",
                "preferred_source": "official",
                "preferred_side": "sell",
                "spread_pct": 2.5,
            },
        )
        assert fx_policy_resp.status_code == 201, fx_policy_resp.text
        assert fx_policy_resp.json()["preferred_side"] == "sell"
    finally:
        _cleanup_client(db, engine)


def test_manager_can_read_but_cannot_mutate_commercial_configuration():
    client, db, engine = _build_client()
    try:
        categories = _seed_hotel(db, 1, "H1")
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        create_resp = client.post(
            "/api/commercial/products",
            json={
                "primary_room_category_id": categories[0].id,
                "code": "DBL_SHARED",
                "name": "Doble compartida",
                "min_occupancy": 1,
                "max_occupancy": 2,
                "compatibilities": [],
            },
        )
        assert create_resp.status_code == 201, create_resp.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        list_resp = client.get("/api/commercial/products")
        assert list_resp.status_code == 200, list_resp.text
        assert [item["code"] for item in list_resp.json()] == ["DBL_SHARED"]

        denied_resp = client.post(
            "/api/commercial/fx-policies",
            json={
                "code": "OFFICIAL",
                "name": "Oficial",
                "base_currency": "ARS",
                "preferred_source": "official",
                "preferred_side": "sell",
                "spread_pct": 0.0,
            },
        )
        assert denied_resp.status_code == 403, denied_resp.text
    finally:
        _cleanup_client(db, engine)


def test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories():
    client, db, engine = _build_client()
    try:
        categories_h1 = _seed_hotel(db, 1, "H1")
        categories_h2 = _seed_hotel(db, 2, "H2")
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        invalid_resp = client.post(
            "/api/commercial/products",
            json={
                "primary_room_category_id": categories_h2[0].id,
                "code": "INVALID",
                "name": "Invalido",
                "min_occupancy": 1,
                "max_occupancy": 2,
                "compatibilities": [],
            },
        )
        assert invalid_resp.status_code == 400, invalid_resp.text

        valid_h1_resp = client.post(
            "/api/commercial/products",
            json={
                "primary_room_category_id": categories_h1[0].id,
                "code": "H1-PROD",
                "name": "Producto H1",
                "min_occupancy": 1,
                "max_occupancy": 2,
                "compatibilities": [],
            },
        )
        assert valid_h1_resp.status_code == 201, valid_h1_resp.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        valid_h2_resp = client.post(
            "/api/commercial/products",
            json={
                "primary_room_category_id": categories_h2[0].id,
                "code": "H2-PROD",
                "name": "Producto H2",
                "min_occupancy": 1,
                "max_occupancy": 2,
                "compatibilities": [],
            },
        )
        assert valid_h2_resp.status_code == 201, valid_h2_resp.text

        list_h2_resp = client.get("/api/commercial/products")
        assert list_h2_resp.status_code == 200, list_h2_resp.text
        assert [item["code"] for item in list_h2_resp.json()] == ["H2-PROD"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        list_h1_resp = client.get("/api/commercial/products")
        assert list_h1_resp.status_code == 200, list_h1_resp.text
        assert [item["code"] for item in list_h1_resp.json()] == ["H1-PROD"]
    finally:
        _cleanup_client(db, engine)
