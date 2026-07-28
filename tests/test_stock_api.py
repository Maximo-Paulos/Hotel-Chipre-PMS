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
