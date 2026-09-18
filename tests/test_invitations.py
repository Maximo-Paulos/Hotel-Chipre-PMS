# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime, timedelta, timezone
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
from app.models.audit_log import AuditLog
from app.services.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.invitation_service import hash_invitation_token, issue_invitation
from app.services.user_session_service import create_session
from app.models.user_session import UserSession
from app.models.user_mfa import UserMfaSecret
from app.services.mfa_service import MFA_ACTIVE, encrypt_totp_secret
from app.dependencies.auth import AuthContext, _authenticate_user
from app.services.permission_service import (
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
)


def get_db_override_target():
    from app.database import get_db
    return get_db


def get_auth_context_target():
    from app.dependencies.auth import get_auth_context
    return get_auth_context


def _invitation_token(db, ctx, email, role="manager"):
    user = db.query(User).filter(User.email.ilike(email)).first()
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
            json={"token": token, "email": victim.email, "password": "attacker-password"},
            headers=headers,
        )

        assert response.status_code == 409, response.text
        assert "Inicia sesión" in response.json()["detail"]
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


def test_google_invitation_reclaims_existing_email_and_revokes_prior_sessions(owner_ctx, monkeypatch):
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

    assert response.status_code == 200, response.text
    assert response.json()["user"]["password_login_enabled"] is False
    assert response.cookies.get("user_session")
    db.refresh(user)
    db.refresh(old_session)
    assert user.google_sub == "claimed-invitee-sub"
    assert user.password_hash != original_hash
    assert not verify_password("OldLocalPassword123!", user.password_hash)
    assert user.password_login_enabled is False
    assert user.token_version == 1
    with pytest.raises(HTTPException) as legacy_rejected:
        _authenticate_user(db, f"Bearer {legacy_token}")
    assert legacy_rejected.value.status_code == 401
    assert old_session.revoked_at is not None
    invitation = db.query(StaffInvitation).filter_by(
        token_hash=hash_invitation_token(invitation_token)
    ).one()
    assert invitation.status == "accepted"
    audit = db.query(SecurityAuditLog).filter_by(action="google_auth.linked").one()
    assert json.loads(audit.details) == {"account_state": "reclaimed", "provider": "google"}


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
            "/api/auth/login/mfa",
            json={"mfa_token": response.json()["mfa_token"], "code": "123456"},
        )
    assert completed_mfa.status_code == 200, completed_mfa.text
    db.refresh(user)
    db.refresh(old_session)
    assert user.google_sub == "claimed-mfa-google-sub"
    assert user.password_hash != original_hash
    assert user.password_login_enabled is False
    assert user.token_version == 1
    assert old_session.revoked_at is not None
    accepted = client.post(
        "/api/invitations/accept",
        headers={"Authorization": f"Bearer {completed_mfa.json()['access_token']}"},
        json={"token": token, "email": email},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["hotel_id"] == ctx["hotel_id"]
    db.refresh(invitation)
    assert invitation.status == "accepted"
    accepted_membership = db.query(HotelMembership).filter_by(
        hotel_id=ctx["hotel_id"], user_id=user.id
    ).one()
    assert accepted_membership.status == "active"


def test_invitation_accept_rejects_password_under_twelve_characters(owner_ctx):
    client, db, ctx = owner_ctx
    email = "short-password@test.com"
    token = _invitation_token(db, ctx, email)

    response = client.post(
        "/api/invitations/accept",
        json={"token": token, "email": email, "password": "short-pw"},
    )

    assert response.status_code == 422, response.text
    assert "12 characters" in response.json()["detail"][0]["msg"]
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
    )
    assert rejected.status_code == 401
    db.refresh(owner_membership)
    assert owner_membership.is_primary_owner is True

    transferred = client.post(
        f"/api/users/{target.id}/primary-owner",
        json={"password": "pw"},
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
