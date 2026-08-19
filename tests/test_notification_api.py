"""API-level coverage: inbox scoping, push subscription CRUD, preference
CRUD, and owner/co-owner-only daily-report-schedule gating."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import Notification
from app.models.user import User


def _auth(hotel_id: int, role: str, user_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id, user_id=user_id, user_email=f"{role}-{user_id}@example.test",
            user_role=role, is_verified=True, permissions=set(),
        )

    return dependency


def _client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=8301, subscription_active=True),
            HotelConfiguration(id=8302, subscription_active=True),
            User(id=301, email="owner-8301@example.test", password_hash="x", is_verified=True),
            User(id=302, email="receptionist-8301@example.test", password_hash="x", is_verified=True),
            User(id=303, email="owner-8302@example.test", password_hash="x", is_verified=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=8301, user_id=301, role="owner", status="active"),
            HotelMembership(hotel_id=8301, user_id=302, role="receptionist", status="active"),
            HotelMembership(hotel_id=8302, user_id=303, role="owner", status="active"),
        ]
    )
    db.add_all(
        [
            Notification(hotel_id=8301, recipient_user_id=301, event_type="reservation.created", title="A"),
            Notification(hotel_id=8302, recipient_user_id=303, event_type="reservation.created", title="B"),
        ]
    )
    db.commit()

    def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    return TestClient(fastapi_app), db


def test_inbox_is_tenant_and_recipient_scoped():
    client, db = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "owner", 301)
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "A"

    fastapi_app.dependency_overrides[get_auth_context] = _auth(8302, "owner", 303)
    resp2 = client.get("/api/notifications")
    assert [item["title"] for item in resp2.json()["items"]] == ["B"]

    fastapi_app.dependency_overrides.clear()


def test_mark_read_is_scoped_to_recipient():
    client, db = _client()
    notification = db.query(Notification).filter(Notification.hotel_id == 8301).one()

    # A different user in the SAME hotel must not be able to mark someone
    # else's notification read.
    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "receptionist", 302)
    resp = client.post(f"/api/notifications/{notification.id}/read")
    assert resp.status_code == 404

    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "owner", 301)
    resp = client.post(f"/api/notifications/{notification.id}/read")
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    fastapi_app.dependency_overrides.clear()


def test_push_subscription_register_and_unregister():
    client, db = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "owner", 301)
    resp = client.post(
        "/api/notifications/push-subscriptions",
        json={"endpoint": "https://push.example.test/abc", "p256dh": "key1", "auth": "auth1"},
    )
    assert resp.status_code == 201

    resp2 = client.post(
        "/api/notifications/push-subscriptions/unregister",
        json={"endpoint": "https://push.example.test/abc"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["removed"] is True

    fastapi_app.dependency_overrides.clear()


def test_preferences_crud():
    client, db = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "owner", 301)
    resp = client.put(
        "/api/notifications/preferences",
        json={"event_type": "stock.low", "push_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["push_enabled"] is False

    listed = client.get("/api/notifications/preferences")
    assert listed.status_code == 200
    assert any(row["event_type"] == "stock.low" for row in listed.json())

    fastapi_app.dependency_overrides.clear()


def test_daily_report_schedule_is_owner_co_owner_only():
    client, db = _client()

    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "receptionist", 302)
    assert client.get("/api/notifications/daily-report-schedule").status_code == 403
    assert client.put(
        "/api/notifications/daily-report-schedule",
        json={"hour": 7, "recipient_roles": ["owner"], "channels": ["in_app"]},
    ).status_code == 403

    fastapi_app.dependency_overrides[get_auth_context] = _auth(8301, "owner", 301)
    resp = client.put(
        "/api/notifications/daily-report-schedule",
        json={"hour": 8, "recipient_roles": ["owner"], "channels": ["in_app"], "enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["hour"] == 8

    fetched = client.get("/api/notifications/daily-report-schedule")
    assert fetched.status_code == 200
    assert fetched.json()["hour"] == 8

    fastapi_app.dependency_overrides.clear()
