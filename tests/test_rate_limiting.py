# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa: F401
from app.adapters.rate_limiter import verify_request_limiter, reset_request_limiter, invite_limiter
from app.services.security import hash_password
from app.models.user import User
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
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
def authed_client(client_with_db):
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


def test_request_reset_rate_limited(client_with_db):
    client, db = client_with_db
    email = "reset@test.com"
    user = User(email=email, password_hash=hash_password("pw"), role="owner", is_verified=True, is_active=True)
    db.add(user)
    db.commit()

    reset_request_limiter.limit = 2
    reset_request_limiter.reset(email, db=db)
    db.commit()
    try:
        r1 = client.post("/api/auth/request-reset", json={"email": email})
        r2 = client.post("/api/auth/request-reset", json={"email": email})
        r3 = client.post("/api/auth/request-reset", json={"email": email})
    finally:
        reset_request_limiter.reset(email, db=db)
        db.commit()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_request_verify_rate_limited(client_with_db):
    client, db = client_with_db
    email = "verify@test.com"
    user = User(email=email, password_hash=hash_password("pw"), role="owner", is_verified=False, is_active=True)
    db.add(user)
    db.commit()

    verify_request_limiter.limit = 2
    verify_request_limiter.reset(email, db=db)
    db.commit()
    try:
        r1 = client.post("/api/auth/request-verify", json={"email": email})
        r2 = client.post("/api/auth/request-verify", json={"email": email})
        r3 = client.post("/api/auth/request-verify", json={"email": email})
    finally:
        verify_request_limiter.reset(email, db=db)
        db.commit()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_invite_rate_limited(authed_client):
    client, db, ctx = authed_client
    invite_key = f"user:{ctx['user_id']}"
    invite_limiter.limit = 1
    invite_limiter.reset(invite_key, db=db)
    db.commit()

    payload = {"email": "guest1@test.com", "role": "manager", "password": "pw"}
    r1 = client.post("/api/users/invite", json=payload)
    r2 = client.post("/api/users/invite", json={"email": "guest2@test.com", "role": "manager", "password": "pw"})

    invite_limiter.reset(invite_key, db=db)
    db.commit()

    assert r1.status_code == 201
    assert r2.status_code == 429
