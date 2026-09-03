from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.hotel_config import HotelConfiguration


@pytest.fixture
def recovery_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()

    db.execute(
        HotelConfiguration.__table__.insert(),
        [
            {"id": 1, "subscription_active": True},
            {"id": 2, "subscription_active": True},
        ],
    )
    db.commit()

    def override_get_db():
        yield db

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=10,
            user_email="operator@example.test",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_context] = override_auth_context
    client = TestClient(app)
    try:
        yield client, db
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _add_event(
    db: Session,
    *,
    event_id: int,
    hotel_id: int = 1,
    domain: str = "analytics",
    published: bool = True,
):
    db.add(
        DomainEventOutbox(
            id=event_id,
            hotel_id=hotel_id,
            domain=domain,
            event_type="resource.changed",
            payload={"reservation_id": 42, "secret": "must-not-be-returned"},
            occurred_at=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc) if published else None,
        )
    )


def test_recovery_requires_authentication(recovery_client):
    client, _db = recovery_client
    app.dependency_overrides.pop(get_auth_context)

    response = client.get("/api/events/recovery?after_cursor=1")

    assert response.status_code == 401


def test_recovery_collapses_published_and_pending_domains_without_payload(recovery_client):
    client, db = recovery_client
    _add_event(db, event_id=9, domain="settings", published=True)
    _add_event(db, event_id=10, domain="reservations", published=True)
    _add_event(db, event_id=11, domain="reservations", published=False)
    _add_event(db, event_id=12, domain="payments", published=False)
    _add_event(db, event_id=13, hotel_id=2, domain="security", published=True)
    db.commit()

    response = client.get("/api/events/recovery?after_cursor=9")

    assert response.status_code == 200
    assert response.json() == {
        "latest_cursor": 12,
        "domains": ["payments", "reservations"],
        "reset_required": False,
        "has_more": False,
    }
    assert "payload" not in response.text
    assert "must-not-be-returned" not in response.text


@pytest.mark.parametrize("query", ["", "?after_cursor=0"])
def test_missing_or_zero_cursor_requires_full_refetch(recovery_client, query):
    client, db = recovery_client
    _add_event(db, event_id=10, domain="rooms")
    db.commit()

    response = client.get(f"/api/events/recovery{query}")

    assert response.status_code == 200
    assert response.json()["reset_required"] is True
    assert response.json()["latest_cursor"] == 10


def test_stale_cursor_requires_full_refetch(recovery_client):
    client, db = recovery_client
    _add_event(db, event_id=10, domain="rooms")
    db.commit()

    response = client.get("/api/events/recovery?after_cursor=1")

    assert response.status_code == 200
    assert response.json() == {
        "latest_cursor": 10,
        "domains": ["rooms"],
        "reset_required": True,
        "has_more": False,
    }


def test_recovery_is_tenant_scoped(recovery_client):
    client, db = recovery_client
    _add_event(db, event_id=10, hotel_id=2, domain="payments")
    db.commit()

    response = client.get("/api/events/recovery?after_cursor=1")

    assert response.status_code == 200
    assert response.json() == {
        "latest_cursor": 1,
        "domains": [],
        "reset_required": False,
        "has_more": False,
    }


def test_recovery_marks_limit_overflow_for_full_refetch(recovery_client):
    client, db = recovery_client
    for event_id in range(1, 502):
        _add_event(db, event_id=event_id, domain="analytics")
    db.commit()

    response = client.get("/api/events/recovery?after_cursor=0")

    assert response.status_code == 200
    assert response.json() == {
        "latest_cursor": 501,
        "domains": ["analytics"],
        "reset_required": True,
        "has_more": True,
    }
