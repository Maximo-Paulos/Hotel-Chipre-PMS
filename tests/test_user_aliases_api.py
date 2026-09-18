"""Tenant-scoped staff aliases and user-management authorization."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.adapters.rate_limiter import invite_limiter
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.permission import UserPermissionOverride
from app.models.user import User
from app.services.invitation_service import issue_invitation
from app.services.security import hash_password
from app.services.permission_service import PERMISSION_SETTINGS_USERS_MANAGE


def _user(email: str, role: str) -> User:
    return User(
        email=email,
        password_hash=hash_password("test-password"),
        role=role,
        is_active=True,
        is_verified=True,
    )


def _invitation(db, *, hotel_id: int, user: User, inviter: User) -> StaffInvitation:
    invitation, _token, _reused = issue_invitation(
        db,
        hotel_id=hotel_id,
        user_id=user.id,
        email=user.email,
        role="manager",
        inviter_user_id=inviter.id,
        inviter_email=inviter.email,
    )
    db.flush()
    return invitation


def test_alias_roster_is_minimal_hotel_scoped_and_includes_active_and_invited_members():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    app.dependency_overrides[get_db] = lambda: db
    owner = _user("owner-alias@example.test", "owner")
    active = _user("active-alias@example.test", "manager")
    invited = _user("invited-alias@example.test", "manager")
    foreign = _user("foreign-alias@example.test", "manager")
    db.add_all([HotelConfiguration(id=31, hotel_name="One"), HotelConfiguration(id=32, hotel_name="Two")])
    db.add_all([owner, active, invited, foreign])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=31, user_id=owner.id, role="owner", status="active"),
            HotelMembership(hotel_id=31, user_id=active.id, role="manager", status="active", alias="Turno día", alias_key="turno dia"),
            HotelMembership(hotel_id=31, user_id=invited.id, role="manager", status="invited"),
            HotelMembership(hotel_id=31, user_id=foreign.id, role="manager", status="revoked"),
            HotelMembership(hotel_id=32, user_id=foreign.id, role="manager", status="active", alias="No mostrar", alias_key="no mostrar"),
        ]
    )
    db.commit()
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        hotel_id=31, user_id=owner.id, user_email=owner.email, user_role="owner", is_verified=True, permissions=set()
    )
    client = TestClient(app)
    try:
        response = client.get("/api/users/aliases")
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"items"}
        assert {item["user_id"] for item in body["items"]} == {owner.id, active.id, invited.id}
        assert all(set(item) == {"user_id", "email", "role", "status", "alias"} for item in body["items"])
        assert next(item for item in body["items"] if item["user_id"] == active.id)["alias"] == "Turno día"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_alias_edit_and_invite_alias_are_normalized_unique_and_hotel_scoped(monkeypatch):
    # Another rate-limit test mutates this process-global limiter. Keep this
    # multi-invite workflow independent and let monkeypatch restore it after.
    monkeypatch.setattr(invite_limiter, "limit", 10)
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    app.dependency_overrides[get_db] = lambda: db
    owner = _user("owner-edit@example.test", "owner")
    active = _user("active-edit@example.test", "manager")
    invited = _user("invited-edit@example.test", "manager")
    other_hotel_user = _user("foreign-edit@example.test", "manager")
    db.add_all([HotelConfiguration(id=41, hotel_name="One"), HotelConfiguration(id=42, hotel_name="Two")])
    db.add_all([owner, active, invited, other_hotel_user])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=41, user_id=owner.id, role="owner", status="active"),
            HotelMembership(hotel_id=41, user_id=active.id, role="manager", status="active"),
            HotelMembership(hotel_id=41, user_id=invited.id, role="manager", status="invited"),
            HotelMembership(hotel_id=42, user_id=other_hotel_user.id, role="manager", status="active"),
        ]
    )
    invitation = _invitation(db, hotel_id=41, user=invited, inviter=owner)
    db.commit()
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        hotel_id=41, user_id=owner.id, user_email=owner.email, user_role="owner", is_verified=True, permissions=set()
    )

    class NotConfiguredMailer:
        configured = False

        def send(self, *_args, **_kwargs):
            raise AssertionError("unconfigured mailer must not send")

    monkeypatch.setattr("app.api.users.mailer", NotConfiguredMailer())
    client = TestClient(app)
    try:
        edited = client.patch(f"/api/users/{active.id}/alias", json={"alias": "  Night   Manager  "})
        assert edited.status_code == 200, edited.text
        db.refresh(db.query(HotelMembership).filter_by(hotel_id=41, user_id=active.id).one())
        active_membership = db.query(HotelMembership).filter_by(hotel_id=41, user_id=active.id).one()
        assert active_membership.alias == "Night Manager"
        assert active_membership.alias_key == "night manager"

        invited_edit = client.patch(f"/api/users/{invited.id}/alias", json={"alias": "Back Office"})
        assert invited_edit.status_code == 200, invited_edit.text
        assert invited_edit.json()["status"] == "invited"
        assert invited_edit.json()["alias"] == "Back Office"

        duplicate = client.patch(f"/api/users/{invited.id}/alias", json={"alias": "NIGHT MANAGER"})
        assert duplicate.status_code == 409, duplicate.text
        foreign = client.patch(f"/api/users/{other_hotel_user.id}/alias", json={"alias": "Outside"})
        assert foreign.status_code == 404

        invited_response = client.post(
            "/api/users/invite",
            json={"email": "new-invite@example.test", "role": "receptionist", "alias": "  Evening   Desk "},
        )
        assert invited_response.status_code == 201, invited_response.text
        assert invited_response.json()["email_delivery"] == "not_configured"
        new_user_id = invited_response.json()["user"]["id"]
        invited_membership = db.query(HotelMembership).filter_by(hotel_id=41, user_id=new_user_id).one()
        assert invited_membership.alias == "Evening Desk"
        assert invited_membership.alias_key == "evening desk"
        assert invited_response.json()["invitation_id"] == invitation.id + 1

        class FailingMailer:
            configured = True

            def send(self, *_args, **_kwargs):
                raise RuntimeError("private provider diagnostic")

        monkeypatch.setattr("app.api.users.mailer", FailingMailer())
        failed_delivery = client.post(
            "/api/users/invite",
            json={"email": "delivery-failed@example.test", "role": "manager"},
        )
        assert failed_delivery.status_code == 201, failed_delivery.text
        assert failed_delivery.json()["email_delivery"] == "failed"
        assert "private provider diagnostic" not in failed_delivery.text
        persisted_user = db.query(User).filter_by(email="delivery-failed@example.test").one()
        persisted_membership = db.query(HotelMembership).filter_by(hotel_id=41, user_id=persisted_user.id).one()
        assert persisted_membership.status == "invited"

        retried_delivery = client.post(
            f"/api/users/invitations/{failed_delivery.json()['invitation_id']}/resend"
        )
        assert retried_delivery.status_code == 200, retried_delivery.text
        assert retried_delivery.json()["email_delivery"] == "failed"
        assert retried_delivery.json()["invitation_id"] == failed_delivery.json()["invitation_id"]

        class SentMailer:
            configured = True

            def send(self, *_args, **_kwargs):
                return True

        monkeypatch.setattr("app.api.users.mailer", SentMailer())
        sent_delivery = client.post(
            "/api/users/invite",
            json={"email": "delivery-sent@example.test", "role": "manager"},
        )
        assert sent_delivery.status_code == 201, sent_delivery.text
        assert sent_delivery.json()["email_delivery"] == "sent"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_user_management_mutations_require_effective_manage_permission():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    app.dependency_overrides[get_db] = lambda: db
    owner = _user("owner-permission@example.test", "owner")
    staff = _user("staff-permission@example.test", "manager")
    db.add(HotelConfiguration(id=51, hotel_name="One"))
    db.add_all([owner, staff])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=51, user_id=owner.id, role="owner", status="active"),
            HotelMembership(hotel_id=51, user_id=staff.id, role="manager", status="invited"),
            UserPermissionOverride(
                hotel_id=51,
                user_id=owner.id,
                permission_code=PERMISSION_SETTINGS_USERS_MANAGE,
                allowed=False,
            ),
        ]
    )
    invitation = _invitation(db, hotel_id=51, user=staff, inviter=owner)
    db.commit()
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        hotel_id=51, user_id=owner.id, user_email=owner.email, user_role="owner", is_verified=True, permissions=set()
    )
    client = TestClient(app)
    try:
        responses = [
            client.get("/api/users/aliases"),
            client.patch(f"/api/users/{staff.id}/alias", json={"alias": "Denied"}),
            client.post("/api/users/invite", json={"email": "new-denied@example.test", "role": "manager"}),
            client.post(f"/api/users/invitations/{invitation.id}/resend"),
            client.delete(f"/api/users/invitations/{invitation.id}"),
            client.delete(f"/api/users/{staff.id}"),
            client.patch(f"/api/users/{staff.id}/role", json={"role": "receptionist"}),
        ]
        assert [response.status_code for response in responses] == [403] * len(responses)
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
