from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent, RoomMoveTypeEnum, RoomMovementGroup
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User


@pytest.fixture
def movement_api_client(monkeypatch: pytest.MonkeyPatch):
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

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    auth_state = {"hotel_id": 1, "user_id": 10, "role": "manager"}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="manager@test.com",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner1@test.com", subscription_active=True),
                HotelConfiguration(id=2, owner_email="owner2@test.com", subscription_active=True),
                User(id=10, email="manager@test.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal, auth_state

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_list_movement_groups_with_filters(movement_api_client):
    client, SessionLocal, _ = movement_api_client
    with SessionLocal() as db:
        first = _seed_group(db, hotel_id=1, suffix="A", trigger_reason="overbooking_resolution")
        second = _seed_group(db, hotel_id=1, suffix="B", trigger_reason="maintenance_relocation")
        second["group"].is_reverted = True
        db.commit()
        first_group_id = first["group"].id
        first_reservation_id = first["reservation"].id
        second_group_id = second["group"].id

    listing = client.get("/api/movement-groups/")
    assert listing.status_code == 200, listing.text
    assert {group["id"] for group in listing.json()} == {first_group_id, second_group_id}

    by_trigger = client.get("/api/movement-groups/", params={"trigger_reason": "overbooking_resolution"})
    assert by_trigger.status_code == 200, by_trigger.text
    assert [group["id"] for group in by_trigger.json()] == [first_group_id]

    by_reverted = client.get("/api/movement-groups/", params={"is_reverted": False})
    assert by_reverted.status_code == 200, by_reverted.text
    assert [group["id"] for group in by_reverted.json()] == [first_group_id]

    by_reservation = client.get("/api/movement-groups/", params={"reservation_id": first_reservation_id})
    assert by_reservation.status_code == 200, by_reservation.text
    assert [group["id"] for group in by_reservation.json()] == [first_group_id]


def test_read_movement_group_detail_includes_movements(movement_api_client):
    client, SessionLocal, _ = movement_api_client
    with SessionLocal() as db:
        seeded = _seed_group(db, hotel_id=1, suffix="DETAIL", trigger_reason="manual_reallocation")
        db.commit()
        group_id = seeded["group"].id
        event_id = seeded["event"].id
        reservation_id = seeded["reservation"].id

    response = client.get(f"/api/movement-groups/{group_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == group_id
    assert body["trigger_reason"] == "manual_reallocation"
    assert len(body["movements"]) == 1
    assert body["movements"][0]["id"] == event_id
    assert body["movements"][0]["reservation_id"] == reservation_id
    assert body["movements"][0]["move_type"] == RoomMoveTypeEnum.AUTO_ASSIGNMENT.value


def test_revert_movement_group_restores_original_room_and_audits(movement_api_client):
    client, SessionLocal, _ = movement_api_client
    with SessionLocal() as db:
        seeded = _seed_group(db, hotel_id=1, suffix="REVERT", trigger_reason="allocation_run")
        db.commit()
        group_id = seeded["group"].id
        reservation_id = seeded["reservation"].id
        from_room_id = seeded["from_room"].id
        from_category_id = seeded["from_room"].category_id

    response = client.post(f"/api/movement-groups/{group_id}/revert")

    assert response.status_code == 200, response.text
    assert response.json()["is_reverted"] is True
    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        group = db.get(RoomMovementGroup, group_id)
        audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.hotel_id == 1).one()
        assert reservation.room_id == from_room_id
        assert reservation.category_id == from_category_id
        assert reservation.allocation_locked is True
        assert reservation.requires_manual_review is False
        assert group.is_reverted is True
        assert group.reverted_by_user_id == 10
        assert audit.action == "room_movement_group.reverted"
        assert audit.resource_id == str(group_id)


def test_movement_group_hotel_isolation(movement_api_client):
    client, SessionLocal, _ = movement_api_client
    with SessionLocal() as db:
        own = _seed_group(db, hotel_id=1, suffix="OWN", trigger_reason="own_group")
        other = _seed_group(db, hotel_id=2, suffix="OTHER", trigger_reason="other_group")
        db.commit()
        own_group_id = own["group"].id
        other_group_id = other["group"].id

    listing = client.get("/api/movement-groups/")
    hidden_detail = client.get(f"/api/movement-groups/{other_group_id}")
    hidden_revert = client.post(f"/api/movement-groups/{other_group_id}/revert")

    assert listing.status_code == 200, listing.text
    assert [group["id"] for group in listing.json()] == [own_group_id]
    assert hidden_detail.status_code == 404
    assert hidden_revert.status_code == 404


def test_revert_already_reverted_group_returns_400(movement_api_client):
    client, SessionLocal, _ = movement_api_client
    with SessionLocal() as db:
        seeded = _seed_group(db, hotel_id=1, suffix="DONE", trigger_reason="already_done")
        seeded["group"].is_reverted = True
        db.commit()
        group_id = seeded["group"].id

    response = client.post(f"/api/movement-groups/{group_id}/revert")

    assert response.status_code == 400
    assert response.json()["detail"] == "Movement group is already reverted"


def _seed_group(db, *, hotel_id: int, suffix: str, trigger_reason: str):
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {suffix}",
        code=f"STD_{suffix}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()

    from_room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}{suffix}1",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    to_room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}{suffix}2",
        floor=2,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Ada",
        last_name=f"Guest {suffix}",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"{hotel_id}{suffix}123",
        terms_accepted=True,
    )
    db.add_all([from_room, to_room, guest])
    db.flush()

    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"{hotel_id}-{suffix}-MOVE",
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
        trigger_reason=trigger_reason,
        notes=f"Seeded group {suffix}",
        is_reverted=False,
        created_by_user_id=10,
    )
    db.add(group)
    db.flush()

    event = RoomMoveEvent(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        movement_group_id=group.id,
        from_room_id=from_room.id,
        to_room_id=to_room.id,
        move_type=RoomMoveTypeEnum.AUTO_ASSIGNMENT,
        reason_code=trigger_reason,
        reason_note=f"Seeded move {suffix}",
        trigger_event="test_seed",
        state_before="from_room",
        state_after="to_room",
    )
    db.add(event)
    db.flush()

    return {
        "reservation": reservation,
        "from_room": from_room,
        "to_room": to_room,
        "group": group,
        "event": event,
    }
