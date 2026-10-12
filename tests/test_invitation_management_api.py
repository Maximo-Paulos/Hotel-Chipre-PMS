"""Hotel-scoped pending invitation management and legacy owner cleanup."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.models.audit_log import AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.services.invitation_service import issue_invitation
from app.services.security import hash_password
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import PERMISSION_SETTINGS_USERS_MANAGE


def _user(email: str, role: str) -> User:
    return User(
        email=email,
        password_hash=hash_password("test-password"),
        role=role,
        is_active=True,
        is_verified=True,
    )


def _step_up_headers(user: User, hotel_id: int, method: str, path: str) -> dict[str, str]:
    return {
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=user.id,
            hotel_id=hotel_id,
            token_version=0,
            permission_code=PERMISSION_SETTINGS_USERS_MANAGE,
            method=method,
            path=path,
        )
    }


def test_pending_invitation_list_is_scoped_redacted_and_owner_can_recover_legacy_owner_invite():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    owner = _user("owner-invites@example.test", "owner")
    co_owner = _user("co-owner-invites@example.test", "co_owner")
    legacy_user = _user("legacy-owner-invite@example.test", "owner")
    foreign_owner = _user("foreign-owner@example.test", "owner")
    foreign_staff = _user("foreign-staff@example.test", "manager")
    db.add_all(
        [
            HotelConfiguration(id=61, hotel_name="Hotel A", owner_email=owner.email),
            HotelConfiguration(id=62, hotel_name="Hotel B", owner_email=foreign_owner.email),
            owner,
            co_owner,
            legacy_user,
            foreign_owner,
            foreign_staff,
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=61, user_id=owner.id, role="owner", status="active", is_primary_owner=True),
            HotelMembership(hotel_id=61, user_id=co_owner.id, role="co_owner", status="active"),
            HotelMembership(hotel_id=61, user_id=legacy_user.id, role="owner", status="invited"),
            HotelMembership(hotel_id=62, user_id=foreign_owner.id, role="owner", status="active", is_primary_owner=True),
            HotelMembership(hotel_id=62, user_id=legacy_user.id, role="manager", status="active"),
            HotelMembership(hotel_id=62, user_id=foreign_staff.id, role="manager", status="invited"),
        ]
    )
    legacy_invitation, _legacy_token, _ = issue_invitation(
        db,
        hotel_id=61,
        # Legacy rows may have lost their nullable user FK while the scoped
        # membership remains pending.
        user_id=None,
        email=legacy_user.email,
        role="owner",
        inviter_user_id=owner.id,
        inviter_email=owner.email,
    )
    issue_invitation(
        db,
        hotel_id=62,
        user_id=foreign_staff.id,
        email=foreign_staff.email,
        role="manager",
        inviter_user_id=foreign_owner.id,
        inviter_email=foreign_owner.email,
    )
    db.commit()

    def set_actor(user: User, role: str, hotel_id: int) -> None:
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            hotel_id=hotel_id,
            user_id=user.id,
            user_email=user.email,
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = lambda: db
    set_actor(owner, "owner", 61)
    client = TestClient(app)
    try:
        listed = client.get(
            "/api/users/invitations",
        )
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 1
        assert listed.json()[0]["invitation_id"] == legacy_invitation.id
        assert listed.json()[0]["status"] == "pending"
        assert set(listed.json()[0]) == {
            "invitation_id", "email", "role", "inviter_email", "status", "created_at", "expires_at"
        }
        assert "token" not in listed.text.lower()
        assert "token_hash" not in listed.text.lower()

        # Read access uses the ordinary users:view permission. Mutations still
        # require the one-use manage permission ticket.
        step_up_required = client.post(
            "/api/users/invite",
            json={"email": "must-not-be-invited@example.test", "role": "manager"},
        )
        assert step_up_required.status_code == 428, step_up_required.text
        assert step_up_required.json()["detail"]["code"] == "STEP_UP_REQUIRED"

        set_actor(co_owner, "co_owner", 61)
        revoke_path = f"/api/users/invitations/{legacy_invitation.id}"
        forbidden = client.delete(
            revoke_path,
            headers=_step_up_headers(co_owner, 61, "DELETE", revoke_path),
        )
        assert forbidden.status_code == 403, forbidden.text

        set_actor(owner, "owner", 61)
        revoked = client.delete(
            revoke_path,
            headers=_step_up_headers(owner, 61, "DELETE", revoke_path),
        )
        assert revoked.status_code == 204, revoked.text
        db.refresh(legacy_invitation)
        assert legacy_invitation.status == "revoked"
        legacy_membership = db.query(HotelMembership).filter_by(
            hotel_id=61, user_id=legacy_user.id
        ).one()
        db.refresh(legacy_membership)
        assert legacy_membership.status == "revoked"
        foreign_membership = db.query(HotelMembership).filter_by(
            hotel_id=62, user_id=legacy_user.id
        ).one()
        assert foreign_membership.role == "manager"
        assert foreign_membership.status == "active"
        assert db.query(AuditLog).filter_by(
            hotel_id=61,
            table_name="hotel_memberships",
            record_id=legacy_membership.id,
        ).count() >= 1
        assert db.query(AuditLog).filter_by(
            hotel_id=61,
            table_name="staff_invitations",
            record_id=legacy_invitation.id,
        ).count() >= 1

        reinvited = client.post(
            "/api/users/invite",
            json={"email": legacy_user.email, "role": "Copropietaria"},
            headers=_step_up_headers(owner, 61, "POST", "/api/users/invite"),
        )
        assert reinvited.status_code == 201, reinvited.text
        db.refresh(legacy_membership)
        assert legacy_membership.role == "co_owner"
        assert legacy_membership.status == "invited"

        set_actor(foreign_owner, "owner", 62)
        foreign_list = client.get(
            "/api/users/invitations",
        )
        assert foreign_list.status_code == 200, foreign_list.text
        assert [item["email"] for item in foreign_list.json()] == [foreign_staff.email]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
