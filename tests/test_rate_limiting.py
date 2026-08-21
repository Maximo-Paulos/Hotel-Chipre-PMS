# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa: F401
from app.adapters.rate_limiter import (
    SimpleRateLimiter,
    verify_request_limiter,
    reset_request_limiter,
    invite_limiter,
    invitation_accept_limiter,
    invitation_preview_limiter,
    code_guess_limiter,
    register_limiter,
)
from app.models.rate_limit_event import RateLimitEvent
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


def test_verify_email_code_guessing_is_rate_limited(client_with_db):
    """Guessing the 6-digit verification code must itself be throttled, not
    just requests for a new code."""
    client, db = client_with_db
    email = "guess-verify@test.com"
    user = User(email=email, password_hash=hash_password("pw"), role="owner", is_verified=False, is_active=True)
    db.add(user)
    db.commit()

    code_guess_limiter.limit = 3
    code_guess_limiter.reset("email_verification:" + email, db=db)
    db.commit()
    try:
        responses = [
            client.post("/api/auth/verify-email", json={"email": email, "code": "000000"})
            for _ in range(4)
        ]
    finally:
        code_guess_limiter.reset("email_verification:" + email, db=db)
        db.commit()

    assert [r.status_code for r in responses[:3]] == [400, 400, 400]
    assert responses[3].status_code == 429


def test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate(client_with_db):
    """validate-reset (no-op check) and reset-password (consumes the code)
    guess the same password_reset code, so they must share one attempt
    budget - otherwise validate-reset alone lets an attacker brute force
    the code for free before ever touching reset-password."""
    client, db = client_with_db
    email = "guess-reset@test.com"
    user = User(email=email, password_hash=hash_password("pw"), role="owner", is_verified=True, is_active=True)
    db.add(user)
    db.commit()

    code_guess_limiter.limit = 3
    code_guess_limiter.reset("password_reset:" + email, db=db)
    db.commit()
    try:
        r1 = client.post("/api/auth/validate-reset", json={"email": email, "code": "000000"})
        r2 = client.post("/api/auth/validate-reset", json={"email": email, "code": "000000"})
        r3 = client.post(
            "/api/auth/reset-password",
            json={"email": email, "code": "000000", "new_password": "Demo1234!pass"},
        )
        r4 = client.post(
            "/api/auth/reset-password",
            json={"email": email, "code": "000000", "new_password": "Demo1234!pass"},
        )
    finally:
        code_guess_limiter.reset("password_reset:" + email, db=db)
        db.commit()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 400
    assert r4.status_code == 429


def test_register_is_rate_limited_by_source(client_with_db):
    """Registration had no throttle at all: an attacker could farm unlimited
    accounts / spam verification emails to arbitrary distinct addresses from
    a single source with no cap."""
    client, db = client_with_db

    register_limiter.limit = 3
    register_limiter.reset("testclient", db=db)
    db.commit()
    try:
        responses = [
            client.post(
                "/api/auth/register",
                json={"email": f"farmed-{i}@test.com", "password": "Demo123!pass"},
            )
            for i in range(4)
        ]
    finally:
        register_limiter.reset("testclient", db=db)
        db.commit()

    assert [r.status_code for r in responses[:3]] == [201, 201, 201]
    assert responses[3].status_code == 429


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


def test_invitation_preview_and_acceptance_are_rate_limited(client_with_db):
    client, db = client_with_db
    preview_limit = invitation_preview_limiter.limit
    accept_limit = invitation_accept_limiter.limit
    invitation_preview_limiter.limit = 1
    invitation_accept_limiter.limit = 1
    invitation_preview_limiter.reset("testclient", db=db)
    invitation_accept_limiter.reset("testclient", db=db)
    db.commit()

    try:
        preview_one = client.get("/api/invitations/not-a-valid-token")
        preview_two = client.get("/api/invitations/not-a-valid-token")
        accept_one = client.post(
            "/api/invitations/not-a-valid-token/accept",
            json={"email": "invite@test.com", "password": "NewPassword123!"},
        )
        accept_two = client.post(
            "/api/invitations/not-a-valid-token/accept",
            json={"email": "invite@test.com", "password": "NewPassword123!"},
        )
    finally:
        invitation_preview_limiter.reset("testclient", db=db)
        invitation_accept_limiter.reset("testclient", db=db)
        db.commit()
        invitation_preview_limiter.limit = preview_limit
        invitation_accept_limiter.limit = accept_limit

    # A garbage token is invalid, not an authentication failure -- the new
    # persisted-invitation lookup (TECH-0031) reports "not found" as 400,
    # not 401. The rate limit itself (asserted below) is what this test
    # actually covers.
    assert preview_one.status_code == 400
    assert preview_two.status_code == 429
    assert accept_one.status_code == 400
    assert accept_two.status_code == 429


def test_concurrent_db_requests_record_each_attempt_before_deciding(tmp_path):
    """Concurrent attempts share the same budget instead of racing on a pre-count."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'rate-limit-race.sqlite').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine, tables=[RateLimitEvent.__table__])
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    limiter = SimpleRateLimiter("concurrent-test", limit=3)
    request_count = 8
    all_requests_ready = Barrier(request_count)

    def allow_request():
        with SessionLocal() as session:
            all_requests_ready.wait(timeout=10)
            allowed = limiter.allow("same-key", db=session)
            session.commit()
            return allowed

    try:
        with ThreadPoolExecutor(max_workers=request_count) as executor:
            results = list(executor.map(lambda _unused: allow_request(), range(request_count)))

        assert sum(results) <= limiter.limit

        with SessionLocal() as session:
            recorded_attempts = (
                session.query(RateLimitEvent)
                .filter(
                    RateLimitEvent.scope == limiter.scope,
                    RateLimitEvent.subject_key == "same-key",
                )
                .count()
            )
            assert recorded_attempts == request_count
    finally:
        Base.metadata.drop_all(bind=engine, tables=[RateLimitEvent.__table__])
        engine.dispose()
