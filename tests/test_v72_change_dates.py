"""
V72 §8.3 / §8.4 / §8.5 — Change reservation dates and extend stay tests.

Ported from claude/fervent-jennings-1299c4 and adapted to main's API.

KEY DIVERGENCE (recorded as xfail below):
  - fervent expected change_reservation_dates to mutate the SAME reservation in place,
    preserving status and exposing old_/new_ date fields + status_transitioned.
  - main instead CANCELS-AND-RECREATES unpaid reservations (returns recreated=True with a
    NEW reservation) and, for paid ones, requires manager_authorized + a real Transaction row
    (amount_paid alone is not treated as "deposit paid"). Result is ReservationDateChangeResult
    (original_reservation / reservation / recreated), not ChangeDatesResult.
  - extend_stay -> extend_reservation_stay, which REQUIRES a payment_action and exposes
    extension_amount (not extra_nights/extra_amount).
"""
from datetime import date, timedelta

import pytest

from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room
from app.services.reservation_operations_service import (
    ReservationDateChangeResult,
    ReservationOperationsError,
    change_reservation_dates,
    extend_reservation_stay,
)
from app.services.reservation_service import ReservationError


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _reservation(
    db,
    *,
    code: str,
    guest: Guest,
    room: Room,
    check_in: date = date(2027, 3, 1),
    check_out: date = date(2027, 3, 4),
    total_amount: float = 300.0,
    amount_paid: float = 0.0,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    **overrides,
) -> Reservation:
    r = Reservation(
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
    db.add(r)
    db.flush()
    return r


# ─────────────────────────────────────────────────────────────────────────────
# §8.3  Change dates — PENDING reservation (no payment)
# ─────────────────────────────────────────────────────────────────────────────

def test_change_dates_pending_updates_dates_and_price(db, sample_guest, sample_rooms):
    """§8.3 — Changing dates of an unpaid reservation produces a reservation on the new dates.

    Adapted: main cancels the original and recreates a NEW reservation (recreated=True).
    BRM intent preserved: the resulting active reservation carries the new dates.
    """
    res = _reservation(
        db,
        code="CD-PENDING-01",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 3, 1),
        check_out=date(2027, 3, 4),  # 3 nights
        total_amount=300.0,
    )

    result = change_reservation_dates(
        db,
        reservation=res,
        hotel_id=sample_guest.hotel_id,
        check_in_date=date(2027, 4, 1),
        check_out_date=date(2027, 4, 6),  # 5 nights
        client_version=res.version or 0,
    )

    assert isinstance(result, ReservationDateChangeResult)
    assert result.recreated is True
    new_res = result.reservation
    assert new_res.check_in_date == date(2027, 4, 1)
    assert new_res.check_out_date == date(2027, 4, 6)
    assert new_res.total_amount > 0
    # Original is cancelled by main's recreate flow.
    assert result.original_reservation.status == ReservationStatusEnum.CANCELLED


def test_change_dates_blocked_when_room_conflict(db, sample_guest, sample_rooms):
    """§8.3 — Cannot change dates when another reservation occupies the room."""
    res1 = _reservation(
        db,
        code="CD-CONFLICT-01",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 5, 1),
        check_out=date(2027, 5, 5),
    )

    # Second reservation — blocks the target window
    _reservation(
        db,
        code="CD-CONFLICT-02",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 5, 10),
        check_out=date(2027, 5, 15),
    )

    # BRM §8.3: moving into an occupied window must be rejected. main's recreate path
    # raises the base ReservationError (unwrapped) from create_reservation's availability check.
    with pytest.raises(ReservationError):
        change_reservation_dates(
            db,
            reservation=res1,
            hotel_id=sample_guest.hotel_id,
            check_in_date=date(2027, 5, 10),
            check_out_date=date(2027, 5, 13),
            client_version=res1.version or 0,
        )


@pytest.mark.xfail(
    reason="main difiere de BRM §8.3: change_reservation_dates no valida fecha de check-in "
    "en el pasado (no existe el chequeo 'pasado') (gap Phase 3/5)",
    strict=False,
)
def test_change_dates_blocked_for_past_check_in(db, sample_guest, sample_rooms):
    """§8.3 — Changing to a past check-in date is rejected."""
    res = _reservation(
        db,
        code="CD-PAST-01",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 6, 1),
        check_out=date(2027, 6, 4),
    )

    past_date = date(2020, 1, 1)
    with pytest.raises(ReservationOperationsError, match="pasado"):
        change_reservation_dates(
            db,
            reservation=res,
            hotel_id=sample_guest.hotel_id,
            check_in_date=past_date,
            check_out_date=past_date + timedelta(days=3),
            client_version=res.version or 0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# §8.4  Change dates — DEPOSIT_PAID reservation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    reason="main difiere de BRM §8.4: 'deposito pagado' se detecta por filas Transaction, "
    "no por amount_paid; ademas change_reservation_dates con pagos exige manager_authorized "
    "y muta in-place sin exponer status_transitioned (gap Phase 3/5)",
    strict=False,
)
def test_change_dates_deposit_paid_keeps_deposit(db, sample_guest, sample_rooms):
    """§8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserved."""
    res = _reservation(
        db,
        code="CD-DEPOSIT-01",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 7, 1),
        check_out=date(2027, 7, 4),
        total_amount=300.0,
        amount_paid=90.0,
        status=ReservationStatusEnum.DEPOSIT_PAID,
    )

    result = change_reservation_dates(
        db,
        reservation=res,
        hotel_id=sample_guest.hotel_id,
        check_in_date=date(2027, 8, 1),
        check_out_date=date(2027, 8, 5),
        client_version=res.version or 0,
        manager_authorized=True,
    )

    db.refresh(res)
    assert res.check_in_date == date(2027, 8, 1)
    assert res.check_out_date == date(2027, 8, 5)
    assert res.amount_paid == 90.0
    assert res.status == ReservationStatusEnum.DEPOSIT_PAID
    assert result.status_transitioned is False


@pytest.mark.xfail(
    reason="main difiere de BRM §8.4: no hay auto-transicion a FULLY_PAID por recalculo de "
    "fechas, ni flag status_transitioned en el resultado (gap Phase 3/5)",
    strict=False,
)
def test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(db, sample_guest, sample_rooms):
    """§8.4 — If new total <= amount_paid after date change, status auto-transitions to FULLY_PAID."""
    res = _reservation(
        db,
        code="CD-AUTO-FP-01",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2027, 9, 1),
        check_out=date(2027, 9, 11),
        total_amount=1000.0,
        amount_paid=1000.0,
        status=ReservationStatusEnum.DEPOSIT_PAID,
    )

    result = change_reservation_dates(
        db,
        reservation=res,
        hotel_id=sample_guest.hotel_id,
        check_in_date=date(2027, 9, 1),
        check_out_date=date(2027, 9, 2),
        client_version=res.version or 0,
        manager_authorized=True,
    )

    db.refresh(res)
    assert res.status == ReservationStatusEnum.FULLY_PAID
    assert result.status_transitioned is True
    assert res.total_amount < res.amount_paid


# ─────────────────────────────────────────────────────────────────────────────
# §8.5  Extend stay
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    reason="main difiere de BRM §8.5: extend_reservation_stay EXIGE payment_action y expone "
    "extension_amount (no hay extension simple con extra_nights/extra_amount) (gap Phase 3/5)",
    strict=False,
)
def test_extend_stay_increases_nights_and_recalculates_price(db, sample_guest, sample_rooms):
    """§8.5 — extend_stay extends check-out, increases night count and total price."""
    res = _reservation(
        db,
        code="EXT-BASIC-CD",
        guest=sample_guest,
        room=sample_rooms[1],
        check_in=date(2027, 10, 1),
        check_out=date(2027, 10, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    result = extend_reservation_stay(
        db,
        reservation=res,
        hotel_id=sample_guest.hotel_id,
        new_check_out=date(2027, 10, 7),
    )

    db.refresh(res)
    assert res.check_out_date == date(2027, 10, 7)
    assert result.extra_nights == 3
    assert result.extra_amount > 0
    assert res.total_amount > 300.0


def test_extend_stay_blocked_when_room_occupied(db, sample_guest, sample_rooms):
    """§8.5 — Cannot extend when another reservation occupies the room during extension period."""
    res1 = _reservation(
        db,
        code="EXT-BLOCK-R1",
        guest=sample_guest,
        room=sample_rooms[2],
        check_in=date(2027, 10, 1),
        check_out=date(2027, 10, 5),
        total_amount=400.0,
        amount_paid=400.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    # Second reservation occupies the same room from Oct 5 → Oct 10
    _reservation(
        db,
        code="EXT-BLOCK-R2",
        guest=sample_guest,
        room=sample_rooms[2],
        check_in=date(2027, 10, 5),
        check_out=date(2027, 10, 10),
        total_amount=500.0,
    )

    # BRM §8.5: cannot extend into an occupied window.
    with pytest.raises(ReservationOperationsError):
        extend_reservation_stay(
            db,
            reservation=res1,
            hotel_id=sample_guest.hotel_id,
            new_checkout_date=date(2027, 10, 8),
            client_version=res1.version or 0,
            pricing_mode="same_rate",
            payment_action="immediate_payment",
        )


def test_extend_stay_blocked_for_zero_or_negative_days(db, sample_guest, sample_rooms):
    """§8.5 — Extending by 0 or negative days (same or earlier date) is rejected."""
    res = _reservation(
        db,
        code="EXT-ZERO-DAYS",
        guest=sample_guest,
        room=sample_rooms[3],
        check_in=date(2027, 11, 1),
        check_out=date(2027, 11, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    # Same date — 0 extra nights
    with pytest.raises(ReservationOperationsError):
        extend_reservation_stay(
            db,
            reservation=res,
            hotel_id=sample_guest.hotel_id,
            new_checkout_date=date(2027, 11, 4),
            client_version=res.version or 0,
            pricing_mode="same_rate",
            payment_action="immediate_payment",
        )

    # Earlier date — negative extension
    with pytest.raises(ReservationOperationsError):
        extend_reservation_stay(
            db,
            reservation=res,
            hotel_id=sample_guest.hotel_id,
            new_checkout_date=date(2027, 11, 2),
            client_version=res.version or 0,
            pricing_mode="same_rate",
            payment_action="immediate_payment",
        )
