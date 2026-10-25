"""Fixed, tenant-scoped post-checkout housekeeping checklist regressions."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure API permission and audit tables exist in SQLite tests
from app.api import housekeeping, rooms
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.audit_log import AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.housekeeping_checklist import (
    HousekeepingChecklist,
    HousekeepingChecklistItem,
    HousekeepingChecklistItemCodeEnum,
    HousekeepingChecklistStatusEnum,
)
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.user import User
from app.services.checkin_service import (
    CheckInError,
    _load_ready_room_for_checkin,
    perform_checkout,
)
from app.services.housekeeping_checklist_policy import (
    REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS,
)
from app.services.housekeeping_checklist_service import (
    HousekeepingChecklistNotFound,
    complete_checklist_item,
    create_checkout_checklist,
    list_open_checklists,
)
from app.services.room_state_service import (
    RoomStateTransitionError,
    change_room_status,
    mutate_room_state,
)


def _checked_in_reservation(db, room, guest, category, *, status=RoomStatusEnum.OCCUPIED):
    room.status = status
    db.flush()
    reservation = Reservation(
        hotel_id=room.hotel_id,
        confirmation_code=f"HK-{uuid4().hex[:16]}",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date.today() - timedelta(days=1),
        check_out_date=date.today(),
        actual_check_in=datetime.now(UTC),
        total_amount=0,
        amount_paid=0,
        num_adults=1,
        status=ReservationStatusEnum.CHECKED_IN,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _checkout(db, monkeypatch, room, guest, category, *, status=RoomStatusEnum.OCCUPIED):
    from app.services import checkin_service

    monkeypatch.setattr(checkin_service, "_notify_reservation_event", lambda *args, **kwargs: None)
    reservation = _checked_in_reservation(db, room, guest, category, status=status)
    checkout = perform_checkout(db, reservation.id, hotel_id=room.hotel_id, actor_user_id=None)
    db.flush()
    checklist = (
        db.query(HousekeepingChecklist)
        .filter(
            HousekeepingChecklist.hotel_id == room.hotel_id,
            HousekeepingChecklist.reservation_id == reservation.id,
        )
        .one()
    )
    return checkout, checklist


def _complete(db, checklist, item_code):
    return complete_checklist_item(
        db,
        hotel_id=checklist.hotel_id,
        checklist_id=checklist.id,
        item_code=item_code,
        actor_user_id=None,
    )


def test_checkout_creates_fixed_checklist_and_final_item_releases_cleaning_room(
    db, hotel_config, sample_guest, sample_rooms, sample_categories, monkeypatch
):
    room = sample_rooms[0]
    reservation, checklist = _checkout(
        db, monkeypatch, room, sample_guest, sample_categories[0]
    )

    assert reservation.status == ReservationStatusEnum.CHECKED_OUT
    assert room.status == RoomStatusEnum.CLEANING
    assert room.housekeeping_status == RoomHousekeepingStatusEnum.DIRTY
    assert checklist.status == HousekeepingChecklistStatusEnum.OPEN.value
    items = (
        db.query(HousekeepingChecklistItem)
        .filter(HousekeepingChecklistItem.checklist_id == checklist.id)
        .order_by(HousekeepingChecklistItem.id)
        .all()
    )
    assert [(item.code, item.label) for item in items] == [
        (code.value, label) for code, label in REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS
    ]
    assert all(item.completed is False for item in items)

    for item_code in HousekeepingChecklistItemCodeEnum:
        result = _complete(db, checklist, item_code)
        if item_code != HousekeepingChecklistItemCodeEnum.CHECK_AMENITIES:
            assert result.completed_now is False
            assert result.checklist.status == HousekeepingChecklistStatusEnum.OPEN
            assert room.status == RoomStatusEnum.CLEANING
            assert room.housekeeping_status == RoomHousekeepingStatusEnum.IN_PROGRESS

    assert result.completed_now is True
    assert result.checklist.status == HousekeepingChecklistStatusEnum.COMPLETED
    assert result.checklist.version == 6
    assert result.checklist.completed_at is not None
    assert room.status == RoomStatusEnum.AVAILABLE
    assert room.housekeeping_status == RoomHousekeepingStatusEnum.CLEAN
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.hotel_id == hotel_config.id,
            AuditLog.table_name == "housekeeping_checklists",
            AuditLog.record_id == checklist.id,
        )
        .count()
        == 2
    )


def test_item_completion_is_idempotent_and_does_not_increment_version(
    db, hotel_config, sample_guest, sample_rooms, sample_categories, monkeypatch
):
    _reservation, checklist = _checkout(
        db, monkeypatch, sample_rooms[0], sample_guest, sample_categories[0]
    )
    code = HousekeepingChecklistItemCodeEnum.CHANGE_SHEETS

    first = _complete(db, checklist, code)
    second = _complete(db, checklist, code)

    assert first.changed is True
    assert first.checklist.version == 2
    assert second.changed is False
    assert second.completed_now is False
    assert second.checklist.version == 2
    assert sample_rooms[0].status == RoomStatusEnum.CLEANING


@pytest.mark.parametrize("protected_status", [RoomStatusEnum.MAINTENANCE, RoomStatusEnum.BLOCKED])
def test_completing_checklist_preserves_maintenance_and_blocked_rooms(
    db,
    hotel_config,
    sample_guest,
    sample_rooms,
    sample_categories,
    monkeypatch,
    protected_status,
):
    room = sample_rooms[0]
    _reservation, checklist = _checkout(
        db,
        monkeypatch,
        room,
        sample_guest,
        sample_categories[0],
        status=protected_status,
    )
    assert room.status == protected_status

    for item_code in HousekeepingChecklistItemCodeEnum:
        result = _complete(db, checklist, item_code)

    assert result.checklist.status == HousekeepingChecklistStatusEnum.COMPLETED
    assert room.status == protected_status
    assert room.housekeeping_status == RoomHousekeepingStatusEnum.CLEAN


def test_open_checklist_blocks_direct_release_and_checkin_even_if_room_looks_ready(
    db, hotel_config, sample_guest, sample_rooms, sample_categories, monkeypatch
):
    room = sample_rooms[0]
    reservation, checklist = _checkout(
        db, monkeypatch, room, sample_guest, sample_categories[0]
    )
    with pytest.raises(RoomStateTransitionError, match="checklist de limpieza pendiente"):
        change_room_status(
            db,
            room=room,
            hotel_id=hotel_config.id,
            status=RoomStatusEnum.AVAILABLE,
        )

    # Simulate a legacy/direct DB write that bypassed the status service. The
    # explicit check-in gate still rejects a room with an open checklist.
    room.status = RoomStatusEnum.AVAILABLE
    room.housekeeping_status = RoomHousekeepingStatusEnum.CLEAN
    db.flush()
    with pytest.raises(CheckInError, match="checklist de limpieza"):
        _load_ready_room_for_checkin(db, reservation, hotel_config.id)
    assert checklist.status == HousekeepingChecklistStatusEnum.OPEN.value


def test_room_state_mutation_audits_inside_the_callers_transaction(
    db, hotel_config, sample_rooms
):
    room = sample_rooms[0]
    original_status = room.status
    nested = db.begin_nested()

    changed = mutate_room_state(
        db,
        room=room,
        hotel_id=hotel_config.id,
        status=RoomStatusEnum.CLEANING,
        actor_user_id=None,
    )

    assert changed is True
    assert room.status == RoomStatusEnum.CLEANING
    assert room.housekeeping_status == RoomHousekeepingStatusEnum.DIRTY
    assert nested.is_active
    room_audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.hotel_id == hotel_config.id,
            AuditLog.table_name == "rooms",
            AuditLog.record_id == room.id,
        )
        .all()
    )
    assert len(room_audits) == 1

    nested.rollback()
    db.refresh(room)
    assert room.status == original_status
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.hotel_id == hotel_config.id,
            AuditLog.table_name == "rooms",
            AuditLog.record_id == room.id,
        )
        .count()
        == 0
    )


def test_room_state_mutation_rejects_a_different_tenant(
    db, hotel_config, sample_rooms
):
    room = sample_rooms[0]
    original_status = room.status

    with pytest.raises(RoomStateTransitionError, match="no pertenece al hotel"):
        mutate_room_state(
            db,
            room=room,
            hotel_id=hotel_config.id + 1,
            status=RoomStatusEnum.CLEANING,
        )

    assert room.status == original_status
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.hotel_id == hotel_config.id,
            AuditLog.table_name == "rooms",
            AuditLog.record_id == room.id,
        )
        .count()
        == 0
    )


def test_complete_item_is_tenant_scoped(db, hotel_config, sample_guest, sample_rooms, sample_categories, monkeypatch):
    _reservation, checklist = _checkout(
        db, monkeypatch, sample_rooms[0], sample_guest, sample_categories[0]
    )
    with pytest.raises(HousekeepingChecklistNotFound):
        complete_checklist_item(
            db,
            hotel_id=hotel_config.id + 1,
            checklist_id=checklist.id,
            item_code=HousekeepingChecklistItemCodeEnum.CHANGE_SHEETS,
            actor_user_id=None,
        )


def test_open_checklist_list_batches_room_and_item_queries(
    db, hotel_config, sample_guest, sample_rooms, sample_categories, monkeypatch
):
    created_checklists = [
        _checkout(db, monkeypatch, room, sample_guest, sample_categories[0])[1]
        for room in sample_rooms[:8]
    ]
    expected_ids = [
        checklist.id
        for checklist in sorted(
            created_checklists,
            key=lambda checklist: (checklist.created_at, checklist.id),
        )
    ]

    select_count = [0]

    def count_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            select_count[0] += 1

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", count_selects)
    try:
        result = list_open_checklists(db, hotel_id=hotel_config.id)
        assert select_count[0] == 3, (
            "an open checklist list should use one query each for checklists, rooms, and items"
        )

        payload = result.model_dump(mode="json")
        assert set(payload) == {"checklists"}
        assert [item["checklist_id"] for item in payload["checklists"]] == expected_ids
        first = payload["checklists"][0]
        assert set(first) == {
            "checklist_id", "room", "status", "version", "created_at", "completed_at", "items"
        }
        assert set(first["room"]) == {
            "id", "number", "operational_status", "housekeeping_status"
        }
        assert [item["code"] for item in first["items"]] == [
            code.value for code, _label in REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS
        ]
        assert [item["label"] for item in first["items"]] == [
            label for _code, label in REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS
        ]
        assert all(item["completed"] is False for item in first["items"])

        select_count[0] = 0
        foreign_hotel = list_open_checklists(db, hotel_id=hotel_config.id + 1)
        assert foreign_hotel.checklists == []
        assert select_count[0] == 1
    finally:
        event.remove(bind, "before_cursor_execute", count_selects)


@pytest.fixture
def api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    hotel_config = HotelConfiguration(id=1, hotel_name="Housekeeping API test", subscription_active=True)
    category = RoomCategory(
        hotel_id=1,
        name="Standard",
        code="STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([hotel_config, category])
    db.flush()
    room = Room(
        hotel_id=1,
        category_id=category.id,
        room_number="101",
        status=RoomStatusEnum.CLEANING,
        housekeeping_status=RoomHousekeepingStatusEnum.DIRTY,
    )
    guest = Guest(hotel_id=1, first_name="Synthetic", last_name="Guest")
    db.add_all([room, guest])
    db.commit()

    app = FastAPI()
    app.include_router(housekeeping.router)
    app.include_router(rooms.router)
    auth = {"role": "housekeeping", "hotel_id": 1, "user_id": 501}

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=auth["hotel_id"],
            user_id=auth["user_id"],
            user_email=f"{auth['role']}@example.test",
            user_role=auth["role"],
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = override_auth
    user = User(id=501, email="housekeeping@example.test", password_hash="test-only")
    db.add(user)
    db.flush()
    with TestClient(app) as client:
        yield client, auth, room, guest, category, db
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_api_contract_authorization_tenant_scope_and_release_guards(
    api_client,
):
    client, auth, room, guest, category, db = api_client
    hotel_id = auth["hotel_id"]
    room.status = RoomStatusEnum.CLEANING
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"HK-API-{uuid4().hex[:12]}",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date.today() - timedelta(days=1),
        check_out_date=date.today(),
        total_amount=0,
        amount_paid=0,
        num_adults=1,
        status=ReservationStatusEnum.CHECKED_OUT,
    )
    db.add(reservation)
    db.flush()
    checklist = create_checkout_checklist(
        db,
        hotel_id=hotel_id,
        room_id=room.id,
        reservation_id=reservation.id,
        actor_user_id=None,
    )
    db.commit()

    response = client.get("/api/housekeeping/checklists")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"checklists"}
    item = payload["checklists"][0]
    assert set(item) == {
        "checklist_id", "room", "status", "version", "created_at", "completed_at", "items"
    }
    assert item["checklist_id"] == checklist.id
    assert item["room"]["id"] == room.id
    assert {row["code"] for row in item["items"]} == {
        code.value for code in HousekeepingChecklistItemCodeEnum
    }
    assert "guest" not in item and "confirmation_code" not in str(payload)

    auth["hotel_id"] = hotel_id + 1
    db.add(HotelConfiguration(id=hotel_id + 1, hotel_name="Second test hotel"))
    db.commit()
    cross_hotel = client.get("/api/housekeeping/checklists")
    assert cross_hotel.status_code == 200, cross_hotel.text
    assert cross_hotel.json() == {"checklists": []}
    foreign_mutation = client.post(
        f"/api/housekeeping/checklists/{checklist.id}/items/change_sheets/complete"
    )
    assert foreign_mutation.status_code == 404
    auth["hotel_id"] = hotel_id

    completed = client.post(
        f"/api/housekeeping/checklists/{checklist.id}/items/change_sheets/complete"
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["version"] == 2
    assert completed.json()["items"][0]["completed"] is True

    dirty_to_clean = client.patch(f"/api/rooms/{room.id}/cleaning-status", json={"status": "clean"})
    assert dirty_to_clean.status_code == 409

    auth["role"] = "manager"
    premature_release = client.patch(f"/api/rooms/{room.id}/status", json={"status": "available"})
    assert premature_release.status_code == 409
    db.refresh(room)
    assert room.status == RoomStatusEnum.CLEANING

    auth["role"] = "receptionist"
    assert client.get("/api/housekeeping/checklists").status_code == 403
