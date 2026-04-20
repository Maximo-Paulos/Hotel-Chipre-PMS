from __future__ import annotations

import logging
import smtplib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.user import User
from app.services import email_service
from app.services.security import hash_password


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
    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(fastapi_app) as client:
            yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
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


def test_register_verify_and_reset_do_not_expose_codes(client_and_db, fixed_code_patch):
    client, _db = client_and_db

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


def test_request_verify_confirms_success_only_after_smtp_send(client_and_db, fixed_code_patch, monkeypatch, caplog):
    client, db = client_and_db
    monkeypatch.setattr(
        email_service.mailer,
        "settings",
        Settings(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_USER="no-reply@example.com",
            SMTP_PASS="super-secret",
            SMTP_FROM="Hotel PMS <no-reply@example.com>",
        ),
    )

    class FakeSMTP:
        instances: list["FakeSMTP"] = []

        def __init__(self, host: str, port: int, timeout: int):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.started_tls = False
            self.logged_in = False
            self.sent_messages = []
            FakeSMTP.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, user: str, password: str):
            self.logged_in = True

        def send_message(self, message):
            self.sent_messages.append(message)

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    caplog.set_level(logging.INFO, logger="app.api.auth")
    caplog.set_level(logging.INFO, logger="app.services.email_service")

    db.add(User(email="smtp-ok@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=False, is_active=True))
    db.commit()

    request_verify = client.post("/api/auth/request-verify", json={"email": "smtp-ok@example.com"})
    assert request_verify.status_code == 200, request_verify.text
    assert request_verify.json() == {"sent": True}

    assert len(FakeSMTP.instances) == 1, "SMTP client was not instantiated exactly once"
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in is True
    assert len(smtp.sent_messages) == 1

    log_text = "\n".join(record.message for record in caplog.records)
    assert "request_verify smtp configured send attempted" in log_text
    assert "SMTP connection attempt" in log_text
    assert "SMTP authentication attempt" in log_text
    assert "SMTP authentication success" in log_text
    assert "SMTP send success" in log_text


def test_request_verify_logs_fallback_when_smtp_is_missing(client_and_db, caplog):
    client, db = client_and_db
    caplog.set_level(logging.INFO, logger="app.api.auth")

    db.add(User(email="fallback@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=False, is_active=True))
    db.commit()

    request_verify = client.post("/api/auth/request-verify", json={"email": "fallback@example.com"})
    assert request_verify.status_code == 200, request_verify.text
    assert request_verify.json() == {"sent": True}

    log_text = "\n".join(record.message for record in caplog.records)
    assert "request_verify smtp not configured fallback used" in log_text
    assert "code_exposed=False" in log_text


def test_request_verify_logs_noop_when_user_missing_or_verified(client_and_db, caplog):
    client, db = client_and_db
    caplog.set_level(logging.INFO, logger="app.api.auth")

    missing = client.post("/api/auth/request-verify", json={"email": "missing@example.com"})
    assert missing.status_code == 200, missing.text
    assert missing.json() == {"sent": True}

    db.add(User(email="verified@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=True, is_active=True))
    db.commit()

    verified = client.post("/api/auth/request-verify", json={"email": "verified@example.com"})
    assert verified.status_code == 200, verified.text
    assert verified.json() == {"sent": True}

    log_text = "\n".join(record.message for record in caplog.records)
    assert "request_verify no-op" in log_text
    assert "reason=not_found" in log_text
    assert "reason=already_verified" in log_text


def test_request_verify_logs_rate_limit_hit(client_and_db, monkeypatch, caplog):
    client, _db = client_and_db
    caplog.set_level(logging.INFO, logger="app.api.auth")

    monkeypatch.setattr("app.api.auth.verify_request_limiter.allow", lambda key, db=None: False)

    request_verify = client.post("/api/auth/request-verify", json={"email": "rate-limited@example.com"})
    assert request_verify.status_code == 429, request_verify.text

    log_text = "\n".join(record.message for record in caplog.records)
    assert "request_verify rate limit hit" in log_text


def test_request_verify_surfaces_smtp_failure(client_and_db, fixed_code_patch, monkeypatch, caplog):
    client, db = client_and_db
    monkeypatch.setattr(
        email_service.mailer,
        "settings",
        Settings(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_USER="no-reply@example.com",
            SMTP_PASS="super-secret",
            SMTP_FROM="Hotel PMS <no-reply@example.com>",
        ),
    )

    class FailingSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, user: str, password: str):
            return None

        def send_message(self, message):
            raise smtplib.SMTPException("550 5.7.1 relay denied")

    monkeypatch.setattr(email_service.smtplib, "SMTP", FailingSMTP)
    caplog.set_level(logging.INFO, logger="app.services.email_service")

    db.add(User(email="smtp-fail@example.com", password_hash=hash_password("Demo123!"), role="owner", is_verified=False, is_active=True))
    db.commit()

    request_verify = client.post("/api/auth/request-verify", json={"email": "smtp-fail@example.com"})
    assert request_verify.status_code == 502
    assert request_verify.json()["detail"] == "No se pudo enviar el email de verificacion"

    log_text = "\n".join(record.message for record in caplog.records)
    assert "SMTP connection attempt" in log_text
    assert "SMTP authentication attempt" in log_text
    assert "SMTP send failed" in log_text


def test_unverified_users_cannot_use_operational_endpoints(client_and_db, fixed_code_patch):
    client, _db = client_and_db

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
    client, _db = client_and_db

    resp = client.post("/api/email/verify?to=test@example.com")
    assert resp.status_code == 410


def test_pilot_auto_verify_skips_email_gating(client_and_db, monkeypatch):
    client, _db = client_and_db
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PILOT_AUTO_VERIFY", "true")
    monkeypatch.setenv("EXPOSE_AUTH_CODES_WHEN_NO_SMTP", "true")
    try:
        register = _register_owner(client, "pilot@example.com")
        assert register["requires_verification"] is False
        assert register["user"]["is_verified"] is True

        headers = _auth_headers(register)
        status_resp = client.get("/api/onboarding/status", headers=headers)
        assert status_resp.status_code == 200

        reset = client.post("/api/auth/request-reset", json={"email": "pilot@example.com"})
        assert reset.status_code == 200
        body = reset.json()
        assert body["sent"] is True
        assert "code" in body and len(body["code"]) == 6
    finally:
        get_settings.cache_clear()
