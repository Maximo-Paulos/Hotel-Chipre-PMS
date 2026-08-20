from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.temporary_action_grant import (
    TemporaryActionGrant,
    TemporaryActionGrantStatusEnum,
)
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.services.mfa_service import MFA_ACTIVE, encrypt_totp_secret
from app.services.temporary_action_grant_service import (
    TemporaryGrantActor,
    consume_grant,
    revoke_grant,
)


@pytest.fixture
def temporary_grant_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    db.add(HotelConfiguration(id=1, subscription_active=True))
    users = [
        User(id=1, email="requester@example.com", password_hash="unused", is_verified=True),
        User(id=2, email="owner@example.com", password_hash="unused", is_verified=True),
        User(id=3, email="manager@example.com", password_hash="unused", is_verified=True),
        User(id=4, email="other@example.com", password_hash="unused", is_verified=True),
        User(id=5, email="owner-without-mfa@example.com", password_hash="unused", is_verified=True),
    ]
    db.add_all(users)
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=1, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=2, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=3, role="manager", status="active"),
            HotelMembership(hotel_id=1, user_id=4, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=5, role="owner", status="active"),
        ]
    )
    mfa_secret = pyotp.random_base32()
    db.add(
        UserMfaSecret(
            user_id=2,
            encrypted_secret=encrypt_totp_secret(mfa_secret),
            status=MFA_ACTIVE,
        )
    )
    db.commit()

    def override_get_db():
        yield db

    def override_auth(user_id: int, role: str):
        def dependency():
            return AuthContext(
                hotel_id=1,
                user_id=user_id,
                user_email=f"user{user_id}@example.com",
                user_role=role,
                is_verified=True,
                permissions=set(),
            )

        return dependency

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(1, "receptionist")
    client = TestClient(fastapi_app)
    try:
        yield client, db, mfa_secret, override_auth
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _request(client: TestClient):
    response = client.post(
        "/api/permissions/temporary-grants/request",
        json={
            "permission_code": "reservation:manual_rate",
            "resource_type": "reservation",
            "resource_id": 123,
            "reason": "Autorizacion puntual para corregir la tarifa acordada",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(client: TestClient, override_auth, db: Session, mfa_secret: str, grant_id: int):
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    response = client.post(
        f"/api/permissions/temporary-grants/{grant_id}/approve",
        json={"totp_code": pyotp.TOTP(mfa_secret).now()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_request_approve_consume_and_double_consume_are_single_use(
    temporary_grant_client,
):
    client, db, mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    assert requested["status"] == "pending"
    assert requested["permission_code"] == "reservation:manual_rate"
    assert requested["resource_id"] == "123"

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    pending = client.get("/api/permissions/temporary-grants/pending")
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()["grants"]] == [requested["id"]]

    approved = _approve(client, override_auth, db, mfa_secret, requested["id"])
    token = approved["token"]
    assert token
    assert "token_hash" not in approved["grant"]
    assert approved["grant"]["status"] == "approved"

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(1, "receptionist")
    consumed = client.post("/api/permissions/temporary-grants/consume", json={"token": token})
    assert consumed.status_code == 200
    assert consumed.json() == {"consumed": True}

    consumed_again = client.post("/api/permissions/temporary-grants/consume", json={"token": token})
    assert consumed_again.status_code == 403
    grant = db.get(TemporaryActionGrant, requested["id"])
    assert grant.status == TemporaryActionGrantStatusEnum.USED


def test_consume_rejects_a_different_requester(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    approved = _approve(client, override_auth, db, mfa_secret, requested["id"])

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(4, "receptionist")
    response = client.post(
        "/api/permissions/temporary-grants/consume",
        json={"token": approved["token"]},
    )
    assert response.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


def test_non_approver_role_cannot_approve(temporary_grant_client):
    client, _db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    response = client.post(
        f"/api/permissions/temporary-grants/{requested['id']}/approve",
        json={"totp_code": "000000"},
    )
    assert response.status_code == 403


def test_deny_does_not_populate_approver_field(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    response = client.post(f"/api/permissions/temporary-grants/{requested['id']}/deny")
    assert response.status_code == 200
    assert response.json()["status"] == "denied"
    grant = db.get(TemporaryActionGrant, requested["id"])
    assert grant.approver_user_id is None


def test_service_can_revoke_an_approved_grant(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    approved = _approve(client, override_auth, db, mfa_secret, requested["id"])
    assert approved["grant"]["status"] == "approved"
    revoked = revoke_grant(db, requested["id"], TemporaryGrantActor(user_id=2, hotel_id=1))
    db.commit()
    assert revoked.status == TemporaryActionGrantStatusEnum.REVOKED


def test_invalid_totp_rejects_approval(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    response = client.post(
        f"/api/permissions/temporary-grants/{requested['id']}/approve",
        json={"totp_code": "000000"},
    )
    assert response.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.PENDING


def test_owner_without_mfa_cannot_approve(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(5, "owner")
    response = client.post(
        f"/api/permissions/temporary-grants/{requested['id']}/approve",
        json={"totp_code": "123456"},
    )
    assert response.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.PENDING


def test_expired_grant_is_rejected_and_marked_expired(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    approved = _approve(client, override_auth, db, mfa_secret, requested["id"])
    grant = db.get(TemporaryActionGrant, requested["id"])
    grant.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(1, "receptionist")
    response = client.post(
        "/api/permissions/temporary-grants/consume",
        json={"token": approved["token"]},
    )
    assert response.status_code == 403
    assert grant.status == TemporaryActionGrantStatusEnum.EXPIRED


def test_service_atomic_consume_returns_false_after_first_use(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    requested = _request(client)
    approved = _approve(client, override_auth, db, mfa_secret, requested["id"])
    requester = TemporaryGrantActor(user_id=1, hotel_id=1)

    assert consume_grant(db, approved["token"], requester) is True
    assert consume_grant(db, approved["token"], requester) is False
