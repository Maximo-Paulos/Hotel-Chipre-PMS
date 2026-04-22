from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.config import get_settings
from app.database import Base, get_db
from app.master_admin.billing_policy import evaluate_hotel_write_access
from app.master_admin.email_provider import connect_system_email
from app.master_admin.models import MasterAdminAuditEvent, MasterStripeWebhookEvent
from app.models.hotel_config import HotelConfiguration
from app.models.subscription_v2 import Subscription
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


@pytest.fixture
def master_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
    db_module.init_db("sqlite:///:memory:")
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db("sqlite:///:memory:"))
    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as client:
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_platform_admin(db, email: str = "platform-admin@example.com") -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password("Master123!"),
            is_active=True,
            is_verified=True,
            role="platform_admin",
        )
        db.add(user)
        db.flush()
    return user


def _seed_hotel(db, hotel_id: int = 1, name: str = "Hotel Uno") -> HotelConfiguration:
    hotel = db.get(HotelConfiguration, hotel_id)
    if not hotel:
        hotel = HotelConfiguration(id=hotel_id, hotel_name=name, owner_email="owner@example.com", subscription_active=True)
        db.add(hotel)
        db.flush()
    return hotel


def _seed_subscription(db, hotel_id: int, status: str = "suspended") -> Subscription:
    subscription = db.query(Subscription).filter(Subscription.hotel_id == hotel_id).first()
    if not subscription:
        subscription = Subscription(
            hotel_id=hotel_id,
            plan="starter",
            status=status,
            room_limit=15,
            staff_limit=3,
            can_write_cache=False,
        )
        db.add(subscription)
        db.flush()
    else:
        subscription.status = status
        subscription.can_write_cache = False
    return subscription


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
        if url == "https://api.stripe.com/v1/account":
            return FakeResponse(True, {"id": "acct_123", "display_name": "Owner Stripe"})
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr("app.master_admin.email_provider.requests.post", fake_post)
    monkeypatch.setattr("app.master_admin.email_provider.requests.get", fake_get)
    monkeypatch.setattr("app.master_admin.stripe.requests.get", fake_get)
    monkeypatch.setattr("app.master_admin.stripe.requests.post", fake_post)


def _seed_master_email(db, monkeypatch: pytest.MonkeyPatch):
    _configure_gmail(monkeypatch)
    connect_system_email(db, "auth-code-123")
    db.commit()


def test_master_login_sets_cookie_and_hydrates_me(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["role"] == "platform_admin"
    assert "master_admin_session" in response.cookies

    me = client.get("/api/master-admin/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "platform-admin@example.com"


def test_master_login_locks_out_after_repeated_failures(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()

    for _ in range(5):
        failed = client.post(
            "/api/master-admin/auth/login",
            json={"email": "platform-admin@example.com", "password": "WrongPass!", "pin": "654321"},
        )
        assert failed.status_code == 401, failed.text

    locked = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert locked.status_code == 429, locked.text


def test_master_policy_update_exempts_hotel_and_user(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        _seed_hotel(db, hotel_id=1)
        _seed_subscription(db, hotel_id=1, status="suspended")
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text
    csrf_token = login.cookies.get("master_admin_csrf")
    assert csrf_token

    update = client.put(
        "/api/master-admin/billing/policy",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "enabled": True,
            "allow_active": True,
            "allow_trialing": True,
            "exempt_hotel_ids": [1],
            "exempt_user_ids": [99],
            "notes": "pilot exemption",
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["exempt_hotel_ids"] == [1]
    assert update.json()["exempt_user_ids"] == [99]

    hotels = client.get("/api/master-admin/dashboard/hotels")
    assert hotels.status_code == 200, hotels.text
    row = next(item for item in hotels.json()["items"] if item["hotel_id"] == 1)
    assert row["can_write"] is True
    assert row["reason"] == "exempt"

    db = SessionLocal()
    try:
        decision = evaluate_hotel_write_access(db, 1, snapshot={"status": "suspended", "plan": "starter", "user_id": 99})
        assert decision.can_write is True
        assert decision.reason == "exempt"
        assert db.query(MasterAdminAuditEvent).filter(MasterAdminAuditEvent.action == "master_admin_update_billing_policy").count() == 1
    finally:
        db.close()


def test_master_email_connect_test_and_disconnect(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    _configure_gmail(monkeypatch)
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text
    csrf_token = login.cookies.get("master_admin_csrf")
    assert csrf_token

    connect = client.post("/api/master-admin/email/connect", headers={"X-CSRF-Token": csrf_token}, json={})
    assert connect.status_code == 200, connect.text
    redirect_url = connect.json()["redirect_url"]
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    state = params["state"][0]

    callback = client.get(f"/api/master-admin/email/oauth/gmail/callback?code=auth-code-123&state={state}")
    assert callback.status_code == 200, callback.text
    assert "master-admin-email-oauth-result" in callback.text

    status_resp = client.get("/api/master-admin/email/status")
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["configured"] is True
    assert status_resp.json()["connected_account_email"] == "owner-mail@example.com"

    test = client.post(
        "/api/master-admin/email/test",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "recipient": "ops@example.com",
            "subject": "test",
            "body": "hello",
        },
    )
    assert test.status_code == 200, test.text
    assert test.json()["ok"] is True

    disconnect = client.post("/api/master-admin/email/disconnect", headers={"X-CSRF-Token": csrf_token}, json={})
    assert disconnect.status_code == 200, disconnect.text
    assert disconnect.json()["configured"] is False


def test_master_stripe_connect_and_webhook_signature_is_verified(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    _configure_gmail(monkeypatch)
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text
    csrf_token = login.cookies.get("master_admin_csrf")
    assert csrf_token

    connect = client.post(
        "/api/master-admin/stripe/connect",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "stripe_secret_key": "sk_test_123",
            "webhook_secret": "whsec_test_secret",
            "enabled": True,
        },
    )
    assert connect.status_code == 200, connect.text
    assert connect.json()["configured"] is True
    assert connect.json()["webhook_secret_configured"] is True

    payload = {"id": "evt_123", "type": "invoice.paid"}
    body = json.dumps(payload, separators=(",", ":"))
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{body}"
    signature = hmac.new(b"whsec_test_secret", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"

    response = client.post(
        "/api/master-admin/stripe/webhook",
        content=body,
        headers={"Stripe-Signature": header, "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["received"] is True

    db = SessionLocal()
    try:
        stored = db.query(MasterStripeWebhookEvent).filter(MasterStripeWebhookEvent.event_id == "evt_123").first()
        assert stored is not None
        assert stored.delivery_status == "processed"
    finally:
        db.close()
