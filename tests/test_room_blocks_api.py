from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import room_blocks
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
import app.models  # noqa: F401
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.permission_service import resolve


def _override_auth(hotel_id: int, role: str):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=123,
            user_email=f"{role}@example.com",
            user_role=role,
            is_verified=True,
        )

    return dependency


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'room_blocks_api.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    app = FastAPI()
    app.include_router(room_blocks.router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, session, app
    app.dependency_overrides.clear()
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_room(db, hotel_id: int = 1) -> Room:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    if db.get(User, 123) is None:
        db.add(
            User(
                id=123,
                email="user123@example.com",
                password_hash="test",
                is_active=True,
                is_verified=True,
            )
        )
    db.flush()
    return room


def _seed_reservation(db, room: Room, *, suffix: str, allocation_locked: bool = False) -> Reservation:
    guest = Guest(
        hotel_id=room.hotel_id,
        first_name="Test",
        last_name=f"Guest {suffix}",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"RB-{room.hotel_id}-{suffix}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=room.hotel_id,
        confirmation_code=f"RB-{room.hotel_id}-{suffix}",
        guest_id=guest.id,
        room_id=room.id,
        category_id=room.category_id,
        check_in_date=date(2026, 7, 10),
        check_out_date=date(2026, 7, 14),
        status=ReservationStatusEnum.PENDING,
        total_amount=400,
        allocation_locked=allocation_locked,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_room_block_permission_defaults(db):
    # room_blocks.py gates create/release separately (room_block:create /
    # room_block:release) -- receptionist may create a block but not release
    # one by default, matching BRM §14.1's intent that front-desk can take a
    # room out of service but only a manager+ clears it back in.
    assert resolve(db, 1, "owner", "room_block:create") is True
    assert resolve(db, 1, "owner", "room_block:release") is True
    assert resolve(db, 1, "co_owner", "room_block:create") is True
    assert resolve(db, 1, "co_owner", "room_block:release") is True
    assert resolve(db, 1, "manager", "room_block:create") is True
    assert resolve(db, 1, "manager", "room_block:release") is True
    assert resolve(db, 1, "receptionist", "room_block:create") is True
    assert resolve(db, 1, "receptionist", "room_block:release") is False
    assert resolve(db, 1, "housekeeping", "room_block:create") is False
    assert resolve(db, 1, "housekeeping", "room_block:release") is False
    assert resolve(db, 1, "housekeeping", "room:read") is True


def test_create_and_resolve_room_block_api(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

    create_response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
            "reason_note": "Pipe repair",
        },
    )

    assert create_response.status_code == 201
    block_id = create_response.json()["id"]

    list_response = test_client.get(
        "/api/room-blocks/",
        params={"start_date": "2026-07-02", "end_date": "2026-07-04"},
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [block_id]

    resolve_response = test_client.post(f"/api/room-blocks/{block_id}/resolve")
    assert resolve_response.status_code == 200
    assert resolve_response.json()["resolved_by_user_id"] == 123


def test_room_block_conflict_preview_returns_counts_without_reservation_identity(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    _seed_reservation(db, room, suffix="open")
    _seed_reservation(db, room, suffix="locked", allocation_locked=True)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

    response = test_client.get(
        "/api/room-blocks/conflicts/preview",
        params={
            "room_id": room.id,
            "starts_at": "2026-07-11",
            "ends_at": "2026-07-12",
            "is_indefinite": "false",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"reservation_count": 2, "protected_reservation_count": 1}

    no_overlap = test_client.get(
        "/api/room-blocks/conflicts/preview",
        params={
            "room_id": room.id,
            "starts_at": "2026-07-20",
            "ends_at": "2026-07-21",
            "is_indefinite": "false",
        },
    )
    assert no_overlap.status_code == 200, no_overlap.text
    assert no_overlap.json() == {"reservation_count": 0, "protected_reservation_count": 0}


def test_room_block_conflict_preview_uses_create_permission_and_validates_dates(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")

    forbidden = test_client.get(
        "/api/room-blocks/conflicts/preview",
        params={
            "room_id": room.id,
            "starts_at": "2026-07-10",
            "ends_at": "2026-07-11",
            "is_indefinite": "false",
        },
    )
    assert forbidden.status_code == 403

    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
    invalid = test_client.get(
        "/api/room-blocks/conflicts/preview",
        params={
            "room_id": room.id,
            "starts_at": "2026-07-11",
            "ends_at": "2026-07-11",
            "is_indefinite": "false",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "ends_at must be after starts_at"


def test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
    created = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )
    assert created.status_code == 201, created.text
    block_id = created.json()["id"]

    app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")
    listing = test_client.get("/api/room-blocks/")
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()] == [block_id]
    denied = test_client.get(
        f"/api/room-blocks/{block_id}/extend-preview",
        params={"ends_at": "2026-07-08"},
    )
    assert denied.status_code == 403


def test_room_block_extension_preview_and_mutation_keep_end_exclusive(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
    created = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )
    assert created.status_code == 201, created.text
    block_id = created.json()["id"]

    invalid_preview = test_client.get(
        f"/api/room-blocks/{block_id}/extend-preview",
        params={"ends_at": "2026-07-05"},
    )
    assert invalid_preview.status_code == 400

    preview = test_client.get(
        f"/api/room-blocks/{block_id}/extend-preview",
        params={"ends_at": "2026-07-08"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "reservation_count": 0,
        "protected_reservation_count": 0,
        "overlapping_block_count": 0,
    }

    extended = test_client.post(f"/api/room-blocks/{block_id}/extend", json={"ends_at": "2026-07-08"})
    assert extended.status_code == 200, extended.text
    assert extended.json()["ends_at"] == "2026-07-08"


def test_receptionist_can_create_but_not_release_room_block_by_default(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")

    create_response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )
    assert create_response.status_code == 201
    block_id = create_response.json()["id"]

    release_response = test_client.post(f"/api/room-blocks/{block_id}/resolve")
    assert release_response.status_code == 403


def test_housekeeping_cannot_create_room_block_by_default(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")

    response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )

    assert response.status_code == 403


def test_housekeeping_only_reads_operational_room_block_reasons(client):
    test_client, db, app = client
    room = _seed_room(db, hotel_id=1)
    reasons = list(RoomBlockReasonEnum)
    for index, reason in enumerate(reasons):
        start = date(2026, 7, 1 + index * 2)
        db.add(RoomBlock(
            hotel_id=1,
            room_id=room.id,
            reason_code=reason,
            starts_at=start,
            ends_at=date(2026, 7, 2 + index * 2),
            is_indefinite=False,
            reason_note=f"Detalle {reason.value}",
            created_by_user_id=123,
        ))
    db.flush()
    app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")

    response = test_client.get("/api/room-blocks/")

    assert response.status_code == 200
    assert {item["reason_code"] for item in response.json()} == {"maintenance", "deep_cleaning"}
    assert {item["reason_note"] for item in response.json()} == {"Detalle maintenance", "Detalle deep_cleaning"}


def test_room_block_api_is_hotel_scoped(client):
    test_client, db, app = client
    room_1 = _seed_room(db, hotel_id=1)
    _seed_room(db, hotel_id=2)
    app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

    response = test_client.post(
        "/api/room-blocks/",
        json={
            "room_id": room_1.id,
            "starts_at": "2026-07-01",
            "ends_at": "2026-07-05",
            "reason_code": "maintenance",
        },
    )
    assert response.status_code == 201

    app.dependency_overrides[get_auth_context] = _override_auth(2, "manager")
    list_response = test_client.get(
        "/api/room-blocks/",
        params={"start_date": "2026-07-02", "end_date": "2026-07-04"},
    )

    assert list_response.status_code == 200
    assert list_response.json() == []
