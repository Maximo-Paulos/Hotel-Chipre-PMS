from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.guest_room_avoidance import GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User


def _client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = session_local()
    role_state = {"role": "receptionist"}
    db.add_all(
        [
            HotelConfiguration(id=9601, hotel_name="Avoidance API", subscription_active=True),
            User(id=9601, email="avoidance@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    category = RoomCategory(
        hotel_id=9601,
        name="Standard",
        code="AVOID-STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=9601, first_name="Complaint", last_name="Guest")
    db.add_all([category, guest])
    db.flush()
    source_room = Room(
        hotel_id=9601,
        category_id=category.id,
        room_number="A101",
        status=RoomStatusEnum.AVAILABLE,
    )
    destination_room = Room(
        hotel_id=9601,
        category_id=category.id,
        room_number="A102",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add_all([source_room, destination_room])
    db.flush()
    reservation = Reservation(
        hotel_id=9601,
        confirmation_code="AVOID-MOVE-1",
        guest_id=guest.id,
        room_id=source_room.id,
        category_id=category.id,
        check_in_date=date(2027, 1, 10),
        check_out_date=date(2027, 1, 12),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.commit()

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=9601,
            user_id=9601,
            user_email=f"{role_state['role']}@example.test",
            user_role=role_state["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    return TestClient(fastapi_app), db, engine, role_state, guest, reservation, source_room, destination_room


def _move(client: TestClient, reservation: Reservation, room: Room, reason_code: str, notes: str | None = None):
    return client.post(
        f"/api/reservations/{reservation.id}/room-move",
        json={"to_room_id": room.id, "reason_code": reason_code, "notes": notes},
    )


def test_receptionist_can_record_complaint_but_cannot_resolve_it(monkeypatch):
    client, db, engine, role_state, guest, reservation, source_room, destination_room = _client()
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    try:
        created = _move(client, reservation, destination_room, "guest_complaint", "Air conditioner was noisy")
        assert created.status_code == 200, created.text

        avoidance = db.query(GuestRoomAvoidance).one()
        event = db.query(RoomMoveEvent).one()
        assert avoidance.hotel_id == reservation.hotel_id
        assert avoidance.guest_id == reservation.guest_id
        assert avoidance.room_id == source_room.id
        assert avoidance.status is GuestRoomAvoidanceStatusEnum.ACTIVE
        assert avoidance.source_move_event_id == event.id
        assert avoidance.reason == "Air conditioner was noisy"
        assert event.reason_code == "guest_complaint"

        listed = client.get(f"/api/guests/{guest.id}/room-avoidances")
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()] == [avoidance.id]
        denied = client.post(
            f"/api/guests/{guest.id}/room-avoidances/{avoidance.id}/resolve",
            json={"resolution_note": "Attempted by reception"},
        )
        assert denied.status_code == 403

        assert _move(client, reservation, source_room, "unstructured staff text").status_code == 422

        role_state["role"] = "manager"
        resolved = client.post(
            f"/api/guests/{guest.id}/room-avoidances/{avoidance.id}/resolve",
            json={"resolution_note": "Maintenance confirmed the repair"},
        )
        assert resolved.status_code == 200, resolved.text
        db.refresh(avoidance)
        db.refresh(event)
        assert avoidance.status is GuestRoomAvoidanceStatusEnum.RESOLVED
        assert avoidance.resolution_note == "Maintenance confirmed the repair"
        assert event.reason_code == "guest_complaint"  # immutable audit record
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_second_complaint_reactivates_the_same_guest_room_row(monkeypatch):
    client, db, engine, role_state, guest, reservation, source_room, destination_room = _client()
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    try:
        first = _move(client, reservation, destination_room, "guest_complaint", "First complaint")
        assert first.status_code == 200, first.text
        avoidance = db.query(GuestRoomAvoidance).one()
        first_id = avoidance.id
        first_event_id = avoidance.source_move_event_id

        role_state["role"] = "manager"
        assert client.post(
            f"/api/guests/{guest.id}/room-avoidances/{first_id}/resolve",
            json={"resolution_note": "Resolved once"},
        ).status_code == 200
        assert _move(client, reservation, source_room, "guest_request", "Temporary return").status_code == 200
        second = _move(client, reservation, destination_room, "guest_complaint", "Second complaint")
        assert second.status_code == 200, second.text

        rows = db.query(GuestRoomAvoidance).all()
        assert len(rows) == 1
        reactivated = rows[0]
        assert reactivated.id == first_id
        assert reactivated.status is GuestRoomAvoidanceStatusEnum.ACTIVE
        assert reactivated.source_move_event_id != first_event_id
        assert reactivated.reason == "Second complaint"
        assert reactivated.resolved_by_user_id is None
        assert reactivated.resolved_at is None
        assert reactivated.resolution_note is None
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
