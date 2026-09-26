# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pyotp
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa
from app.config import get_settings
from app.models.user import User
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.security_audit_log import SecurityAuditLog
from app.models.invitation import StaffInvitation
from app.models.permission import UserPermissionOverride
from app.models.audit_log import AuditLog
from app.services.security import (
    create_access_token,
    create_signed_token,
    decode_signed_token,
    hash_password,
    verify_password,
)
from app.services.invitation_service import consume_invitation, hash_invitation_token, issue_invitation
from app.services.user_lookup_service import find_user_by_email
from app.services.user_session_service import create_session
from app.models.user_session import UserSession
from app.models.user_mfa import UserMfaSecret
from app.models.rate_limit_event import RateLimitEvent
from app.adapters.rate_limiter import login_limiter
from app.services.mfa_service import MFA_ACTIVE, encrypt_totp_secret
from app.services.action_step_up_service import create_action_step_up_ticket
from app.dependencies.auth import AuthContext, _authenticate_user
from app.services.permission_service import (
    PERMISSION_HOTEL_PROPERTY_MANAGE,
    PERMISSION_GUEST_READ,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
    PERMISSION_RESERVATION_CREATE,
    set_user_override,
)


def get_db_override_target():
    from app.database import get_db
    return get_db


def get_auth_context_target():
    from app.dependencies.auth import get_auth_context
    return get_auth_context


def _invitation_token(db, ctx, email, role="manager"):
    user = find_user_by_email(db, email)
    _invitation, token, _reused = issue_invitation(
        db,
        hotel_id=ctx["hotel_id"],
        user_id=user.id if user else None,
        email=email,
        role=role,
        inviter_user_id=ctx["user_id"],
        inviter_email=ctx["user_email"],
    )
    db.commit()
    return token


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db_override_target()] = override_get_db
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.fixture
def owner_ctx(client_with_db):
    client, db = client_with_db
    owner = User(email="owner@test.com", password_hash=hash_password("pw"), role="owner", is_verified=True)
    db.add(owner)
    db.flush()
    hotel = HotelConfiguration(id=1, owner_email=owner.email, subscription_active=True)
    db.add(hotel)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel.id, user_id=owner.id, role="owner", status="active"))
    db.commit()

    ctx = {"hotel_id": hotel.id, "user_id": owner.id, "user_email": owner.email}

    def override_auth_context():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=ctx["user_id"],
            user_email=ctx["user_email"],
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context
    try:
        yield client, db, ctx
    finally:
        fastapi_app.dependency_overrides.clear()


def test_invite_returns_token_and_accepts(owner_ctx):
    client, db, ctx = owner_ctx

    resp = client.post(
        "/api/users/invite",
        json={"email": "guest@test.com", "role": "manager", "password": "pw"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "invite_token" in body
    token = body["invite_token"]
    assert "accept_url" in body
    assert body["user"]["is_active"] is False
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    assert token not in invitation.token_hash
    assert invitation.hotel_id == ctx["hotel_id"]
    assert invitation.email == "guest@test.com"
    assert invitation.role == "manager"
    assert invitation.inviter_user_id == ctx["user_id"]
    assert invitation.inviter_email == ctx["user_email"]
    pending_user = db.query(User).filter(User.email == "guest@test.com").first()
    assert pending_user is not None
    pending_membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == ctx["hotel_id"], HotelMembership.user_id == pending_user.id)
        .first()
    )
    assert pending_user.is_active is False
    assert pending_user.is_verified is False
    assert pending_membership is not None
    assert pending_membership.status == "invited"

    accept = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": "guest@test.com", "password": "new-password"},
    )
    assert accept.status_code == 200
    accept_body = accept.json()
    assert accept_body["csrf_token"]
    assert accept.cookies.get("user_session")
    assert accept_body["user"]["is_verified"] is True
    assert PERMISSION_REPORTS_OPERATIONAL_VIEW in accept_body["permissions"]
    assert PERMISSION_REPORTS_FINANCIAL_VIEW not in accept_body["permissions"]
    assert accept_body["user"]["permissions"] == accept_body["permissions"]
    invited_user = db.query(User).filter(User.email == "guest@test.com").first()
    invited_membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == ctx["hotel_id"], HotelMembership.user_id == invited_user.id)
        .first()
    )
    assert invited_membership is not None
    assert invited_membership.status == "active"
    assert invited_user.is_active and invited_user.is_verified
    db.refresh(invitation)
    assert invitation.status == "accepted"

    replay = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": "guest@test.com", "password": "new-account-password"},
    )
    assert replay.status_code == 400, replay.text


def test_atomic_invitation_consumption_rejects_a_rotated_token_hash(owner_ctx):
    _client, db, ctx = owner_ctx
    email = "rotated-token-atomicity@test.com"
    old_token = _invitation_token(db, ctx, email)
    invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(old_token)
    ).one()
    old_hash = invitation.token_hash
    new_token = _invitation_token(db, ctx, email)
    assert new_token != old_token
    db.refresh(invitation)

    assert invitation.token_hash == hash_invitation_token(new_token)
    assert consume_invitation(db, invitation, expected_token_hash=old_hash) is False
    db.refresh(invitation)
    assert invitation.status == "pending"
    assert invitation.consumed_at is None


def test_existing_user_invitation_requires_matching_authenticated_user(owner_ctx):
    client, db, ctx = owner_ctx
    victim = User(
        email="existing-victim@test.com",
        password_hash=hash_password("original-password"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    other_user = User(
        email="other-user@test.com",
        password_hash=hash_password("other-password"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add_all([victim, other_user])
    db.commit()
    original_hash = victim.password_hash
    token = _invitation_token(db, ctx, victim.email)

    for headers in ({}, {"Authorization": f"Bearer {create_access_token(other_user.id)}"}):
        response = client.post(
            "/api/invitations/accept",
            json={"token": token, "email": victim.email},
            headers=headers,
        )

        assert response.status_code == 409, response.text
        assert "contraseña actual" in response.json()["detail"]
        db.refresh(victim)
        assert victim.password_hash == original_hash
        assert victim.is_verified is True
        assert victim.is_active is True


def test_existing_user_invitation_with_own_auth_attaches_without_resetting_account(owner_ctx):
    client, db, ctx = owner_ctx
    victim = User(
        email="existing-member@test.com",
        password_hash=hash_password("original-password"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(victim)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"],
        user_id=victim.id,
        role="receptionist",
        status="invited",
    )
    db.add(membership)
    db.commit()
    original_hash = victim.password_hash
    token = _invitation_token(db, ctx, victim.email, role="manager")
    headers = {"Authorization": f"Bearer {create_access_token(victim.id)}"}

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": victim.email},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    db.refresh(victim)
    db.refresh(membership)
    assert victim.password_hash == original_hash
    assert verify_password("original-password", victim.password_hash)
    assert victim.is_verified is True
    assert victim.is_active is True
    assert membership.status == "active"
    assert membership.role == "manager"
    assert response.json()["user"]["id"] == victim.id


def test_revoked_membership_cannot_be_reactivated_by_replaying_old_accept_token(owner_ctx):
    client, db, ctx = owner_ctx
    victim = User(
        email="revoked-member@test.com",
        password_hash=hash_password("original-password"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(victim)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"],
        user_id=victim.id,
        role="receptionist",
        status="revoked",
    )
    db.add(membership)
    db.commit()
    # A pre-revoke accept token stays cryptographically valid for up to 7 days
    # and is independent of membership state; the victim may still hold an
    # unexpired session for their own account.
    token = _invitation_token(db, ctx, victim.email, role="manager")
    headers = {"Authorization": f"Bearer {create_access_token(victim.id)}"}

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": victim.email, "password": "does-not-matter"},
        headers=headers,
    )

    assert response.status_code == 409, response.text
    assert "revocado" in response.json()["detail"].lower()
    db.refresh(membership)
    assert membership.status == "revoked"


def test_owner_can_reactivate_revoked_member_only_through_a_fresh_invitation(owner_ctx):
    client, db, ctx = owner_ctx
    email = "reactivated-member@test.com"
    first_invite = client.post(
        "/api/users/invite",
        json={"email": email, "role": "manager"},
    )
    assert first_invite.status_code == 201, first_invite.text

    first_accept = client.post(
        "/api/invitations/accept",
        json={
            "token": first_invite.json()["invite_token"],
            "email": email,
            "password": "original-password-123",
        },
    )
    assert first_accept.status_code == 200, first_accept.text
    user = db.query(User).filter_by(email=email).one()
    original_password_hash = user.password_hash
    membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=user.id).one()
    assert membership.status == "active"

    revoked = client.delete(f"/api/users/{user.id}")
    assert revoked.status_code == 204, revoked.text
    db.refresh(membership)
    assert membership.status == "revoked"

    fresh_invite = client.post(
        "/api/users/invite",
        json={"email": email, "role": "manager"},
    )
    assert fresh_invite.status_code == 201, fresh_invite.text
    db.refresh(membership)
    assert membership.status == "invited"
    assert first_invite.json()["invite_token"] != fresh_invite.json()["invite_token"]

    accepted = client.post(
        "/api/invitations/accept",
        json={
            "token": fresh_invite.json()["invite_token"],
            "email": email,
            "current_password": "original-password-123",
        },
    )

    assert accepted.status_code == 200, accepted.text
    db.refresh(membership)
    db.refresh(user)
    assert membership.status == "active"
    assert accepted.json()["user"]["id"] == user.id
    assert user.password_hash == original_password_hash


def test_reinvitation_with_wrong_existing_password_keeps_invitation_pending(owner_ctx):
    client, db, ctx = owner_ctx
    email = "wrong-password-reinvite@test.com"
    user = User(
        email=email,
        password_hash=hash_password("original-password-123"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"],
        user_id=user.id,
        role="manager",
        status="revoked",
    )
    db.add(membership)
    db.commit()
    original_hash = user.password_hash

    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invite.status_code == 201, invite.text
    response = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": email,
            "current_password": "incorrect-password",
        },
    )

    assert response.status_code == 401, response.text
    db.refresh(membership)
    db.refresh(user)
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(invite.json()["invite_token"])).one()
    assert invitation.status == "pending"
    assert membership.status == "invited"
    assert user.password_hash == original_hash


def test_reinvitation_accepts_an_existing_legacy_password_shorter_than_twelve(owner_ctx):
    client, db, ctx = owner_ctx
    email = "legacy-short-password@test.com"
    user = User(
        email=email,
        password_hash=hash_password("short-old"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=user.id, role="manager", status="revoked"))
    db.commit()
    original_hash = user.password_hash
    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invite.status_code == 201, invite.text

    accepted = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": email,
            "current_password": "short-old",
        },
    )

    assert accepted.status_code == 200, accepted.text
    db.refresh(user)
    assert user.password_hash == original_hash


def test_google_only_account_cannot_accept_existing_membership_with_password(owner_ctx):
    client, db, ctx = owner_ctx
    email = "google-only-reinvite@test.com"
    user = User(
        email=email,
        password_hash=hash_password("not-a-real-local-login"),
        google_sub="google-only-provider-sub",
        password_login_enabled=False,
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=user.id, role="manager", status="revoked"))
    db.commit()
    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invite.status_code == 201, invite.text

    rejected = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": email,
            "current_password": "not-a-real-local-login",
        },
    )

    assert rejected.status_code == 409, rejected.text
    assert "Google" in rejected.json()["detail"]
    invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(invite.json()["invite_token"])
    ).one()
    assert invitation.status == "pending"


def test_used_mfa_factor_stays_consumed_if_invitation_activation_fails(owner_ctx):
    client, db, ctx = owner_ctx
    email = "activation-failure-mfa@test.com"
    secret = pyotp.random_base32()
    user = User(
        email=email,
        password_hash=hash_password("original-password-123"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"], user_id=user.id, role="manager", status="revoked"
    )
    mfa_secret = UserMfaSecret(
        user_id=user.id,
        encrypted_secret=encrypt_totp_secret(secret),
        status=MFA_ACTIVE,
    )
    db.add_all([membership, mfa_secret])
    db.commit()
    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    challenge = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": email,
            "current_password": "original-password-123",
        },
    )
    assert invite.status_code == 201, invite.text
    assert challenge.status_code == 200, challenge.text
    code = pyotp.TOTP(secret).now()
    mfa_payload = {
        "token": invite.json()["invite_token"],
        "mfa_token": challenge.json()["mfa_token"],
        "code": code,
    }

    with patch(
        "app.api.invitations._activate_invitation_for_user",
        side_effect=HTTPException(status_code=409, detail="Simulated activation conflict"),
    ):
        failed_activation = client.post("/api/invitations/accept/mfa", json=mfa_payload)
    assert failed_activation.status_code == 409, failed_activation.text
    db.refresh(mfa_secret)
    assert mfa_secret.last_used_step is not None

    replay = client.post("/api/invitations/accept/mfa", json=mfa_payload)
    assert replay.status_code == 401, replay.text
    db.refresh(membership)
    assert membership.status == "invited"


def test_reinvitation_password_guesses_share_the_normal_login_limit(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "limited-password-reinvite@test.com"
    user = User(
        email=email,
        password_hash=hash_password("original-password-123"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=user.id, role="manager", status="revoked"))
    db.commit()
    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invite.status_code == 201, invite.text

    login_limiter.reset(email, db=db)
    db.commit()
    monkeypatch.setattr(get_settings(), "LOGIN_RATE_LIMIT", 1)
    payload = {
        "token": invite.json()["invite_token"],
        "email": email,
        "current_password": "incorrect-password",
    }
    first = client.post("/api/invitations/accept", json=payload)
    second = client.post(
        "/api/auth/login",
        json={"email": f"  {email}  ", "password": "incorrect-password"},
    )

    assert first.status_code == 401, first.text
    assert second.status_code == 429, second.text
    assert db.query(RateLimitEvent).filter_by(scope="login", subject_key=email).count() >= 2


def test_invitation_mfa_challenge_is_invalidated_when_owner_reissues_link(owner_ctx):
    client, db, ctx = owner_ctx
    email = "rotated-mfa-invite@test.com"
    user = User(
        email=email,
        password_hash=hash_password("original-password-123"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=user.id, role="manager", status="revoked"))
    db.add(UserMfaSecret(
        user_id=user.id,
        encrypted_secret=encrypt_totp_secret(pyotp.random_base32()),
        status=MFA_ACTIVE,
    ))
    db.commit()

    first_invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    first_challenge = client.post(
        "/api/invitations/accept",
        json={
            "token": first_invite.json()["invite_token"],
            "email": email,
            "current_password": "original-password-123",
        },
    )
    assert first_invite.status_code == 201, first_invite.text
    assert first_challenge.status_code == 200, first_challenge.text
    assert first_challenge.json()["requires_mfa"] is True

    replacement_invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert replacement_invite.status_code == 201, replacement_invite.text
    assert replacement_invite.json()["invite_token"] != first_invite.json()["invite_token"]
    stale = client.post(
        "/api/invitations/accept/mfa",
        json={
            "token": replacement_invite.json()["invite_token"],
            "mfa_token": first_challenge.json()["mfa_token"],
            "code": "123456",
        },
    )
    assert stale.status_code == 409, stale.text

    current_challenge = client.post(
        "/api/invitations/accept",
        json={
            "token": replacement_invite.json()["invite_token"],
            "email": email,
            "current_password": "original-password-123",
        },
    )
    assert current_challenge.status_code == 200, current_challenge.text
    with patch("app.api.auth.mfa_service.consume_mfa_code", return_value=True):
        accepted = client.post(
            "/api/invitations/accept/mfa",
            json={
                "token": replacement_invite.json()["invite_token"],
                "mfa_token": current_challenge.json()["mfa_token"],
                "code": "123456",
            },
        )
    assert accepted.status_code == 200, accepted.text
    membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=user.id).one()
    assert membership.status == "active"


def test_reinvitation_with_password_requires_mfa_before_consuming_invitation(owner_ctx):
    client, db, ctx = owner_ctx
    email = "mfa-password-reinvite@test.com"
    user = User(
        email=email,
        password_hash=hash_password("original-password-123"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"],
        user_id=user.id,
        role="manager",
        status="revoked",
    )
    db.add(membership)
    db.add(UserMfaSecret(
        user_id=user.id,
        encrypted_secret=encrypt_totp_secret(pyotp.random_base32()),
        status=MFA_ACTIVE,
    ))
    db.commit()

    invite = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invite.status_code == 201, invite.text
    response = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": email,
            "current_password": "original-password-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["requires_mfa"] is True
    password_challenge_audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=ctx["hotel_id"], action="auth.mfa_challenge"
    ).one()
    assert json.loads(password_challenge_audit.details) == {"method": "password", "scope": "invitation_acceptance"}
    db.refresh(membership)
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(invite.json()["invite_token"])).one()
    assert invitation.status == "pending"
    assert membership.status == "invited"

    # Invitation challenges cannot be upgraded into unrestricted login sessions.
    wrong_endpoint = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": response.json()["mfa_token"], "code": "123456"},
    )
    assert wrong_endpoint.status_code == 401, wrong_endpoint.text
    login_challenge = create_signed_token(
        {"purpose": "mfa_login", "user_id": user.id, "token_version": user.token_version}
    )
    reverse_wrong_endpoint = client.post(
        "/api/invitations/accept/mfa",
        json={"token": invite.json()["invite_token"], "mfa_token": login_challenge, "code": "123456"},
    )
    assert reverse_wrong_endpoint.status_code == 401, reverse_wrong_endpoint.text

    with patch("app.api.auth.mfa_service.consume_mfa_code", return_value=False):
        rejected = client.post(
            "/api/invitations/accept/mfa",
            json={"token": invite.json()["invite_token"], "mfa_token": response.json()["mfa_token"], "code": "000000"},
        )
    assert rejected.status_code == 401, rejected.text
    shared_mfa_budget = db.query(RateLimitEvent).filter_by(
        scope="mfa_code_guess", subject_key=f"login:{user.id}"
    ).count()
    assert shared_mfa_budget == 1

    # A normal-login challenge consumes the same account-level budget.
    with patch("app.api.auth.mfa_service.consume_mfa_code", return_value=False):
        normal_login_rejected = client.post(
            "/api/auth/login/mfa",
            json={"mfa_token": login_challenge, "code": "000000"},
        )
    assert normal_login_rejected.status_code == 401, normal_login_rejected.text
    assert db.query(RateLimitEvent).filter_by(
        scope="mfa_code_guess", subject_key=f"login:{user.id}"
    ).count() == 2

    db.refresh(invitation)
    db.refresh(membership)
    assert invitation.status == "pending"
    assert membership.status == "invited"

    with patch("app.api.auth.mfa_service.consume_mfa_code", return_value=True):
        completed = client.post(
            "/api/invitations/accept/mfa",
            json={"token": invite.json()["invite_token"], "mfa_token": response.json()["mfa_token"], "code": "123456"},
        )
    assert completed.status_code == 200, completed.text
    assert completed.json()["hotel_id"] == ctx["hotel_id"]
    assert db.query(RateLimitEvent).filter_by(
        scope="mfa_code_guess", subject_key=f"login:{user.id}"
    ).count() == 0
    db.refresh(invitation)
    db.refresh(membership)
    assert invitation.status == "accepted"
    assert membership.status == "active"


def test_invitation_creates_and_activates_user_when_email_is_new(owner_ctx):
    client, db, ctx = owner_ctx
    email = "brand-new-user@test.com"
    assert db.query(User).filter(User.email == email).first() is None
    token = _invitation_token(db, ctx, email)

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": email, "password": "new-account-password"},
    )

    assert response.status_code == 200, response.text
    new_user = db.query(User).filter(User.email == email).first()
    assert new_user is not None
    assert verify_password("new-account-password", new_user.password_hash)
    assert new_user.is_verified is True
    assert new_user.is_active is True
    new_membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == ctx["hotel_id"], HotelMembership.user_id == new_user.id)
        .first()
    )
    assert new_membership is not None
    assert new_membership.status == "active"


def _google_claims(email, *, sub="invited-google-sub", email_verified=True):
    return {
        "email": email,
        "email_verified": email_verified,
        "sub": sub,
        "iss": "https://accounts.google.com",
        "aud": "test-client-id.apps.googleusercontent.com",
        "exp": int(time.time()) + 300,
    }


def _enable_test_google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_LOGIN_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    get_settings.cache_clear()


def test_google_invitation_claim_creates_only_a_non_owner_hotel_membership(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "google-invitee@test.com"
    token = _invitation_token(db, ctx, email, role="manager")
    hotels_before = db.query(HotelConfiguration).count()
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(email),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "verified-google-id-token"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hotel_id"] == ctx["hotel_id"]
    assert body["csrf_token"]
    assert response.cookies.get("user_session")
    assert body["user"]["role"] == "manager"
    assert body["user"]["password_login_enabled"] is False
    user = db.query(User).filter_by(email=email).one()
    assert user.is_active and user.is_verified
    assert user.google_sub == "invited-google-sub"
    assert user.password_login_enabled is False
    membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=user.id
    ).one()
    assert membership.role == "manager"
    assert membership.status == "active"
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    assert invitation.status == "accepted"
    assert db.query(HotelConfiguration).count() == hotels_before


def test_google_invitation_claim_activates_the_provisioned_placeholder(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "google-placeholder@test.com"
    invitation_response = client.post(
        "/api/users/invite",
        json={"email": email, "role": "receptionist"},
    )
    assert invitation_response.status_code == 201, invitation_response.text
    token = invitation_response.json()["invite_token"]
    user = db.query(User).filter_by(email=email).one()
    membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=user.id
    ).one()
    assert not user.is_active and not user.is_verified
    assert membership.status == "invited"
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(email, sub="placeholder-google-sub"),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "placeholder-google-id-token"},
        )

    assert response.status_code == 200, response.text
    db.refresh(user)
    db.refresh(membership)
    assert user.is_active and user.is_verified
    assert user.google_sub == "placeholder-google-sub"
    assert user.password_login_enabled is False
    assert membership.status == "active"
    assert membership.role == "receptionist"
    stored_invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(token)
    ).one()
    assert stored_invitation.status == "accepted"


def test_google_invitation_preserves_existing_password_account_without_mfa(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "local-invitee@test.com"
    user = User(
        email=email,
        password_hash=hash_password("OldLocalPassword123!"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    existing_hotel = HotelConfiguration(
        id=2,
        owner_email=email,
        hotel_name="Existing hotel",
        subscription_active=True,
    )
    db.add(existing_hotel)
    db.flush()
    db.add(HotelMembership(
        hotel_id=existing_hotel.id,
        user_id=user.id,
        role="manager",
        status="active",
    ))
    old_session, _old_token, _old_csrf = create_session(db, user)
    db.commit()
    legacy_token = create_access_token(user.id, extra={"email": user.email, "verified": True})
    assert _authenticate_user(db, f"Bearer {legacy_token}")[0].id == user.id
    original_hash = user.password_hash
    invitation_token = _invitation_token(db, ctx, email, role="manager")
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(email, sub="claimed-invitee-sub"),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": invitation_token, "id_token": "verified-google-id-token"},
        )

    assert response.status_code == 409, response.text
    assert "Iniciá sesión con esa cuenta" in response.json()["detail"]
    db.refresh(user)
    db.refresh(old_session)
    assert user.google_sub is None
    assert user.password_hash == original_hash
    assert verify_password("OldLocalPassword123!", user.password_hash)
    assert user.password_login_enabled is True
    assert user.token_version == 0
    assert _authenticate_user(db, f"Bearer {legacy_token}")[0].id == user.id
    assert old_session.revoked_at is None
    invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(invitation_token)
    ).one()
    assert invitation.status == "pending"
    assert invitation.consumed_at is None
    assert db.query(SecurityAuditLog).filter_by(action="google_auth.linked").count() == 0

    password_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "OldLocalPassword123!"},
    )
    assert password_login.status_code == 200, password_login.text


def test_google_invitation_requires_the_exact_verified_recipient_email(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "expected-invitee@test.com"
    token = _invitation_token(db, ctx, email)
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("different-user@test.com"),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "wrong-google-id-token"},
        )

    assert response.status_code == 400, response.text
    assert db.query(User).filter_by(email=email).count() == 0
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    assert invitation.status == "pending"
    assert invitation.consumed_at is None


def test_google_invitation_treats_underscores_as_literal_email_characters(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "staff_manager@example.com"
    near_match = User(
        email="staffXmanager@example.com",
        password_hash=hash_password("ExistingPassword123!"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(near_match)
    db.commit()
    token = _invitation_token(db, ctx, email)
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(email, sub="literal-email-match-sub"),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "verified-google-id-token"},
        )

    assert response.status_code == 200, response.text
    db.refresh(near_match)
    assert near_match.google_sub is None
    assert verify_password("ExistingPassword123!", near_match.password_hash)
    invited_user = db.query(User).filter_by(email=email).one()
    assert invited_user.id != near_match.id
    assert invited_user.google_sub == "literal-email-match-sub"
    membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=invited_user.id
    ).one()
    assert membership.status == "active"
    invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(token)
    ).one()
    assert invitation.status == "accepted"


def test_google_invitation_rejects_an_owner_role_from_invalid_stored_state(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "invalid-owner-invite@test.com"
    token = _invitation_token(db, ctx, email, role="manager")
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    invitation.role = "owner"
    db.commit()
    _enable_test_google(monkeypatch)

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(email),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "invalid-role-google-id-token"},
        )

    assert response.status_code == 400, response.text
    assert db.query(User).filter_by(email=email).count() == 0
    db.refresh(invitation)
    assert invitation.status == "pending"
    assert db.query(HotelConfiguration).count() == 1


def test_google_invitation_waits_for_mfa_before_consuming_token(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "mfa-invitee@test.com"
    user = User(
        email=email,
        password_hash=hash_password("ExistingStrongPassword!"),
        role="manager",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    existing_hotel = HotelConfiguration(
        id=2,
        owner_email=email,
        hotel_name="Existing hotel",
        subscription_active=True,
    )
    db.add(existing_hotel)
    db.flush()
    db.add(HotelMembership(
        hotel_id=existing_hotel.id,
        user_id=user.id,
        role="manager",
        status="active",
    ))
    old_session, _old_session_token, _old_csrf_token = create_session(db, user)
    original_hash = user.password_hash
    mfa_secret = pyotp.random_base32()
    db.add(
        UserMfaSecret(
            user_id=user.id,
            encrypted_secret=encrypt_totp_secret(mfa_secret),
            status=MFA_ACTIVE,
        )
    )
    db.commit()
    token = _invitation_token(db, ctx, email, role="manager")
    _enable_test_google(monkeypatch)

    with (
        patch(
            "app.api.auth.google_id_token.verify_oauth2_token",
            return_value=_google_claims(email, sub="claimed-mfa-google-sub"),
        ),
    ):
        response = client.post(
            "/api/invitations/accept/google",
            json={"token": token, "id_token": "mfa-google-id-token"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["requires_mfa"] is True
    challenge_claims = decode_signed_token(response.json()["mfa_token"])
    assert challenge_claims["purpose"] == "invitation_accept_mfa"
    assert "token_hash" not in str(challenge_claims)
    assert "fingerprint" in challenge_claims["invitation"]
    challenge_audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=ctx["hotel_id"], action="google_auth.mfa_challenge"
    ).one()
    assert json.loads(challenge_audit.details) == {"method": "google", "scope": "invitation_acceptance"}
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    assert invitation.status == "pending"
    assert invitation.consumed_at is None
    db.refresh(user)
    db.refresh(old_session)
    assert user.google_sub is None
    assert user.password_hash == original_hash
    assert user.token_version == 0
    assert old_session.revoked_at is None
    target_membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=user.id
    ).first()
    assert target_membership is None or target_membership.status != "active"

    with patch("app.api.auth.mfa_service.consume_mfa_code", return_value=True):
        completed_mfa = client.post(
            "/api/invitations/accept/mfa",
            json={"token": token, "mfa_token": response.json()["mfa_token"], "code": "123456"},
        )
    assert completed_mfa.status_code == 200, completed_mfa.text
    db.refresh(user)
    db.refresh(old_session)
    assert user.google_sub == "claimed-mfa-google-sub"
    assert user.password_hash == original_hash
    assert verify_password("ExistingStrongPassword!", user.password_hash)
    assert user.password_login_enabled is True
    assert user.token_version == 1
    assert old_session.revoked_at is not None
    assert completed_mfa.json()["hotel_id"] == ctx["hotel_id"]
    db.refresh(invitation)
    assert invitation.status == "accepted"
    accepted_membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=user.id
    ).one()
    assert accepted_membership.status == "active"
    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=ctx["hotel_id"], action="google_auth.linked"
    ).one()
    assert json.loads(audit.details) == {"account_state": "linked_after_mfa_invitation", "provider": "google"}


def test_invitation_accept_rejects_password_under_twelve_characters(owner_ctx):
    client, db, ctx = owner_ctx
    email = "short-password@test.com"
    token = _invitation_token(db, ctx, email)

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": email, "password": "short-pw"},
    )

    assert response.status_code == 422, response.text
    assert "12 caracteres" in response.json()["detail"]
    assert db.query(User).filter(User.email == email).first() is None


def test_static_invitation_flow_keeps_bearer_out_of_urls_and_application_logs(owner_ctx, caplog):
    client, db, ctx = owner_ctx
    caplog.set_level("INFO")
    email = "static-invite@example.test"
    invited = client.post("/api/users/invite", json={"email": email, "role": "manager"})
    assert invited.status_code == 201, invited.text
    token = invited.json()["invite_token"]
    assert "#token=" in invited.json()["accept_url"]
    assert "?token=" not in invited.json()["accept_url"]

    caplog.clear()
    preview = client.post("/api/invitations/preview", json={"token": token})
    assert preview.status_code == 200, f"{preview.text}\n{caplog.text}"
    accepted = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": email, "password": "StrongInvitePass123!"},
    )

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["hotel_id"] == ctx["hotel_id"]
    assert accepted.json()["user"]["role"] == "manager"
    assert token not in caplog.text
    assert "route=/api/invitations" in caplog.text
    assert db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], role="manager", status="active").count() == 1


def test_invitation_routes_keep_static_flow_and_legacy_acceptance_compatibility():
    invitation_paths = {
        path for path in fastapi_app.openapi()["paths"] if path.startswith("/api/invitations")
    }

    assert "/api/invitations/preview" in invitation_paths
    assert "/api/invitations/accept" in invitation_paths
    assert "/api/invitations/accept/mfa" in invitation_paths
    assert "/api/invitations/accept/google" in invitation_paths
    assert "/api/invitations/{token}/accept" in invitation_paths
    assert "/api/invitations/{token}/accept/google" in invitation_paths


def test_legacy_dynamic_invitation_acceptance_routes_remain_compatible(owner_ctx, monkeypatch):
    client, db, ctx = owner_ctx
    email = "legacy-invitee@test.com"
    password_token = _invitation_token(db, ctx, email)
    password_accepted = client.post(
        f"/api/invitations/{password_token}/accept",
        json={"email": email, "password": "LegacyInvitePass123!"},
    )
    assert password_accepted.status_code == 200, password_accepted.text
    assert password_accepted.json()["user"]["role"] == "manager"

    google_email = "legacy-google-invitee@test.com"
    google_token = _invitation_token(db, ctx, google_email, role="receptionist")
    _enable_test_google(monkeypatch)
    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims(google_email, sub="legacy-google-sub"),
    ):
        google_accepted = client.post(
            f"/api/invitations/{google_token}/accept/google",
            json={"id_token": "verified-google-id-token"},
        )

    assert google_accepted.status_code == 200, google_accepted.text
    assert google_accepted.json()["user"]["role"] == "receptionist"
    user = db.query(User).filter_by(email=google_email).one()
    membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=user.id).one()
    assert user.google_sub == "legacy-google-sub"
    assert membership.status == "active"


def test_expired_invitation_is_not_available(owner_ctx):
    client, db, ctx = owner_ctx
    email = "expired-invite@test.com"
    token = _invitation_token(db, ctx, email)
    invitation = db.query(StaffInvitation).filter_by(token_hash=hash_invitation_token(token)).one()
    invitation.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()

    assert client.post("/api/invitations/preview", json={"token": token}).status_code == 400
    assert client.post(
        "/api/invitations/accept",
        json={"token": token, "email": email, "password": "new-account-password"},
    ).status_code == 400


def test_duplicate_invite_reuses_pending_record_and_audits_resend(owner_ctx):
    client, db, _ctx = owner_ctx
    first = client.post(
        "/api/users/invite",
        json={"email": "duplicate@test.com", "role": "manager"},
    )
    second = client.post(
        "/api/users/invite",
        json={"email": "duplicate@test.com", "role": "manager"},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["invitation_id"] == second.json()["invitation_id"]
    assert first.json()["invite_token"] != second.json()["invite_token"]
    assert db.query(StaffInvitation).filter(StaffInvitation.status == "pending").count() == 1

    assert client.post(
        "/api/invitations/preview", json={"token": first.json()["invite_token"]}
    ).status_code == 400
    assert client.post(
        "/api/invitations/preview", json={"token": second.json()["invite_token"]}
    ).status_code == 200
    invitation_id = second.json()["invitation_id"]
    resend = client.post(f"/api/users/invitations/{invitation_id}/resend")
    assert resend.status_code == 200, resend.text
    assert resend.json()["invitation_id"] == invitation_id
    assert resend.json()["accept_url"].endswith(f"#token={resend.json()['invite_token']}")
    assert client.post(
        "/api/invitations/preview", json={"token": second.json()["invite_token"]}
    ).status_code == 400
    assert client.post(
        "/api/invitations/preview", json={"token": resend.json()["invite_token"]}
    ).status_code == 200

    events = db.query(AuditLog).filter_by(table_name="staff_invitations", record_id=invitation_id).all()
    payloads = [json.loads(event.payload_after or "{}") for event in events]
    assert any(payload.get("event") == "invitation.resend" for payload in payloads)

    revoked = client.delete(f"/api/users/invitations/{invitation_id}")
    assert revoked.status_code == 204, revoked.text
    invitation = db.get(StaffInvitation, invitation_id)
    assert invitation.status == "revoked"
    assert client.post(
        "/api/invitations/preview", json={"token": resend.json()["invite_token"]}
    ).status_code == 400
    assert any(
        json.loads(event.payload_after or "{}").get("event") == "invitation.revoked"
        for event in db.query(AuditLog).filter_by(table_name="staff_invitations", record_id=invitation_id).all()
    )


def test_invitation_email_explains_that_only_the_latest_link_works():
    from app.api.users import _send_invitation_email

    with patch(
        "app.api.users.get_settings",
        return_value=SimpleNamespace(FRONTEND_URL="https://app.example.test/"),
    ), patch("app.api.users.mailer") as mocked_mailer:
        mocked_mailer.configured = True
        mocked_mailer.send.return_value = True
        accept_url, delivery = _send_invitation_email(
            email="invitee@example.test",
            hotel_name="Hotel de prueba",
            role="Gerencia",
            inviter_email="owner@example.test",
            token="synthetic-invite-token",
        )

    assert delivery == "sent"
    assert accept_url == "https://app.example.test/invitations/accept#token=synthetic-invite-token"
    email_body = mocked_mailer.send.call_args.args[2]
    assert accept_url in email_body
    assert "cada reenvío invalida los anteriores" in email_body


def test_revoke_user_invalidates_jwt_version_and_all_server_sessions(owner_ctx):
    client, db, ctx = owner_ctx
    staff = User(
        email="active-staff@test.com",
        password_hash=hash_password("original-password"),
        role="manager",
        is_verified=True,
        is_active=True,
        token_version=0,
    )
    db.add(staff)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=staff.id, role="manager", status="active"))
    sessions = [create_session(db, staff), create_session(db, staff)]
    db.commit()
    access_token = create_access_token(staff.id, extra={"token_version": staff.token_version})

    revoked = client.delete(f"/api/users/{staff.id}")

    assert revoked.status_code == 204, revoked.text
    db.refresh(staff)
    assert staff.token_version == 1
    assert db.query(UserSession).filter(UserSession.user_id == staff.id, UserSession.revoked_at.is_(None)).count() == 0
    assert all(session.revoked_at is not None for session, _token, _csrf in sessions)
    fastapi_app.dependency_overrides.pop(get_auth_context_target(), None)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}).status_code == 401


def test_update_role_requires_owner(owner_ctx):
    client, db, ctx = owner_ctx
    # create another user and membership
    mgr = User(email="mgr@test.com", password_hash=hash_password("pw"), role="manager", is_verified=True)
    db.add(mgr); db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=mgr.id, role="manager", status="active"))
    db.commit()

    # as owner: can update
    r_ok = client.patch(f"/api/users/{mgr.id}/role", json={"role": "housekeeping"})
    assert r_ok.status_code == 200
    db.refresh(mgr)
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == ctx["hotel_id"], HotelMembership.user_id == mgr.id)
        .first()
    )
    assert membership is not None
    assert membership.role == "housekeeping"
    role_audit = (
        db.query(AuditLog)
        .filter(AuditLog.table_name == "hotel_memberships", AuditLog.record_id == membership.id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert role_audit is not None
    assert json.loads(role_audit.payload_after or "{}")["event"] == "staff.role_changed"

    # switch context to manager and expect 403
    def override_auth_context_manager():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=mgr.id,
            user_email=mgr.email,
            user_role="manager",
            is_verified=True,
            permissions=set(),
        )
    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context_manager
    r_forbidden = client.patch(f"/api/users/{mgr.id}/role", json={"role": "owner"})
    assert r_forbidden.status_code == 403


def test_update_role_cannot_reactivate_invited_or_revoked_memberships(owner_ctx):
    client, db, ctx = owner_ctx
    cases = ("invited", "revoked")
    for membership_status in cases:
        email = f"inactive-{membership_status}@test.com"
        user = User(
            email=email,
            password_hash=hash_password("pw"),
            role="manager",
            is_verified=False,
            is_active=False,
        )
        db.add(user)
        db.flush()
        membership = HotelMembership(
            hotel_id=ctx["hotel_id"],
            user_id=user.id,
            role="manager",
            status=membership_status,
        )
        db.add(membership)
        db.commit()
        if membership_status == "invited":
            _invitation_token(db, ctx, email, role="manager")

        response = client.patch(f"/api/users/{user.id}/role", json={"role": "housekeeping"})

        assert response.status_code == 409, response.text
        db.refresh(membership)
        assert membership.role == "manager"
        assert membership.status == membership_status
        if membership_status == "invited":
            pending = db.query(StaffInvitation).filter_by(
                hotel_id=ctx["hotel_id"], email=email, status="pending"
            ).one()
            assert pending.role == "manager"


def test_role_change_clears_user_grants_but_preserves_denials(owner_ctx):
    client, db, ctx = owner_ctx
    staff = User(
        email="role-change-overrides@test.com",
        password_hash=hash_password("StrongPassword123!"),
        role="manager",
        is_verified=True,
        is_active=True,
    )
    db.add(staff)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"], user_id=staff.id, role="manager", status="active"
    )
    db.add(membership)
    db.commit()

    set_user_override(
        db,
        ctx["hotel_id"],
        staff.id,
        "manager",
        PERMISSION_RESERVATION_CREATE,
        True,
        ctx["user_id"],
    )
    set_user_override(
        db,
        ctx["hotel_id"],
        staff.id,
        "manager",
        PERMISSION_GUEST_READ,
        False,
        ctx["user_id"],
    )
    db.commit()

    response = client.patch(f"/api/users/{staff.id}/role", json={"role": "housekeeping"})

    assert response.status_code == 200, response.text
    db.refresh(membership)
    assert membership.role == "housekeeping"
    rows = db.query(UserPermissionOverride).filter_by(
        hotel_id=ctx["hotel_id"], user_id=staff.id
    ).all()
    assert [(row.permission_code, row.allowed) for row in rows] == [(PERMISSION_GUEST_READ, False)]

    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=ctx["hotel_id"],
        user_id=ctx["user_id"],
        action="permission.user_grants.cleared_by_role_change",
    ).one()
    details = json.loads(audit.details)
    assert details["before"] == {
        "role": "manager",
        "grants": [{"permission_code": PERMISSION_RESERVATION_CREATE, "allowed": True, "version": 1}],
    }
    assert details["after"] == {
        "role": "housekeeping",
        "grants": [],
        "preserved_denials": [PERMISSION_GUEST_READ],
    }


def test_inviting_existing_member_with_new_role_clears_carried_permission_grants(owner_ctx):
    client, db, ctx = owner_ctx
    staff = User(
        email="reinvite-role-change@test.com",
        password_hash=hash_password("StrongPassword123!"),
        role="manager",
        is_verified=True,
        is_active=True,
    )
    db.add(staff)
    db.flush()
    membership = HotelMembership(
        hotel_id=ctx["hotel_id"], user_id=staff.id, role="manager", status="active"
    )
    db.add(membership)
    db.commit()

    set_user_override(
        db,
        ctx["hotel_id"],
        staff.id,
        "manager",
        PERMISSION_RESERVATION_CREATE,
        True,
        ctx["user_id"],
    )
    set_user_override(
        db,
        ctx["hotel_id"],
        staff.id,
        "manager",
        PERMISSION_GUEST_READ,
        False,
        ctx["user_id"],
    )
    db.commit()

    response = client.post(
        "/api/users/invite",
        json={"email": staff.email, "role": "housekeeping"},
    )

    assert response.status_code == 201, response.text
    db.refresh(membership)
    assert membership.role == "housekeeping"
    assert membership.status == "invited"
    rows = db.query(UserPermissionOverride).filter_by(
        hotel_id=ctx["hotel_id"], user_id=staff.id
    ).all()
    assert [(row.permission_code, row.allowed) for row in rows] == [(PERMISSION_GUEST_READ, False)]


def test_co_owner_cannot_grant_privileged_roles(owner_ctx):
    client, db, ctx = owner_ctx
    co_owner = User(email="co@test.com", password_hash=hash_password("pw"), role="co_owner", is_verified=True)
    staff = User(email="staff@test.com", password_hash=hash_password("pw"), role="manager", is_verified=True)
    db.add_all([co_owner, staff])
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=co_owner.id, role="co_owner", status="active"))
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=staff.id, role="manager", status="active"))
    db.commit()

    def override_auth_context_co_owner():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=co_owner.id,
            user_email=co_owner.email,
            user_role="co_owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context_co_owner

    invite = client.post("/api/users/invite", json={"email": "newco@test.com", "role": "co_owner"})
    assert invite.status_code == 403

    promote = client.patch(f"/api/users/{staff.id}/role", json={"role": "co_owner"})
    assert promote.status_code == 403

    demote_to_manager = client.patch(f"/api/users/{staff.id}/role", json={"role": "manager"})
    assert demote_to_manager.status_code == 200


def test_co_owner_cannot_demote_peer_through_invitation_email(owner_ctx):
    client, db, ctx = owner_ctx
    co_owner = User(email="peer-one@test.com", password_hash=hash_password("pw"), role="co_owner", is_verified=True)
    peer = User(email="peer-two@test.com", password_hash=hash_password("pw"), role="co_owner", is_verified=True)
    db.add_all([co_owner, peer])
    db.flush()
    db.add_all([
        HotelMembership(hotel_id=ctx["hotel_id"], user_id=co_owner.id, role="co_owner", status="active"),
        HotelMembership(hotel_id=ctx["hotel_id"], user_id=peer.id, role="co_owner", status="active"),
    ])
    db.commit()

    fastapi_app.dependency_overrides[get_auth_context_target()] = lambda: AuthContext(
        hotel_id=ctx["hotel_id"],
        user_id=co_owner.id,
        user_email=co_owner.email,
        user_role="co_owner",
        is_verified=True,
        permissions=set(),
    )

    response = client.post(
        "/api/users/invite",
        json={"email": peer.email, "role": "manager"},
    )

    assert response.status_code == 403, response.text
    peer_membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=peer.id).one()
    db.refresh(peer_membership)
    assert peer_membership.role == "co_owner"
    assert peer_membership.status == "active"
    assert db.query(StaffInvitation).filter_by(hotel_id=ctx["hotel_id"], email=peer.email).count() == 0


def test_owner_cannot_assign_owner_or_revoke_self(owner_ctx):
    client, db, ctx = owner_ctx

    invite_owner = client.post("/api/users/invite", json={"email": "other-owner@test.com", "role": "owner"})
    assert invite_owner.status_code == 400

    revoke_self = client.delete(f"/api/users/{ctx['user_id']}")
    assert revoke_self.status_code == 400
    membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=ctx["user_id"]).one()
    assert membership.role == "owner"
    assert membership.status == "active"


def test_single_active_owner_cannot_be_downgraded_by_invitation(owner_ctx):
    client, db, ctx = owner_ctx
    owner = db.get(User, ctx["user_id"])
    token = _invitation_token(db, ctx, owner.email, role="manager")

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": owner.email, "password": "must-not-change-role"},
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
    )

    assert response.status_code == 409, response.text
    membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=owner.id
    ).one()
    assert membership.role == "owner"
    assert membership.status == "active"


def test_primary_owner_cannot_be_downgraded_by_invitation_replay(owner_ctx):
    client, db, ctx = owner_ctx
    owner = db.get(User, ctx["user_id"])
    membership = db.query(HotelMembership).filter_by(hotel_id=ctx["hotel_id"], user_id=owner.id).one()
    membership.is_primary_owner = True
    db.commit()

    token = _invitation_token(db, ctx, owner.email, role="manager")
    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": owner.email, "password": "must-not-change-role"},
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
    )

    assert response.status_code == 409, response.text
    db.refresh(membership)
    assert membership.role == "owner"
    assert membership.status == "active"
    assert membership.is_primary_owner is True


def test_primary_owner_transfer_requires_reauth_and_writes_audit(owner_ctx):
    client, db, ctx = owner_ctx
    owner = db.get(User, ctx["user_id"])
    owner_membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=owner.id
    ).one()
    owner_membership.is_primary_owner = True
    target = User(
        email="target-owner@test.com",
        password_hash=hash_password("target-password"),
        role="owner",
        is_verified=True,
        is_active=True,
    )
    db.add(target)
    db.flush()
    db.add(HotelMembership(hotel_id=ctx["hotel_id"], user_id=target.id, role="owner", status="active"))
    db.commit()

    rejected = client.post(
        f"/api/users/{target.id}/primary-owner",
        json={"password": "wrong-password"},
        headers={"X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=owner.id,
            hotel_id=ctx["hotel_id"],
            token_version=0,
            permission_code=PERMISSION_HOTEL_PROPERTY_MANAGE,
            method="POST",
            path=f"/api/users/{target.id}/primary-owner",
        )},
    )
    assert rejected.status_code == 401
    db.refresh(owner_membership)
    assert owner_membership.is_primary_owner is True

    transferred = client.post(
        f"/api/users/{target.id}/primary-owner",
        json={"password": "pw"},
        headers={"X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=owner.id,
            hotel_id=ctx["hotel_id"],
            token_version=0,
            permission_code=PERMISSION_HOTEL_PROPERTY_MANAGE,
            method="POST",
            path=f"/api/users/{target.id}/primary-owner",
        )},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json() == {
        "hotel_id": ctx["hotel_id"],
        "primary_owner_user_id": target.id,
        "transferred": True,
    }

    db.refresh(owner_membership)
    target_membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=target.id
    ).one()
    assert owner_membership.is_primary_owner is False
    assert target_membership.is_primary_owner is True
    hotel = db.get(HotelConfiguration, ctx["hotel_id"])
    assert hotel.owner_email == target.email
    audit = db.query(SecurityAuditLog).filter_by(
        hotel_id=ctx["hotel_id"], action="membership.primary_owner.transferred"
    ).one()
    assert audit.user_id == owner.id
    assert audit.resource_id == str(target_membership.id)


def test_owner_and_co_owner_can_assign_receptionist(owner_ctx):
    client, db, ctx = owner_ctx

    owner_invite = client.post(
        "/api/users/invite",
        json={"email": "reception-owner@test.com", "role": "receptionist"},
    )
    assert owner_invite.status_code == 201, owner_invite.text
    assert owner_invite.json()["user"]["role"] == "receptionist"

    co_owner = User(
        email="co-reception@test.com",
        password_hash=hash_password("pw"),
        role="co_owner",
        is_verified=True,
    )
    db.add(co_owner)
    db.flush()
    db.add(
        HotelMembership(
            hotel_id=ctx["hotel_id"],
            user_id=co_owner.id,
            role="co_owner",
            status="active",
        )
    )
    db.commit()

    def override_auth_context_co_owner():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=co_owner.id,
            user_email=co_owner.email,
            user_role="co_owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context_co_owner
    co_owner_invite = client.post(
        "/api/users/invite",
        json={"email": "reception-co@test.com", "role": "receptionist"},
    )
    assert co_owner_invite.status_code == 201, co_owner_invite.text
    assert co_owner_invite.json()["user"]["role"] == "receptionist"
