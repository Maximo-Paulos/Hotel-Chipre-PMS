"""Security settings API is tenant-scoped, redacted and revokes real JWTs."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.security import create_access_token, hash_password


@pytest.fixture
def security_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    owner = User(
        email="owner-security@example.test",
        password_hash=hash_password("Demo123!pass"),
        role="owner",
        is_verified=True,
        is_active=True,
        token_version=0,
        last_login=datetime.now(timezone.utc),
    )
    manager = User(
        email="manager-security@example.test",
        password_hash=hash_password("Demo123!pass"),
        role="manager",
        is_verified=True,
        is_active=True,
    )
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="One", subscription_active=True),
            HotelConfiguration(id=2, hotel_name="Two", subscription_active=True),
            owner,
            manager,
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=owner.id, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=manager.id, role="manager", status="invited"),
        ]
    )
    db.add_all(
        [
            SecurityAuditLog(
                hotel_id=1,
                user_id=owner.id,
                action="permission.denied",
                resource_type="permission",
                resource_id="guest:export",
                details='{"email":"secret@example.test","token":"never-return"}',
            ),
            SecurityAuditLog(
                hotel_id=2,
                user_id=None,
                action="other-hotel.event",
                resource_type="secret",
                resource_id="do-not-leak",
                details="cross tenant",
            ),
        ]
    )
    db.commit()

    def token_for(user: User, role: str, hotel_id: int = 1) -> str:
        return create_access_token(
            user.id,
            extra={
                "email": user.email,
                "role": role,
                "verified": True,
                "hotel_id": hotel_id,
                "hotel_ids": [hotel_id],
                "token_version": user.token_version or 0,
            },
        )

    client = TestClient(app)
    try:
        yield client, db, owner, manager, token_for
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Hotel-Id": "1"}


def test_security_overview_and_events_are_redacted_and_tenant_scoped(security_client):
    client, _db, owner, _manager, token_for = security_client
    headers = _headers(token_for(owner, "owner"))

    overview = client.get("/api/settings/security/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["active_members"] == 1
    assert overview.json()["pending_invitations"] == 1
    assert overview.json()["permission_denials_24h"] == 1
    assert overview.json()["session_timeout_minutes"] > 0

    events = client.get("/api/settings/security/events", params={"limit": 100}, headers=headers)
    assert events.status_code == 200, events.text
    body = events.json()
    assert [event["action"] for event in body["events"]] == ["permission.denied"]
    assert "details" not in body["events"][0]
    assert "secret@example.test" not in events.text
    assert "other-hotel.event" not in events.text
    assert client.get("/api/settings/security/events", params={"limit": 101}, headers=headers).status_code == 422


def test_manager_cannot_read_security_settings(security_client):
    client, _db, _owner, manager, token_for = security_client

    response = client.get(
        "/api/settings/security/overview",
        headers=_headers(token_for(manager, "manager")),
    )

    assert response.status_code == 403


def test_revoke_all_invalidates_the_callers_previous_token(security_client):
    client, db, owner, _manager, token_for = security_client
    old_token = token_for(owner, "owner")

    revoked = client.post("/api/settings/security/revoke-all", headers=_headers(old_token))

    assert revoked.status_code == 200, revoked.text
    assert revoked.json() == {
        "revoked": True,
        "user_id": owner.id,
        "token_version": 1,
        "reauthentication_required": True,
    }
    db.refresh(owner)
    assert owner.token_version == 1
    assert client.get("/api/auth/me", headers=_headers(old_token)).status_code == 401
