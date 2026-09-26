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
from app.models.hotel_role import HotelRole
from app.models.permission import HotelPermissionOverride, UserPermissionOverride
from app.models.permission import RolePermissionDefault
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.action_step_up_service import (
    create_action_step_up_ticket,
    create_permission_admin_read_step_up_ticket,
    is_permission_admin_read_action,
)
from app.services.permission_service import (
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
    PERMISSION_GUEST_PROHIBITION_MANAGE,
    PERMISSION_GUEST_PROHIBITION_READ,
    PERMISSION_GUEST_READ,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_SETTINGS_USERS_MANAGE,
    PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE,
    PERMISSION_SETTINGS_ASSISTANT_VIEW,
    PERMISSION_SETTINGS_DAILY_REPORT_MANAGE,
    PERMISSION_SETTINGS_DAILY_REPORT_VIEW,
    PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
    PERMISSION_RATES_UPDATE,
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    PERMISSION_ROOM_STATUS_UPDATE,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_READ,
    _ROLE_SCOPES,
    get_effective_permission_details,
    get_matrix,
    resolve,
    set_role_override,
    set_user_override,
    seed_default_permissions,
)


def _step_up_headers(path: str, *, method: str):
    """Issue a synthetic RBAC-read grant or action-bound ticket."""
    if is_permission_admin_read_action(method, path):
        return {
            "X-Action-Step-Up-Ticket": create_permission_admin_read_step_up_ticket(
                user_id=10,
                hotel_id=1,
                token_version=0,
            )
        }
    return {
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=10,
            hotel_id=1,
            token_version=0,
            permission_code=PERMISSION_PERMISSION_MANAGE,
            method=method,
            path=path,
        )
    }


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


def test_legacy_explicit_denials_survive_permission_splits(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(User(id=20, email="co-owner@example.test", password_hash="synthetic", is_verified=True))
    db.flush()
    seed_default_permissions(db)
    db.add(HotelMembership(hotel_id=1, user_id=20, role="co_owner", status="active"))
    db.flush()
    db.add_all(
        [
            UserPermissionOverride(
                hotel_id=1,
                user_id=20,
                permission_code=PERMISSION_SETTINGS_ASSISTANT_VIEW,
                allowed=False,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="co_owner",
                permission_code=PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
                allowed=False,
            ),
        ]
    )
    db.flush()

    details = get_effective_permission_details(db, 1, "co_owner", user_id=20)

    assistant = details[PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE]
    assert assistant["allowed"] is False
    assert assistant["source"] == "legacy_user_deny"
    assert assistant["legacy_permission_code"] == PERMISSION_SETTINGS_ASSISTANT_VIEW

    for code in (PERMISSION_SETTINGS_DAILY_REPORT_VIEW, PERMISSION_SETTINGS_DAILY_REPORT_MANAGE):
        daily_report = details[code]
        assert daily_report["allowed"] is False
        assert daily_report["source"] == "legacy_role_deny"
        assert daily_report["legacy_permission_code"] == PERMISSION_SETTINGS_NOTIFICATIONS_VIEW

    # Authorization enforcement must consume the same effective decision as
    # the administrative matrix; these legacy denials must fail closed at runtime.
    assert not resolve(
        db,
        1,
        "co_owner",
        PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE,
        user_id=20,
    )
    for code in (PERMISSION_SETTINGS_DAILY_REPORT_VIEW, PERMISSION_SETTINGS_DAILY_REPORT_MANAGE):
        assert not resolve(db, 1, "co_owner", code, user_id=20)

    role_matrix = get_matrix(db, 1)
    assert role_matrix["co_owner"][PERMISSION_SETTINGS_DAILY_REPORT_VIEW]["source"] == "legacy_role_deny"
    assert role_matrix["co_owner"][PERMISSION_SETTINGS_DAILY_REPORT_VIEW]["legacy_permission_code"] == PERMISSION_SETTINGS_NOTIFICATIONS_VIEW


def test_new_permission_decisions_win_and_legacy_grants_are_not_inherited(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(User(id=10, email="owner@example.test", password_hash="synthetic", is_verified=True))
    db.add(User(id=20, email="co-owner@example.test", password_hash="synthetic", is_verified=True))
    db.flush()
    seed_default_permissions(db)
    db.add(HotelMembership(hotel_id=1, user_id=20, role="co_owner", status="active"))
    db.flush()
    db.add_all(
        [
            UserPermissionOverride(
                hotel_id=1,
                user_id=20,
                permission_code=PERMISSION_SETTINGS_ASSISTANT_VIEW,
                allowed=False,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="co_owner",
                permission_code=PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE,
                allowed=True,
            ),
            UserPermissionOverride(
                hotel_id=1,
                user_id=20,
                permission_code=PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
                allowed=True,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="co_owner",
                permission_code=PERMISSION_SETTINGS_NOTIFICATIONS_VIEW,
                allowed=False,
            ),
            HotelPermissionOverride(
                hotel_id=1,
                role="manager",
                permission_code=PERMISSION_SETTINGS_ASSISTANT_VIEW,
                allowed=True,
            ),
        ]
    )
    db.flush()

    details = get_effective_permission_details(db, 1, "co_owner", user_id=20)
    assert details[PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE]["allowed"] is False
    assert details[PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE]["source"] == "legacy_user_deny"
    assert details[PERMISSION_SETTINGS_DAILY_REPORT_VIEW]["allowed"] is False
    assert details[PERMISSION_SETTINGS_DAILY_REPORT_VIEW]["source"] == "legacy_role_deny"
    assert not resolve(db, 1, "manager", PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE)

    db.add(
        UserPermissionOverride(
            hotel_id=1,
            user_id=20,
            permission_code=PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE,
            allowed=True,
        )
    )
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="co_owner",
            permission_code=PERMISSION_SETTINGS_DAILY_REPORT_MANAGE,
            allowed=True,
        )
    )
    db.flush()

    details = get_effective_permission_details(db, 1, "co_owner", user_id=20)
    assert details[PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE]["allowed"] is True
    assert details[PERMISSION_SETTINGS_ASSISTANT_ACTIONS_MANAGE]["source"] == "user_override"
    assert details[PERMISSION_SETTINGS_DAILY_REPORT_MANAGE]["allowed"] is True
    assert details[PERMISSION_SETTINGS_DAILY_REPORT_MANAGE]["source"] == "role_override"


def test_role_scoped_capabilities_cannot_be_granted_outside_their_builtin_roles(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(User(id=10, email="owner@example.test", password_hash="synthetic", is_verified=True))
    db.flush()
    seed_default_permissions(db)
    db.add(HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"))
    db.add(
        HotelRole(
            hotel_id=1,
            code="cr_owner_ops",
            name="Owner operations",
            name_key="owner operations",
            base_role="manager",
            is_active=True,
        )
    )
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="manager",
            permission_code=PERMISSION_SETTINGS_USERS_MANAGE,
            allowed=True,
        )
    )
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="cr_owner_ops",
            permission_code=PERMISSION_SETTINGS_USERS_MANAGE,
            allowed=True,
        )
    )
    db.flush()

    assert resolve(db, 1, "owner", PERMISSION_SETTINGS_USERS_MANAGE, user_id=10)
    assert not resolve(db, 1, "manager", PERMISSION_SETTINGS_USERS_MANAGE)
    assert not resolve(db, 1, "cr_owner_ops", PERMISSION_SETTINGS_USERS_MANAGE)
    assert get_effective_permission_details(db, 1, "cr_owner_ops")[PERMISSION_SETTINGS_USERS_MANAGE] == {
        "allowed": False,
        "source": "invariant",
        "locked": True,
        "lock_reason": "role_scope",
    }

    set_user_override(
        db,
        1,
        10,
        "owner",
        PERMISSION_SETTINGS_USERS_MANAGE,
        False,
        actor_user_id=10,
    )
    assert not resolve(db, 1, "owner", PERMISSION_SETTINGS_USERS_MANAGE, user_id=10)


def test_every_role_scoped_capability_rejects_out_of_scope_role_overrides(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(
        HotelRole(
            hotel_id=1,
            code="cr_scope_test",
            name="Scope test",
            name_key="scope test",
            base_role="manager",
            is_active=True,
        )
    )
    seed_default_permissions(db)

    candidate_roles = ("owner", "co_owner", "manager", "receptionist", "housekeeping", "cr_scope_test")
    restricted_roles = ("manager", "receptionist", "housekeeping", "cr_scope_test")
    overrides = [
        HotelPermissionOverride(
            hotel_id=1,
            role=role,
            permission_code=permission_code,
            allowed=True,
        )
        for permission_code in _ROLE_SCOPES
        for role in restricted_roles
        if role not in _ROLE_SCOPES[permission_code]
    ]
    db.add_all(overrides)
    db.flush()

    for permission_code, allowed_roles in _ROLE_SCOPES.items():
        for role in candidate_roles:
            expected = role in allowed_roles
            assert resolve(db, 1, role, permission_code) is expected
            if not expected:
                assert get_effective_permission_details(db, 1, role)[permission_code] == {
                    "allowed": False,
                    "source": "invariant",
                    "locked": True,
                    "lock_reason": "role_scope",
                }


def test_cash_difference_denial_does_not_revoke_independent_owner_custody_receipt(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(User(id=10, email="owner@example.test", password_hash="synthetic", is_verified=True))
    db.flush()
    seed_default_permissions(db)
    db.add(HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"))
    db.add(
        HotelPermissionOverride(
            hotel_id=1,
            role="owner",
            permission_code=PERMISSION_CASH_APPROVE_DIFFERENCE,
            allowed=False,
        )
    )
    db.flush()

    details = get_effective_permission_details(db, 1, "owner", user_id=10)
    assert details[PERMISSION_CASH_APPROVE_DIFFERENCE]["allowed"] is False
    assert details[PERMISSION_CASH_CUSTODY_RECEIVE]["allowed"] is True
    assert details[PERMISSION_CASH_CUSTODY_RECEIVE]["source"] == "invariant"


def test_only_owner_can_use_administration_catalog_and_co_owner_is_denied():
    client, db, engine = _client()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
        catalog_path = "/api/permissions/catalog"
        owner = client.get(
            catalog_path,
            headers=_step_up_headers(catalog_path, method="GET"),
        )
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
            headers=_step_up_headers("/api/permissions/user-overrides/20", method="PUT"),
        )
        assert granted.status_code == 200
        assert granted.json()["source"] == "user_override"
        assert granted.json()["version"] == 1

        preview_path = "/api/permissions/effective/preview"
        preview = client.get(
            preview_path,
            params={"user_id": 20},
            headers=_step_up_headers(preview_path, method="GET"),
        )
        assert preview.status_code == 200
        assert preview.json()["details"][PERMISSION_RESERVATION_PROHIBITION_OVERRIDE]["allowed"] is True

        revoked = client.put(
            "/api/permissions/user-overrides/20",
            json={"permission_code": PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, "allowed": False},
            headers=_step_up_headers("/api/permissions/user-overrides/20", method="PUT"),
        )
        assert revoked.status_code == 200
        assert revoked.json()["version"] == 2
        restored = client.delete(
            "/api/permissions/user-overrides/20",
            headers=_step_up_headers("/api/permissions/user-overrides/20", method="DELETE"),
        )
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


def test_owner_cannot_change_or_restore_another_owners_user_overrides():
    client, db, engine = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(1, "owner", 10)
    try:
        other_owner = User(
            id=40,
            email="second-owner@example.test",
            password_hash="synthetic",
            role="owner",
            is_verified=True,
        )
        db.add(other_owner)
        db.flush()
        db.add(HotelMembership(hotel_id=1, user_id=other_owner.id, role="owner", status="active"))
        existing_override = UserPermissionOverride(
            hotel_id=1,
            user_id=other_owner.id,
            permission_code=PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
            allowed=True,
            version=1,
        )
        db.add(existing_override)
        db.commit()

        path = f"/api/permissions/user-overrides/{other_owner.id}"
        changed = client.put(
            path,
            json={"permission_code": PERMISSION_RESERVATION_PROHIBITION_OVERRIDE, "allowed": False},
            headers=_step_up_headers(path, method="PUT"),
        )
        restored = client.delete(path, headers=_step_up_headers(path, method="DELETE"))

        assert changed.status_code == 403
        assert restored.status_code == 403
        db.refresh(existing_override)
        assert existing_override.allowed is True
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
            headers=_step_up_headers("/api/permissions/override", method="PUT"),
        )
        assert changed.status_code == 200
        assert changed.json()["version"] == 1

        restored = client.delete(
            f"/api/permissions/overrides/role/receptionist/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
            headers=_step_up_headers(
                f"/api/permissions/overrides/role/receptionist/{PERMISSION_GUEST_READ}",
                method="DELETE",
            ),
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
            headers=_step_up_headers("/api/permissions/user-overrides/20", method="PUT"),
        )
        assert changed.status_code == 200
        assert changed.json()["version"] == 1

        restored = client.delete(
            f"/api/permissions/overrides/user/20/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
            headers=_step_up_headers(
                f"/api/permissions/overrides/user/20/{PERMISSION_GUEST_READ}",
                method="DELETE",
            ),
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

        preview_path = "/api/permissions/effective/preview"
        preview = client.get(
            preview_path,
            params={"user_id": 20},
            headers=_step_up_headers(preview_path, method="GET"),
        )
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
            headers=_step_up_headers("/api/permissions/override", method="PUT"),
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
            headers=_step_up_headers("/api/permissions/override", method="PUT"),
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        stale_restore = client.delete(
            f"/api/permissions/role-overrides/receptionist/{PERMISSION_GUEST_READ}",
            params={"expected_version": 1},
            headers=_step_up_headers(
                f"/api/permissions/role-overrides/receptionist/{PERMISSION_GUEST_READ}",
                method="DELETE",
            ),
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
            headers=_step_up_headers(
                f"/api/permissions/overrides/role/owner/{PERMISSION_PERMISSION_MANAGE}",
                method="DELETE",
            ),
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
            headers=_step_up_headers("/api/permissions/user-overrides/10", method="PUT"),
        )
        assert self_change.status_code == 422

        cross_hotel = client.put(
            "/api/permissions/user-overrides/30",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": True},
            headers=_step_up_headers("/api/permissions/user-overrides/30", method="PUT"),
        )
        unknown = client.put(
            "/api/permissions/user-overrides/999999",
            json={"permission_code": PERMISSION_GUEST_READ, "allowed": True},
            headers=_step_up_headers("/api/permissions/user-overrides/999999", method="PUT"),
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
