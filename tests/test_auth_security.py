from __future__ import annotations

from dataclasses import dataclass
import json
import time
from unittest.mock import patch

import pyotp
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
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.models.user_mfa import UserMfaRecoveryCode, UserMfaSecret
from app.schemas.onboarding import (
    DepositPolicyPayload,
    HotelIdentityPayload,
    OTAChannelsPayload,
    OwnerPayload,
    PaymentMethodsPayload,
    RoomInput,
    StaffMember,
    SubscriptionChoicePayload,
)
from app.schemas.room import RoomCategoryCreate
from app.services import onboarding_service
from app.services.security import hash_password, needs_rehash, verify_password


LEGACY_PASSWORD = "LegacyPassphrase!"
LEGACY_BCRYPT_HASH = "$2b$12$yigTHM64/nKxzect75/p1uSTwcu7SD3hYkF1b5sQHXJ8.O4rN2Qjm"


@pytest.fixture(autouse=True)
def _enable_mocked_auth_providers(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_LOGIN_ENABLED", "true")
    monkeypatch.setenv("APPLE_LOGIN_ENABLED", "true")
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
    with patch("app.api.auth._generate_code", return_value="123456"):
        yield


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _register_owner(client: TestClient, email: str):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Demo123!pass", "role": "owner"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(auth_payload: dict[str, object]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {auth_payload['access_token']}",
        "X-Hotel-Id": str(auth_payload["hotel_id"]),
        "X-User-Id": auth_payload["user"]["email"],
    }


def _complete_onboarding(db, hotel_id: int, owner_email: str) -> None:
    onboarding_service.set_owner(
        db,
        OwnerPayload(name="Ana Manager", email=owner_email, phone="+54 11 5555 1111", role="Owner"),
        hotel_id=hotel_id,
    )
    onboarding_service.set_hotel_identity(
        db,
        HotelIdentityPayload(
            name=f"Hotel {hotel_id}",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            languages=["es", "en"],
            jurisdiction_code="AR",
        ),
        hotel_id=hotel_id,
    )
    onboarding_service.upsert_categories(
        db,
        [
            RoomCategoryCreate(
                name="Standard",
                code=f"STD-{hotel_id}",
                base_price_per_night=100.0,
                max_occupancy=2,
                amenities="wifi",
            )
        ],
        hotel_id=hotel_id,
    )
    onboarding_service.upsert_rooms(
        db,
        [RoomInput(room_number=f"{hotel_id}01", floor=1, category_code=f"STD-{hotel_id}")],
        hotel_id=hotel_id,
    )
    onboarding_service.set_deposit_policy(
        db,
        DepositPolicyPayload(
            deposit_percentage=30,
            free_cancellation_hours=48,
            cancellation_penalty_percentage=0,
        ),
        hotel_id=hotel_id,
    )
    onboarding_service.upsert_payment_methods(
        db,
        PaymentMethodsPayload(
            mercado_pago={"enabled": True, "credentials": {"account_id": "mp-user"}},
            paypal={"enabled": False, "credentials": {}},
            stripe={"enabled": False, "credentials": {}},
        ),
        hotel_id=hotel_id,
    )
    onboarding_service.upsert_ota_channels(
        db,
        OTAChannelsPayload(
            booking={"enabled": True, "credentials": {"account_id": "booking-user"}},
            expedia={"enabled": False, "credentials": {}},
            despegar={"enabled": False, "credentials": {}},
        ),
        hotel_id=hotel_id,
    )
    onboarding_service.set_subscription_choice(
        db,
        SubscriptionChoicePayload(plan_code="pro", start_trial=True),
        hotel_id=hotel_id,
    )
    onboarding_service.store_staff(
        db,
        [StaffMember(name="Lucia", role="Front desk", email="lucia@example.com")],
        hotel_id=hotel_id,
    )
    onboarding_service.finish_onboarding(db, hotel_id=hotel_id, actor_role="owner")


def _configure_resend(monkeypatch: pytest.MonkeyPatch, sent_payloads: list[dict] | None = None):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("SYSTEM_EMAIL_FROM", "Hotel Chipre PMS <noreply@auth.hotels-pms.com>")
    monkeypatch.setenv("SYSTEM_EMAIL_REPLY_TO", "hotelxpms@gmail.com")
    get_settings.cache_clear()
    payloads = sent_payloads if sent_payloads is not None else []

    def fake_post(url, data=None, headers=None, json=None, timeout=None):
        if url != "https://api.resend.com/emails":
            raise AssertionError(f"Unexpected POST {url}")
        payloads.append(json or {})
        return FakeResponse(True, {"id": "resend-message-123"})

    monkeypatch.setattr("app.services.email.providers.requests.post", fake_post)
    return payloads


def test_hash_password_uses_argon2id():
    hashed = hash_password("A sufficiently long passphrase!")

    assert hashed.startswith("$argon2id$")
    assert verify_password("A sufficiently long passphrase!", hashed)


def test_existing_bcrypt_hash_still_verifies():
    assert verify_password(LEGACY_PASSWORD, LEGACY_BCRYPT_HASH)
    assert not verify_password("wrong legacy password", LEGACY_BCRYPT_HASH)


def test_needs_rehash_identifies_legacy_bcrypt_only():
    assert needs_rehash(LEGACY_BCRYPT_HASH) is True

    fresh_hash = hash_password("A sufficiently long passphrase!")
    assert needs_rehash(fresh_hash) is False


def test_successful_login_upgrades_legacy_bcrypt_hash(client_and_db):
    client, db, _session_factory = client_and_db
    user = User(
        email="legacy-login@example.com",
        password_hash=LEGACY_BCRYPT_HASH,
        role="owner",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelConfiguration(id=1, owner_email=user.email, hotel_name="Legacy Hotel", subscription_active=True))
    db.add(HotelMembership(hotel_id=1, user_id=user.id, role="owner", status="active"))
    db.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": LEGACY_PASSWORD},
    )

    assert response.status_code == 200, response.text
    db.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != LEGACY_BCRYPT_HASH
    assert needs_rehash(user.password_hash) is False
    assert verify_password(LEGACY_PASSWORD, user.password_hash)


def test_argon2id_does_not_truncate_long_passwords():
    long_password = "long-password-" + ("x" * 100)
    hashed = hash_password(long_password)

    assert verify_password(long_password, hashed)
    assert not verify_password(long_password + "x", hashed)


def test_password_policy_requires_twelve_characters_for_register_and_reset(
    client_and_db, fixed_code_patch, monkeypatch
):
    client, _db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])

    short_register = client.post(
        "/api/auth/register",
        json={"email": "short-register@example.com", "password": "short-pass"},
    )
    assert short_register.status_code == 422
    assert "12 characters" in short_register.json()["detail"][0]["msg"]

    short_reset = client.post(
        "/api/auth/reset-password",
        json={"email": "short-reset@example.com", "code": "123456", "new_password": "short-pass"},
    )
    assert short_reset.status_code == 422
    assert "12 characters" in short_reset.json()["detail"][0]["msg"]

    exact_password = "TwelveChars!"
    email = "exact-length@example.com"
    register = client.post(
        "/api/auth/register",
        json={"email": email, "password": exact_password},
    )
    assert register.status_code == 201, register.text

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": "123456"},
    )
    assert verify.status_code == 200, verify.text

    request_reset = client.post("/api/auth/request-reset", json={"email": email})
    assert request_reset.status_code == 200, request_reset.text

    reset = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": "123456", "new_password": exact_password},
    )
    assert reset.status_code == 200, reset.text


def test_register_verify_and_reset_use_resend_provider(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    sent_payloads = _configure_resend(monkeypatch, [])

    register = _register_owner(client, "owner@example.com")
    assert register == {
        "accepted": True,
        "message": "Si el email es elegible, recibiras instrucciones por correo.",
    }

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
    assert reset_unknown.json() == reset_known.json() == {"sent": True}
    assert sent_payloads[-1]["subject"] == "Solicitud recibida en Hotel Chipre PMS"

    reset = client.post(
        "/api/auth/reset-password",
        json={"email": "owner@example.com", "code": "123456", "new_password": "Demo1234!pass"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["requires_verification"] is False

    login = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "Demo1234!pass"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "owner@example.com"

    assert len(sent_payloads) >= 4
    assert sent_payloads[0]["from"] == "Hotel Chipre PMS <noreply@auth.hotels-pms.com>"
    assert sent_payloads[0]["reply_to"] == ["hotelxpms@gmail.com"]


def test_register_is_anti_enumeration_and_does_not_touch_existing_credentials(
    client_and_db, fixed_code_patch, monkeypatch
):
    client, db, _session_factory = client_and_db
    sent_payloads = _configure_resend(monkeypatch, [])

    first = client.post(
        "/api/auth/register",
        json={"email": "same@example.com", "password": "OriginalPass123!"},
    )
    duplicate = client.post(
        "/api/auth/register",
        json={"email": "same@example.com", "password": "AttackerPass123!"},
    )

    assert first.status_code == duplicate.status_code == 201
    assert first.json() == duplicate.json()
    assert "access_token" not in first.json()
    assert "access_token" not in duplicate.json()
    assert len(sent_payloads) == 2

    stored_user = db.query(User).filter(User.email == "same@example.com").one()
    assert db.query(User).filter(User.email == "same@example.com").count() == 1
    assert verify_password("OriginalPass123!", stored_user.password_hash)
    assert not verify_password("AttackerPass123!", stored_user.password_hash)


def test_auth_flows_fail_without_connected_mail_provider(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("SYSTEM_EMAIL_FROM", "")
    monkeypatch.setenv("SYSTEM_EMAIL_REPLY_TO", "")
    get_settings.cache_clear()

    failed_register = client.post(
        "/api/auth/register",
        json={"email": "blocked@example.com", "password": "Demo123!pass", "role": "owner"},
    )
    assert failed_register.status_code == 503
    assert "Resend" in failed_register.json()["detail"]

    db.add(User(email="pending@example.com", password_hash=hash_password("Demo123!pass"), role="owner", is_verified=False, is_active=True))
    db.commit()

    failed_request_verify = client.post("/api/auth/request-verify", json={"email": "pending@example.com"})
    assert failed_request_verify.status_code == 503

    db.add(User(email="reset@example.com", password_hash=hash_password("Demo123!pass"), role="owner", is_verified=True, is_active=True))
    db.commit()

    failed_request_reset = client.post("/api/auth/request-reset", json={"email": "reset@example.com"})
    assert failed_request_reset.status_code == 503


def test_unverified_users_cannot_use_operational_endpoints(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])

    _register_owner(client, "blocked@example.com")
    login = client.post(
        "/api/auth/login",
        json={"email": "blocked@example.com", "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    headers = _auth_headers(login.json())

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


def test_login_prefers_a_completed_hotel_when_multiple_memberships_exist(client_and_db, fixed_code_patch):
    client, db, _session_factory = client_and_db

    user = User(
        email="multi@example.com",
        password_hash=hash_password("Demo123!pass"),
        role="owner",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.add_all(
        [
            HotelConfiguration(id=1, owner_email="multi@example.com", hotel_name="Pending Hotel", subscription_active=True),
            HotelConfiguration(id=2, owner_email="multi@example.com", hotel_name="Ready Hotel", subscription_active=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=user.id, role="owner", status="active"),
            HotelMembership(hotel_id=2, user_id=user.id, role="owner", status="active"),
        ]
    )
    db.flush()

    _complete_onboarding(db, 2, "multi@example.com")
    db.commit()

    login = client.post("/api/auth/login", json={"email": "multi@example.com", "password": "Demo123!pass"})
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["hotel_id"] == 2
    assert payload["hotel_ids"] == [1, 2]
    audits = (
        db.query(SecurityAuditLog)
        .filter(SecurityAuditLog.action == "auth.login.success")
        .order_by(SecurityAuditLog.hotel_id.asc())
        .all()
    )
    assert [audit.hotel_id for audit in audits] == [1, 2]

    headers = _auth_headers(payload)
    status = client.get("/api/onboarding/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["completed"] is True


def test_legacy_public_email_endpoints_are_retired(client_and_db):
    client, _db, _session_factory = client_and_db

    resp = client.post("/api/email/verify?to=test@example.com")
    assert resp.status_code == 410


def test_register_rejects_malformed_email(client_and_db, monkeypatch):
    """RegisterRequest.email was a plain str with no format validation, so
    garbage like "not-an-email" was silently accepted and stored."""
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])

    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email-at-all", "password": "Demo123!pass"},
    )
    assert response.status_code == 422, response.text
    assert db.query(User).filter(User.email == "not-an-email-at-all").first() is None


def test_register_rejects_reserved_test_tld_outside_test_mode(client_and_db, monkeypatch):
    """".test" is an RFC 2606 reserved TLD email-validator blocks as
    special-use by default (regardless of DNS deliverability checks, which
    are already disabled here). Outside test mode this must stay rejected --
    a real production signup with a garbage/reserved domain is not a valid
    owner account."""
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    response = client.post(
        "/api/auth/register",
        json={"email": "owner@example.test", "password": "Demo123!pass"},
    )
    assert response.status_code == 422, response.text
    assert db.query(User).filter(User.email == "owner@example.test").first() is None


def test_register_accepts_reserved_test_tld_in_test_mode(client_and_db, monkeypatch):
    """The isolated Playwright E2E backend boots with APP_ENV=test and its
    specs register synthetic owners like "qa-onboarding-<ts>@example.test".
    email-validator has a `test_environment` flag made exactly for this (RFC
    2606 reserved TLDs used in automated tests); registration must succeed
    when APP_ENV=test without ever touching DNS/deliverability checks."""
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])
    monkeypatch.setenv("APP_ENV", "test")

    response = client.post(
        "/api/auth/register",
        json={"email": "owner@example.test", "password": "Demo123!pass"},
    )
    assert response.status_code == 201, response.text
    assert db.query(User).filter(User.email == "owner@example.test").first() is not None


def test_reset_password_revokes_previously_issued_tokens(client_and_db, fixed_code_patch, monkeypatch):
    """
    JWTs are stateless with no server-side blacklist, so a password reset -
    the standard remediation after a suspected credential/token leak - must
    itself invalidate tokens issued before the reset, or the compromised
    session simply keeps working for up to JWT_EXPIRES_MINUTES regardless.
    """
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])

    _register_owner(client, "leaked@example.com")

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": "leaked@example.com", "code": "123456"},
    )
    assert verify.status_code == 200, verify.text
    old_token = verify.json()["access_token"]

    me_before = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_before.status_code == 200, me_before.text

    request_reset = client.post("/api/auth/request-reset", json={"email": "leaked@example.com"})
    assert request_reset.status_code == 200, request_reset.text

    reset = client.post(
        "/api/auth/reset-password",
        json={"email": "leaked@example.com", "code": "123456", "new_password": "Demo1234!pass"},
    )
    assert reset.status_code == 200, reset.text

    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_after.status_code == 401, me_after.text


def test_self_registration_cannot_grant_platform_admin_role(client_and_db, fixed_code_patch, monkeypatch):
    """
    A guest self-registering must never end up with User.role="platform_admin"
    just by sending that value in the request body (mass-assignment /
    privilege escalation). require_platform_admin() trusts User.role alone,
    with no PIN or master-admin session, so this role must be server-assigned.
    """
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])

    register = client.post(
        "/api/auth/register",
        json={"email": "attacker@example.com", "password": "Demo123!pass", "role": "platform_admin"},
    )
    assert register.status_code == 201, register.text

    stored_user = db.query(User).filter(User.email == "attacker@example.com").first()
    assert stored_user.role != "platform_admin"

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": "attacker@example.com", "code": "123456"},
    )
    assert verify.status_code == 200, verify.text

    login = client.post(
        "/api/auth/login",
        json={"email": "attacker@example.com", "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    forged_admin_action = client.post(
        "/api/admin/subscription/comped-override",
        json={"hotel_id": 1, "plan_code": "ultra", "reason": "self-escalated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forged_admin_action.status_code == 403, forged_admin_action.text


def _fake_google_claims(
    email: str, email_verified: bool = True, sub: str = "google-sub-123"
) -> dict:
    return {"email": email, "email_verified": email_verified, "sub": sub, "name": "Test User"}


def _fake_apple_claims(email: str, sub: str = "apple-sub-123") -> dict:
    return {
        "email": email,
        "email_verified": True,
        "sub": sub,
        "iss": "https://appleid.apple.com",
        "aud": "com.example.hotel-chipre",
    }


def test_google_login_returns_503_when_not_configured(client_and_db, monkeypatch):
    client, _db, _session_factory = client_and_db
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    get_settings.cache_clear()

    response = client.post("/api/auth/google", json={"id_token": "whatever"})
    assert response.status_code == 503, response.text


def test_google_login_creates_new_user_when_email_unknown(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_fake_google_claims("newgoogleuser@example.com"),
    ) as mocked_verify:
        response = client.post("/api/auth/google", json={"id_token": "fake-jwt-from-google"})

    assert response.status_code == 200, response.text
    mocked_verify.assert_called_once()
    _, _, audience = mocked_verify.call_args.args
    assert audience == "test-client-id.apps.googleusercontent.com"

    body = response.json()
    assert body["user"]["email"] == "newgoogleuser@example.com"
    assert body["user"]["is_verified"] is True
    assert body["requires_verification"] is False

    stored_user = db.query(User).filter(User.email == "newgoogleuser@example.com").first()
    assert stored_user is not None
    assert stored_user.role == "owner"
    assert stored_user.is_verified is True
    assert stored_user.google_sub == "google-sub-123"
    # Random unguessable password_hash was set, never handed to the client.
    assert stored_user.password_hash
    assert not verify_password("", stored_user.password_hash)

    audit = db.query(SecurityAuditLog).filter_by(action="google_auth.linked").one()
    assert audit.hotel_id == body["hotel_id"]
    assert json.loads(audit.details) == {"account_state": "created", "provider": "google"}


def test_google_login_relogin_with_same_sub_preserves_password(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    claims = _fake_google_claims("google-relogin@example.com", sub="google-relogin-sub")
    with patch("app.api.auth.google_id_token.verify_oauth2_token", return_value=claims):
        first_response = client.post("/api/auth/google", json={"id_token": "first-google-jwt"})
    assert first_response.status_code == 200, first_response.text

    stored_user = db.query(User).filter(User.email == "google-relogin@example.com").one()
    original_password_hash = stored_user.password_hash

    with patch("app.api.auth.google_id_token.verify_oauth2_token", return_value=claims):
        second_response = client.post("/api/auth/google", json={"id_token": "second-google-jwt"})

    assert second_response.status_code == 200, second_response.text
    db.refresh(stored_user)
    assert stored_user.google_sub == "google-relogin-sub"
    assert stored_user.password_hash == original_password_hash
    audits = (
        db.query(SecurityAuditLog)
        .filter(SecurityAuditLog.action == "google_auth.linked")
        .order_by(SecurityAuditLog.id.asc())
        .all()
    )
    assert len(audits) == 2
    assert [json.loads(audit.details)["account_state"] for audit in audits] == ["created", "existing"]


def test_google_login_replaces_password_for_unverified_email_squatter(
    client_and_db, fixed_code_patch, monkeypatch
):
    client, db, _session_factory = client_and_db
    _configure_resend(monkeypatch, [])
    _register_owner(client, "existinguser@example.com")
    old_access_token = None
    stored_user = db.query(User).filter(User.email == "existinguser@example.com").one()
    old_password_hash = stored_user.password_hash

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": "existinguser@example.com", "code": "123456"},
    )
    assert verify.status_code == 200, verify.text
    old_access_token = verify.json()["access_token"]

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_fake_google_claims("existinguser@example.com", sub="google-victim-sub"),
    ):
        response = client.post("/api/auth/google", json={"id_token": "fake-jwt-from-google"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "existinguser@example.com"
    assert body["user"]["is_verified"] is True

    db.refresh(stored_user)
    assert stored_user.google_sub == "google-victim-sub"
    assert stored_user.password_hash != old_password_hash
    assert stored_user.token_version == 1

    audit = db.query(SecurityAuditLog).filter_by(action="google_auth.account_reclaimed").one()
    assert audit.hotel_id == body["hotel_id"]
    assert json.loads(audit.details) == {"password_invalidated": True, "provider": "google"}

    password_login = client.post(
        "/api/auth/login",
        json={"email": "existinguser@example.com", "password": "Demo123!pass"},
    )
    assert password_login.status_code == 401, password_login.text

    old_session = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert old_session.status_code == 401, old_session.text

    users_with_email = db.query(User).filter(User.email == "existinguser@example.com").all()
    assert len(users_with_email) == 1


def test_google_unlink_requires_password_and_revokes_previous_bearer_session(
    client_and_db, monkeypatch
):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    claims = _fake_google_claims("google-unlink@example.com", sub="google-unlink-sub")
    with patch("app.api.auth.google_id_token.verify_oauth2_token", return_value=claims):
        google_login = client.post("/api/auth/google", json={"id_token": "google-jwt"})
    assert google_login.status_code == 200, google_login.text

    auth = google_login.json()
    user = db.query(User).filter(User.email == claims["email"]).one()
    user.password_hash = hash_password("Demo123!pass")
    db.commit()
    original_token_version = user.token_version

    unlink = client.post(
        "/api/auth/google/unlink",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"password": "Demo123!pass"},
    )

    assert unlink.status_code == 200, unlink.text
    assert unlink.json() == {"unlinked": True}
    db.refresh(user)
    assert user.google_sub is None
    assert user.token_version == original_token_version + 1

    old_session = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert old_session.status_code == 401, old_session.text

    audit = db.query(SecurityAuditLog).filter_by(action="google_auth.unlinked").one()
    assert audit.hotel_id == auth["hotel_id"]
    assert json.loads(audit.details) == {"provider": "google"}


def test_google_unlink_rejects_incorrect_password_without_mutating_link(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    claims = _fake_google_claims("google-unlink-wrong@example.com", sub="google-unlink-wrong-sub")
    with patch("app.api.auth.google_id_token.verify_oauth2_token", return_value=claims):
        google_login = client.post("/api/auth/google", json={"id_token": "google-jwt"})
    assert google_login.status_code == 200, google_login.text

    auth = google_login.json()
    user = db.query(User).filter(User.email == claims["email"]).one()
    user.password_hash = hash_password("Demo123!pass")
    db.commit()
    original_token_version = user.token_version
    original_google_sub = user.google_sub

    unlink = client.post(
        "/api/auth/google/unlink",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"password": "WrongPassword!"},
    )

    assert unlink.status_code == 401, unlink.text
    db.refresh(user)
    assert user.google_sub == original_google_sub
    assert user.token_version == original_token_version
    assert db.query(SecurityAuditLog).filter_by(action="google_auth.unlinked").count() == 0


def test_google_only_account_cannot_unlink_with_unknown_password(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    claims = _fake_google_claims("google-only-unlink@example.com", sub="google-only-unlink-sub")
    with patch("app.api.auth.google_id_token.verify_oauth2_token", return_value=claims):
        google_login = client.post("/api/auth/google", json={"id_token": "google-jwt"})
    assert google_login.status_code == 200, google_login.text

    auth = google_login.json()
    user = db.query(User).filter(User.email == claims["email"]).one()
    original_password_hash = user.password_hash
    original_token_version = user.token_version

    unlink = client.post(
        "/api/auth/google/unlink",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"password": "PasswordTheGoogleOnlyUserNeverSet"},
    )

    assert unlink.status_code == 401, unlink.text
    db.refresh(user)
    assert user.google_sub == claims["sub"]
    assert user.password_hash == original_password_hash
    assert user.token_version == original_token_version
    assert db.query(SecurityAuditLog).filter_by(action="google_auth.unlinked").count() == 0


def test_google_login_rejects_unverified_google_email(client_and_db, monkeypatch):
    client, _db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_fake_google_claims("unverified@example.com", email_verified=False),
    ):
        response = client.post("/api/auth/google", json={"id_token": "fake-jwt-from-google"})

    assert response.status_code == 401, response.text


def test_google_login_rejects_invalid_token(client_and_db, monkeypatch):
    client, _db, _session_factory = client_and_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()

    with patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        side_effect=ValueError("Token used too early"),
    ):
        response = client.post("/api/auth/google", json={"id_token": "garbage"})

    assert response.status_code == 401, response.text


def test_apple_login_creates_account_and_persists_first_authorization_name(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.example.hotel-chipre")
    get_settings.cache_clear()
    claims = _fake_apple_claims("relay@privaterelay.appleid.com")
    with patch("app.api.auth.verify_apple_id_token", return_value=claims) as verify:
        response = client.post(
            "/api/auth/apple",
            json={
                "id_token": "apple-jwt",
                "nonce": "nonce-1",
                "user": {"name": {"firstName": "Apple", "lastName": "Owner"}},
            },
        )
    assert response.status_code == 200, response.text
    verify.assert_called_once()
    stored = db.query(User).filter(User.email == "relay@privaterelay.appleid.com").one()
    assert stored.apple_sub == "apple-sub-123"
    assert stored.display_name == "Apple Owner"
    audit = db.query(SecurityAuditLog).filter_by(action="apple_auth.linked").one()
    assert json.loads(audit.details) == {"account_state": "created", "provider": "apple"}


def test_apple_login_reclaims_matching_local_email_like_google(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    existing = User(
        email="existing-apple@example.com",
        password_hash=hash_password("Demo123!pass"),
        role="owner",
        is_verified=True,
    )
    db.add(existing)
    db.flush()
    db.add(HotelConfiguration(id=1, owner_email=existing.email, hotel_name="Apple Hotel", subscription_active=True))
    db.add(HotelMembership(hotel_id=1, user_id=existing.id, role="owner", status="active"))
    db.commit()
    old_hash = existing.password_hash
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.example.hotel-chipre")
    get_settings.cache_clear()
    with patch(
        "app.api.auth.verify_apple_id_token",
        return_value=_fake_apple_claims(existing.email, sub="apple-victim-sub"),
    ):
        response = client.post("/api/auth/apple", json={"id_token": "apple-jwt", "nonce": "nonce-2"})
    assert response.status_code == 200, response.text
    db.refresh(existing)
    assert existing.apple_sub == "apple-victim-sub"
    assert existing.password_hash != old_hash
    assert existing.token_version == 1
    audit = db.query(SecurityAuditLog).filter_by(action="apple_auth.account_reclaimed").one()
    assert json.loads(audit.details) == {"password_invalidated": True, "provider": "apple"}


def test_apple_login_rejects_different_subject_claiming_linked_email(client_and_db, monkeypatch):
    client, _db, _session_factory = client_and_db
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.example.hotel-chipre")
    get_settings.cache_clear()
    with patch(
        "app.api.auth.verify_apple_id_token",
        return_value=_fake_apple_claims("same-apple@example.com", sub="apple-first-sub"),
    ):
        first = client.post("/api/auth/apple", json={"id_token": "first", "nonce": "nonce-3"})
    assert first.status_code == 200, first.text
    with patch(
        "app.api.auth.verify_apple_id_token",
        return_value=_fake_apple_claims("same-apple@example.com", sub="apple-second-sub"),
    ):
        second = client.post("/api/auth/apple", json={"id_token": "second", "nonce": "nonce-4"})
    assert second.status_code == 409, second.text


def test_apple_login_rejects_invalid_verified_token(client_and_db, monkeypatch):
    from app.services.apple_auth_service import AppleTokenError

    client, _db, _session_factory = client_and_db
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.example.hotel-chipre")
    get_settings.cache_clear()
    with patch("app.api.auth.verify_apple_id_token", side_effect=AppleTokenError("bad token")):
        response = client.post("/api/auth/apple", json={"id_token": "invalid", "nonce": "nonce-5"})
    assert response.status_code == 401, response.text


def test_apple_unlink_requires_password_and_revokes_session(client_and_db, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("APPLE_CLIENT_ID", "com.example.hotel-chipre")
    get_settings.cache_clear()
    with patch(
        "app.api.auth.verify_apple_id_token",
        return_value=_fake_apple_claims("apple-unlink@example.com", sub="apple-unlink-sub"),
    ):
        login = client.post("/api/auth/apple", json={"id_token": "apple-jwt", "nonce": "nonce-6"})
    assert login.status_code == 200, login.text
    auth = login.json()
    user = db.query(User).filter(User.email == "apple-unlink@example.com").one()
    user.password_hash = hash_password("Demo123!pass")
    db.commit()
    unlink = client.post(
        "/api/auth/apple/unlink",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"password": "Demo123!pass"},
    )
    assert unlink.status_code == 200, unlink.text
    db.refresh(user)
    assert user.apple_sub is None
    assert db.query(SecurityAuditLog).filter_by(action="apple_auth.unlinked").one()


def _next_totp_code(secret: str, steps_ahead: int = 1) -> str:
    current_step = int(time.time()) // 30
    return pyotp.TOTP(secret).at((current_step + steps_ahead) * 30)


def _verified_auth(client: TestClient, email: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    _configure_resend(monkeypatch, [])
    registered = _register_owner(client, email)
    verified = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": "123456"},
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


def _enroll_and_confirm_mfa(
    client: TestClient, db, email: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], str, list[str]]:
    auth = _verified_auth(client, email, monkeypatch)
    headers = _auth_headers(auth)
    enrollment = client.post("/api/auth/mfa/enroll", headers=headers)
    assert enrollment.status_code == 200, enrollment.text
    enrollment_body = enrollment.json()
    secret = enrollment_body["secret"]
    confirmation = client.post(
        "/api/auth/mfa/enroll/confirm",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert confirmation.status_code == 200, confirmation.text
    recovery_codes = confirmation.json()["recovery_codes"]
    user = db.query(User).filter(User.email == email).one()
    mfa_secret = db.query(UserMfaSecret).filter(UserMfaSecret.user_id == user.id).one()
    assert mfa_secret.status == "active"
    audit = db.query(SecurityAuditLog).filter_by(action="mfa.enrolled").one()
    assert audit.hotel_id == auth["hotel_id"]
    assert json.loads(audit.details) == {"factor": "totp"}
    return auth, secret, recovery_codes


def test_login_without_mfa_keeps_returning_the_normal_auth_response(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    auth = _verified_auth(client, "without-mfa@example.com", monkeypatch)

    login = client.post(
        "/api/auth/login",
        json={"email": "without-mfa@example.com", "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    assert login.json()["user"]["email"] == auth["user"]["email"]

    audit = db.query(SecurityAuditLog).filter_by(action="auth.login.success").one()
    assert audit.hotel_id == login.json()["hotel_id"]
    assert json.loads(audit.details) == {"method": "password"}


def test_mfa_enroll_confirm_uses_encrypted_secret_and_requires_second_login_step(
    client_and_db, fixed_code_patch, monkeypatch
):
    client, db, _session_factory = client_and_db
    auth, secret, recovery_codes = _enroll_and_confirm_mfa(client, db, "totp-login@example.com", monkeypatch)
    headers = _auth_headers(auth)

    stored = db.query(UserMfaSecret).one()
    assert stored.status == "active"
    assert stored.encrypted_secret != secret
    assert secret not in stored.encrypted_secret
    assert len(recovery_codes) == 10
    stored_codes = db.query(UserMfaRecoveryCode).all()
    assert len(stored_codes) == 10
    assert all(code not in row.code_hash for row in stored_codes for code in recovery_codes)

    login = client.post(
        "/api/auth/login",
        json={"email": "totp-login@example.com", "password": "Demo123!pass"},
    )
    assert login.status_code == 200, login.text
    challenge = login.json()
    assert challenge["requires_mfa"] is True
    assert "access_token" not in challenge
    assert challenge["expires_in"] == 300

    completed = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": _next_totp_code(secret)},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["access_token"]
    audit = db.query(SecurityAuditLog).filter_by(action="auth.login.success").one()
    assert audit.hotel_id == completed.json()["hotel_id"]
    assert json.loads(audit.details) == {"method": "password+mfa"}


def test_mfa_rejects_invalid_and_replayed_totp_codes(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    _auth, secret, _recovery_codes = _enroll_and_confirm_mfa(client, db, "totp-replay@example.com", monkeypatch)

    invalid_challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-replay@example.com", "password": "Demo123!pass"},
    ).json()
    invalid = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": invalid_challenge["mfa_token"], "code": "000000"},
    )
    assert invalid.status_code == 401, invalid.text

    challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-replay@example.com", "password": "Demo123!pass"},
    ).json()
    code = _next_totp_code(secret)
    first = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": code},
    )
    assert first.status_code == 200, first.text

    replay = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": code},
    )
    assert replay.status_code == 401, replay.text


def test_recovery_code_is_single_use_and_regeneration_invalidates_old_codes(
    client_and_db, fixed_code_patch, monkeypatch
):
    client, db, _session_factory = client_and_db
    auth, _secret, recovery_codes = _enroll_and_confirm_mfa(client, db, "totp-recovery@example.com", monkeypatch)

    first_challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-recovery@example.com", "password": "Demo123!pass"},
    ).json()
    first_login = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": first_challenge["mfa_token"], "code": recovery_codes[0]},
    )
    assert first_login.status_code == 200, first_login.text
    authenticated_headers = _auth_headers(first_login.json())

    second_challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-recovery@example.com", "password": "Demo123!pass"},
    ).json()
    reused = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": second_challenge["mfa_token"], "code": recovery_codes[0]},
    )
    assert reused.status_code == 401, reused.text

    regenerated = client.post(
        "/api/auth/mfa/recovery-codes/regenerate",
        headers=authenticated_headers,
        json={"code": recovery_codes[1]},
    )
    assert regenerated.status_code == 200, regenerated.text
    new_codes = regenerated.json()["recovery_codes"]
    assert len(new_codes) == 10
    assert set(new_codes).isdisjoint(recovery_codes)
    audit = db.query(SecurityAuditLog).filter_by(action="mfa.recovery_codes_regenerated").one()
    assert audit.hotel_id == auth["hotel_id"]
    assert json.loads(audit.details) == {"factor": "totp"}

    old_challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-recovery@example.com", "password": "Demo123!pass"},
    ).json()
    old_code = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": old_challenge["mfa_token"], "code": recovery_codes[2]},
    )
    assert old_code.status_code == 401, old_code.text

    new_challenge = client.post(
        "/api/auth/login",
        json={"email": "totp-recovery@example.com", "password": "Demo123!pass"},
    ).json()
    new_login = client.post(
        "/api/auth/login/mfa",
        json={"mfa_token": new_challenge["mfa_token"], "code": new_codes[0]},
    )
    assert new_login.status_code == 200, new_login.text


def test_disable_mfa_requires_current_password_and_a_valid_factor(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    auth, secret, _recovery_codes = _enroll_and_confirm_mfa(client, db, "totp-disable@example.com", monkeypatch)
    headers = _auth_headers(auth)
    code = _next_totp_code(secret)

    wrong_password = client.post(
        "/api/auth/mfa/disable",
        headers=headers,
        json={"password": "wrong password", "code": code},
    )
    assert wrong_password.status_code == 401, wrong_password.text
    assert db.query(UserMfaSecret).one().status == "active"

    disabled = client.post(
        "/api/auth/mfa/disable",
        headers=headers,
        json={"password": "Demo123!pass", "code": code},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json() == {"disabled": True}
    assert db.query(UserMfaSecret).count() == 0
    assert db.query(UserMfaRecoveryCode).count() == 0
    audit = db.query(SecurityAuditLog).filter_by(action="mfa.disabled").one()
    assert audit.hotel_id == auth["hotel_id"]
    assert json.loads(audit.details) == {"factor": "totp"}
