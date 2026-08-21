import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.permission import HotelPermissionOverride, UserPermissionOverride
from app.models.permission import RolePermissionDefault
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.permission_service import (
    PERMISSION_GUEST_PROHIBITION_MANAGE,
    PERMISSION_GUEST_PROHIBITION_READ,
    PERMISSION_GUEST_READ,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_RATES_UPDATE,
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    PERMISSION_ROOM_STATUS_UPDATE,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_READ,
    get_effective_permission_details,
    resolve,
    set_role_override,
    set_user_override,
    seed_default_permissions,
)


def _auth(hotel_id: int, role: str, user_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email="synthetic@example.test",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(id=10, email="owner@example.test", password_hash="synthetic", is_verified=True),
            User(id=20, email="reception@example.test", password_hash="synthetic", is_verified=True),
            User(id=30, email="other@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"),
            HotelMembership(hotel_id=2, user_id=30, role="manager", status="active"),
        ]
    )
    db.commit()

    def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    return TestClient(fastapi_app), db, engine


def test_agreed_defaults_are_explicit_and_do_not_broaden_sensitive_access(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.flush()

    assert resolve(db, 1, "owner", PERMISSION_PERMISSION_MANAGE, user_id=1)
    assert not resolve(db, 1, "co_owner", PERMISSION_PERMISSION_MANAGE, user_id=2)
    assert resolve(db, 1, "manager", PERMISSION_GUEST_PROHIBITION_MANAGE, user_id=3)
    assert resolve(db, 1, "manager", PERMISSION_RATES_UPDATE, user_id=3)
    assert not resolve(db, 1, "manager", PERMISSION_STOCK_ADJUST, user_id=3)
    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_PROHIBITION_READ, user_id=4)
    assert not resolve(db, 1, "receptionist", PERMISSION_GUEST_PROHIBITION_MANAGE, user_id=4)
    assert not resolve(db, 1, "housekeeping", PERMISSION_GUEST_READ, user_id=5)
    assert resolve(db, 1, "housekeeping", PERMISSION_ROOM_STATUS_UPDATE, user_id=5)
    assert not resolve(db, 1, "housekeeping", PERMISSION_STOCK_READ, user_id=5)


def test_resolution_precedence_is_invariant_user_role_default_deny(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add_all(
        [
            User(id=10, email="o@example.test", password_hash="synthetic", is_verified=True),
            User(id=20, email="r@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    db.add(HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"))
    db.flush()

    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_READ, user_id=20)
    set_role_override(db, 1, "receptionist", PERMISSION_GUEST_READ, False, actor_user_id=10)
    assert not resolve(db, 1, "receptionist", PERMISSION_GUEST_READ, user_id=20)
    set_user_override(db, 1, 20, "receptionist", PERMISSION_GUEST_READ, True, actor_user_id=10)
    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_READ, user_id=20)

    details = get_effective_permission_details(db, 1, "receptionist", user_id=20)
    assert details[PERMISSION_GUEST_READ]["source"] == "user_override"
    assert details[PERMISSION_PERMISSION_MANAGE] == {
        "allowed": False,
        "source": "invariant",
        "locked": True,
        "lock_reason": "owner_only",
    }


def test_only_owner_can_use_administration_catalog_and_co_owner_is_denied():
    client, db, engine = _client()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
        owner = client.get("/api/permissions/catalog")
        assert owner.status_code == 200
        assert any(row["code"] == PERMISSION_GUEST_READ for row in owner.json()["permissions"])

        fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "co_owner", 10)
        assert client.get("/api/permissions/catalog").status_code == 403
        assert client.get("/api/permissions/matrix").status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_owner_can_grant_and_revoke_user_override_then_restore_defaults():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        granted = client.put(
            "/api/permissions/user-overrides/20",
            json={"permission_code": PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, "allowed": True},
        )
        assert granted.status_code == 200
        assert granted.json()["source"] == "user_override"
        assert granted.json()["version"] == 1

        preview = client.get("/api/permissions/effective/preview", params={"user_id": 20})
        assert preview.status_code == 200
        assert preview.json()["details"][PERMISSION_RESERVATION_PROHIBITION_OVERRIDE]["allowed"] is True

        revoked = client.put(
            "/api/permissions/user-overrides/20",
            json={"permission_code": PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, "allowed": False},
        )
        assert revoked.status_code == 200
        assert revoked.json()["version"] == 2
        restored = client.delete("/api/permissions/user-overrides/20")
        assert restored.status_code == 200
        assert db.query(UserPermissionOverride).filter_by(hotel_id=1, user_id=20).count() == 0

        audit = (
            db.query(SecurityAuditLog)
            .filter(SecurityAuditLog.action == "permission.user_override.updated")
            .order_by(SecurityAuditLog.id.asc())
            .first()
        )
        details = json.loads(audit.details)
        assert details["before"] is None
        assert details["after"]["allowed"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_owner_can_restore_one_role_override_to_catalog_default_with_audit():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        changed = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_READ, "allowed": False},
        )
        assert changed.status_code == 200
        assert changed.json()["version"] == 1

        restored = client.delete(
            f"/api/permissions/overrides/role/receptionist/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
        )
        assert restored.status_code == 200
        assert restored.json() == {
            "hotel_id": 1,
            "role": "receptionist",
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": True,
            "source": "role_default",
            "restored": True,
        }
        assert db.query(HotelPermissionOverride).filter_by(
            hotel_id=1, role="receptionist", permission_code=PERMISSION_GUEST_READ
        ).one_or_none() is None

        fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "receptionist", 20)
        effective = client.get("/api/permissions/effective")
        assert effective.status_code == 200
        assert effective.json()["details"][PERMISSION_GUEST_READ] == {
            "allowed": True,
            "source": "role_default",
            "locked": False,
            "lock_reason": None,
        }

        audit = db.query(SecurityAuditLog).filter(
            SecurityAuditLog.action == "permission.override.restored"
        ).one()
        details = json.loads(audit.details)
        assert details["before"] == {
            "role": "receptionist",
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": False,
            "version": 1,
        }
        assert details["after"] == {
            "role": "receptionist",
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": True,
            "source": "role_default",
        }
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_owner_can_restore_one_user_override_to_role_default_with_audit():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        changed = client.put(
            "/api/permissions/user-overrides/20",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": False},
        )
        assert changed.status_code == 200
        assert changed.json()["version"] == 1

        restored = client.delete(
            f"/api/permissions/overrides/user/20/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
        )
        assert restored.status_code == 200
        assert restored.json() == {
            "hotel_id": 1,
            "user_id": 20,
            "role": "receptionist",
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": True,
            "source": "role_default",
            "restored": True,
        }
        assert db.query(UserPermissionOverride).filter_by(
            hotel_id=1, user_id=20, permission_code=PERMISSION_GUEST_READ
        ).one_or_none() is None

        preview = client.get("/api/permissions/effective/preview", params={"user_id": 20})
        assert preview.status_code == 200
        assert preview.json()["details"][PERMISSION_GUEST_READ]["source"] == "role_default"
        assert preview.json()["details"][PERMISSION_GUEST_READ]["allowed"] is True

        audit = db.query(SecurityAuditLog).filter(
            SecurityAuditLog.action == "permission.user_override.restored"
        ).one()
        details = json.loads(audit.details)
        assert details["before"] == {
            "user_id": 20,
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": False,
            "version": 1,
        }
        assert details["after"] == {
            "user_id": 20,
            "role": "receptionist",
            "permission_code": PERMISSION_GUEST_READ,
            "allowed": True,
            "source": "role_default",
        }
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_restore_override_rejects_stale_expected_version_with_409():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        created = client.put(
            "/api/permissions/override",
            json={"role": "receptionist", "permission_code": PERMISSION_GUEST_READ, "allowed": False},
        )
        assert created.status_code == 200

        updated = client.put(
            "/api/permissions/override",
            json={
                "role": "receptionist",
                "permission_code": PERMISSION_GUEST_READ,
                "allowed": True,
                "expected_version": 1,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        stale_restore = client.delete(
            f"/api/permissions/role-overrides/receptionist/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
        )
        assert stale_restore.status_code == 409
        assert db.query(HotelPermissionOverride).filter_by(
            hotel_id=1, role="receptionist", permission_code=PERMISSION_GUEST_READ
        ).one().version == 2
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_restore_cannot_leave_owner_without_permission_management():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        seed_default_permissions(db)
        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="owner",
                permission_code=PERMISSION_PERMISSION_MANAGE,
                allowed=False,
                version=1,
            )
        )
        db.commit()

        restored = client.delete(
            f"/api/permissions/overrides/role/owner/{PERMISSION_PERMISSION_MANAGE}",
            params={"expected_version": 1},
        )
        assert restored.status_code == 200
        assert restored.json()["allowed"] is True
        assert resolve(db, 1, "owner", PERMISSION_PERMISSION_MANAGE, user_id=10) is True
        assert db.query(HotelPermissionOverride).filter_by(
            hotel_id=1, role="owner", permission_code=PERMISSION_PERMISSION_MANAGE
        ).one_or_none() is None
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_user_override_rejects_self_elevation_and_cross_hotel_id_without_disclosure():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        self_change = client.put(
            "/api/permissions/user-overrides/10",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": False},
        )
        assert self_change.status_code == 422

        cross_hotel = client.put(
            "/api/permissions/user-overrides/30",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": True},
        )
        unknown = client.put(
            "/api/permissions/user-overrides/999999",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": True},
        )
        assert cross_hotel.status_code == unknown.status_code == 404
        assert cross_hotel.json() == unknown.json()
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_runtime_seeding_never_overwrites_existing_backfilled_default(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    seed_default_permissions(db)
    backfilled = db.query(RolePermissionDefault).filter_by(
        role="receptionist", permission_code=PERMISSION_GUEST_READ
    ).one()
    backfilled.allowed = False
    db.flush()

    seed_default_permissions(db)

    db.refresh(backfilled)
    assert backfilled.allowed is False
    assert resolve(db, 1, "receptionist", PERMISSION_GUEST_READ, user_id=20) is False
