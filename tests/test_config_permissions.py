# -*- coding: utf-8 -*-
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa
from app.models.hotel_config import HotelConfiguration
from app.dependencies.auth import AuthContext
from app.services.permission_service import PERMISSION_CONFIG_MANAGE, resolve, set_override


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
def ctx(client_with_db):
    client, db = client_with_db
    cfg = HotelConfiguration(id=1)
    db.add(cfg)
    db.commit()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = override_auth_context
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()


def test_config_defaults_include_permissions(ctx):
    client, db = ctx
    r = client.get("/api/config/")
    assert r.status_code == 200
    body = r.json()
    assert body["receptionist_view_past_days"] == 0
    assert body["receptionist_view_future_days"] == 7
    assert body["allow_revenue_manager"] is True
    assert body["allow_revenue_receptionist"] is False


def test_config_update_permissions(ctx):
    client, db = ctx
    payload = {
        "receptionist_view_past_days": 2,
        "receptionist_view_future_days": 10,
        "allow_revenue_manager": False,
        "allow_revenue_receptionist": True,
    }
    r = client.patch("/api/config/", json=payload)
    assert r.status_code == 200
    body = r.json()
    for k, v in payload.items():
        assert body[k] == v


def test_config_rejects_invalid_timezone(ctx):
    client, db = ctx
    r = client.patch("/api/config/", json={"hotel_timezone": "Not/A_Real_Zone"})
    assert r.status_code == 422


# C5: config:manage is a delegable permission (SettingsPermissionsPage), so
# the /api/config endpoints must respect a role override, not just the
# owner/co_owner base roles.


def test_config_manage_permission_defaults(ctx):
    client, db = ctx
    assert resolve(db, 1, "owner", PERMISSION_CONFIG_MANAGE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_CONFIG_MANAGE) is True
    assert resolve(db, 1, "manager", PERMISSION_CONFIG_MANAGE) is False
    assert resolve(db, 1, "receptionist", PERMISSION_CONFIG_MANAGE) is False
    assert resolve(db, 1, "housekeeping", PERMISSION_CONFIG_MANAGE) is False


def _override_role(role: str):
    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=2,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return override_auth_context


def test_manager_without_config_manage_permission_is_denied(ctx):
    client, db = ctx
    fastapi_app.dependency_overrides[get_auth_context_target()] = _override_role("manager")

    assert client.get("/api/config/").status_code == 403
    assert client.patch("/api/config/", json={"receptionist_view_future_days": 5}).status_code == 403
    assert client.get("/api/config/email/status").status_code == 403


def test_manager_cannot_cross_config_manage_security_ceiling(ctx):
    client, db = ctx
    with pytest.raises(ValueError, match="techo de seguridad"):
        set_override(db, 1, "manager", PERMISSION_CONFIG_MANAGE, True, user_id=None)
    fastapi_app.dependency_overrides[get_auth_context_target()] = _override_role("manager")

    assert client.get("/api/config/").status_code == 403
    assert client.patch("/api/config/", json={"receptionist_view_future_days": 5}).status_code == 403
    assert client.get("/api/config/email/status").status_code == 403
