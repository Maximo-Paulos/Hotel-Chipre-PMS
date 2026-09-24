"""Security and API contract tests for per-hotel custom roles."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.hotel_role import HotelRole
from app.models.hotel_role_visibility_window import HotelRoleVisibilityWindow
from app.models.invitation import StaffInvitation
from app.models.permission import HotelPermissionOverride
from app.models.user import User
from app.services.permission_service import (
    HotelRoleNotFound,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_RESERVATION_CREATE,
    ROLE_HOUSEKEEPING,
    ROLE_RECEPTIONIST,
    archive_custom_role,
    create_custom_role,
    effective_role_code,
    get_effective_permission_details,
    get_visibility_window,
    require_active_hotel_role,
    restore_role_override,
    restore_user_override,
    set_role_override,
    set_user_override,
    set_visibility_window,
)
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.security import create_access_token


@pytest.fixture
def role_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine,
        "connect",
        lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="Hotel Uno", subscription_active=True),
            HotelConfiguration(id=2, hotel_name="Hotel Dos", subscription_active=True),
            User(
                id=7,
                email="owner@example.test",
                password_hash="test-hash",
                role="owner",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.commit()
    state = {"hotel_id": 1, "user_id": 7, "role": "owner"}

    def override_get_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=state["hotel_id"],
            user_id=state["user_id"],
            user_email="owner@example.test",
            user_role=state["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    try:
        yield TestClient(fastapi_app), db, state
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _create_role(db, *, hotel_id=1, name="Turno noche", base_role=ROLE_RECEPTIONIST):
    row = create_custom_role(
        db,
        hotel_id,
        name=name,
        base_role=base_role,
        actor_user_id=7,
    )
    db.commit()
    return row


def test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(role_api):
    _client, db, state = role_api
    custom = _create_role(db, base_role=ROLE_HOUSEKEEPING)
    membership = HotelMembership(
        hotel_id=1,
        user_id=state["user_id"],
        role=custom.code,
        status="active",
    )
    db.add(membership)
    db.commit()

    context = get_auth_context(
        db=db,
        x_hotel_id=None,
        authorization=f"Bearer {create_access_token(state['user_id'])}",
    )
    assert context.user_role == custom.code
    assert context.base_role == ROLE_HOUSEKEEPING
    assert context.operational_role == ROLE_HOUSEKEEPING
    assert effective_role_code(db, 1, "manager") == "manager"

    membership.role = "cr_missing_role"
    db.commit()
    with pytest.raises(HTTPException) as exc_info:
        get_auth_context(
            db=db,
            x_hotel_id=None,
            authorization=f"Bearer {create_access_token(state['user_id'])}",
        )
    assert exc_info.value.status_code == 403
    assert "rol asignado no está disponible" in exc_info.value.detail


def _step_up_headers(state, method: str, path: str) -> dict[str, str]:
    return {
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=state["user_id"],
            hotel_id=state["hotel_id"],
            token_version=0,
            permission_code=PERMISSION_PERMISSION_MANAGE,
            method=method,
            path=path,
        )
    }


def test_roles_api_contract_read_access_and_owner_only_mutations(role_api):
    client, _db, state = role_api
    create_path = "/api/roles"

    created = client.post(
        create_path,
        json={"name": "  Turno   Noche ", "base_role": "receptionist"},
        headers=_step_up_headers(state, "POST", create_path),
    )
    assert created.status_code == 201, created.text
    item = created.json()["role"]
    assert set(item) == {
        "code",
        "name",
        "kind",
        "base_role",
        "is_active",
        "assigned_count",
        "pending_invitation_count",
        "permission_count",
        "version",
    }
    assert item["code"].startswith("cr_") and len(item["code"]) <= 20
    assert item["name"] == "Turno Noche"
    assert item["kind"] == "custom"
    assert item["base_role"] == "receptionist"
    assert item["version"] == 1

    listed = client.get("/api/roles")
    assert listed.status_code == 200
    assert {row["code"] for row in listed.json()["roles"]} >= {
        "owner",
        "co_owner",
        "manager",
        "receptionist",
        "housekeeping",
        item["code"],
    }

    state["role"] = "co_owner"
    readable = client.get("/api/roles")
    assert readable.status_code == 200, readable.text
    assert item["code"] in {row["code"] for row in readable.json()["roles"]}
    assert client.post(
        create_path,
        json={"name": "No autorizado", "base_role": "manager"},
    ).status_code == 403
    assert client.patch(
        f"/api/roles/{item['code']}",
        json={"name": "No autorizado", "expected_version": 1},
    ).status_code == 403
    assert client.delete(
        f"/api/roles/{item['code']}?expected_version=1"
    ).status_code == 403
    assert client.put(
        "/api/permissions/role-overrides",
        json={
            "role": item["code"],
            "permission_code": PERMISSION_RESERVATION_CREATE,
            "allowed": False,
            "expected_version": 0,
        },
        headers=_step_up_headers(state, "PUT", "/api/permissions/role-overrides"),
    ).status_code == 403
    assert client.put(
        "/api/permissions/visibility-windows",
        json={"role": item["code"], "past_hours": 24, "future_hours": 48},
        headers=_step_up_headers(state, "PUT", "/api/permissions/visibility-windows"),
    ).status_code == 403
    state["role"] = "owner"

    renamed = client.patch(
        f"/api/roles/{item['code']}",
        json={"name": "Turno tarde", "expected_version": 1},
        headers=_step_up_headers(state, "PATCH", f"/api/roles/{item['code']}"),
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["role"]["code"] == item["code"]
    assert renamed.json()["role"]["name"] == "Turno tarde"
    assert renamed.json()["role"]["version"] == 2
    stale = client.patch(
        f"/api/roles/{item['code']}",
        json={"name": "Nombre obsoleto", "expected_version": 1},
        headers=_step_up_headers(state, "PATCH", f"/api/roles/{item['code']}"),
    )
    assert stale.status_code == 409


def test_role_archive_refuses_active_members_and_pending_invites(role_api):
    client, db, state = role_api
    role = _create_role(db)
    invitation = StaffInvitation(
        hotel_id=1,
        email="invitee@example.test",
        role=role.code,
        inviter_email="owner@example.test",
        token_hash="a" * 64,
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
    )
    db.add(invitation)
    db.commit()

    catalog = client.get("/api/roles")
    assert catalog.status_code == 200, catalog.text
    catalog_role = next(row for row in catalog.json()["roles"] if row["code"] == role.code)
    assert catalog_role["assigned_count"] == 0
    assert catalog_role["pending_invitation_count"] == 1

    delete_path = f"/api/roles/{role.code}"
    pending = client.delete(
        f"{delete_path}?expected_version=1",
        headers=_step_up_headers(state, "DELETE", delete_path),
    )
    assert pending.status_code == 409

    invitation.status = "revoked"
    member = User(
        id=8,
        email="member@example.test",
        password_hash="test-hash",
        role="receptionist",
        is_active=True,
        is_verified=True,
    )
    db.add(member)
    db.flush()
    membership = HotelMembership(
        hotel_id=1,
        user_id=member.id,
        role=role.code,
        status="active",
    )
    db.add(membership)
    db.commit()

    active = client.delete(
        f"{delete_path}?expected_version=1",
        headers=_step_up_headers(state, "DELETE", delete_path),
    )
    assert active.status_code == 409

    membership.status = "revoked"
    db.commit()
    archived = client.delete(
        f"{delete_path}?expected_version=1",
        headers=_step_up_headers(state, "DELETE", delete_path),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["role"]["is_active"] is False
    assert archived.json()["role"]["assigned_count"] == 0
    assert archived.json()["role"]["pending_invitation_count"] == 0
    stale_repeat = client.delete(
        f"{delete_path}?expected_version=1",
        headers=_step_up_headers(state, "DELETE", delete_path),
    )
    assert stale_repeat.status_code == 409
    current_repeat = client.delete(
        f"{delete_path}?expected_version=2",
        headers=_step_up_headers(state, "DELETE", delete_path),
    )
    assert current_repeat.status_code == 200

    body_role = _create_role(db, name="Body version")
    body_path = f"/api/roles/{body_role.code}"
    body_archived = client.request(
        "DELETE",
        body_path,
        json={"expected_version": 1},
        headers=_step_up_headers(state, "DELETE", body_path),
    )
    assert body_archived.status_code == 200, body_archived.text
    assert body_archived.json()["role"]["is_active"] is False


def test_custom_role_permission_precedence_invariants_and_tenant_isolation(role_api):
    _client, db, _state = role_api
    role = _create_role(db, base_role=ROLE_RECEPTIONIST)
    member = User(
        id=8,
        email="staff@example.test",
        password_hash="test-hash",
        role="receptionist",
        is_active=True,
        is_verified=True,
    )
    db.add(member)
    db.flush()
    db.add(
        HotelMembership(
            hotel_id=1,
            user_id=member.id,
            role=role.code,
            status="active",
        )
    )
    db.commit()

    baseline = get_effective_permission_details(db, 1, role.code)
    assert baseline[PERMISSION_RESERVATION_CREATE]["allowed"] is True
    assert baseline[PERMISSION_RESERVATION_CREATE]["source"] == "base_role_default"

    set_role_override(
        db,
        1,
        role.code,
        PERMISSION_RESERVATION_CREATE,
        False,
        actor_user_id=7,
        expected_version=0,
    )
    db.commit()
    role_denied = get_effective_permission_details(db, 1, role.code)
    assert role_denied[PERMISSION_RESERVATION_CREATE]["allowed"] is False
    assert role_denied[PERMISSION_RESERVATION_CREATE]["source"] == "role_override"

    set_user_override(
        db,
        1,
        member.id,
        role.code,
        PERMISSION_RESERVATION_CREATE,
        True,
        actor_user_id=7,
    )
    db.commit()
    user_override = get_effective_permission_details(db, 1, role.code, user_id=member.id)
    assert user_override[PERMISSION_RESERVATION_CREATE]["allowed"] is True
    assert user_override[PERMISSION_RESERVATION_CREATE]["source"] == "user_override"

    invariant = user_override[PERMISSION_PERMISSION_MANAGE]
    assert invariant["allowed"] is False
    assert invariant["source"] == "invariant"
    with pytest.raises(ValueError, match="bloqueado"):
        set_role_override(
            db,
            1,
            role.code,
            PERMISSION_PERMISSION_MANAGE,
            True,
            actor_user_id=7,
        )

    restored_role = restore_role_override(
        db,
        1,
        role.code,
        PERMISSION_RESERVATION_CREATE,
        actor_user_id=7,
        expected_version=1,
    )
    assert restored_role["source"] == "base_role_default"
    restored_user = restore_user_override(
        db,
        1,
        member.id,
        actor_user_id=7,
        code=PERMISSION_RESERVATION_CREATE,
        expected_version=1,
    )
    assert restored_user["source"] == "base_role_default"
    db.commit()

    assert get_effective_permission_details(db, 2, role.code) == {}
    with pytest.raises(HotelRoleNotFound):
        require_active_hotel_role(db, 2, role.code)

    db.query(HotelMembership).filter_by(hotel_id=1, user_id=member.id).update(
        {"status": "revoked"}
    )
    db.commit()
    archive_custom_role(db, 1, role.code, expected_version=1, actor_user_id=7)
    db.commit()
    assert get_effective_permission_details(db, 1, role.code, user_id=member.id) == {}


def test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed(role_api):
    _client, db, _state = role_api
    role = _create_role(db, base_role=ROLE_RECEPTIONIST)
    set_visibility_window(db, 1, ROLE_RECEPTIONIST, 24, 72, actor_user_id=7)
    db.commit()

    inherited = get_visibility_window(db, 1, role.code)
    assert inherited is not None
    assert inherited.role == role.code
    assert (inherited.past_hours, inherited.future_hours) == (24, 72)

    own = set_visibility_window(db, 1, role.code, 12, 24, actor_user_id=7)
    db.commit()
    assert (own.past_hours, own.future_hours) == (12, 24)
    assert db.query(HotelRoleVisibilityWindow).filter_by(hotel_id=1, role=role.code).count() == 1

    unknown = get_visibility_window(db, 2, role.code)
    assert unknown is not None
    assert (unknown.past_hours, unknown.future_hours) == (0, 0)

    archive_custom_role(db, 1, role.code, expected_version=1, actor_user_id=7)
    db.commit()
    archived = get_visibility_window(db, 1, role.code)
    assert archived is not None
    assert (archived.past_hours, archived.future_hours) == (0, 0)


def test_permission_and_visibility_apis_accept_only_active_tenant_roles(role_api):
    client, db, state = role_api
    role = _create_role(db, base_role=ROLE_RECEPTIONIST)
    foreign_role = _create_role(db, hotel_id=2, name="Otro hotel")
    archived_role = _create_role(db, name="Archivado")
    archive_custom_role(
        db,
        1,
        archived_role.code,
        expected_version=1,
        actor_user_id=7,
    )
    set_visibility_window(db, 1, ROLE_RECEPTIONIST, 24, 72, actor_user_id=7)
    db.commit()

    profiles_path = "/api/permissions/role-overrides"
    profiles = client.get(
        profiles_path,
        headers=_step_up_headers(state, "GET", profiles_path),
    )
    assert profiles.status_code == 200, profiles.text
    assert role.code in profiles.json()["matrix"]
    assert foreign_role.code not in profiles.json()["matrix"]
    assert archived_role.code not in profiles.json()["matrix"]
    assert (
        profiles.json()["matrix"][role.code][PERMISSION_RESERVATION_CREATE]["source"]
        == "base_role_default"
    )

    override_path = "/api/permissions/role-overrides"
    updated = client.put(
        override_path,
        json={
            "role": role.code,
            "permission_code": PERMISSION_RESERVATION_CREATE,
            "allowed": False,
            "expected_version": 0,
        },
        headers=_step_up_headers(state, "PUT", override_path),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == role.code
    assert updated.json()["source"] == "role_override"
    assert updated.json()["allowed"] is False

    restore_path = (
        f"/api/permissions/role-overrides/{role.code}/"
        f"{PERMISSION_RESERVATION_CREATE}"
    )
    restored = client.delete(
        f"{restore_path}?expected_version=1",
        headers=_step_up_headers(state, "DELETE", restore_path),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["source"] == "base_role_default"

    visibility_path = "/api/permissions/visibility-windows"
    matrix_path = "/api/permissions/matrix"
    matrix = client.get(
        matrix_path,
        headers=_step_up_headers(state, "GET", matrix_path),
    )
    assert matrix.status_code == 200, matrix.text
    assert role.code in matrix.json()["matrix"]
    assert foreign_role.code not in matrix.json()["matrix"]
    assert archived_role.code not in matrix.json()["matrix"]

    inherited = client.get(
        visibility_path,
        headers=_step_up_headers(state, "GET", visibility_path),
    )
    assert inherited.status_code == 200, inherited.text
    inherited_window = next(
        row for row in inherited.json()["windows"] if row["role"] == role.code
    )
    assert foreign_role.code not in {row["role"] for row in inherited.json()["windows"]}
    assert archived_role.code not in {row["role"] for row in inherited.json()["windows"]}
    assert (inherited_window["past_hours"], inherited_window["future_hours"]) == (24, 72)

    own_window = client.put(
        visibility_path,
        json={"role": role.code, "past_hours": 12, "future_hours": 48},
        headers=_step_up_headers(state, "PUT", visibility_path),
    )
    assert own_window.status_code == 200, own_window.text
    assert (own_window.json()["past_hours"], own_window.json()["future_hours"]) == (12, 48)

    for invalid_role in ("cr_ffffffffffffffff", foreign_role.code, archived_role.code):
        invalid_override = client.put(
            override_path,
            json={
                "role": invalid_role,
                "permission_code": PERMISSION_RESERVATION_CREATE,
                "allowed": False,
                "expected_version": 0,
            },
            headers=_step_up_headers(state, "PUT", override_path),
        )
        assert invalid_override.status_code == 422, invalid_override.text

        invalid_window = client.put(
            visibility_path,
            json={"role": invalid_role, "past_hours": 24, "future_hours": 48},
            headers=_step_up_headers(state, "PUT", visibility_path),
        )
        assert invalid_window.status_code == 422, invalid_window.text

    owner_only = client.put(
        override_path,
        json={
            "role": role.code,
            "permission_code": PERMISSION_PERMISSION_MANAGE,
            "allowed": True,
            "expected_version": 0,
        },
        headers=_step_up_headers(state, "PUT", override_path),
    )
    assert owner_only.status_code == 422, owner_only.text
    assert (
        get_effective_permission_details(db, 1, role.code)[PERMISSION_PERMISSION_MANAGE]["allowed"]
        is False
    )


def test_custom_role_downgrade_aborts_before_any_data_changes(role_api, monkeypatch):
    _client, db, _state = role_api
    role = _create_role(db, base_role=ROLE_RECEPTIONIST)
    member = User(
        id=8,
        email="rollback-member@example.test",
        password_hash="test-hash",
        role="receptionist",
        is_active=True,
        is_verified=True,
    )
    db.add(member)
    db.flush()
    membership = HotelMembership(
        hotel_id=1,
        user_id=member.id,
        role=role.code,
        status="active",
    )
    invitation = StaffInvitation(
        hotel_id=1,
        email="rollback-invite@example.test",
        role=role.code,
        inviter_email="owner@example.test",
        token_hash="b" * 64,
        status="pending",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
    )
    db.add_all([membership, invitation])
    set_role_override(
        db,
        1,
        role.code,
        PERMISSION_RESERVATION_CREATE,
        False,
        actor_user_id=7,
        expected_version=0,
    )
    set_visibility_window(
        db,
        1,
        role.code,
        12,
        24,
        actor_user_id=7,
    )
    db.commit()

    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260924_custom_hotel_roles.py"
    )
    spec = importlib.util.spec_from_file_location(
        "custom_hotel_roles_migration_test",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class NoMutationOps:
        def get_bind(self):
            return db.connection()

        def __getattr__(self, name):
            raise AssertionError(f"downgrade attempted a mutation before its guard: {name}")

    monkeypatch.setattr(migration, "op", NoMutationOps())
    with pytest.raises(RuntimeError, match="Downgrade cancelado.*No se realizaron cambios"):
        migration.downgrade()

    db.expire_all()
    assert db.query(HotelRole).filter_by(hotel_id=1, code=role.code).one().is_active is True
    assert db.query(HotelMembership).filter_by(hotel_id=1, user_id=member.id).one().role == role.code
    assert db.query(StaffInvitation).filter_by(token_hash="b" * 64).one().role == role.code
    assert db.query(HotelPermissionOverride).filter_by(
        hotel_id=1,
        role=role.code,
        permission_code=PERMISSION_RESERVATION_CREATE,
    ).one().allowed is False
    persisted_window = db.query(HotelRoleVisibilityWindow).filter_by(
        hotel_id=1,
        role=role.code,
    ).one()
    assert (persisted_window.past_hours, persisted_window.future_hours) == (12, 24)


def test_custom_roles_can_be_assigned_and_invited_but_owner_transfer_stays_separate(role_api):
    client, db, _state = role_api
    role = _create_role(db, base_role=ROLE_HOUSEKEEPING)
    member = User(
        id=8,
        email="existing-staff@example.test",
        password_hash="test-hash",
        role="receptionist",
        is_active=True,
        is_verified=True,
    )
    db.add(member)
    db.flush()
    db.add(
        HotelMembership(
            hotel_id=1,
            user_id=member.id,
            role="receptionist",
            status="active",
        )
    )
    db.commit()

    changed = client.patch(f"/api/users/{member.id}/role", json={"role": role.code})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == role.code
    assert db.query(HotelMembership).filter_by(hotel_id=1, user_id=member.id).one().role == role.code

    invite = client.post(
        "/api/users/invite",
        json={"email": "new-staff@example.test", "role": role.code},
    )
    assert invite.status_code == 201, invite.text
    assert invite.json()["user"]["role"] == role.code
    invitation = db.query(StaffInvitation).filter_by(id=invite.json()["invitation_id"]).one()
    assert invitation.role == role.code
    invited_membership = db.query(HotelMembership).filter_by(
        hotel_id=1,
        user_id=invitation.user_id,
    ).one()
    assert invited_membership.role == role.code

    preview = client.post(
        "/api/invitations/preview",
        json={"token": invite.json()["invite_token"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["role"] == role.code

    accepted = client.post(
        "/api/invitations/accept",
        json={
            "token": invite.json()["invite_token"],
            "email": "new-staff@example.test",
            "password": "StrongInvitePass123!",
        },
    )
    assert accepted.status_code == 200, accepted.text
    db.refresh(invited_membership)
    assert invited_membership.status == "active"
    assert invited_membership.role == role.code

    invalid_owner = client.post(
        "/api/users/invite",
        json={"email": "owner-transfer@example.test", "role": "owner"},
    )
    assert invalid_owner.status_code == 400
