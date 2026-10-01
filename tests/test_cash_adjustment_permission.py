import importlib.util
from pathlib import Path

import pytest
import pyotp
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.api.cash_register import router as cash_register_router
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as _registered_app  # noqa: F401 - registers all model tables
from app.models.hotel_config import HotelConfiguration
from app.models.permission import HotelPermissionOverride
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.services.action_step_up_service import permission_requires_step_up
from app.services.mfa_service import encrypt_totp_secret
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_CASH_ADJUSTMENT_MANAGE,
    get_permission_catalog,
)


HOTEL_ID = 71
USER_ID = 91
TOKEN_VERSION = 4
@pytest.fixture
def cash_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    mfa_secret = pyotp.random_base32()
    db.add_all(
        [
            HotelConfiguration(id=HOTEL_ID, subscription_active=True),
            User(
                id=USER_ID,
                email="cash-adjustment@example.test",
                password_hash="unused-test-hash",
                is_active=True,
                is_verified=True,
                role="owner",
                token_version=TOKEN_VERSION,
            ),
            UserMfaSecret(
                user_id=USER_ID,
                encrypted_secret=encrypt_totp_secret(mfa_secret),
                status="active",
            ),
        ]
    )
    db.commit()
    current = {"role": "owner"}

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(cash_register_router)

    def override_db():
        yield db

    def override_auth_context():
        return AuthContext(
            hotel_id=HOTEL_ID,
            user_id=USER_ID,
            user_email="cash-adjustment@example.test",
            user_role=current["role"],
            is_verified=True,
            permissions=set(),
            token_version=TOKEN_VERSION,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = override_auth_context
    try:
        yield TestClient(app), db, current, mfa_secret
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _open_session(client: TestClient) -> int:
    response = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_adjustment_defaults_are_delegable_and_require_step_up(cash_api):
    _client, db, _current, _secret = cash_api

    assert DEFAULT_MATRIX["owner"][PERMISSION_CASH_ADJUSTMENT_MANAGE] is True
    assert DEFAULT_MATRIX["co_owner"][PERMISSION_CASH_ADJUSTMENT_MANAGE] is True
    for role in ("manager", "receptionist", "housekeeping"):
        assert DEFAULT_MATRIX[role][PERMISSION_CASH_ADJUSTMENT_MANAGE] is False

    catalog_item = next(
        item for item in get_permission_catalog(db)
        if item["code"] == PERMISSION_CASH_ADJUSTMENT_MANAGE
    )
    assert catalog_item["locked"] is False
    assert catalog_item["delegable"] is True
    assert catalog_item["critical"] is False
    assert catalog_item["step_up_required"] is True
    assert permission_requires_step_up(db, PERMISSION_CASH_ADJUSTMENT_MANAGE) is True


@pytest.mark.parametrize("role", ["manager", "receptionist"])
def test_adjustment_denied_without_grant_while_income_stays_available(cash_api, role):
    client, _db, current, _secret = cash_api
    session_id = _open_session(client)
    current["role"] = role
    path = f"/api/cash-register/sessions/{session_id}/movements"

    adjustment = client.post(
        path,
        json={"movement_type": "adjustment", "amount": "1.00", "description": "conteo manual"},
    )
    assert adjustment.status_code == 403, adjustment.text

    income = client.post(
        path,
        json={"movement_type": "income", "amount": "1.00", "description": "cobro en efectivo"},
    )
    assert income.status_code == 201, income.text
    assert income.json()["movement_type"] == "income"


def test_delegated_adjustment_still_requires_a_fresh_action_bound_ticket(cash_api):
    client, db, current, mfa_secret = cash_api
    session_id = _open_session(client)
    path = f"/api/cash-register/sessions/{session_id}/movements"
    db.add(
        HotelPermissionOverride(
            hotel_id=HOTEL_ID,
            role="manager",
            permission_code=PERMISSION_CASH_ADJUSTMENT_MANAGE,
            allowed=True,
            version=1,
        )
    )
    db.commit()
    current["role"] = "manager"
    payload = {"movement_type": "adjustment", "amount": "0.01", "description": "conteo validado"}

    missing_ticket = client.post(path, json=payload)
    assert missing_ticket.status_code == 428
    assert missing_ticket.json()["detail"]["permission_code"] == PERMISSION_CASH_ADJUSTMENT_MANAGE

    issued = client.post(
        "/api/auth/step-up",
        json={
            "code": pyotp.TOTP(mfa_secret).now(),
            "permission_code": PERMISSION_CASH_ADJUSTMENT_MANAGE,
            "method": "POST",
            "path": path,
        },
    )
    assert issued.status_code == 200, issued.text
    ticket = issued.json()["ticket"]
    allowed = client.post(path, json=payload, headers={"X-Action-Step-Up-Ticket": ticket})
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["movement_type"] == "adjustment"

    replayed = client.post(path, json=payload, headers={"X-Action-Step-Up-Ticket": ticket})
    assert replayed.status_code == 428


def test_cash_operate_remains_required_for_adjustments(cash_api):
    client, _db, current, _secret = cash_api
    session_id = _open_session(client)
    current["role"] = "housekeeping"

    response = client.post(
        f"/api/cash-register/sessions/{session_id}/movements",
        json={"movement_type": "adjustment", "amount": "1.00", "description": "conteo manual"},
    )
    assert response.status_code == 403


def test_cash_adjustment_permission_migration_is_idempotent_and_keeps_overrides():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20261013_cash_adjustment_permission.py"
    )
    spec = importlib.util.spec_from_file_location("cash_adjustment_permission_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE permissions (code TEXT PRIMARY KEY, description TEXT NOT NULL, "
            "critical BOOLEAN NOT NULL, step_up_required BOOLEAN NOT NULL, delegable BOOLEAN NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE role_permission_defaults (role TEXT NOT NULL, permission_code TEXT NOT NULL, "
            "allowed BOOLEAN NOT NULL, UNIQUE(role, permission_code))"
        ))
        connection.execute(text(
            "CREATE TABLE hotel_permission_overrides (hotel_id INTEGER NOT NULL, role TEXT NOT NULL, "
            "permission_code TEXT NOT NULL, allowed BOOLEAN NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE user_permission_overrides (permission_code TEXT NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE temporary_action_grants (permission_code TEXT NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE action_step_up_ticket_uses (permission_code TEXT NOT NULL)"
        ))
        connection.execute(
            text(
                "INSERT INTO hotel_permission_overrides (hotel_id, role, permission_code, allowed) "
                "VALUES (1, 'manager', 'cash:adjustment_manage', false)"
            )
        )

        operations_context = MigrationContext.configure(connection)
        with Operations.context(operations_context):
            migration.upgrade()
            migration.upgrade()

        permission = connection.execute(
            text(
                "SELECT critical, step_up_required, delegable FROM permissions "
                "WHERE code = 'cash:adjustment_manage'"
            )
        ).one()
        assert tuple(permission) == (0, 1, 1)
        defaults = dict(connection.execute(
            text(
                "SELECT role, allowed FROM role_permission_defaults "
                "WHERE permission_code = 'cash:adjustment_manage'"
            )
        ).all())
        assert defaults == {
            "owner": 1,
            "co_owner": 1,
            "manager": 0,
            "receptionist": 0,
            "housekeeping": 0,
        }
        override = connection.execute(
            text(
                "SELECT allowed FROM hotel_permission_overrides "
                "WHERE hotel_id = 1 AND role = 'manager' AND permission_code = 'cash:adjustment_manage'"
            )
        ).scalar_one()
        assert override == 0
    engine.dispose()
