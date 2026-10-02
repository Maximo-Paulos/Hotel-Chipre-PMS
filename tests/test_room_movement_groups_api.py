from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.company import Company
from app.models.hotel_membership import HotelMembership
from app.models.operations import RoomMoveEvent, RoomMoveTypeEnum, RoomMovementGroup
from app.models.permission import HotelPermissionOverride, UserPermissionOverride
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.permission_service import (
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT,
    seed_default_permissions,
)


def _override_auth(hotel_id: int, role: str = "manager", user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
        )

    return dependency


def _client_with_db():
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

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(id=10, email="user10@example.com", password_hash="test", is_active=True, is_verified=True),
        ]
    )
    db.flush()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app), db, engine


def test_revert_movement_group_marks_reservations_protected():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=10)
    try:
        reservation, from_room, to_room, group = _seed_group(db, hotel_id=1)
        version_before_revert = reservation.version
        db.commit()

        response = client.post(f"/api/room-movement-groups/{group.id}/revert")

        assert response.status_code == 200
        body = response.json()
        db.refresh(reservation)
        db.refresh(group)
        assert body["is_reverted"] is True
        assert reservation.room_id == from_room.id
        assert reservation.category_id == from_room.category_id
        assert reservation.version == version_before_revert + 1
        assert reservation.allocation_locked is True
        assert group.reverted_by_user_id == 10
        audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.hotel_id == 1).one()
        assert audit.action == "room_movement_group.reverted"
        assert audit.resource_id == str(group.id)
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_receptionist_can_read_but_cannot_revert_room_movement_group():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist", user_id=10)
    try:
        reservation, _, to_room, group = _seed_group(db, hotel_id=1)
        db.commit()

        listing = client.get("/api/room-movement-groups/")
        denied = client.post(f"/api/room-movement-groups/{group.id}/revert")

        db.refresh(reservation)
        db.refresh(group)
        assert listing.status_code == 200, listing.text
        assert denied.status_code == 403, denied.text
        assert group.is_reverted is False
        assert reservation.room_id == to_room.id
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.mark.parametrize("route_prefix", ["/api/movement-groups", "/api/room-movement-groups"])
def test_explicit_receptionist_grant_can_revert_group(route_prefix):
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist", user_id=10)
    try:
        _, _, _, group = _seed_group(db, hotel_id=1)
        seed_default_permissions(db)
        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="receptionist",
                permission_code=PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT,
                allowed=True,
                updated_by_user_id=10,
            )
        )
        db.commit()

        response = client.post(f"{route_prefix}/{group.id}/revert")

        assert response.status_code == 200, response.text
        assert response.json()["is_reverted"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.mark.parametrize("route_prefix", ["/api/movement-groups", "/api/room-movement-groups"])
def test_company_group_revert_denies_reception_even_with_individual_company_manage_override(route_prefix):
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist", user_id=10)
    try:
        reservation, _, to_room, group = _seed_group(db, hotel_id=1)
        company = Company(
            hotel_id=1,
            legal_name="Synthetic Company",
            display_name="Synthetic Company",
        )
        db.add(company)
        db.flush()
        reservation.company_id = company.id
        seed_default_permissions(db)
        db.add(HotelMembership(hotel_id=1, user_id=10, role="receptionist", status="active"))
        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="receptionist",
                permission_code=PERMISSION_RESERVATION_MOVEMENT_GROUP_REVERT,
                allowed=True,
                updated_by_user_id=10,
            )
        )
        db.commit()
        version_before_revert = reservation.version

        denied = client.post(f"{route_prefix}/{group.id}/revert")

        assert denied.status_code == 403, denied.text
        db.refresh(reservation)
        db.refresh(group)
        assert reservation.room_id == to_room.id
        assert reservation.version == version_before_revert
        assert group.is_reverted is False

        db.add(
            UserPermissionOverride(
                hotel_id=1,
                user_id=10,
                permission_code=PERMISSION_COMPANY_MANAGE,
                allowed=True,
                updated_by_user_id=10,
            )
        )
        db.commit()

        still_denied = client.post(f"{route_prefix}/{group.id}/revert")

        assert still_denied.status_code == 403, still_denied.text
        db.refresh(reservation)
        db.refresh(group)
        assert reservation.room_id == to_room.id
        assert reservation.version == version_before_revert
        assert group.is_reverted is False
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_housekeeping_cannot_read_or_revert_room_movement_group():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping", user_id=10)
    try:
        _, _, _, group = _seed_group(db, hotel_id=1)
        db.commit()

        listing = client.get("/api/room-movement-groups/")
        detail = client.get(f"/api/room-movement-groups/{group.id}")
        denied = client.post(f"/api/room-movement-groups/{group.id}/revert")

        assert listing.status_code == 403, listing.text
        assert detail.status_code == 403, detail.text
        assert denied.status_code == 403, denied.text
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_room_movement_group_cross_hotel_isolation():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=10)
    try:
        _, _, _, group_h1 = _seed_group(db, hotel_id=1)
        _, _, _, group_h2 = _seed_group(db, hotel_id=2)
        db.commit()

        hidden_get = client.get(f"/api/room-movement-groups/{group_h2.id}")
        hidden_revert = client.post(f"/api/room-movement-groups/{group_h2.id}/revert")
        own_get = client.get(f"/api/room-movement-groups/{group_h1.id}")

        assert hidden_get.status_code == 404
        assert hidden_revert.status_code == 400
        assert own_get.status_code == 200
        assert own_get.json()["id"] == group_h1.id
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _seed_group(db, *, hotel_id: int):
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    from_room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    to_room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}02",
        floor=2,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Ada",
        last_name=f"Hotel{hotel_id}",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"{hotel_id}123",
        terms_accepted=True,
    )
    db.add_all([from_room, to_room, guest])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"{hotel_id}-MOVE",
        guest_id=guest.id,
        room_id=to_room.id,
        category_id=to_room.category_id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        status=ReservationStatusEnum.PENDING,
        total_amount=100,
        amount_paid=0,
        deposit_amount=0,
    )
    db.add(reservation)
    db.flush()
    group = RoomMovementGroup(
        hotel_id=hotel_id,
        trigger_reason="test_allocation",
    )
    db.add(group)
    db.flush()
    db.add(
        RoomMoveEvent(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            movement_group_id=group.id,
            from_room_id=from_room.id,
            to_room_id=to_room.id,
            move_type=RoomMoveTypeEnum.AUTO_ASSIGNMENT,
            reason_code="test_allocation",
        )
    )
    db.flush()
    return reservation, from_room, to_room, group
