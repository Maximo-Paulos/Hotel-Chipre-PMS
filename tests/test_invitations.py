# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa
from app.models.user import User
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.services.security import hash_password, decode_signed_token
from app.dependencies.auth import AuthContext


def get_db_override_target():
    from app.database import get_db
    return get_db


def get_auth_context_target():
    from app.dependencies.auth import get_auth_context
    return get_auth_context


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
    payload = decode_signed_token(token)
    assert payload["type"] == "invite"
    assert payload["hotel_id"] == ctx["hotel_id"]
    assert payload["email"] == "guest@test.com"
    assert payload["role"] == "manager"
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

    accept = client.post(f"/api/invitations/{token}/accept", json={"email": "guest@test.com", "password": "newpw"})
    assert accept.status_code == 200
    accept_body = accept.json()
    assert accept_body["user"]["is_verified"] is True
    invited_user = db.query(User).filter(User.email == "guest@test.com").first()
    invited_membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == ctx["hotel_id"], HotelMembership.user_id == invited_user.id)
        .first()
    )
    assert invited_membership is not None
    assert invited_membership.status == "active"
    assert invited_user.is_active and invited_user.is_verified


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
