"""
API tests for /api/connections/{provider}/connect.
Focus on JSON serialization of credentials/settings and idempotent upsert.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.api import connections
from app.database import Base, get_db
from app.models.connection import Connection


@pytest.fixture
def api_client():
    """Provide a TestClient wired to an in-memory database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Ensure models are registered before creating tables
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.dependency_overrides[get_db] = override_get_db
    app.include_router(connections.router)

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_connect_serializes_json_objects(api_client):
    client, SessionLocal = api_client
    payload = {
        "credentials": {"apiKey": "abc123", "secret": "shh"},
        "settings": {"hotel_id": 99, "sandbox": True},
    }

    response = client.post("/api/connections/booking/connect", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["provider"] == "booking"
    assert data["status"] == "connected"
    assert isinstance(data["credentials"], dict)
    assert isinstance(data["settings"], dict)
    assert data["credentials"]["apiKey"] == "abc123"
    assert data["settings"]["hotel_id"] == 99

    db = SessionLocal()
    try:
        row = db.query(Connection).filter_by(provider="booking").first()
        assert row is not None
        assert row.credentials["secret"] == "shh"
        assert row.settings["sandbox"] is True
    finally:
        db.close()


def test_connect_is_idempotent_per_provider(api_client):
    client, SessionLocal = api_client

    first = client.post("/api/connections/expedia/connect", json={"credentials": {"token": "v1"}})
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = client.post(
        "/api/connections/expedia/connect",
        json={"credentials": {"token": "v2"}, "settings": {"hotel_id": 7}},
    )
    assert second.status_code == 200
    data = second.json()
    assert data["id"] == first_id
    assert data["credentials"]["token"] == "v2"
    assert data["settings"]["hotel_id"] == 7

    db = SessionLocal()
    try:
        row = db.query(Connection).filter_by(provider="expedia").first()
        assert row.credentials["token"] == "v2"
    finally:
        db.close()


def test_connect_rejects_non_object_credentials(api_client):
    client, _ = api_client
    resp = client.post("/api/connections/foo/connect", json={"credentials": "abc"})
    assert resp.status_code == 422
