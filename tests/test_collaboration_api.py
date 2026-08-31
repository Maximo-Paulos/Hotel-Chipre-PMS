from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.services import collaboration as collaboration_service
from app.api import collaboration as collaboration_api


class FakeTicketRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    def ping(self):
        return True

    def setex(self, key: str, _ttl: int, value: str):
        self.values[key] = value
        return True

    def getdel(self, key: str):
        return self.values.pop(key, None)


@pytest.fixture()
def collaboration_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    db.add(HotelConfiguration(id=1, hotel_name="Hotel original"))
    db.add(User(id=11, email="collaboration@example.test", password_hash="not-used", is_active=True, is_verified=True))
    db.add(HotelMembership(hotel_id=1, user_id=11, role="owner", status="active"))
    db.commit()

    context = AuthContext(
        hotel_id=1,
        user_id=11,
        user_email="collaboration@example.test",
        user_role="owner",
        is_verified=True,
    )
    fake_redis = FakeTicketRedis()
    monkeypatch.setattr(collaboration_api, "get_realtime_client", lambda: fake_redis)
    monkeypatch.setattr(collaboration_api, "resolve", lambda *args, **kwargs: True)
    monkeypatch.setattr(collaboration_api, "audit_permission_denied", lambda *args, **kwargs: None)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_auth_context] = lambda: context
    try:
        # Do not enter the TestClient lifespan here: the normal application
        # startup points at the configured PostgreSQL service, while this
        # fixture deliberately uses the isolated pytest session below.
        yield TestClient(app), db, fake_redis
    finally:
        app.dependency_overrides.clear()
        db.rollback()
        db.close()
        engine.dispose()


def test_patch_persists_only_allowlisted_fields_and_returns_revision(collaboration_client):
    client, db, _redis = collaboration_client
    initial = collaboration_service.serialize_resource("settings", db.get(HotelConfiguration, 1))
    response = client.patch(
        "/api/collaboration/resources/settings/1",
        json={
            "base_revision": collaboration_service.resource_revision(initial),
            "changes": {"hotel_name": "Hotel actualizado"},
            "base_values": {"hotel_name": initial["hotel_name"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["resource"]["hotel_name"] == "Hotel actualizado"
    assert db.get(HotelConfiguration, 1).hotel_name == "Hotel actualizado"

    forbidden = client.patch(
        "/api/collaboration/resources/settings/1",
        json={
            "base_revision": response.json()["revision"],
            "changes": {"api_key": "must-not-persist"},
        },
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "COLLABORATION_VALIDATION_FAILED"


def test_patch_accepts_pending_revision_for_a_new_editor(collaboration_client):
    client, db, _redis = collaboration_client
    response = client.patch(
        "/api/collaboration/resources/settings/1",
        json={
            "base_revision": "pending",
            "changes": {"hotel_name": "Primer guardado"},
            "base_values": {"hotel_name": "Hotel original"},
        },
    )

    assert response.status_code == 200
    assert db.get(HotelConfiguration, 1).hotel_name == "Primer guardado"


def test_patch_returns_structured_same_field_conflict(collaboration_client):
    client, db, _redis = collaboration_client
    original = collaboration_service.serialize_resource("settings", db.get(HotelConfiguration, 1))
    original_revision = collaboration_service.resource_revision(original)

    db.get(HotelConfiguration, 1).hotel_name = "Cambio remoto"
    db.commit()

    response = client.patch(
        "/api/collaboration/resources/settings/1",
        json={
            "base_revision": original_revision,
            "changes": {"hotel_name": "Mi cambio"},
            "base_values": {"hotel_name": "Hotel original"},
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "COLLABORATION_CONFLICT"
    assert detail["conflicting_fields"] == ["hotel_name"]
    assert detail["server_resource"]["hotel_name"] == "Cambio remoto"


def test_ticket_is_tenant_bound_and_one_use_for_websocket(collaboration_client):
    client, _db, fake_redis = collaboration_client
    ticket_response = client.post(
        "/api/collaboration/tickets",
        json={"resource_type": "settings", "resource_id": 1},
    )
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["ticket"]

    with client.websocket_connect("/api/collaboration/ws") as websocket:
        websocket.send_json({"ticket": ticket, "hotel_id": 1})
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        websocket.send_json({"type": "draft_patch", "base_revision": "pending", "changes": {"hotel_name": "borrador"}})

    with pytest.raises(Exception):
        with client.websocket_connect("/api/collaboration/ws") as websocket:
            websocket.send_json({"ticket": ticket, "hotel_id": 1})
            websocket.receive_json()

    assert fake_redis.values == {}


def test_ticket_does_not_reveal_a_resource_from_another_hotel(collaboration_client):
    client, _db, _redis = collaboration_client
    response = client.post(
        "/api/collaboration/tickets",
        json={"resource_type": "settings", "resource_id": 2},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Recurso no encontrado"
