# -*- coding: utf-8 -*-
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base
import app.models  # noqa
from app.models.hotel_config import HotelConfiguration
from app.models.audit_log import AuditLog
from app.dependencies.auth import AuthContext
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import (
    PERMISSION_CONFIG_MANAGE,
    PERMISSION_HOTEL_SETTINGS_READ,
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
    PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
    PERMISSION_SETTINGS_FX_MANAGE,
    resolve,
    set_override,
)


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
    assert "allow_revenue_manager" not in body
    assert "allow_revenue_receptionist" not in body


def test_manual_rate_permissions_keep_owner_policy_separate_from_bounded_entry(ctx):
    _client, db = ctx
    assert resolve(db, 1, "owner", PERMISSION_RESERVATION_MANUAL_RATE) is True
    assert resolve(db, 1, "owner", PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE) is True
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_MANUAL_RATE) is False
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_MANUAL_RATE_LIMITED) is True
    assert resolve(db, 1, "co_owner", PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE) is False
    assert resolve(db, 1, "manager", PERMISSION_RESERVATION_MANUAL_RATE_LIMITED) is True
    assert resolve(db, 1, "manager", PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE) is False
    assert resolve(db, 1, "receptionist", PERMISSION_RESERVATION_MANUAL_RATE_LIMITED) is False


def test_config_update_permissions(ctx):
    client, db = ctx
    payload = {"allow_overbooking": True}
    r = client.patch("/api/config/", json=payload)
    assert r.status_code == 200
    body = r.json()
    for k, v in payload.items():
        assert body[k] == v


def test_config_read_permission_allows_get_without_allowing_updates(ctx):
    client, db = ctx
    set_override(db, 1, "manager", PERMISSION_HOTEL_SETTINGS_READ, True, user_id=None)

    def manager_context():
        return AuthContext(
            hotel_id=1,
            user_id=12,
            user_email="manager@test.com",
            user_role="manager",
            is_verified=True,
            permissions={PERMISSION_HOTEL_SETTINGS_READ},
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = manager_context

    read_response = client.get("/api/config/")
    update_response = client.patch("/api/config/", json={"allow_overbooking": True})

    assert read_response.status_code == 200, read_response.text
    assert update_response.status_code == 403, update_response.text


def test_fx_market_configuration_is_audited_and_accepts_both_display_quotes(ctx):
    client, db = ctx
    payload = {"fx_conversion_rate_type": "blue", "fx_display_rate_types": ["oficial", "blue"]}
    challenge = client.patch("/api/config/", json=payload)
    assert challenge.status_code == 428
    assert challenge.json()["detail"]["permission_code"] == PERMISSION_SETTINGS_FX_MANAGE
    ticket = create_action_step_up_ticket(
        user_id=1,
        hotel_id=1,
        token_version=0,
        permission_code=PERMISSION_SETTINGS_FX_MANAGE,
        method="PATCH",
        path="/api/config/",
    )
    response = client.patch(
        "/api/config/",
        json=payload,
        headers={"X-Action-Step-Up-Ticket": ticket},
    )

    assert response.status_code == 200, response.text
    assert response.json()["fx_conversion_rate_type"] == "blue"
    assert response.json()["fx_display_rate_types"] == ["oficial", "blue"]
    log = (
        db.query(AuditLog)
        .filter(AuditLog.hotel_id == 1, AuditLog.table_name == "hotel_configuration")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert log is not None
    assert json.loads(log.payload_before) == {
        "fx_conversion_rate_type": "oficial",
        "fx_display_rate_types": ["oficial"],
    }
    assert json.loads(log.payload_after) == {
        "fx_conversion_rate_type": "blue",
        "fx_display_rate_types": ["oficial", "blue"],
    }


def test_co_owner_can_change_fx_market_after_step_up(ctx):
    client, _db = ctx

    def co_owner_context():
        return AuthContext(
            hotel_id=1,
            user_id=11,
            user_email="co-owner@test.com",
            user_role="co_owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context_target()] = co_owner_context
    payload = {"fx_conversion_rate_type": "blue"}
    challenge = client.patch("/api/config/", json=payload)
    assert challenge.status_code == 428
    assert challenge.json()["detail"]["permission_code"] == PERMISSION_SETTINGS_FX_MANAGE

    ticket = create_action_step_up_ticket(
        user_id=11,
        hotel_id=1,
        token_version=0,
        permission_code=PERMISSION_SETTINGS_FX_MANAGE,
        method="PATCH",
        path="/api/config/",
    )
    response = client.patch(
        "/api/config/",
        json=payload,
        headers={"X-Action-Step-Up-Ticket": ticket},
    )
    assert response.status_code == 200, response.text
    assert response.json()["fx_conversion_rate_type"] == "blue"


@pytest.mark.parametrize(
    "payload",
    [
        {"fx_conversion_rate_type": "tarjeta"},
        {"fx_display_rate_types": []},
        {"fx_display_rate_types": ["oficial", "oficial"]},
        {"fx_display_rate_types": ["cripto"]},
    ],
)
def test_fx_market_configuration_rejects_unsupported_or_ambiguous_quotes(ctx, payload):
    client, _db = ctx
    response = client.patch("/api/config/", json=payload)
    assert response.status_code == 422, response.text


def test_config_saves_hotel_checkin_and_checkout_times(ctx):
    client, db = ctx
    response = client.patch(
        "/api/config/",
        json={"check_in_time": "14:00", "check_out_time": "10:00"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["check_in_time"] == "14:00"
    assert response.json()["check_out_time"] == "10:00"
    db.expire_all()
    stored = db.get(HotelConfiguration, 1)
    assert stored.check_in_time == "14:00"
    assert stored.check_out_time == "10:00"


@pytest.mark.parametrize("field", ["check_in_time", "check_out_time"])
@pytest.mark.parametrize("value", ["2pm", "24:00", "12:60", "noon"])
def test_config_rejects_invalid_hotel_schedule_time(ctx, field, value):
    client, _db = ctx
    response = client.patch("/api/config/", json={field: value})
    assert response.status_code == 422


@pytest.mark.parametrize("policy", ["deposit", "total", "free"])
def test_config_can_select_checkin_payment_policy(ctx, policy):
    client, _db = ctx
    response = client.patch("/api/config/", json={"checkin_payment_policy": policy})
    assert response.status_code == 200, response.text
    assert response.json()["checkin_payment_policy"] == policy


def test_config_rejects_unknown_checkin_payment_policy(ctx):
    client, _db = ctx
    response = client.patch("/api/config/", json={"checkin_payment_policy": "waive"})
    assert response.status_code == 422


def test_config_rejects_null_checkin_payment_policy(ctx):
    client, _db = ctx
    response = client.patch("/api/config/", json={"checkin_payment_policy": None})
    assert response.status_code == 422


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
    assert client.patch("/api/config/", json={"hotel_name": "Otro hotel"}).status_code == 403
    assert client.get("/api/config/email/status").status_code == 403


def test_housekeeping_can_read_only_the_hotel_interface_language(ctx):
    client, db = ctx
    db.get(HotelConfiguration, 1).interface_language = "en"
    db.commit()
    fastapi_app.dependency_overrides[get_auth_context_target()] = _override_role("housekeeping")

    response = client.get("/api/config/interface-language")

    assert response.status_code == 200
    assert response.json() == {"interface_language": "en"}
    assert client.get("/api/config/").status_code == 403
    assert client.get("/api/config/email/status").status_code == 403


def test_owner_can_grant_manager_config_manage_override(ctx):
    client, db = ctx
    set_override(db, 1, "manager", PERMISSION_HOTEL_SETTINGS_READ, True, user_id=None)
    set_override(db, 1, "manager", PERMISSION_CONFIG_MANAGE, True, user_id=None)
    assert resolve(db, 1, "manager", PERMISSION_HOTEL_SETTINGS_READ) is True
    assert resolve(db, 1, "manager", PERMISSION_CONFIG_MANAGE) is True
    fastapi_app.dependency_overrides[get_auth_context_target()] = _override_role("manager")

    assert client.get("/api/config/").status_code == 200
    assert client.patch("/api/config/", json={"hotel_name": "Otro hotel"}).status_code == 200
    assert client.get("/api/config/email/status").status_code == 200


def _manual_rate_policy_step_up_headers():
    ticket = create_action_step_up_ticket(
        user_id=1,
        hotel_id=1,
        token_version=0,
        permission_code=PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
        method="PATCH",
        path="/api/config/",
    )
    return {"X-Action-Step-Up-Ticket": ticket}


def test_manual_rate_policy_configuration_requires_owner_step_up(ctx):
    client, db = ctx

    response = client.patch(
        "/api/config/",
        json={
            "manual_rate_min_adjustment_pct": -25,
            "manual_rate_max_adjustment_pct": 10,
        },
    )

    assert response.status_code == 428, response.text
    stored = db.get(HotelConfiguration, 1)
    assert stored.manual_rate_min_adjustment_pct is None
    assert stored.manual_rate_max_adjustment_pct is None


def test_manual_rate_policy_configuration_is_audited_and_requires_both_bounds(ctx):
    client, db = ctx

    incomplete = client.patch(
        "/api/config/",
        json={"manual_rate_min_adjustment_pct": -25},
        headers=_manual_rate_policy_step_up_headers(),
    )
    assert incomplete.status_code == 422, incomplete.text

    invalid_order = client.patch(
        "/api/config/",
        json={
            "manual_rate_min_adjustment_pct": 10,
            "manual_rate_max_adjustment_pct": -25,
        },
        headers=_manual_rate_policy_step_up_headers(),
    )
    assert invalid_order.status_code == 422, invalid_order.text

    response = client.patch(
        "/api/config/",
        json={
            "manual_rate_min_adjustment_pct": -25,
            "manual_rate_max_adjustment_pct": 10,
        },
        headers=_manual_rate_policy_step_up_headers(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["manual_rate_min_adjustment_pct"] == "-25.00"
    assert response.json()["manual_rate_max_adjustment_pct"] == "10.00"

    audit = db.query(AuditLog).filter_by(
        hotel_id=1,
        table_name="hotel_configuration",
        record_id=1,
    ).one()
    assert audit.actor_user_id == 1
    assert json.loads(audit.payload_after) == {
        "manual_rate_min_adjustment_pct": "-25",
        "manual_rate_max_adjustment_pct": "10",
    }


def test_clearing_manual_rate_policy_requires_clearing_both_bounds(ctx):
    client, db = ctx
    config = db.get(HotelConfiguration, 1)
    config.manual_rate_min_adjustment_pct = -25
    config.manual_rate_max_adjustment_pct = 10
    db.commit()

    response = client.patch(
        "/api/config/",
        json={"manual_rate_min_adjustment_pct": None},
        headers=_manual_rate_policy_step_up_headers(),
    )

    assert response.status_code == 422, response.text
    db.refresh(config)
    assert str(config.manual_rate_min_adjustment_pct) == "-25.00"
    assert str(config.manual_rate_max_adjustment_pct) == "10.00"
