from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
import pytest
import pyotp
from fastapi.testclient import TestClient
from starlette.responses import Response
from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.config import get_settings
from app.database import Base, get_db
from app.master_admin.billing_policy import evaluate_hotel_write_access
from app.master_admin.models import MasterAdminAuditEvent, MasterStripeWebhookEvent
import app.master_admin.security as master_security
from app.models.hotel_config import HotelConfiguration
from app.models.subscription_v2 import Subscription
from app.models.user import User
from app.services.security import hash_password


@pytest.fixture(autouse=True)
def _enable_mocked_master_providers(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


def _configure_resend(monkeypatch: pytest.MonkeyPatch, sent_payloads: list[dict] | None = None):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("SYSTEM_EMAIL_FROM", "Hotel Chipre PMS <noreply@auth.hotels-pms.com>")
    monkeypatch.setenv("SYSTEM_EMAIL_REPLY_TO", "hotelxpms@gmail.com")
    get_settings.cache_clear()
    payloads = sent_payloads if sent_payloads is not None else []

    def fake_post(url, data=None, headers=None, json=None, timeout=None):
        if url == "https://api.resend.com/emails":
            payloads.append(json or {})
            return FakeResponse(True, {"id": "resend-message-123"})
        raise AssertionError(f"Unexpected POST {url}")

    def fake_get(url, headers=None, timeout=None):
        if url == "https://openidconnect.googleapis.com/v1/userinfo":
            return FakeResponse(True, {"email": "owner-mail@example.com", "name": "Owner Mail", "sub": "google-sub"})
        if url == "https://api.stripe.com/v1/account":
            return FakeResponse(True, {"id": "acct_123", "display_name": "Owner Stripe"})
        raise AssertionError(f"Unexpected GET {url}")

    monkeypatch.setattr("app.services.email.providers.requests.post", fake_post)
    monkeypatch.setattr("app.master_admin.stripe.requests.get", fake_get)
    monkeypatch.setattr("app.master_admin.stripe.requests.post", fake_post)
    return payloads


def test_master_login_bootstraps_env_account(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_EMAIL", "owner-admin@example.com")
    monkeypatch.setenv("MASTER_ADMIN_PASSWORD", "Secret123!")
    monkeypatch.setenv("MANAGER_PIN", "654321")
    get_settings.cache_clear()

    response = client.post(
        "/api/master-admin/auth/login",
        json={"email": "owner-admin@example.com", "password": "Secret123!", "pin": "654321"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["role"] == "platform_admin"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "owner-admin@example.com").first()
        assert user is not None
        assert user.role == "platform_admin"
        assert user.is_active is True
        assert user.is_verified is True
    finally:
        db.close()


def test_master_audit_redacts_sensitive_metadata_on_storage_and_read(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        admin = _seed_platform_admin(db)
        master_security.audit_master_action(
            db,
            actor_user_id=admin.id,
            action="sensitive_metadata_test",
            metadata={
                "email": "alice@example.com",
                "recipient": "guest@example.com",
                "sender_email": "sender@example.com",
                "reply_to": "reply@example.com",
                "password": "do-not-store",
                "token": "token-do-not-store",
                "secret": "secret-do-not-store",
                "code": "123456",
                "plan_code": "pro",
                "nested": {"access_token": "nested-token-do-not-store"},
            },
        )
        db.commit()
        event = db.query(MasterAdminAuditEvent).filter(MasterAdminAuditEvent.action == "sensitive_metadata_test").one()
        stored_metadata_json = event.metadata_json
        stored_metadata = json.loads(stored_metadata_json or "{}")
    finally:
        db.close()

    assert stored_metadata == {
        "code": "[REDACTED]",
        "email": "a***@example.com",
        "nested": {"access_token": "[REDACTED]"},
        "password": "[REDACTED]",
        "plan_code": "pro",
        "recipient": "g***@example.com",
        "reply_to": "r***@example.com",
        "secret": "[REDACTED]",
        "sender_email": "s***@example.com",
        "token": "[REDACTED]",
    }
    assert "do-not-store" not in stored_metadata_json

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text

    response = client.get("/api/master-admin/audit/events")
    assert response.status_code == 200, response.text
    api_event = next(item for item in response.json()["items"] if item["action"] == "sensitive_metadata_test")
    assert json.loads(api_event["metadata_json"]) == stored_metadata


def test_master_bootstrap_login_does_not_hijack_existing_non_admin_account(master_client, monkeypatch):
    """
    If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login
    email (an operator config mistake, but a plausible one), bootstrap
    login must not silently overwrite that tenant's password and promote
    them to platform_admin - it must fail closed instead.
    """
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_EMAIL", "shared@example.com")
    monkeypatch.setenv("MASTER_ADMIN_PASSWORD", "Secret123!")
    monkeypatch.setenv("MANAGER_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        tenant = User(
            email="shared@example.com",
            password_hash=hash_password("TenantOwnPassword!"),
            is_active=True,
            is_verified=True,
            role="owner",
        )
        db.add(tenant)
        db.commit()
        original_hash = tenant.password_hash
    finally:
        db.close()

    response = client.post(
        "/api/master-admin/auth/login",
        json={"email": "shared@example.com", "password": "Secret123!", "pin": "654321"},
    )
    assert response.status_code != 200, response.text

    db = SessionLocal()
    try:
        tenant = db.query(User).filter(User.email == "shared@example.com").first()
        assert tenant.role == "owner"
        assert tenant.password_hash == original_hash
    finally:
        db.close()


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
    assert response.cookies.get("master_admin_session_hint") == "1"

    me = client.get("/api/master-admin/auth/me")
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["user"]["email"] == "platform-admin@example.com"
    assert payload["csrf_token"]


def test_master_admin_optional_mfa_enroll_confirm_login_and_disable(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
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
    headers = {"X-CSRF-Token": csrf_token}

    reauth_rejected = client.post(
        "/api/master-admin/mfa/enroll",
        headers=headers,
        json={"password": "wrong-password"},
    )
    assert reauth_rejected.status_code == 401, reauth_rejected.text

    enroll = client.post(
        "/api/master-admin/mfa/enroll",
        headers=headers,
        json={"password": "Master123!"},
    )
    assert enroll.status_code == 200, enroll.text
    enrollment = enroll.json()
    assert enrollment["status"] == "pending"
    assert enrollment["secret"]
    assert enrollment["otpauth_uri"].startswith("otpauth://totp/")

    invalid_confirm = client.post(
        "/api/master-admin/mfa/enroll/confirm",
        headers=headers,
        json={"code": "not-a-code"},
    )
    assert invalid_confirm.status_code == 400, invalid_confirm.text

    totp = pyotp.TOTP(enrollment["secret"])
    confirm = client.post(
        "/api/master-admin/mfa/enroll/confirm",
        headers=headers,
        json={"code": totp.now()},
    )
    assert confirm.status_code == 200, confirm.text
    recovery_codes = confirm.json()["recovery_codes"]
    assert len(recovery_codes) == 10

    logout = client.post("/api/master-admin/auth/logout", headers=headers)
    assert logout.status_code == 200, logout.text

    mfa_login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert mfa_login.status_code == 200, mfa_login.text
    challenge = mfa_login.json()
    assert challenge["requires_mfa"] is True
    assert challenge["expires_in"] == 5 * 60
    assert "master_admin_session" not in mfa_login.cookies
    assert client.get("/api/master-admin/auth/me").status_code == 401

    mfa_login_complete = client.post(
        "/api/master-admin/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": recovery_codes[0]},
    )
    assert mfa_login_complete.status_code == 200, mfa_login_complete.text
    assert mfa_login_complete.cookies.get("master_admin_session")
    csrf_token = mfa_login_complete.cookies.get("master_admin_csrf")
    headers = {"X-CSRF-Token": csrf_token}

    wrong_password = client.post(
        "/api/master-admin/mfa/disable",
        headers=headers,
        json={"password": "wrong-password", "code": recovery_codes[1]},
    )
    assert wrong_password.status_code == 401, wrong_password.text

    invalid_disable_code = client.post(
        "/api/master-admin/mfa/disable",
        headers=headers,
        json={"password": "Master123!", "code": "not-a-code"},
    )
    assert invalid_disable_code.status_code == 401, invalid_disable_code.text

    disable = client.post(
        "/api/master-admin/mfa/disable",
        headers=headers,
        json={"password": "Master123!", "code": recovery_codes[1]},
    )
    assert disable.status_code == 200, disable.text
    assert disable.json() == {"disabled": True}

    no_mfa_login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert no_mfa_login.status_code == 200, no_mfa_login.text
    assert no_mfa_login.json()["user"]["role"] == "platform_admin"

    db = SessionLocal()
    try:
        actions = [event.action for event in db.query(MasterAdminAuditEvent).all()]
    finally:
        db.close()
    assert "master_admin_mfa_enroll" in actions
    assert "master_admin_mfa_confirm" in actions
    assert "master_admin_mfa_disable" in actions


def test_master_login_cookie_works_on_underscore_alias(master_client, monkeypatch):
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
    assert "Path=/api/" in response.headers.get("set-cookie", "")

    me = client.get("/api/master_admin/auth/me")
    assert me.status_code == 200, me.text
    summary = client.get("/api/master_admin/dashboard/summary")
    assert summary.status_code == 200, summary.text
    hotels = client.get("/api/master_admin/dashboard/hotels")
    assert hotels.status_code == 200, hotels.text


def test_master_dashboard_summary_counts_subscriptions_across_hotels(master_client, monkeypatch):
    """C2 regression (SQLite, syntactic only -- RLS is a Postgres-only concern,
    see tests/test_master_admin_rls_bypass_pg.py for the functional proof).

    Confirms wiring set_master_admin_context(db) into require_master_admin
    didn't break the existing request flow: with subscriptions seeded across
    three different hotels, the dashboard summary must still count every
    hotel's row, not just one.
    """
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        _seed_hotel(db, hotel_id=1, name="Hotel Uno")
        _seed_hotel(db, hotel_id=2, name="Hotel Dos")
        _seed_hotel(db, hotel_id=3, name="Hotel Tres")
        _seed_subscription(db, hotel_id=1, status="active")
        _seed_subscription(db, hotel_id=2, status="trialing")
        _seed_subscription(db, hotel_id=3, status="past_due")
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text

    summary = client.get("/api/master-admin/dashboard/summary")
    assert summary.status_code == 200, summary.text
    counts = summary.json()["counts"]
    assert counts["hotels"] == 3
    assert counts["active_subscriptions"] == 1
    assert counts["trialing"] == 1
    assert counts["past_due"] == 1

    hotels = client.get("/api/master-admin/dashboard/hotels")
    assert hotels.status_code == 200, hotels.text
    items = hotels.json()["items"]
    assert {item["hotel_id"] for item in items} == {1, 2, 3}
    assert all("owner_email" not in item for item in items)


def test_require_master_admin_sets_master_admin_rls_context(master_client, monkeypatch):
    """Wiring proof: every authenticated master-admin call must set the RLS
    bypass context (app/services/tenant_context.py::set_master_admin_context)
    before touching any endpoint logic -- not just some endpoints.
    """
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        _seed_platform_admin(db)
        db.commit()
    finally:
        db.close()

    calls: list[object] = []
    original = master_security.set_master_admin_context

    def _spy(db_arg, *args, **kwargs):
        calls.append(db_arg)
        return original(db_arg, *args, **kwargs)

    monkeypatch.setattr(master_security, "set_master_admin_context", _spy)

    login = client.post(
        "/api/master-admin/auth/login",
        json={"email": "platform-admin@example.com", "password": "Master123!", "pin": "654321"},
    )
    assert login.status_code == 200, login.text
    # login doesn't call require_master_admin (it's the endpoint that creates
    # the session), so the spy should still be empty here.
    assert calls == []

    me = client.get("/api/master-admin/auth/me")
    assert me.status_code == 200, me.text
    assert len(calls) == 1

    summary = client.get("/api/master-admin/dashboard/summary")
    assert summary.status_code == 200, summary.text
    assert len(calls) == 2


def test_master_session_cookie_uses_cross_site_settings_in_production(monkeypatch):
    monkeypatch.setattr(master_security, "is_production_mode", lambda settings=None: True)
    response = Response()

    master_security.set_master_session_cookies(response, "session-token", "csrf-token")

    cookie_headers = [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]
    normalized_headers = [header.lower() for header in cookie_headers]
    assert any("master_admin_session=session-token" in header for header in normalized_headers)
    assert any("samesite=none" in header and "secure" in header for header in normalized_headers)
    assert any("path=/api/" in header for header in normalized_headers)


def test_master_session_cookie_defaults_secure_in_preview(monkeypatch):
    monkeypatch.setattr(
        master_security,
        "get_settings",
        lambda: type("PreviewSettings", (), {"MASTER_ADMIN_COOKIE_SECURE": None})(),
    )
    monkeypatch.setattr(master_security, "is_production_mode", lambda settings=None: False)
    monkeypatch.setattr(master_security, "is_preview_qa_mode", lambda settings=None: True)
    response = Response()

    master_security.set_master_session_cookies(response, "session-token", "csrf-token")

    headers = [
        value.decode("latin-1").lower()
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]
    assert any("samesite=none" in header and "secure" in header for header in headers)


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


@pytest.mark.parametrize(
    ("path", "action"),
    [
        ("/api/master-admin/email/connect", "master_admin_email_connect"),
        ("/api/master-admin/email/disconnect", "master_admin_email_disconnect"),
    ],
)
def test_master_retired_email_actions_are_csrf_protected_and_audited(master_client, monkeypatch, path, action):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        admin = _seed_platform_admin(db)
        admin_id = admin.id
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

    missing_csrf = client.post(path)
    assert missing_csrf.status_code == 403, missing_csrf.text

    response = client.post(path, headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 410, response.text

    db = SessionLocal()
    try:
        event = db.query(MasterAdminAuditEvent).filter(MasterAdminAuditEvent.action == action).one()
        assert event.actor_user_id == admin_id
        assert event.outcome == "failed"
        assert event.target_type is None
        assert event.target_id is None
        assert event.request_path == path
        assert event.request_method == "POST"
        assert json.loads(event.metadata_json or "{}") == {"reason": "retired_endpoint"}
    finally:
        db.close()


def test_master_billing_policy_handles_legacy_schema():
    from app.master_admin.billing_policy import get_policy_payload, update_policy

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    metadata = MetaData()
    Table(
        "master_billing_policies",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("policy_key", String(50), nullable=False, unique=True),
        Column("enabled", Boolean, nullable=False, default=True),
        Column("allow_active", Boolean, nullable=False, default=True),
        Column("allow_trialing", Boolean, nullable=False, default=True),
        Column("exempt_hotel_ids_json", Text, nullable=False, default="[]"),
        Column("notes", Text, nullable=True),
        Column("updated_by_user_id", Integer, nullable=True),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        payload = get_policy_payload(db)
        assert payload["policy_key"] == "default"
        assert payload["enabled"] is True
        assert payload["exempt_user_ids"] == []

        updated = update_policy(
            db,
            {
                "enabled": False,
                "allow_active": False,
                "allow_trialing": True,
                "exempt_hotel_ids": [7],
                "exempt_user_ids": [9],
                "notes": "legacy-schema",
            },
            actor_user_id=42,
        )
        assert updated["enabled"] is False
        assert updated["exempt_hotel_ids"] == [7]
        assert updated["exempt_user_ids"] == [9]
    finally:
        db.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_master_email_status_and_test_mail(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    sent_payloads = _configure_resend(monkeypatch, [])
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

    status_resp = client.get("/api/master-admin/email/status")
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["configured"] is True
    assert status_resp.json()["provider"] == "resend"
    assert status_resp.json()["sender_email"] == "noreply@auth.hotels-pms.com"
    assert status_resp.json()["reply_to"] == "hotelxpms@gmail.com"

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
    assert test.json()["provider"] == "resend"
    assert test.json()["sender_email"] == "noreply@auth.hotels-pms.com"
    assert test.json()["reply_to"] == "hotelxpms@gmail.com"
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["reply_to"] == ["hotelxpms@gmail.com"]


def test_master_session_hint_cookie_is_cleared_on_logout(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
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
    assert login.cookies.get("master_admin_session_hint") == "1"

    csrf_token = login.cookies.get("master_admin_csrf")
    assert csrf_token
    logout = client.post("/api/master-admin/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200, logout.text
    assert "master_admin_session_hint" in logout.headers.get("set-cookie", "")


def test_master_stripe_connect_and_webhook_signature_is_verified(master_client, monkeypatch):
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    _configure_resend(monkeypatch, [])
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


def test_master_stripe_webhook_retry_of_same_event_is_idempotent_not_500(master_client, monkeypatch):
    """A genuine Stripe retry (network timeout, no ack received) redelivers the
    SAME event id. That must be a no-op 200, never a 500 from a unique
    constraint violation — an unhandled 500 just makes Stripe retry forever.
    """
    client, SessionLocal = master_client
    monkeypatch.setenv("MASTER_ADMIN_PIN", "654321")
    _configure_resend(monkeypatch, [])
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

    payload = {"id": "evt_retry_1", "type": "invoice.paid"}
    body = json.dumps(payload, separators=(",", ":"))

    def _post():
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{body}"
        signature = hmac.new(b"whsec_test_secret", signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        header = f"t={timestamp},v1={signature}"
        return client.post(
            "/api/master-admin/stripe/webhook",
            content=body,
            headers={"Stripe-Signature": header, "Content-Type": "application/json"},
        )

    first = _post()
    assert first.status_code == 200, first.text
    second = _post()
    assert second.status_code == 200, second.text
    assert second.json()["event_id"] == "evt_retry_1"

    db = SessionLocal()
    try:
        count = db.query(MasterStripeWebhookEvent).filter(MasterStripeWebhookEvent.event_id == "evt_retry_1").count()
        assert count == 1
    finally:
        db.close()
