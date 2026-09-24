import time
from dataclasses import replace

import pyotp
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.database import Base, get_db
from app.dependencies.auth import (
    AuthContext,
    get_auth_context,
    require_all_permissions,
    require_any_permission,
    require_permission,
    require_permission_administrator,
)
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.services.action_step_up_service import ACTION_STEP_UP_TICKET_TTL_SECONDS
from app.services.mfa_service import encrypt_totp_secret
from app.services.permission_service import (
    PERMISSION_APIKEY_MANAGE,
    PERMISSION_HOTEL_SECURITY_MANAGE,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_RESERVATION_READ,
)

USER_ID = 41
HOTEL_ID = 7
ACTION_PATH = "/api/test/sensitive"


def _auth_context(*, user_id: int = USER_ID, hotel_id: int = HOTEL_ID, token_version: int = 3) -> AuthContext:
    return AuthContext(
        hotel_id=hotel_id,
        user_id=user_id,
        user_email="owner@example.test",
        user_role="owner",
        is_verified=True,
        permissions=set(),
        token_version=token_version,
    )


@pytest.fixture
def step_up_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    secret = pyotp.random_base32()
    db.add_all(
        [
            HotelConfiguration(id=HOTEL_ID, subscription_active=True),
            HotelConfiguration(id=HOTEL_ID + 1, subscription_active=True),
            User(
                id=USER_ID,
                email="owner@example.test",
                password_hash="unused-test-hash",
                is_active=True,
                is_verified=True,
                role="owner",
                token_version=3,
            ),
            UserMfaSecret(
                user_id=USER_ID,
                encrypted_secret=encrypt_totp_secret(secret),
                status="active",
            ),
        ]
    )
    db.commit()

    current = {"context": _auth_context()}
    app = FastAPI()
    app.include_router(auth_router)

    def override_db():
        yield db

    def override_auth_context():
        return current["context"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = override_auth_context

    @app.get(ACTION_PATH)
    def sensitive_action(context: AuthContext = Depends(require_permission(PERMISSION_PERMISSION_MANAGE))):
        return {"executed": True}

    @app.get(
        "/api/test/all-sensitive",
        dependencies=[Depends(require_all_permissions(PERMISSION_PERMISSION_MANAGE, PERMISSION_APIKEY_MANAGE))],
    )
    def all_sensitive_action():
        return {"executed": True}

    @app.get(
        "/api/test/any-sensitive",
        dependencies=[Depends(require_any_permission(PERMISSION_PERMISSION_MANAGE, PERMISSION_APIKEY_MANAGE))],
    )
    def any_sensitive_action():
        return {"executed": True}

    @app.get(
        "/api/test/any-alternative",
        dependencies=[Depends(require_any_permission(PERMISSION_PERMISSION_MANAGE, PERMISSION_RESERVATION_READ))],
    )
    def any_alternative_action():
        return {"executed": True}

    @app.get(
        "/api/test/permission-admin",
        dependencies=[Depends(require_permission_administrator)],
    )
    def permission_admin_action():
        return {"executed": True}

    try:
        yield TestClient(app), db, secret, current
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _code_at(secret: str, step_offset: int = 0) -> str:
    step = int(time.time()) // 30 + step_offset
    return pyotp.TOTP(secret).at(step * 30)


def _invalid_code(secret: str) -> str:
    current_step = int(time.time()) // 30
    valid_codes = {
        pyotp.TOTP(secret).at(step * 30)
        for step in range(max(0, current_step - 1), current_step + 2)
    }
    return next(f"{candidate:06d}" for candidate in range(1_000_000) if f"{candidate:06d}" not in valid_codes)


def _issue_ticket(
    client: TestClient,
    secret: str,
    *,
    permission_code: str = PERMISSION_PERMISSION_MANAGE,
    method: str = "GET",
    path: str = ACTION_PATH,
    code: str | None = None,
):
    return client.post(
        "/api/auth/step-up",
        json={
            "code": code or _code_at(secret),
            "permission_code": permission_code,
            "method": method,
            "path": path,
        },
    )


def test_sensitive_permission_requires_a_matching_ticket_before_handler(step_up_client):
    client, _db, secret, _current = step_up_client

    missing = client.get(ACTION_PATH)
    assert missing.status_code == 428
    assert missing.json()["detail"] == {
        "code": "STEP_UP_REQUIRED",
        "permission_code": PERMISSION_PERMISSION_MANAGE,
        "method": "GET",
        "path": ACTION_PATH,
    }
    assert "ticket" not in missing.text.lower()

    issued = _issue_ticket(client, secret)
    assert issued.status_code == 200, issued.text
    body = issued.json()
    assert body["permission_code"] == PERMISSION_PERMISSION_MANAGE
    assert body["expires_in"] == ACTION_STEP_UP_TICKET_TTL_SECONDS == 120

    allowed = client.get(
        ACTION_PATH,
        headers={"X-Action-Step-Up-Ticket": body["ticket"]},
    )
    assert allowed.status_code == 200
    assert allowed.json() == {"executed": True}

    replayed = client.get(
        ACTION_PATH,
        headers={"X-Action-Step-Up-Ticket": body["ticket"]},
    )
    assert replayed.status_code == 428
    assert replayed.json()["detail"]["code"] == "STEP_UP_REQUIRED"


@pytest.mark.parametrize("mismatch", ["user", "hotel", "permission", "method", "path", "token_version"])
def test_ticket_is_bound_to_user_hotel_permission_method_path_and_token_version(step_up_client, mismatch):
    client, _db, secret, current = step_up_client
    ticket_permission = (
        PERMISSION_HOTEL_SECURITY_MANAGE if mismatch == "permission" else PERMISSION_PERMISSION_MANAGE
    )
    ticket_method = "POST" if mismatch == "method" else "GET"
    ticket_path = "/api/test/different" if mismatch == "path" else ACTION_PATH
    issued = _issue_ticket(
        client,
        secret,
        permission_code=ticket_permission,
        method=ticket_method,
        path=ticket_path,
    )
    assert issued.status_code == 200, issued.text

    context_changes = {
        "user": {"user_id": USER_ID + 1},
        "hotel": {"hotel_id": HOTEL_ID + 1},
        "token_version": {"token_version": 4},
    }
    if mismatch in context_changes:
        current["context"] = replace(current["context"], **context_changes[mismatch])

    response = client.get(
        ACTION_PATH,
        headers={"X-Action-Step-Up-Ticket": issued.json()["ticket"]},
    )
    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "STEP_UP_REQUIRED"
    assert issued.json()["ticket"] not in response.text


def test_invalid_ticket_fails_closed_without_echoing_it(step_up_client):
    client, _db, secret, _current = step_up_client
    issued = _issue_ticket(client, secret)
    assert issued.status_code == 200
    ticket = issued.json()["ticket"]
    tampered = ticket[:-1] + ("A" if ticket[-1] != "A" else "B")

    response = client.get(ACTION_PATH, headers={"X-Action-Step-Up-Ticket": tampered})

    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "STEP_UP_REQUIRED"
    assert tampered not in response.text


def test_step_up_requires_active_mfa_and_a_valid_non_replayed_totp(step_up_client):
    client, db, secret, _current = step_up_client
    mfa_secret = db.query(UserMfaSecret).filter_by(user_id=USER_ID).one()
    mfa_secret.status = "pending"
    db.commit()

    missing_mfa = _issue_ticket(client, secret)
    assert missing_mfa.status_code == 403
    assert missing_mfa.json()["detail"] == {"code": "MFA_ENROLLMENT_REQUIRED"}

    mfa_secret.status = "active"
    db.commit()
    invalid_code = _invalid_code(secret)
    invalid = _issue_ticket(client, secret, code=invalid_code)
    assert invalid.status_code == 401
    assert "Codigo MFA invalido" in invalid.text
    assert invalid_code not in invalid.text

    code = _code_at(secret)
    accepted = _issue_ticket(client, secret, code=code)
    assert accepted.status_code == 200, accepted.text
    replayed = _issue_ticket(client, secret, code=code)
    assert replayed.status_code == 401


def test_step_up_code_guesses_use_existing_persistent_rate_limit(step_up_client):
    client, _db, secret, _current = step_up_client
    invalid_code = _invalid_code(secret)

    for _ in range(8):
        assert _issue_ticket(client, secret, code=invalid_code).status_code == 401
    limited = _issue_ticket(client, secret, code=invalid_code)

    assert limited.status_code == 429
    assert invalid_code not in limited.text


def test_require_all_accepts_one_ticket_per_sensitive_permission(step_up_client):
    client, _db, secret, _current = step_up_client
    first_code = _code_at(secret)
    first_ticket = _issue_ticket(
        client,
        secret,
        permission_code=PERMISSION_PERMISSION_MANAGE,
        path="/api/test/all-sensitive",
        code=first_code,
    )
    assert first_ticket.status_code == 200, first_ticket.text

    missing_second = client.get(
        "/api/test/all-sensitive",
        headers={"X-Action-Step-Up-Ticket": first_ticket.json()["ticket"]},
    )
    assert missing_second.status_code == 428
    assert missing_second.json()["detail"]["permission_code"] == PERMISSION_APIKEY_MANAGE

    second_ticket = _issue_ticket(
        client,
        secret,
        permission_code=PERMISSION_APIKEY_MANAGE,
        path="/api/test/all-sensitive",
        code=_code_at(secret, step_offset=1),
    )
    assert second_ticket.status_code == 200, second_ticket.text

    allowed = client.get(
        "/api/test/all-sensitive",
        headers={
            "X-Action-Step-Up-Ticket": (
                f"{first_ticket.json()['ticket']},{second_ticket.json()['ticket']}"
            )
        },
    )
    assert allowed.status_code == 200

    replayed = client.get(
        "/api/test/all-sensitive",
        headers={
            "X-Action-Step-Up-Ticket": (
                f"{first_ticket.json()['ticket']},{second_ticket.json()['ticket']}"
            )
        },
    )
    assert replayed.status_code == 428
    assert replayed.json()["detail"]["code"] == "STEP_UP_REQUIRED"


def test_require_any_uses_a_matching_granted_sensitive_permission(step_up_client):
    client, _db, secret, _current = step_up_client
    missing = client.get("/api/test/any-sensitive")
    assert missing.status_code == 428
    assert missing.json()["detail"]["permission_code"] == PERMISSION_PERMISSION_MANAGE

    issued = _issue_ticket(
        client,
        secret,
        permission_code=PERMISSION_APIKEY_MANAGE,
        path="/api/test/any-sensitive",
    )
    assert issued.status_code == 200, issued.text
    allowed = client.get(
        "/api/test/any-sensitive",
        headers={"X-Action-Step-Up-Ticket": issued.json()["ticket"]},
    )
    assert allowed.status_code == 200


def test_require_any_keeps_a_valid_non_sensitive_alternative(step_up_client):
    client, _db, _secret, _current = step_up_client

    response = client.get("/api/test/any-alternative")

    assert response.status_code == 200


def test_permission_administrator_also_requires_step_up(step_up_client):
    client, _db, _secret, _current = step_up_client

    response = client.get("/api/test/permission-admin")

    assert response.status_code == 428
    assert response.json()["detail"]["permission_code"] == PERMISSION_PERMISSION_MANAGE
