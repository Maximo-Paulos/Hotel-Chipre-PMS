from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.models.user_session import UserSession
from app.services import user_session_service
from app.services.security import create_access_token, hash_password


@pytest.fixture
def session_user(db: Session) -> User:
    user = User(
        email="session-service@example.test",
        password_hash=hash_password("Demo123!pass"),
        role="owner",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def session_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    user = User(
        email="session-api@example.test",
        password_hash=hash_password("Demo123!pass"),
        role="owner",
        is_verified=True,
        is_active=True,
        token_version=0,
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="Session Hotel", subscription_active=True),
            HotelMembership(hotel_id=1, user_id=user.id, role="owner", status="active"),
        ]
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, db, user
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _bearer_headers(payload: dict[str, object]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Hotel-Id": str(payload["hotel_id"]),
    }


def test_create_validate_and_rotate_session(session_user: User, db: Session):
    session, token, csrf = user_session_service.create_session(db, session_user)
    db.commit()

    assert session.session_token_hash != token
    assert token not in session.session_token_hash
    rotated = user_session_service.validate_and_touch_session(db, token, csrf, csrf)

    assert rotated is not None
    rotated_session, new_token = rotated
    assert rotated_session.id == session.id
    assert new_token != token
    db.commit()
    assert user_session_service.validate_and_touch_session(db, token, csrf, csrf) is None
    assert user_session_service.validate_and_touch_session(db, new_token, csrf, csrf) is not None


def test_absolute_expiration_rejects_and_revokes(session_user: User, db: Session, monkeypatch):
    base = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(user_session_service, "_now", lambda: base)
    session, token, csrf = user_session_service.create_session(db, session_user)
    db.commit()

    monkeypatch.setattr(
        user_session_service,
        "_now",
        lambda: base + user_session_service.USER_SESSION_ABSOLUTE_TTL + timedelta(seconds=1),
    )
    assert user_session_service.validate_and_touch_session(db, token, csrf, csrf) is None
    db.refresh(session)
    assert session.revoked_at is not None


def test_idle_expiration_rejects_and_revokes(session_user: User, db: Session, monkeypatch):
    base = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(user_session_service, "_now", lambda: base)
    session, token, csrf = user_session_service.create_session(db, session_user)
    session.last_seen_at = base - user_session_service.USER_SESSION_IDLE_TTL - timedelta(seconds=1)
    db.commit()

    assert user_session_service.validate_and_touch_session(db, token, csrf, csrf) is None
    db.refresh(session)
    assert session.revoked_at is not None


def test_csrf_invalid_and_double_submit_mismatch_are_rejected(session_user: User, db: Session):
    _session, token, csrf = user_session_service.create_session(db, session_user)
    db.commit()

    assert user_session_service.validate_and_touch_session(db, token, "wrong", csrf) is None
    assert user_session_service.validate_and_touch_session(db, token, csrf, "different") is None
    assert user_session_service.validate_and_touch_session(db, token, "wrong", None) is None


def test_individual_revocation_leaves_another_session_alive(session_user: User, db: Session):
    first, first_token, first_csrf = user_session_service.create_session(db, session_user)
    second, second_token, second_csrf = user_session_service.create_session(db, session_user)
    db.commit()

    assert user_session_service.revoke_session(db, first.id, session_user.id) is not None
    db.commit()
    assert user_session_service.validate_and_touch_session(db, first_token, first_csrf, first_csrf) is None
    assert user_session_service.validate_and_touch_session(db, second_token, second_csrf, second_csrf) is not None
    assert [row.id for row in user_session_service.list_active_sessions(db, session_user.id)] == [second.id]


def test_global_revocation_invalidates_all_sessions(session_user: User, db: Session):
    sessions = [user_session_service.create_session(db, session_user) for _ in range(2)]
    db.commit()

    assert user_session_service.revoke_all_sessions(db, session_user.id) == 2
    db.commit()
    assert user_session_service.list_active_sessions(db, session_user.id) == []
    for _session, token, csrf in sessions:
        assert user_session_service.validate_and_touch_session(db, token, csrf, csrf) is None


def test_user_session_cookie_cannot_disable_secure_in_production(monkeypatch):
    monkeypatch.setattr(
        user_session_service,
        "get_settings",
        lambda: type("ProductionSettings", (), {"USER_SESSION_COOKIE_SECURE": False})(),
    )
    monkeypatch.setattr(user_session_service, "is_production_mode", lambda settings=None: True)
    response = Response()

    user_session_service.set_user_session_cookies(response, "session-token", "csrf-token")

    cookie_headers = [
        value.decode("latin-1").lower()
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]
    assert cookie_headers
    assert all("secure" in header for header in cookie_headers)


def test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(session_client):
    client, db, user = session_client
    login = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Demo123!pass"},
        headers={
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36"
            )
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert set(body) == {
        "access_token",
        "token_type",
        "hotel_id",
        "hotel_ids",
        "user",
        "permissions",
        "requires_verification",
        "csrf_token",
    }
    assert client.cookies.get(user_session_service.USER_SESSION_COOKIE_NAME)
    assert client.cookies.get(user_session_service.USER_CSRF_COOKIE_NAME)
    # The API and the SPA are cross-site (Render vs Vercel): the frontend
    # can never read the CSRF cookie via document.cookie, so the raw value
    # must also come back in the JSON body -- this is the only channel it
    # has to learn it.
    assert body["csrf_token"] == client.cookies.get(user_session_service.USER_CSRF_COOKIE_NAME)
    stored = db.query(UserSession).one()
    assert stored.session_token_hash != client.cookies.get(user_session_service.USER_SESSION_COOKIE_NAME)
    assert stored.device_label == "Chrome en Windows"

    bearer_response = client.get("/api/auth/me", headers=_bearer_headers(body))
    assert bearer_response.status_code == 200, bearer_response.text
    assert bearer_response.json()["email"] == user.email


def test_refresh_rotates_cookie_and_returns_same_auth_shape(session_client):
    client, db, user = session_client
    login = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    old_token = client.cookies.get(user_session_service.USER_SESSION_COOKIE_NAME)
    csrf = client.cookies.get(user_session_service.USER_CSRF_COOKIE_NAME)

    refresh = client.post("/api/auth/session/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh.status_code == 200, refresh.text
    assert set(refresh.json()) == set(login.json())
    new_token = client.cookies.get(user_session_service.USER_SESSION_COOKIE_NAME)
    assert old_token and new_token and new_token != old_token
    assert db.query(UserSession).count() == 1

    assert client.post(
        "/api/auth/session/refresh",
        headers={"X-CSRF-Token": "not-the-cookie"},
    ).status_code == 401


def test_session_listing_individual_revoke_logout_and_revoke_all(session_client):
    client, db, user = session_client
    login = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    headers = _bearer_headers(login.json())
    current_session = db.query(UserSession).one()
    _other_session, _other_token, _other_csrf = user_session_service.create_session(db, user)
    db.commit()

    listed = client.get("/api/auth/sessions", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 2
    assert sum(item["current"] for item in listed.json()) == 1
    assert all({"id", "created_at", "last_seen_at", "device_label", "current"} <= set(item) for item in listed.json())

    other_id = next(item["id"] for item in listed.json() if item["id"] != current_session.id)
    revoked = client.delete(f"/api/auth/sessions/{other_id}", headers=headers)
    assert revoked.status_code == 200, revoked.text
    db.refresh(user)
    assert user.token_version == 1
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    # The current cookie session remains active and can issue a fresh bearer
    # after the targeted server-side revoke invalidates the old JWT plane.
    csrf = client.cookies.get(user_session_service.USER_CSRF_COOKIE_NAME)
    refreshed = client.post("/api/auth/session/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200, refreshed.text
    fresh_headers = _bearer_headers(refreshed.json())
    assert len(client.get("/api/auth/sessions", headers=fresh_headers).json()) == 1

    logged_out = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 200, logged_out.text
    db.refresh(current_session)
    assert current_session.revoked_at is not None
    db.refresh(user)
    assert user.token_version == 2
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/auth/me", headers=fresh_headers).status_code == 401

    # Re-create a browser session and verify the pre-existing token_version
    # control also revokes the server-side session plane.
    login_again = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Demo123!pass"},
    )
    assert login_again.status_code == 200, login_again.text
    session_before_global = db.query(UserSession).filter(UserSession.revoked_at.is_(None)).one()
    global_revoke = client.post(
        "/api/settings/security/revoke-all",
        headers=_bearer_headers(login_again.json()),
    )
    assert global_revoke.status_code == 200, global_revoke.text
    db.refresh(session_before_global)
    assert session_before_global.revoked_at is not None
    assert client.post(
        "/api/auth/session/refresh",
        headers={"X-CSRF-Token": client.cookies.get(user_session_service.USER_CSRF_COOKIE_NAME)},
    ).status_code == 401
    assert client.get("/api/auth/me", headers=_bearer_headers(login_again.json())).status_code == 401
