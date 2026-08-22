from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
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
from app.models.subscription import HotelSubscription
from app.models.subscription_v2 import Subscription, SubscriptionAdjustment, SubscriptionEvent
from app.models.user import User
from app.services.security import create_access_token, hash_password
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


def test_subscription_catalog_has_updated_tier_limits():
    plans = {plan["code"]: plan for plan in plan_catalog()}

    assert plans["starter"]["room_limit"] == 15
    assert plans["starter"]["staff_limit"] == 3
    assert plans["pro"]["room_limit"] == 40
    assert plans["pro"]["staff_limit"] == 8
    assert plans["ultra"]["room_limit"] == 80
    assert plans["ultra"]["staff_limit"] == 20


def test_trial_auto_suspends_after_fourteen_days(client):
    _, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=1)
        subscription = start_trial(db, hotel_id=1, plan_code="pro", actor={"source": "test"})
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


def test_comped_override_records_audit_event(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    try:
        _ensure_hotel(db, hotel_id=7)
        admin_headers = _auth_headers(db, hotel_id=999, membership_role=None, user_role="platform_admin")
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/admin/subscription/comped-override",
        json={"hotel_id": 7, "plan_code": "ultra", "reason": "pilot-comp"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "comped"
    assert payload["plan"] == "ultra"

    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "platform_admin-global-999@test.com").one()
        latest_event = (
            db.query(SubscriptionEvent)
            .filter(SubscriptionEvent.hotel_id == 7)
            .order_by(SubscriptionEvent.id.desc())
            .first()
        )
        assert latest_event is not None
        assert latest_event.event_type == "comped_granted"
        assert "pilot-comp" in (latest_event.payload or "")

        audit_event = (
            db.query(MasterAdminAuditEvent)
            .filter(MasterAdminAuditEvent.action == "comped_override_grant")
            .one()
        )
        assert audit_event.actor_user_id == admin_user.id
        assert audit_event.outcome == "success"
        assert audit_event.target_type == "hotel"
        assert audit_event.target_id == "7"
        assert audit_event.request_path == "/api/admin/subscription/comped-override"
        assert audit_event.request_method == "POST"
        assert json.loads(audit_event.metadata_json or "{}") == {
            "hotel_id": 7,
            "plan_code": "ultra",
            "reason": "pilot-comp",
        }
        adjustment = db.query(SubscriptionAdjustment).filter_by(hotel_id=7).one()
        assert adjustment.adjustment_type == "override"
        assert adjustment.plan_code == "ultra"
        assert adjustment.reason == "pilot-comp"
        assert adjustment.actor_user_id == admin_user.id
        assert adjustment.actor_role == "platform_admin"
        assert adjustment.valid_until is None
        assert adjustment.idempotency_key
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


def test_comped_override_rejects_unknown_hotel_without_subscription_state(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    try:
        admin_headers = _auth_headers(db, hotel_id=1, membership_role=None, user_role="platform_admin")
        db.commit()
    finally:
        db.close()

    response = test_client.post(
        "/api/admin/subscription/comped-override",
        json={"hotel_id": 99999, "plan_code": "ultra", "reason": "unknown-hotel"},
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Hotel no encontrado"

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
        db.commit()
    finally:
        db.close()

    owner_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=owner_headers,
    )
    manager_trial = test_client.post(
        "/api/subscription/trial",
        json={"plan_code": "pro"},
        headers=manager_headers,
    )
    owner_admin_override = test_client.post(
        "/api/admin/subscription/comped-override",
        json={"hotel_id": 3, "plan_code": "pro", "reason": "should-fail"},
        headers=owner_no_admin_headers,
    )

    assert owner_trial.status_code == 200, owner_trial.text
    assert manager_trial.status_code == 403, manager_trial.text
    assert owner_admin_override.status_code == 403, owner_admin_override.text


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
