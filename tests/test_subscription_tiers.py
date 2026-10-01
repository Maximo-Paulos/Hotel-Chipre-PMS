from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.master_admin.models import MasterAdminAuditEvent
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.subscription import HotelSubscription, SubscriptionPlan
from app.models.subscription_v2 import Subscription, SubscriptionAdjustment, SubscriptionEvent
from app.models.user import User
from app.services.security import create_access_token, decode_access_token, hash_password
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import PERMISSION_SETTINGS_SUBSCRIPTION_MANAGE
from app.services.hotel_service import _ensure_membership_and_subscription
from app.services.subscription_entitlements import (
    get_subscription_snapshot,
    grant_comped,
    plan_catalog,
    start_trial,
    suspend_subscription,
)
from app.services.subscription_service import (
    delete_entitlement_override,
    ensure_subscription,
    set_entitlement_override,
    set_subscription_plan,
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
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

    with TestClient(main_module.app) as test_client:
        yield test_client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _ensure_hotel(db, hotel_id: int, owner_email: str = "owner@test.com") -> None:
    if not db.get(HotelConfiguration, hotel_id):
        db.add(
            HotelConfiguration(
                id=hotel_id,
                owner_email=owner_email,
                hotel_name=f"Hotel {hotel_id}",
                subscription_active=True,
            )
        )
        db.flush()


def _auth_headers(db, hotel_id: int, *, membership_role: str | None = "owner", user_role: str = "owner") -> dict[str, str]:
    _ensure_hotel(db, hotel_id)
    email = f"{user_role}-{membership_role or 'global'}-{hotel_id}@test.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password("Demo123!pass"),
            is_active=True,
            is_verified=True,
            role=user_role,
        )
        db.add(user)
        db.flush()
    if membership_role and not db.query(HotelMembership).filter(
        HotelMembership.hotel_id == hotel_id,
        HotelMembership.user_id == user.id,
    ).first():
        db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role=membership_role, status="active"))
        db.flush()

    token = create_access_token(
        subject=user.id,
        extra={
            "email": user.email,
            "role": membership_role or user_role,
            "verified": True,
            "hotel_id": hotel_id,
            "hotel_ids": [hotel_id],
        },
    )
    headers = {"Authorization": f"Bearer {token}"}
    if membership_role:
        headers["X-Hotel-Id"] = str(hotel_id)
    return headers


def _step_up_headers(
    headers: dict[str, str], *, method: str, path: str, permission_code: str
) -> dict[str, str]:
    claims = decode_access_token(headers["Authorization"].removeprefix("Bearer "))
    user_id = int(claims["sub"])
    hotel_id = int(headers["X-Hotel-Id"])
    token_version = int(claims.get("token_version", 0))
    return {
        **headers,
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=user_id,
            hotel_id=hotel_id,
            token_version=token_version,
            permission_code=permission_code,
            method=method,
            path=path,
        ),
    }


def test_subscription_catalog_has_updated_tier_limits():
    plans = {plan["code"]: plan for plan in plan_catalog()}

    assert plans["starter"]["room_limit"] == 15
    assert plans["starter"]["staff_limit"] == 3
    assert plans["pro"]["room_limit"] == 40
    assert plans["pro"]["staff_limit"] == 8
    assert plans["ultra"]["room_limit"] == 80
    assert plans["ultra"]["staff_limit"] == 20
    assert all(plan["price_month"] is None for plan in plans.values())


def test_trial_auto_suspends_after_fourteen_days(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=1)
        subscription = start_trial(db, hotel_id=1, plan_code="pro", actor={"source": "test"})
        assert get_subscription_snapshot(db, 1)["trial_available"] is False
        subscription.trial_end_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.flush()

        snapshot = get_subscription_snapshot(db, 1)
        event_types = [event.event_type for event in db.query(SubscriptionEvent).filter(SubscriptionEvent.hotel_id == 1).all()]

        assert snapshot["status"] == "suspended"
        assert "trial_started" in event_types
        assert "trial_ended" in event_types
        assert "subscription_suspended" in event_types
    finally:
        db.close()


def test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=71)
        valid_until = datetime.now(timezone.utc) + timedelta(days=30)
        first = grant_comped(
            db,
            hotel_id=71,
            plan_code="ultra",
            reason="pilot-comp",
            actor={"source": "test"},
            valid_until=valid_until,
            idempotency_key="comped-71-pilot-001",
        )
        second = grant_comped(
            db,
            hotel_id=71,
            plan_code="ultra",
            reason="pilot-comp",
            actor={"source": "retry"},
            valid_until=valid_until,
            idempotency_key="comped-71-pilot-001",
        )
        db.commit()

        assert first.id == second.id
        adjustment = db.query(SubscriptionAdjustment).filter_by(hotel_id=71).one()
        assert adjustment.valid_until is not None
        assert abs((adjustment.valid_until.replace(tzinfo=timezone.utc) - valid_until).total_seconds()) < 1
        assert db.query(SubscriptionAdjustment).filter_by(hotel_id=71).count() == 1
        assert db.query(SubscriptionEvent).filter_by(hotel_id=71, event_type="comped_granted").count() == 1
    finally:
        db.close()


def test_subscription_adjustment_preserves_history_when_hotel_delete_is_attempted(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        hotel = HotelConfiguration(id=72, hotel_name="Adjustment Hotel", subscription_active=True)
        db.add(hotel)
        db.flush()
        grant_comped(db, hotel_id=72, plan_code="pro", reason="support-credit", actor={"source": "test"})
        db.commit()

        db.delete(hotel)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        assert db.get(HotelConfiguration, 72) is not None
        assert db.query(SubscriptionAdjustment).filter_by(hotel_id=72).count() == 1
    finally:
        db.close()


def test_trial_does_not_replace_existing_legacy_paid_plan(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=75)
        pro = SubscriptionPlan(code="pro", name="Pro", room_limit=40)
        db.add(pro)
        db.flush()
        legacy = HotelSubscription(hotel_id=75, plan_id=pro.id, status="active")
        db.add(legacy)
        db.flush()

        with pytest.raises(HTTPException) as raised:
            start_trial(db, hotel_id=75, plan_code="pro", actor={"source": "test"})

        assert raised.value.status_code == 409
        assert db.query(Subscription).filter_by(hotel_id=75).count() == 0
        assert db.get(HotelSubscription, legacy.id).plan_id == pro.id
        assert db.get(HotelSubscription, legacy.id).status == "active"
    finally:
        db.close()


def test_comped_override_requires_master_admin_session_before_disclosing_hotel_state(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    try:
        admin_headers = _auth_headers(db, hotel_id=1, membership_role=None, user_role="platform_admin")
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/admin/subscription/comped-override",
        json={
            "hotel_id": 99999,
            "plan_code": "ultra",
            "reason": "unknown-hotel",
            "valid_until": "2099-01-01T00:00:00+00:00",
        },
        headers=admin_headers,
    )

    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Sesion master requerida"

    db = SessionLocal()
    try:
        assert db.query(Subscription).filter(Subscription.hotel_id == 99999).count() == 0
        assert db.query(SubscriptionEvent).filter(SubscriptionEvent.hotel_id == 99999).count() == 0
        assert db.query(HotelSubscription).filter(HotelSubscription.hotel_id == 99999).count() == 0
    finally:
        db.close()


def test_role_gating_for_trial_and_comped_override(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=3)
        owner_headers = _auth_headers(db, hotel_id=3, membership_role="owner", user_role="owner")
        manager_headers = _auth_headers(db, hotel_id=3, membership_role="manager", user_role="manager")
        owner_no_admin_headers = _auth_headers(db, hotel_id=3, membership_role="owner", user_role="owner")
        platform_admin_headers = _auth_headers(db, hotel_id=3, membership_role="owner", user_role="platform_admin")
        db.commit()
    finally:
        db.close()

    owner_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=_step_up_headers(
            owner_headers,
            method="POST",
            path="/api/subscription/trial",
            permission_code=PERMISSION_SETTINGS_SUBSCRIPTION_MANAGE,
        ),
    )
    owner_ultra_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "ultra"},
        headers=_step_up_headers(
            owner_headers,
            method="POST",
            path="/api/subscription/trial",
            permission_code=PERMISSION_SETTINGS_SUBSCRIPTION_MANAGE,
        ),
    )
    owner_repeated_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=_step_up_headers(
            owner_headers,
            method="POST",
            path="/api/subscription/trial",
            permission_code=PERMISSION_SETTINGS_SUBSCRIPTION_MANAGE,
        ),
    )
    manager_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=manager_headers,
    )
    owner_plan_change = test_client.post(
        "/api/subscription/plan",
        json={"plan_code": "ultra"},
        headers=owner_headers,
    )
    owner_entitlement_override = test_client.post(
        "/api/subscription/entitlements/override",
        json={"code": "reports.advanced", "value": True},
        headers=owner_headers,
    )
    owner_entitlement_delete = test_client.delete(
        "/api/subscription/entitlements/override/rooms.max_active",
        headers=owner_headers,
    )
    owner_admin_override = test_client.post(
        "/api/admin/subscription/comped-override",
        json={
            "hotel_id": 3,
            "plan_code": "pro",
            "reason": "should-fail",
            "valid_until": "2099-01-01T00:00:00+00:00",
        },
        headers=owner_no_admin_headers,
    )
    admin_plan_change = test_client.post(
        "/api/subscription/plan",
        json={"plan_code": "ultra"},
        headers=platform_admin_headers,
    )
    admin_entitlement_override = test_client.post(
        "/api/subscription/entitlements/override",
        json={"code": "reports.advanced", "value": True},
        headers=platform_admin_headers,
    )
    owner_trial_after_admin_plan_change = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=_step_up_headers(
            owner_headers,
            method="POST",
            path="/api/subscription/trial",
            permission_code=PERMISSION_SETTINGS_SUBSCRIPTION_MANAGE,
        ),
    )

    assert owner_trial.status_code == 200, owner_trial.text
    assert owner_trial.json()["trial_available"] is False
    assert owner_ultra_trial.status_code == 400, owner_ultra_trial.text
    assert owner_repeated_trial.status_code == 409, owner_repeated_trial.text
    assert manager_trial.status_code == 403, manager_trial.text
    assert owner_plan_change.status_code == 401, owner_plan_change.text
    assert owner_entitlement_override.status_code == 401, owner_entitlement_override.text
    assert owner_entitlement_delete.status_code == 401, owner_entitlement_delete.text
    assert owner_admin_override.status_code == 401, owner_admin_override.text
    assert admin_plan_change.status_code == 401, admin_plan_change.text
    assert admin_entitlement_override.status_code == 401, admin_entitlement_override.text
    assert owner_trial_after_admin_plan_change.status_code == 409, owner_trial_after_admin_plan_change.text

    db = SessionLocal()
    try:
        assert db.query(SubscriptionEvent).filter_by(hotel_id=3, event_type="trial_started").count() == 1
        admin_actions = {
            row.action
            for row in db.query(MasterAdminAuditEvent).filter(MasterAdminAuditEvent.target_id == "3").all()
        }
        assert "subscription_plan_activation_blocked" not in admin_actions
        assert "subscription_entitlement_override_set" not in admin_actions
        subscription = db.query(Subscription).filter_by(hotel_id=3).one()
        assert subscription.plan == "pro"
        assert subscription.status == "trialing"
    finally:
        db.close()


def test_manual_transitions_emit_events(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=9)
        start_trial(db, hotel_id=9, plan_code="starter", actor={"source": "test"})
        suspend_subscription(db, hotel_id=9, reason="manual-freeze", actor={"source": "test"})
        grant_comped(db, hotel_id=9, plan_code="ultra", reason="vip-owner", actor={"source": "test"})

        event_types = [
            event.event_type
            for event in db.query(SubscriptionEvent).filter(SubscriptionEvent.hotel_id == 9).order_by(SubscriptionEvent.id.asc())
        ]
        assert event_types == ["trial_started", "subscription_suspended", "comped_granted"]
    finally:
        db.close()


def test_legacy_compatibility_bootstrap_also_creates_v2_subscription(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=73)

        legacy = ensure_subscription(db, hotel_id=73)
        v2 = db.query(Subscription).filter(Subscription.hotel_id == 73).one()

        assert legacy.plan.code == "starter"
        assert v2.plan == "starter"
        assert v2.status == "active"
    finally:
        db.close()


def test_hotel_bootstrap_and_legacy_plan_entry_point_use_v2_write_path(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=74)
        _ensure_membership_and_subscription(db, hotel_id=74, owner_email="missing-owner@test.com")

        initial = db.query(Subscription).filter(Subscription.hotel_id == 74).one()
        assert initial.plan == "starter"

        result = set_subscription_plan(db, hotel_id=74, plan_code="pro")
        db.expire_all()
        v2 = db.query(Subscription).filter(Subscription.hotel_id == 74).one()
        legacy = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == 74).one()

        assert result["plan"] == "pro"
        assert v2.plan == "pro"
        assert legacy.plan.code == "pro"
    finally:
        db.close()


def test_room_limit_override_updates_v2_and_legacy_projection(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=75)
        ensure_subscription(db, hotel_id=75)

        set_entitlement_override(db, 75, "rooms.max_active", 7, "int")
        v2 = db.query(Subscription).filter(Subscription.hotel_id == 75).one()
        legacy = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == 75).one()
        assert v2.room_limit == 7
        assert legacy.room_limit_override == 7

        delete_entitlement_override(db, 75, "rooms.max_active")
        assert v2.room_limit == 15
        assert legacy.room_limit_override == 15
    finally:
        db.close()


def test_ensure_subscription_rebuilds_a_missing_legacy_projection(db, hotel_config):
    """A hotel can carry the canonical v2 row without its legacy projection.

    ensure_subscription_seed() used to return early whenever the v2 row existed,
    so the projection was never rebuilt and ensure_subscription() raised
    "No se pudo inicializar la suscripción del hotel" on every call. That call
    sits under room creation, so POST /api/rooms/ answered 500 for such a hotel
    (seen in the e2e business journey).
    """
    db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_config.id).delete()
    db.query(Subscription).filter(Subscription.hotel_id == hotel_config.id).delete()
    db.add(Subscription(hotel_id=hotel_config.id, plan="pro", status="active", room_limit=40, staff_limit=10, can_write_cache=True))
    db.flush()
    assert db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_config.id).count() == 0

    legacy = ensure_subscription(db, hotel_config.id)

    assert legacy.hotel_id == hotel_config.id
    assert legacy.room_limit_override == 40
    assert legacy.status == "active"
    # Rebuilt from the v2 row, not reset to the starter default.
    assert legacy.plan.code == "pro"
