from __future__ import annotations

from datetime import date

from app.api.daily_rates import DailyRateIn, upsert_daily_rate
from app.api.guests import update_guest
from app.api.reservations import cancel_reservation
from app.api.rooms import update_room
from app.api.users import UpdateRolePayload, update_role
from app.dependencies.auth import AuthContext
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.user import User
from app.schemas.guest import GuestUpdate
from app.schemas.room import RoomUpdate


def _hotel(db, hotel_id: int = 1) -> HotelConfiguration:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Audit Hotel {hotel_id}", subscription_active=True)
        db.add(hotel)
        db.flush()
    return hotel


def _user(db, user_id: int, *, role: str = "owner") -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            email=f"audit-coverage-{user_id}@example.com",
            password_hash="test",
            is_active=True,
            is_verified=True,
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def _context(user_id: int = 9101, *, role: str = "owner") -> AuthContext:
    return AuthContext(
        hotel_id=1,
        user_id=user_id,
        user_email=f"audit-coverage-{user_id}@example.com",
        user_role=role,
    )


def _category(db) -> RoomCategory:
    _hotel(db)
    category = RoomCategory(
        hotel_id=1,
        name="Audit Standard",
        code="AUD-STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _room(db, category: RoomCategory | None = None) -> Room:
    category = category or _category(db)
    room = Room(hotel_id=1, room_number=f"AUD-{category.id}", floor=1, category_id=category.id)
    db.add(room)
    db.flush()
    return room


def _guest(db) -> Guest:
    _hotel(db)
    guest = Guest(
        hotel_id=1,
        first_name="Audit",
        last_name="Guest",
        document_type="DNI",
        document_number="AUD-100",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _reservation(db) -> Reservation:
    category = _category(db)
    room = _room(db, category)
    guest = _guest(db)
    reservation = Reservation(
        confirmation_code="AUD-CANCEL-1",
        hotel_id=1,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 3),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _audit_for(db, *, table_name: str, record_id: int) -> AuditLog:
    return (
        db.query(AuditLog)
        .filter(AuditLog.hotel_id == 1, AuditLog.table_name == table_name, AuditLog.record_id == record_id)
        .order_by(AuditLog.id.desc())
        .first()
    )


def test_update_guest_creates_audit_log(db):
    _user(db, 9101)
    guest = _guest(db)

    result = update_guest(guest.id, GuestUpdate(last_name="Updated"), db=db, context=_context())

    audit = _audit_for(db, table_name="guests", record_id=result.id)
    assert audit is not None
    assert audit.table_name == "guests"
    assert audit.action == AuditActionEnum.UPDATE
    assert audit.actor_user_id == 9101
    assert audit.payload_before is not None
    assert audit.payload_after is not None


def test_reservation_cancel_creates_audit_log(db):
    _user(db, 9101)
    reservation = _reservation(db)

    result = cancel_reservation(reservation.id, db=db, context=_context())

    audit = _audit_for(db, table_name="reservations", record_id=result.id)
    assert audit is not None
    assert audit.table_name == "reservations"
    assert audit.action == AuditActionEnum.STATUS_CHANGE


def test_room_update_creates_audit_log(db):
    _user(db, 9101)
    room = _room(db)

    result = update_room(room.id, RoomUpdate(notes="Fresh paint"), db=db, context=_context(role="manager"))

    audit = _audit_for(db, table_name="rooms", record_id=result.id)
    assert audit is not None
    assert audit.table_name == "rooms"
    assert audit.action == AuditActionEnum.UPDATE


def test_daily_rate_upsert_creates_audit_log(db):
    _user(db, 9101)
    category = _category(db)

    result = upsert_daily_rate(
        category.id,
        DailyRateIn(date=date(2026, 10, 1), price=150),
        db=db,
        context=_context(role="manager"),
    )

    audit = _audit_for(db, table_name="daily_rates", record_id=result.id)
    assert audit is not None
    assert audit.table_name == "daily_rates"
    assert audit.action == AuditActionEnum.CREATE


def test_user_role_update_creates_audit_log(db):
    _hotel(db)
    _user(db, 9101, role="owner")
    target = _user(db, 9102, role="manager")
    membership = HotelMembership(hotel_id=1, user_id=target.id, role="manager", status="active")
    db.add(membership)
    db.flush()

    update_role(target.id, UpdateRolePayload(role="housekeeping"), db=db, context=_context())

    audit = _audit_for(db, table_name="hotel_memberships", record_id=membership.id)
    assert audit is not None
    assert audit.table_name == "hotel_memberships"
    assert audit.action == AuditActionEnum.UPDATE


def test_update_guest_succeeds_when_audit_write_fails(db, monkeypatch):
    _user(db, 9101)
    guest = _guest(db)

    def raise_audit(*args, **kwargs):
        raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", raise_audit)

    update_guest(guest.id, GuestUpdate(last_name="Still Saved"), db=db, context=_context())

    assert db.get(Guest, guest.id).last_name == "Still Saved"


def test_reservation_cancel_succeeds_when_audit_write_fails(db, monkeypatch):
    _user(db, 9101)
    reservation = _reservation(db)

    def raise_audit(*args, **kwargs):
        raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", raise_audit)

    cancel_reservation(reservation.id, db=db, context=_context())

    assert db.get(Reservation, reservation.id).status == ReservationStatusEnum.CANCELLED


def test_room_update_succeeds_when_audit_write_fails(db, monkeypatch):
    _user(db, 9101)
    room = _room(db)

    def raise_audit(*args, **kwargs):
        raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", raise_audit)

    update_room(room.id, RoomUpdate(notes="Saved without audit"), db=db, context=_context(role="manager"))

    assert db.get(Room, room.id).notes == "Saved without audit"


def test_daily_rate_upsert_succeeds_when_audit_write_fails(db, monkeypatch):
    _user(db, 9101)
    category = _category(db)

    def raise_audit(*args, **kwargs):
        raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", raise_audit)

    result = upsert_daily_rate(
        category.id,
        DailyRateIn(date=date(2026, 10, 2), price=175),
        db=db,
        context=_context(role="manager"),
    )

    assert result.id is not None


def test_user_role_update_succeeds_when_audit_write_fails(db, monkeypatch):
    _hotel(db)
    _user(db, 9101, role="owner")
    target = _user(db, 9102, role="manager")
    db.add(HotelMembership(hotel_id=1, user_id=target.id, role="manager", status="active"))
    db.flush()

    def raise_audit(*args, **kwargs):
        raise RuntimeError("audit sink unavailable")

    monkeypatch.setattr("app.services.audit_log_service.create_audit_log", raise_audit)

    update_role(target.id, UpdateRolePayload(role="housekeeping"), db=db, context=_context())

    membership = db.query(HotelMembership).filter_by(hotel_id=1, user_id=target.id).one()
    assert membership.role == "housekeeping"
