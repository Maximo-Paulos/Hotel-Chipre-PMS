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
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
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


def test_register_verify_and_reset_use_resend_provider(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    sent_payloads = _configure_resend(monkeypatch, [])

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

    reset = client.post(
        "/api/auth/reset-password",
        json={"email": "owner@example.com", "code": "123456", "new_password": "Demo1234!"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["requires_verification"] is False

    login = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "Demo1234!"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "owner@example.com"

    assert len(sent_payloads) >= 4
    assert sent_payloads[0]["from"] == "Hotel Chipre PMS <noreply@auth.hotels-pms.com>"
    assert sent_payloads[0]["reply_to"] == ["hotelxpms@gmail.com"]


def test_auth_flows_fail_without_connected_mail_provider(client_and_db, fixed_code_patch, monkeypatch):
    client, db, _session_factory = client_and_db
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("SYSTEM_EMAIL_FROM", "")
    monkeypatch.setenv("SYSTEM_EMAIL_REPLY_TO", "")
    get_settings.cache_clear()

    failed_register = client.post(
        "/api/auth/register",
        json={"email": "blocked@example.com", "password": "Demo123!", "role": "owner"},
    )
    assert failed_register.status_code == 503
    assert "Resend" in failed_register.json()["detail"]

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
    _configure_resend(monkeypatch, [])

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


def test_login_prefers_a_completed_hotel_when_multiple_memberships_exist(client_and_db, fixed_code_patch):
    client, db, _session_factory = client_and_db

    user = User(
        email="multi@example.com",
        password_hash=hash_password("Demo123!"),
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

    login = client.post("/api/auth/login", json={"email": "multi@example.com", "password": "Demo123!"})
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["hotel_id"] == 2
    assert payload["hotel_ids"] == [1, 2]

    headers = _auth_headers(payload)
    status = client.get("/api/onboarding/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["completed"] is True


def test_legacy_public_email_endpoints_are_retired(client_and_db):
    client, _db, _session_factory = client_and_db

    resp = client.post("/api/email/verify?to=test@example.com")
    assert resp.status_code == 410
