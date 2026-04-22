from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base, get_db
from app.master_admin.email_provider import connect_system_email
from app.models.user import User
from app.services.security import hash_password


@dataclass
class FakeResponse:
    ok: bool
    payload: dict
    text: str = ""

    @property
    def content(self):
        return b"{}"

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.text or "request failed")


@pytest.fixture
def client_and_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
    db_module.init_db("sqlite:///:memory:")
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db("sqlite:///:memory:"))
    main_module.app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(main_module.app) as client:
            yield client, db, SessionLocal
    finally:
        main_module.app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.fixture
def fixed_code_patch():
    with patch("app.api.auth._generate_code", return_value="123456"), patch(
        "app.api.email._generate_code", return_value="123456"
    ):
        yield


def _register_owner(client: TestClient, email: str):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Demo123!", "role": "owner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(auth_payload: dict[str, object]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {auth_payload['access_token']}",
        "X-Hotel-Id": str(auth_payload["hotel_id"]),
        "X-User-Id": auth_payload["user"]["email"],
    }


def _configure_gmail(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GMAIL_CLIENT_ID", "client-id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("MASTER_EMAIL_GMAIL_REDIRECT_URI", "https://example.com/api/master-admin/email/oauth/gmail/callback")
    get_settings.cache_clear()

    def fake_post(url, data=None, headers=None, json=None, timeout=None):
        if url == "https://oauth2.googleapis.com/token":
            return FakeResponse(
                True,
                {
                    "access_token": "access-123",
                    "refresh_token": "refresh-123",
                    "expires_in": 3600,
                    "scope": "openid email profile https://www.googleapis.com/auth/gmail.send",
                },
            )
        if url == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
            return FakeResponse(True, {"id": "msg-123"})
        raise AssertionError(f"Unexpected POST {url}")

    def fake_get(url, headers=None, timeout=None):
        if url == "https://openidconnect.googleapis.com/v1/userinfo":
            return FakeResponse(True, {"email": "owner-mail@example.com", "name": "Owner Mail", "sub": "google-sub"})
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr("app.master_admin.email_provider.requests.post", fake_post)
    monkeypatch.setattr("app.master_admin.email_provider.requests.get", fake_get)


def _seed_connected_email(db, monkeypatch: pytest.MonkeyPatch):
    _configure_gmail(monkeypatch)
    connect_system_email(db, "auth-code-123")
    db.commit()


def test_register_verify_and_reset_use_connected_gmail_provider(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    _seed_connected_email(db, monkeypatch)

    register = _register_owner(client, "owner@example.com")
    assert "code" not in register
    assert register["requires_verification"] is True

    request_verify = client.post("/api/auth/request-verify", json={"email": "owner@example.com"})
    assert request_verify.status_code == 200
    assert request_verify.json() == {"sent": True}

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": "owner@example.com", "code": "123456"},
    )
    assert verify.status_code == 200, verify.text
    verified = verify.json()
    assert verified["requires_verification"] is False

    reset_known = client.post("/api/auth/request-reset", json={"email": "owner@example.com"})
    assert reset_known.status_code == 200
    assert reset_known.json() == {"sent": True}

    reset_unknown = client.post("/api/auth/request-reset", json={"email": "unknown@example.com"})
    assert reset_unknown.status_code == 200
    assert reset_unknown.json() == {"sent": True}


def test_auth_flows_fail_without_connected_mail_provider(client_and_db, fixed_code_patch):
    client, db, _session_factory = client_and_db

    failed_register = client.post(
        "/api/auth/register",
        json={"email": "blocked@example.com", "password": "Demo123!", "role": "owner"},
    )
    assert failed_register.status_code == 503
    assert "Gmail" in failed_register.json()["detail"] or "Conecta Gmail" in failed_register.json()["detail"]

    db.add(User(email="pending@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=False, is_active=True))
    db.commit()

    failed_request_verify = client.post("/api/auth/request-verify", json={"email": "pending@example.com"})
    assert failed_request_verify.status_code == 503

    db.add(User(email="reset@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=True, is_active=True))
    db.commit()

    failed_request_reset = client.post("/api/auth/request-reset", json={"email": "reset@example.com"})
    assert failed_request_reset.status_code == 503


def test_unverified_users_cannot_use_operational_endpoints(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    _seed_connected_email(db, monkeypatch)

    register = _register_owner(client, "blocked@example.com")
    headers = _auth_headers(register)

    blocked = client.get("/api/onboarding/status", headers=headers)
    assert blocked.status_code == 403
    assert "Verifica tu email" in blocked.json()["detail"]

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": "blocked@example.com", "code": "123456"},
    )
    assert verify.status_code == 200, verify.text

    allowed = client.get("/api/onboarding/status", headers=headers)
    assert allowed.status_code == 200, allowed.text


def test_legacy_public_email_endpoints_are_retired(client_and_db):
    client, _db, _session_factory = client_and_db

    resp = client.post("/api/email/verify?to=test@example.com")
    assert resp.status_code == 410
