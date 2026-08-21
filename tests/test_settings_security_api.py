"""Security settings API is tenant-scoped, redacted and revokes real JWTs."""

import csv
from datetime import datetime, timezone
from io import StringIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models.analytics import HotelAuditEvent
from app.models.audit_log import AuditActionEnum, AuditLog
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


def test_unified_audit_timeline_combines_sources_orders_redacts_and_isolates_tenant(security_client):
    client, db, owner, _manager, token_for = security_client
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            AuditLog(
                hotel_id=1,
                table_name="rooms",
                record_id=7,
                action=AuditActionEnum.UPDATE,
                actor_user_id=owner.id,
                created_at=now.replace(microsecond=300000),
                payload_after=(
                    '{"status":"clean", "password_hash":"hash-must-not-leak", '
                    '"access_token":"token-must-not-leak", "totp_code":"654321", '
                    '"recovery_codes":["recovery-must-not-leak"]}'
                ),
            ),
            HotelAuditEvent(
                hotel_id=1,
                user_id=owner.id,
                action_code="reservation.created",
                entity_type="reservation",
                entity_id=42,
                created_at=now.replace(microsecond=400000),
                after_json=(
                    '{"status":"confirmed", "password_hash":"hash-business-secret", '
                    '"api_token":"business-token-secret", "mfa_code":"112233"}'
                ),
            ),
            SecurityAuditLog(
                hotel_id=1,
                user_id=owner.id,
                action="auth.login.success",
                resource_type="user_session",
                resource_id="session-secret-id",
                details=(
                    '{"provider":"password", "token":"security-token-secret", '
                    '"recovery_code":"security-recovery-secret", "email":"secret@example.test"}'
                ),
                created_at=now.replace(microsecond=500000),
            ),
            AuditLog(
                hotel_id=2,
                table_name="rooms",
                record_id=99,
                action=AuditActionEnum.DELETE,
                actor_user_id=owner.id,
                created_at=now.replace(microsecond=600000),
                payload_after='{"marker":"other-hotel-row"}',
            ),
            HotelAuditEvent(
                hotel_id=2,
                user_id=owner.id,
                action_code="other.hotel.business",
                entity_type="reservation",
                entity_id=100,
                created_at=now.replace(microsecond=700000),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/settings/security/audit-timeline",
        params={"limit": 10},
        headers=_headers(token_for(owner, "owner")),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hotel_id"] == 1
    assert body["total"] == 4
    assert body["has_more"] is False
    assert [item["created_at"] for item in body["items"]] == sorted(
        (item["created_at"] for item in body["items"]), reverse=True
    )
    new_events = [
        item
        for item in body["items"]
        if item["action"] in {"auth.login.success", "reservation.created", "update"}
    ]
    assert [item["source"] for item in new_events] == [
        "security_event",
        "business_event",
        "row_mutation",
    ]
    assert {item["action"] for item in body["items"]} == {
        "permission.denied",
        "auth.login.success",
        "reservation.created",
        "update",
    }
    assert "other.hotel.business" not in response.text
    assert "other-hotel-row" not in response.text
    for secret in (
        "hash-must-not-leak",
        "token-must-not-leak",
        "654321",
        "recovery-must-not-leak",
        "hash-business-secret",
        "business-token-secret",
        "112233",
        "security-token-secret",
        "security-recovery-secret",
        "session-secret-id",
        "secret@example.test",
    ):
        assert secret not in response.text
    for sensitive_key in ("password_hash", "access_token", "totp_code", "recovery_codes", "mfa_code"):
        assert sensitive_key not in response.text

    page = client.get(
        "/api/settings/security/audit-timeline",
        params={"limit": 2, "offset": 1},
        headers=_headers(token_for(owner, "owner")),
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 4
    assert page.json()["offset"] == 1
    assert len(page.json()["items"]) == 2
    assert page.json()["has_more"] is True


def test_unified_audit_timeline_supports_inclusive_date_filters_and_role_guard(security_client):
    client, db, owner, manager, token_for = security_client
    db.add(
        AuditLog(
            hotel_id=1,
            table_name="rooms",
            record_id=8,
            action=AuditActionEnum.CREATE,
            actor_user_id=owner.id,
            created_at=datetime(2026, 8, 19, 12, tzinfo=timezone.utc),
        )
    )
    db.commit()

    filtered = client.get(
        "/api/settings/security/audit-timeline",
        params={"from": "2026-08-19", "to": "2026-08-19"},
        headers=_headers(token_for(owner, "owner")),
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["action"] == "create"

    invalid_range = client.get(
        "/api/settings/security/audit-timeline",
        params={"from": "2026-08-20", "to": "2026-08-19"},
        headers=_headers(token_for(owner, "owner")),
    )
    assert invalid_range.status_code == 422

    forbidden = client.get(
        "/api/settings/security/audit-timeline",
        headers=_headers(token_for(manager, "manager")),
    )
    assert forbidden.status_code == 403


def test_unified_audit_timeline_csv_export_filters_and_redacts(security_client):
    client, db, owner, _manager, token_for = security_client
    db.add_all(
        [
            AuditLog(
                hotel_id=1,
                table_name="rooms",
                record_id=9,
                action=AuditActionEnum.UPDATE,
                actor_user_id=owner.id,
                created_at=datetime(2026, 8, 19, 12, tzinfo=timezone.utc),
                payload_after=(
                    '{"status":"clean", "password_hash":"csv-hash-secret", '
                    '"access_token":"csv-token-secret", "visible":"ok"}'
                ),
            ),
            SecurityAuditLog(
                hotel_id=1,
                user_id=owner.id,
                action="auth.login.success",
                resource_type="user_session",
                resource_id="csv-session-secret",
                details=(
                    '{"token":"csv-security-token", "email":"csv-secret@example.test", '
                    '"provider":"password"}'
                ),
                created_at=datetime(2026, 8, 19, 13, tzinfo=timezone.utc),
            ),
            AuditLog(
                hotel_id=1,
                table_name="rooms",
                record_id=10,
                action=AuditActionEnum.CREATE,
                actor_user_id=owner.id,
                created_at=datetime(2026, 8, 20, 12, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/settings/security/audit-timeline/export",
        params={"from": "2026-08-19", "to": "2026-08-19"},
        headers=_headers(token_for(owner, "owner")),
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="audit-timeline-1.csv"'
    rows = list(csv.DictReader(StringIO(response.text)))
    assert [row["action"] for row in rows] == ["auth.login.success", "update"]
    assert set(rows[0]) == {
        "source",
        "action",
        "actor_user_id",
        "created_at",
        "summary",
        "details",
    }
    assert "2026-08-20" not in response.text
    for secret in (
        "csv-hash-secret",
        "csv-token-secret",
        "csv-security-token",
        "csv-secret@example.test",
        "csv-session-secret",
        "password_hash",
        "access_token",
    ):
        assert secret not in response.text
    assert "[REDACTED]" in response.text

    forbidden = client.get(
        "/api/settings/security/audit-timeline/export",
        headers=_headers(token_for(_manager, "manager")),
    )
    assert forbidden.status_code == 403


def test_unified_audit_timeline_csv_export_caps_rows(security_client):
    client, db, owner, _manager, token_for = security_client
    db.add_all(
        [
            SecurityAuditLog(
                hotel_id=1,
                user_id=owner.id,
                action=f"bulk.event.{index}",
                resource_type="permission",
                resource_id=str(index),
                created_at=datetime(2026, 8, 19, tzinfo=timezone.utc).replace(microsecond=index),
            )
            for index in range(5001)
        ]
    )
    db.commit()

    response = client.get(
        "/api/settings/security/audit-timeline/export",
        params={"from": "2026-08-19", "to": "2026-08-19"},
        headers=_headers(token_for(owner, "owner")),
    )

    assert response.status_code == 200, response.text
    rows = list(csv.DictReader(StringIO(response.text)))
    assert len(rows) == 5000
    assert rows[0]["action"] == "bulk.event.5000"


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
