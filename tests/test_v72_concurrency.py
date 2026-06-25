"""
Tests for V72 §5 - Concurrency guards: double-booking and duplicate payments.

The source branch test was imported from
claude/fervent-jennings-1299c4:tests/test_v72_concurrency.py and adapted to
the current branch contracts:
- ReservationCreate has no is_wait_listed field.
- PaymentRequest has no is_deposit field; deposits are represented by
  transaction_type=DEPOSIT.
- SQLite tests verify the invariant after interleaved sequential calls.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest
from app.services.payment_service import PaymentError, process_payment
from app.services.reservation_service import (
    ReservationError,
    check_room_availability,
    create_reservation,
)


HOTEL_ID = 1
CHECK_IN = date(2026, 8, 1)
CHECK_OUT = date(2026, 8, 5)


@pytest.fixture()
def dual_session_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def two_sessions(dual_session_engine):
    factory = sessionmaker(autocommit=False, autoflush=False, bind=dual_session_engine)
    session_a = factory()
    session_b = factory()
    try:
        yield session_a, session_b
    finally:
        session_a.rollback()
        session_a.close()
        session_b.rollback()
        session_b.close()


def _seed_hotel(db: Session) -> HotelConfiguration:
    hotel = db.get(HotelConfiguration, HOTEL_ID)
    if hotel is None:
        hotel = HotelConfiguration(
            id=HOTEL_ID,
            deposit_percentage=30.0,
            enable_cash=True,
            enable_mercado_pago=True,
            enable_paypal=True,
            enable_credit_card=True,
            enable_debit_card=True,
            subscription_active=True,
        )
        db.add(hotel)
        db.flush()
    return hotel


def _seed_category(db: Session, *, code: str = "STD") -> RoomCategory:
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == HOTEL_ID, RoomCategory.code == code)
        .first()
    )
    if category is None:
        category = RoomCategory(
            name=f"Category {code}",
            code=code,
            base_price_per_night=100.0,
            max_occupancy=2,
            description="Test category",
            hotel_id=HOTEL_ID,
        )
        db.add(category)
        db.flush()
    return category


def _seed_room(db: Session, category: RoomCategory, *, number: str) -> Room:
    room = Room(
        room_number=number,
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        hotel_id=HOTEL_ID,
    )
    db.add(room)
    db.flush()
    return room


def _seed_guest(db: Session, *, suffix: str) -> Guest:
    guest = Guest(
        first_name=f"Guest{suffix}",
        last_name="Tester",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"9999000{suffix}",
        nationality="Argentina",
        date_of_birth=date(1990, 1, 1),
        email=f"guest{suffix}@test.com",
        phone="+541155550000",
        terms_accepted=True,
        hotel_id=HOTEL_ID,
    )
    db.add(guest)
    db.flush()
    return guest


def _make_reservation(
    db: Session,
    *,
    guest: Guest,
    category: RoomCategory,
    room: Room | None = None,
) -> Reservation:
    return create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id if room else None,
            check_in_date=CHECK_IN,
            check_out_date=CHECK_OUT,
        ),
        hotel_id=HOTEL_ID,
    )


def test_no_double_booking_same_room_same_dates(two_sessions):
    session_a, session_b = two_sessions
    _seed_hotel(session_a)
    category = _seed_category(session_a)
    room = _seed_room(session_a, category, number="101")
    guest_a = _seed_guest(session_a, suffix="A")
    guest_b = _seed_guest(session_a, suffix="B")
    session_a.commit()

    reservation_a = _make_reservation(session_a, guest=guest_a, category=category, room=room)
    session_a.commit()

    with pytest.raises(ReservationError, match="not available"):
        _make_reservation(
            session_b,
            guest=session_b.get(Guest, guest_b.id),
            category=session_b.get(RoomCategory, category.id),
            room=session_b.get(Room, room.id),
        )

    assert reservation_a.id is not None
    count = (
        session_a.query(Reservation)
        .filter(
            Reservation.room_id == room.id,
            Reservation.status.notin_(
                [ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]
            ),
        )
        .count()
    )
    assert count == 1


def test_auto_assign_no_double_booking(two_sessions):
    session_a, session_b = two_sessions
    _seed_hotel(session_a)
    category = _seed_category(session_a, code="SINGLE")
    room = _seed_room(session_a, category, number="201")
    guest_a = _seed_guest(session_a, suffix="X")
    guest_b = _seed_guest(session_a, suffix="Y")
    session_a.commit()

    reservation_a = _make_reservation(session_a, guest=guest_a, category=category)
    assert reservation_a.room_id == room.id
    session_a.commit()

    with pytest.raises(ReservationError, match="No rooms available"):
        _make_reservation(
            session_b,
            guest=session_b.get(Guest, guest_b.id),
            category=session_b.get(RoomCategory, category.id),
        )

    active = (
        session_a.query(Reservation)
        .filter(
            Reservation.room_id == room.id,
            Reservation.status.notin_(
                [ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]
            ),
        )
        .all()
    )
    assert len(active) == 1


def test_allocation_respects_existing_reservations(db):
    _seed_hotel(db)
    category = _seed_category(db, code="FILL")
    rooms = [_seed_room(db, category, number=f"F{i}") for i in range(1, 4)]
    guests = [_seed_guest(db, suffix=str(i)) for i in range(1, 5)]

    for index, room in enumerate(rooms):
        _make_reservation(db, guest=guests[index], category=category, room=room)
    db.flush()

    for room in rooms:
        assert (
            check_room_availability(db, room.id, CHECK_IN, CHECK_OUT, hotel_id=HOTEL_ID)
            is False
        )

    with pytest.raises(ReservationError, match="No rooms available"):
        _make_reservation(db, guest=guests[3], category=category)

    total = (
        db.query(Reservation)
        .filter(
            Reservation.category_id == category.id,
            Reservation.status.notin_(
                [ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]
            ),
        )
        .count()
    )
    assert total == 3


def test_allocation_overflow_can_be_waitlisted(db):
    _seed_hotel(db)
    category = _seed_category(db, code="OVF")
    room = _seed_room(db, category, number="OV1")
    guest_a = _seed_guest(db, suffix="ov1")
    guest_b = _seed_guest(db, suffix="ov2")

    _make_reservation(db, guest=guest_a, category=category, room=room)
    db.flush()

    with pytest.raises(ReservationError, match="No rooms available"):
        _make_reservation(db, guest=guest_b, category=category)

    waitlisted = Reservation(
        confirmation_code="WL-CONCURRENCY",
        hotel_id=HOTEL_ID,
        guest_id=guest_b.id,
        room_id=None,
        category_id=category.id,
        check_in_date=CHECK_IN,
        check_out_date=CHECK_OUT,
        total_amount=400.0,
        amount_paid=0.0,
        deposit_amount=120.0,
        subtotal_amount=400.0,
        tax_amount=0.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=400.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        is_wait_listed=True,
        wait_list_reason="overflow",
    )
    db.add(waitlisted)
    db.flush()

    assert waitlisted.room_id is None


def test_payment_idempotency_on_duplicate_submission(two_sessions):
    session_a, session_b = two_sessions
    _seed_hotel(session_a)
    category = _seed_category(session_a, code="PAY")
    room = _seed_room(session_a, category, number="P01")
    guest = _seed_guest(session_a, suffix="P")
    session_a.commit()

    reservation = _make_reservation(session_a, guest=guest, category=category, room=room)
    session_a.commit()
    total = float(reservation.total_amount)

    tx_a = process_payment(
        session_a,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=total,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        ),
        hotel_id=HOTEL_ID,
    )
    session_a.commit()
    assert tx_a.status == TransactionStatusEnum.COMPLETED

    with pytest.raises(PaymentError, match="exceeds balance due"):
        process_payment(
            session_b,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=total,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            ),
            hotel_id=HOTEL_ID,
        )

    session_a.expire(reservation)
    refreshed = session_a.get(Reservation, reservation.id)
    assert abs(float(refreshed.amount_paid) - total) < 0.01


def test_payment_partial_then_duplicate_partial(two_sessions):
    session_a, session_b = two_sessions
    _seed_hotel(session_a)
    category = _seed_category(session_a, code="DEP")
    room = _seed_room(session_a, category, number="D01")
    guest = _seed_guest(session_a, suffix="D")
    session_a.commit()

    reservation = _make_reservation(session_a, guest=guest, category=category, room=room)
    session_a.commit()
    deposit = float(reservation.deposit_amount)

    process_payment(
        session_a,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=deposit,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=HOTEL_ID,
    )
    session_a.commit()

    try:
        process_payment(
            session_b,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=deposit,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.DEPOSIT,
            ),
            hotel_id=HOTEL_ID,
        )
        session_b.commit()
    except PaymentError:
        session_b.rollback()

    session_a.expire(reservation)
    final = session_a.get(Reservation, reservation.id)
    assert float(final.amount_paid) <= float(final.total_amount) + 0.01
