from __future__ import annotations

from datetime import date

import pytest

from app.models.guest import Guest
from app.models.operations import RoomMoveEvent, RoomMoveTypeEnum, RoomMovementGroup
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.transaction import PaymentRequest
from app.services.reservation_operations_service import extend_reservation_stay
from app.services.cash_register_service import open_session


@pytest.fixture(autouse=True)
def opened_cash_register(db, sample_guest):
    """Immediate cash settlement scenarios require an operator-opened caja."""
    open_session(db, hotel_id=sample_guest.hotel_id, opened_by_user_id=None, opening_balance=0)


def _reservation(
    db,
    *,
    code: str,
    guest: Guest,
    room: Room,
    check_in: date,
    check_out: date,
    total_amount: float = 300.0,
    amount_paid: float = 0.0,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    **overrides,
) -> Reservation:
    reservation = Reservation(
        confirmation_code=code,
        hotel_id=guest.hotel_id,
        guest_id=guest.id,
        room_id=room.id,
        category_id=room.category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=total_amount,
        subtotal_amount=total_amount,
        net_amount=total_amount,
        amount_paid=amount_paid,
        deposit_amount=0.0,
        currency_code="ARS",
        status=status,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
        **overrides,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _payment(reservation: Reservation, amount: float = 200.0) -> PaymentRequest:
    return PaymentRequest(
        reservation_id=reservation.id,
        amount=amount,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
        currency="ARS",
    )


def test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(db, sample_guest, sample_rooms):
    current = _reservation(
        db,
        code="EXT-CONF-EQ-CURRENT",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 10, 1),
        check_out=date(2027, 10, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )
    future = _reservation(
        db,
        code="EXT-CONF-EQ-FUTURE",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 10, 4),
        check_out=date(2027, 10, 7),
    )

    result = extend_reservation_stay(
        db,
        reservation=current,
        hotel_id=sample_guest.hotel_id,
        new_checkout_date=date(2027, 10, 6),
        client_version=current.version or 0,
        pricing_mode="original_average",
        payment_action="immediate_payment",
        immediate_payment=_payment(current),
    )

    assert result.success is True
    assert current.check_out_date == date(2027, 10, 6)
    assert future.room_id != sample_rooms[0].id
    assert future.category_id == sample_rooms[0].category_id
    group = db.query(RoomMovementGroup).filter_by(trigger_reason="extension_conflict").one()
    event = db.query(RoomMoveEvent).filter_by(movement_group_id=group.id).one()
    assert event.reservation_id == future.id
    assert event.move_type == RoomMoveTypeEnum.AUTO_ASSIGNMENT
    assert event.reason_code == "extension_conflict_equivalent"


def test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(db, sample_guest, sample_rooms):
    current = _reservation(
        db,
        code="EXT-CONF-UP-CURRENT",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 11, 1),
        check_out=date(2027, 11, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )
    future = _reservation(
        db,
        code="EXT-CONF-UP-FUTURE",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 11, 4),
        check_out=date(2027, 11, 7),
    )
    for index, room in enumerate(sample_rooms[1:20], start=1):
        _reservation(
            db,
            code=f"EXT-CONF-UP-BLOCK-{index:02d}",
            guest=sample_guest,
            room=room,
            check_in=date(2027, 11, 4),
            check_out=date(2027, 11, 7),
        )

    result = extend_reservation_stay(
        db,
        reservation=current,
        hotel_id=sample_guest.hotel_id,
        new_checkout_date=date(2027, 11, 6),
        client_version=current.version or 0,
        pricing_mode="original_average",
        payment_action="immediate_payment",
        immediate_payment=_payment(current),
    )

    assert result.success is True
    assert current.check_out_date == date(2027, 11, 6)
    assert future.room_id in {room.id for room in sample_rooms[20:35]}
    assert future.category_id == sample_rooms[20].category_id
    group = db.query(RoomMovementGroup).filter_by(trigger_reason="extension_conflict").one()
    event = db.query(RoomMoveEvent).filter_by(movement_group_id=group.id).one()
    assert event.move_type == RoomMoveTypeEnum.UPGRADE
    assert event.reason_code == "extension_conflict_upgrade"
    assert "superior" in (event.reason_note or "")


def test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(db, sample_guest, sample_rooms):
    current = _reservation(
        db,
        code="EXT-CONF-PAID-CURRENT",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 12, 1),
        check_out=date(2027, 12, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )
    future = _reservation(
        db,
        code="EXT-CONF-PAID-FUTURE",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 12, 4),
        check_out=date(2027, 12, 7),
        total_amount=300.0,
        amount_paid=100.0,
        status=ReservationStatusEnum.DEPOSIT_PAID,
    )

    result = extend_reservation_stay(
        db,
        reservation=current,
        hotel_id=sample_guest.hotel_id,
        new_checkout_date=date(2027, 12, 6),
        client_version=current.version or 0,
        pricing_mode="original_average",
        payment_action="immediate_payment",
    )

    assert result.success is False
    assert current.check_out_date == date(2027, 12, 4)
    assert future.room_id == sample_rooms[0].id
    assert result.conflicts
    assert result.conflicts[0]["reservation_id"] == future.id
    assert result.conflicts[0]["reason"] == "future_reservation_has_payment_or_deposit"
    assert db.query(RoomMovementGroup).count() == 0


def test_no_future_conflict_extends_normally(db, sample_guest, sample_rooms):
    current = _reservation(
        db,
        code="EXT-CONF-NONE-CURRENT",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2028, 1, 1),
        check_out=date(2028, 1, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    result = extend_reservation_stay(
        db,
        reservation=current,
        hotel_id=sample_guest.hotel_id,
        new_checkout_date=date(2028, 1, 6),
        client_version=current.version or 0,
        pricing_mode="original_average",
        payment_action="immediate_payment",
        immediate_payment=_payment(current),
    )

    assert result.success is True
    assert result.conflicts is None
    assert current.check_out_date == date(2028, 1, 6)
    assert float(result.extension_amount) == pytest.approx(200.0)
    assert db.query(RoomMovementGroup).count() == 0
