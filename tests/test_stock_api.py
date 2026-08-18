"""API-level coverage for stock items: delete-then-recreate (owner-reported
bug), unit_cost and tenant isolation, following the same harness pattern as
tests/test_laundry_vendor_api.py.
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration


def _override_auth(hotel_id: int, role: str, user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.flush()
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    client = TestClient(fastapi_app)
    return client, db, engine


def _teardown(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _second_hotel(db):
    db.add(HotelConfiguration(id=2, subscription_active=True))
    db.flush()
    db.commit()


def test_owner_can_delete_item_and_recreate_it_with_the_same_name():
    client, db, engine = _client_with_db()
    try:
        created = client.post("/api/stock/items", json={"name": "Detergente", "unit": "unidad"})
        assert created.status_code == 201
        item_id = created.json()["id"]

        deleted = client.delete(f"/api/stock/items/{item_id}")
        assert deleted.status_code == 204

        recreated = client.post("/api/stock/items", json={"name": "Detergente", "unit": "unidad"})
        assert recreated.status_code == 201
        assert recreated.json()["id"] != item_id

        # The old id is gone from the list, only the replacement remains.
        listed = client.get("/api/stock/items")
        assert [row["id"] for row in listed.json()] == [recreated.json()["id"]]
    finally:
        _teardown(db, engine)


def test_duplicate_active_name_returns_clean_409_not_a_500():
    client, db, engine = _client_with_db()
    try:
        first = client.post("/api/stock/items", json={"name": "Jabon", "unit": "unidad"})
        assert first.status_code == 201

        duplicate = client.post("/api/stock/items", json={"name": "Jabon", "unit": "unidad"})
        assert duplicate.status_code == 409
    finally:
        _teardown(db, engine)


def test_stock_item_unit_cost_is_exposed_on_create_and_update():
    client, db, engine = _client_with_db()
    try:
        created = client.post(
            "/api/stock/items", json={"name": "Bolsas chicas", "unit": "unidad", "unit_cost": "12.50"}
        )
        assert created.status_code == 201
        assert created.json()["unit_cost"] == "12.50"

        no_cost = client.post("/api/stock/items", json={"name": "Jabon", "unit": "unidad"})
        assert no_cost.json()["unit_cost"] is None

        updated = client.patch(f"/api/stock/items/{created.json()['id']}", json={"unit_cost": "15.00"})
        assert updated.status_code == 200
        assert updated.json()["unit_cost"] == "15.00"
    finally:
        _teardown(db, engine)


def test_stock_item_full_edit_updates_name_sku_unit_and_min_quantity():
    """Owner: "editar el producto por las dudas" -- PATCH already accepted
    every field (StockItemUpdate), the frontend just never sent them. This
    guards the API contract the new full-edit modal (StockPage.tsx) relies on."""
    client, db, engine = _client_with_db()
    try:
        created = client.post(
            "/api/stock/items",
            json={"name": "Sabanas", "sku": "SAB-1", "unit": "unidad", "min_quantity": "5"},
        )
        assert created.status_code == 201
        item_id = created.json()["id"]

        updated = client.patch(
            f"/api/stock/items/{item_id}",
            json={"name": "Sabanas King", "sku": "SAB-1-K", "unit": "juego", "min_quantity": "2"},
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["name"] == "Sabanas King"
        assert body["sku"] == "SAB-1-K"
        assert body["unit"] == "juego"
        assert body["min_quantity"] == "2.00"

        listed = client.get("/api/stock/items")
        assert listed.json()[0]["name"] == "Sabanas King"
    finally:
        _teardown(db, engine)


def test_movement_idempotency_key_header_dedupes_a_retried_request():
    """Same convention as POST /api/payment-links: a client resending the
    same POST (e.g. after a timeout) with the same Idempotency-Key header
    gets back the original movement instead of a duplicate."""
    client, db, engine = _client_with_db()
    try:
        item = client.post("/api/stock/items", json={"name": "Sabanas", "unit": "unidad"}).json()

        headers = {"Idempotency-Key": "retry-key-001"}
        first = client.post(
            "/api/stock/movements",
            json={"item_id": item["id"], "movement_type": "in", "quantity": "10.00"},
            headers=headers,
        )
        assert first.status_code == 201
        assert first.json()["idempotency_key"] == "retry-key-001"

        retried = client.post(
            "/api/stock/movements",
            json={"item_id": item["id"], "movement_type": "in", "quantity": "10.00"},
            headers=headers,
        )
        assert retried.status_code == 201
        assert retried.json()["id"] == first.json()["id"]

        history = client.get(f"/api/stock/movements?item_id={item['id']}")
        assert len(history.json()) == 1
    finally:
        _teardown(db, engine)


def test_stock_summary_is_hotel_scoped_and_requires_stock_read_permission():
    client, db, engine = _client_with_db()
    try:
        _second_hotel(db)
        item = client.post("/api/stock/items", json={"name": "Sabanas", "unit": "unidad"}).json()
        client.post(
            "/api/stock/movements", json={"item_id": item["id"], "movement_type": "in", "quantity": "8.00"}
        )

        summary = client.get("/api/stock/summary")
        assert summary.status_code == 200
        assert len(summary.json()) == 1
        assert summary.json()[0]["item"]["id"] == item["id"]
        assert summary.json()[0]["current_quantity"] == "8.00"

        # A different hotel's summary must never see hotel 1's item/balance.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        other_hotel_summary = client.get("/api/stock/summary")
        assert other_hotel_summary.json() == []

        # A role without stock:read (e.g. receptionist) is denied, no mutation risk here (read-only route).
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        denied = client.get("/api/stock/summary")
        assert denied.status_code == 403
    finally:
        _teardown(db, engine)
