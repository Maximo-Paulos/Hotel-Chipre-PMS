from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import bookings as bookings_api
from app.api import reservations as reservations_api
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.temporary_action_grant import (
    TemporaryActionGrant,
    TemporaryActionGrantStatusEnum,
)
from app.models.user import User
from app.models.user_mfa import UserMfaSecret
from app.services.mfa_service import MFA_ACTIVE, encrypt_totp_secret
from app.services.permission_service import set_user_override
from app.services.reservation_service import ReservationError
from app.services.temporary_action_grant_service import (
    TemporaryGrantActor,
    consume_grant_for_action,
    revoke_grant,
)


@pytest.fixture
def temporary_grant_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
        ]
    )
    users = [
        User(id=1, email="requester@example.com", password_hash="unused", is_verified=True),
        User(id=2, email="owner@example.com", password_hash="unused", is_verified=True),
        User(id=3, email="manager@example.com", password_hash="unused", is_verified=True),
        User(id=4, email="other@example.com", password_hash="unused", is_verified=True),
        User(id=5, email="owner-without-mfa@example.com", password_hash="unused", is_verified=True),
    ]
    db.add_all(users)
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=1, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=2, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=3, role="manager", status="active"),
            HotelMembership(hotel_id=1, user_id=4, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=5, role="owner", status="active"),
            HotelMembership(hotel_id=2, user_id=3, role="manager", status="active"),
        ]
    )
    category = RoomCategory(
        hotel_id=1,
        name="Temporary Grant Test",
        code="TGT",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    guest = Guest(hotel_id=1, first_name="Ana", last_name="Grant")
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        confirmation_code="GRANT-RES-1",
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=2),
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("200.00"),
        num_adults=1,
    )
    db.add(reservation)

    mfa_secret = pyotp.random_base32()
    db.add(
        UserMfaSecret(
            user_id=2,
            encrypted_secret=encrypt_totp_secret(mfa_secret),
            status=MFA_ACTIVE,
        )
    )
    db.commit()

    def override_get_db():
        yield db

    def override_auth(user_id: int, role: str, hotel_id: int = 1):
        def dependency():
            return AuthContext(
                hotel_id=hotel_id,
                user_id=user_id,
                user_email=f"user{user_id}@example.com",
                user_role=role,
                is_verified=True,
                permissions=set(),
            )

        return dependency

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    client = TestClient(fastapi_app)
    try:
        yield client, db, mfa_secret, override_auth
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _reservation_id(db: Session) -> int:
    return db.query(Reservation.id).filter(Reservation.hotel_id == 1).order_by(Reservation.id).first()[0]


def _create_reservation(db: Session, confirmation_code: str) -> Reservation:
    category_id = (
        db.query(Reservation.category_id)
        .filter(Reservation.hotel_id == 1)
        .order_by(Reservation.id)
        .first()[0]
    )
    guest = Guest(hotel_id=1, first_name="Second", last_name="Guest")
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        guest_id=guest.id,
        category_id=category_id,
        confirmation_code=confirmation_code,
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=2),
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("200.00"),
        num_adults=1,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _request(client: TestClient, db: Session, reservation_id: int | None = None):
    response = client.post(
        "/api/permissions/temporary-grants/request",
        json={
            "permission_code": "reservation:cancel",
            "resource_type": "reservation",
            "resource_id": reservation_id or _reservation_id(db),
            "reason": "Autorizacion puntual para cancelar esta reserva",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(client: TestClient, override_auth, mfa_secret: str, grant_id: int):
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    response = client.post(
        f"/api/permissions/temporary-grants/{grant_id}/approve",
        json={"totp_code": pyotp.TOTP(mfa_secret).now()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_cancel_permission(
    db: Session,
    allowed: bool,
    *,
    user_id: int = 3,
    role: str = "manager",
):
    set_user_override(
        db,
        hotel_id=1,
        target_user_id=user_id,
        target_role=role,
        code="reservation:cancel",
        allowed=allowed,
        actor_user_id=2,
    )
    db.commit()


def _consume(db: Session, token: str, reservation_id: int, *, actor=None, **overrides) -> bool:
    arguments = {
        "permission_code": "reservation:cancel",
        "resource_type": "reservation",
        "resource_id": reservation_id,
    }
    arguments.update(overrides)
    return consume_grant_for_action(
        db,
        token,
        actor or TemporaryGrantActor(user_id=3, hotel_id=1),
        **arguments,
    )


def test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(
    temporary_grant_client,
):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    requested = _request(client, db)
    assert requested["status"] == "pending"
    assert requested["permission_code"] == "reservation:cancel"
    assert requested["resource_type"] == "reservation"
    assert requested["resource_id"] == str(reservation_id)

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    pending = client.get("/api/permissions/temporary-grants/pending")
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()["grants"]] == [requested["id"]]

    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    token = approved["token"]
    assert token
    assert "token_hash" not in approved["grant"]
    assert approved["grant"]["status"] == "approved"

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    cancelled = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": token},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == ReservationStatusEnum.CANCELLED.value
    assert token not in cancelled.text
    grant = db.get(TemporaryActionGrant, requested["id"])
    assert grant.status == TemporaryActionGrantStatusEnum.USED
    assert not _consume(db, token, reservation_id)

    replay = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": token},
    )
    assert replay.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.USED

    retired = client.post("/api/permissions/temporary-grants/consume", json={"token": token})
    assert retired.status_code == 410
    assert token not in retired.text


def test_ordinary_permission_allows_cancel_without_consuming_supplied_grant(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, True)
    requested = _request(client, db)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    response = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )
    assert response.status_code == 200, response.text
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


def test_canonical_reservation_cancel_accepts_exact_approved_grant(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    response = client.post(
        f"/api/reservations/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == ReservationStatusEnum.CANCELLED.value
    assert approved["token"] not in response.text
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.USED


def test_canonical_wrong_resource_does_not_consume_grant(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    other_reservation = _create_reservation(db, "GRANT-RES-CANONICAL-2")
    db.commit()
    _set_cancel_permission(db, False)
    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    wrong_resource = client.post(
        f"/api/reservations/{other_reservation.id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert wrong_resource.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED
    assert db.get(Reservation, other_reservation.id).status == ReservationStatusEnum.PENDING

    exact_resource = client.post(
        f"/api/reservations/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )
    assert exact_resource.status_code == 200, exact_resource.text
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.USED


def test_canonical_mutation_failure_rolls_back_grant_consumption(temporary_grant_client, monkeypatch):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    def mutate_then_fail(session, reservation, *_args, **_kwargs):
        reservation.status = ReservationStatusEnum.CANCELLED
        session.flush()
        raise ReservationError("synthetic cancellation failure")

    monkeypatch.setattr(reservations_api, "transition_reservation_status", mutate_then_fail)
    response = client.post(
        f"/api/reservations/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert response.status_code == 400
    assert db.get(Reservation, reservation_id).status == ReservationStatusEnum.PENDING
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


def test_canonical_normal_permission_does_not_consume_supplied_grant(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, True)
    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    response = client.post(
        f"/api/reservations/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert response.status_code == 200, response.text
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


@pytest.mark.parametrize("route_prefix", ["bookings", "reservations"])
def test_receptionist_is_denied_without_grant_and_can_cancel_exact_granted_reservation(
    temporary_grant_client,
    route_prefix,
):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False, user_id=1, role="receptionist")
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(1, "receptionist")

    denied_without_grant = client.post(f"/api/{route_prefix}/{reservation_id}/cancel")
    assert denied_without_grant.status_code == 403
    assert db.get(Reservation, reservation_id).status == ReservationStatusEnum.PENDING

    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(1, "receptionist")
    exact_action = client.post(
        f"/api/{route_prefix}/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert exact_action.status_code == 200, exact_action.text
    assert exact_action.json()["status"] == ReservationStatusEnum.CANCELLED.value
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.USED


def test_permission_denial_without_matching_grant_does_not_cancel(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    response = client.post(f"/api/bookings/{reservation_id}/cancel")
    assert response.status_code == 403
    assert db.get(Reservation, reservation_id).status == ReservationStatusEnum.PENDING


def test_wrong_action_resource_requester_or_hotel_does_not_consume_valid_grant(
    temporary_grant_client,
):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    requested = _request(client, db)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    token = approved["token"]

    assert not _consume(db, token, reservation_id, permission_code="reservation:manual_rate")
    assert not _consume(db, token, reservation_id, resource_type="booking")
    assert not _consume(db, token, reservation_id + 100)
    assert not _consume(db, token, reservation_id, actor=TemporaryGrantActor(user_id=4, hotel_id=1))
    assert not _consume(db, token, reservation_id, actor=TemporaryGrantActor(user_id=3, hotel_id=2))
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


def test_wrong_booking_id_on_action_route_keeps_grant_usable_for_bound_reservation(
    temporary_grant_client,
):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    other_reservation = _create_reservation(db, "GRANT-RES-2")
    db.commit()
    _set_cancel_permission(db, False)
    requested = _request(client, db, reservation_id)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    wrong_resource = client.post(
        f"/api/bookings/{other_reservation.id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )
    assert wrong_resource.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED
    assert db.get(Reservation, other_reservation.id).status == ReservationStatusEnum.PENDING

    correct_resource = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )
    assert correct_resource.status_code == 200
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.USED


def test_mutation_failure_rolls_back_grant_consumption(temporary_grant_client, monkeypatch):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    requested = _request(client, db)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")

    def mutate_then_fail(session, booking, *_args, **_kwargs):
        booking.status = ReservationStatusEnum.CANCELLED
        session.flush()
        raise ReservationError("synthetic cancellation failure")

    monkeypatch.setattr(bookings_api, "transition_reservation_status", mutate_then_fail)
    response = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )

    assert response.status_code == 400
    assert db.get(Reservation, reservation_id).status == ReservationStatusEnum.PENDING
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.APPROVED


def test_expired_grant_is_rejected_and_marked_expired(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    _set_cancel_permission(db, False)
    requested = _request(client, db)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    grant = db.get(TemporaryActionGrant, requested["id"])
    grant.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    response = client.post(
        f"/api/bookings/{reservation_id}/cancel",
        headers={"X-Temporary-Action-Grant": approved["token"]},
    )
    assert response.status_code == 403
    assert grant.status == TemporaryActionGrantStatusEnum.EXPIRED
    assert db.get(Reservation, reservation_id).status == ReservationStatusEnum.PENDING


def test_revoked_grant_cannot_be_consumed(temporary_grant_client):
    client, db, mfa_secret, override_auth = temporary_grant_client
    reservation_id = _reservation_id(db)
    requested = _request(client, db)
    approved = _approve(client, override_auth, mfa_secret, requested["id"])
    revoke_grant(db, requested["id"], TemporaryGrantActor(user_id=2, hotel_id=1))
    db.commit()

    assert not _consume(db, approved["token"], reservation_id)
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.REVOKED


def test_non_approver_role_cannot_approve(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client, db)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(3, "manager")
    response = client.post(
        f"/api/permissions/temporary-grants/{requested['id']}/approve",
        json={"totp_code": "000000"},
    )
    assert response.status_code == 403


def test_deny_does_not_populate_approver_field(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client, db)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    response = client.post(f"/api/permissions/temporary-grants/{requested['id']}/deny")
    assert response.status_code == 200
    assert response.json()["status"] == "denied"
    assert db.get(TemporaryActionGrant, requested["id"]).approver_user_id is None


def test_invalid_totp_and_owner_without_mfa_reject_approval(temporary_grant_client):
    client, db, _mfa_secret, override_auth = temporary_grant_client
    requested = _request(client, db)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(2, "owner")
    invalid_totp = client.post(
        f"/api/permissions/temporary-grants/{requested['id']}/approve",
        json={"totp_code": "000000"},
    )
    assert invalid_totp.status_code == 403
    assert db.get(TemporaryActionGrant, requested["id"]).status == TemporaryActionGrantStatusEnum.PENDING

    requested_without_mfa = _request(client, db)
    fastapi_app.dependency_overrides[get_auth_context] = override_auth(5, "owner")
    no_mfa = client.post(
        f"/api/permissions/temporary-grants/{requested_without_mfa['id']}/approve",
        json={"totp_code": "123456"},
    )
    assert no_mfa.status_code == 403
    assert db.get(TemporaryActionGrant, requested_without_mfa["id"]).status == TemporaryActionGrantStatusEnum.PENDING


def test_request_rejects_other_actions_and_resources(temporary_grant_client):
    client, db, _mfa_secret, _override_auth = temporary_grant_client
    invalid_action = client.post(
        "/api/permissions/temporary-grants/request",
        json={
            "permission_code": "reservation:manual_rate",
            "resource_type": "reservation",
            "resource_id": _reservation_id(db),
            "reason": "No corresponde a la accion permitida",
        },
    )
    assert invalid_action.status_code == 422

    invalid_resource = client.post(
        "/api/permissions/temporary-grants/request",
        json={
            "permission_code": "reservation:cancel",
            "resource_type": "booking",
            "resource_id": _reservation_id(db),
            "reason": "El tipo de recurso no es canonico",
        },
    )
    assert invalid_resource.status_code == 422

    missing_reservation = client.post(
        "/api/permissions/temporary-grants/request",
        json={
            "permission_code": "reservation:cancel",
            "resource_type": "reservation",
            "resource_id": 999999,
            "reason": "La reserva no existe",
        },
    )
    assert missing_reservation.status_code == 422


def test_retired_standalone_consume_returns_gone_without_echoing_token(temporary_grant_client):
    client, _db, _mfa_secret, _override_auth = temporary_grant_client
    token = "opaque-one-time-token"
    response = client.post("/api/permissions/temporary-grants/consume", json={"token": token})
    assert response.status_code == 410
    assert token not in response.text
