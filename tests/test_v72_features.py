"""V72 feature tests ported from claude/fervent-jennings-1299c4 and adapted to main's API.

Adaptation notes (fervent API -> main API):
  - GuestAlert model -> GuestTag (app.models.guest), "active" = expires_at is NULL/future.
  - add_guest_alert/deactivate_guest_alert/set_guest_rating -> add_tag/resolve_tag/set_rating.
  - get_guest_summary -> quick_profile (different dict shape).
  - extend_stay -> extend_reservation_stay (main REQUIRES payment action).
  - prohibido-alojar override: reservation.is_prohibited_override field -> perform_checkin(override_prohibido=).
  - manual-move "motor protection" -> reservation.allocation_locked.

xfail tests below flag REAL gaps where main diverges from the BRM the fervent suite encoded.
"""

from datetime import date

import pytest

from app.models.guest import (
    DocumentTypeEnum,
    Guest,
    GuestRatingEnum,
    GuestTag,
    GuestTagTypeEnum,
)
from app.models.operations import RoomMoveTypeEnum
from app.models.reservation import (
    Reservation,
    ReservationStatusEnum,
    ReservationSourceEnum,
)
from app.models.room import Room, RoomStatusEnum
from app.services.allocation_engine import (
    ReservationSlot,
    RoomSlot,
    _run_allocation_greedy,
)
from app.services.checkin_service import CheckInError, perform_checkin
from app.services.guest_service import (
    add_tag,
    list_active_tags,
    quick_profile,
    resolve_tag,
    set_rating,
)
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    extend_reservation_stay,
    move_reservation_room,
)


def _reservation(
    db,
    *,
    code: str,
    guest: Guest,
    room: Room,
    check_in: date = date(2026, 9, 1),
    check_out: date = date(2026, 9, 4),
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
        num_adults=1,
        num_children=0,
        **overrides,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_guest_rating_set_and_retrieve(db, sample_guest):
    result = set_rating(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        rating=GuestRatingEnum.EXCELENTE,
    )

    db.refresh(sample_guest)
    assert result.id == sample_guest.id
    assert sample_guest.rating == GuestRatingEnum.EXCELENTE


def test_guest_alert_add_prohibido_alojar(db, sample_guest):
    alert = add_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Bloqueado por administracion",
    )

    db.refresh(sample_guest)
    # BRM: an active prohibido_alojar alert exists for the guest.
    assert isinstance(alert, GuestTag)
    assert alert.tag_type == GuestTagTypeEnum.PROHIBIDO_ALOJAR
    assert alert.note == "Bloqueado por administracion"
    active = list_active_tags(db, hotel_id=sample_guest.hotel_id, guest_id=sample_guest.id)
    assert any(t.tag_type == GuestTagTypeEnum.PROHIBIDO_ALOJAR for t in active)


def test_guest_alert_deactivate_clears_prohibited_flag(db, sample_guest):
    alert = add_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Bloqueado por administracion",
    )

    resolve_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_id=alert.id,
    )

    db.refresh(sample_guest)
    # BRM: after deactivation the alert is no longer active.
    active = list_active_tags(db, hotel_id=sample_guest.hotel_id, guest_id=sample_guest.id)
    assert all(t.id != alert.id for t in active)


def test_checkin_blocked_by_prohibido_alojar(db, sample_guest, sample_rooms):
    add_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Bloqueado por administracion",
    )
    reservation = _reservation(
        db,
        code="V72-CHECKIN-BLOCKED-ALERT",
        guest=sample_guest,
        room=sample_rooms[0],
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    # BRM §2.7: prohibido_alojar blocks check-in (main message is English).
    with pytest.raises(CheckInError, match="prohibido_alojar"):
        perform_checkin(db, reservation.id, hotel_id=sample_guest.hotel_id)


def test_checkin_allowed_with_prohibited_override(db, sample_guest, sample_rooms):
    add_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Bloqueado por administracion",
    )
    reservation = _reservation(
        db,
        code="V72-CHECKIN-OVERRIDE",
        guest=sample_guest,
        room=sample_rooms[0],
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    # BRM §2.7: an authorized override allows check-in despite the alert.
    result = perform_checkin(
        db,
        reservation.id,
        hotel_id=sample_guest.hotel_id,
        override_prohibido=True,
        override_user_id=10,
    )
    assert result.status == ReservationStatusEnum.CHECKED_IN


@pytest.mark.xfail(
    reason="main difiere de BRM: bloqueo prohibido se modela via GuestTag, "
    "no existe el campo guest.is_prohibited_stay (gap Phase 3/5)",
    strict=False,
)
def test_checkin_blocked_by_is_prohibited_stay_flag(db, sample_guest, sample_rooms):
    sample_guest.is_prohibited_stay = True
    reservation = _reservation(
        db,
        code="V72-CHECKIN-BLOCKED-FLAG",
        guest=sample_guest,
        room=sample_rooms[0],
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    with pytest.raises(CheckInError, match="Prohibido alojar"):
        perform_checkin(db, reservation.id, hotel_id=sample_guest.hotel_id)


def test_room_score_field(db, hotel_config, sample_categories):
    room = Room(
        hotel_id=hotel_config.id,
        room_number="V72-801",
        floor=8,
        category_id=sample_categories[0].id,
        status=RoomStatusEnum.AVAILABLE,
        score=8,
    )
    db.add(room)
    db.flush()
    db.refresh(room)

    assert room.score == 8


def test_room_is_accessible_default_false(db, hotel_config, sample_categories):
    room = Room(
        hotel_id=hotel_config.id,
        room_number="V72-802",
        floor=8,
        category_id=sample_categories[0].id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    db.refresh(room)

    assert room.is_accessible is False


def test_reservation_mobility_restriction_field(db, sample_guest, sample_rooms):
    reservation = _reservation(
        db,
        code="V72-MOBILITY",
        guest=sample_guest,
        room=sample_rooms[0],
        mobility_restriction=True,
    )

    db.refresh(reservation)
    assert reservation.mobility_restriction is True


def test_reservation_is_motor_protected_set_on_manual_move(db, sample_guest, sample_rooms):
    reservation = _reservation(db, code="V72-MANUAL-MOVE", guest=sample_guest, room=sample_rooms[0])

    move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=sample_rooms[1].id,
        hotel_id=sample_guest.hotel_id,
        move_type=RoomMoveTypeEnum.MANUAL_MOVE,
        reason_code="guest_request",
    )

    db.refresh(reservation)
    # BRM §8: a MANUAL move protects the reservation from motor re-optimization.
    # main expresses this as allocation_locked (renamed from is_motor_protected).
    assert reservation.allocation_locked is True


@pytest.mark.xfail(
    reason="main difiere de BRM §9: no existen los campos reservation.is_wait_listed / "
    "wait_list_reason (waitlist se modela en tabla waitlist aparte) (gap Phase 3/5)",
    strict=False,
)
def test_reservation_is_wait_listed_field(db, sample_guest, sample_rooms):
    reservation = _reservation(
        db,
        code="V72-WAITLIST",
        guest=sample_guest,
        room=sample_rooms[0],
        is_wait_listed=True,
        wait_list_reason="Sin disponibilidad inmediata",
    )

    db.refresh(reservation)
    assert reservation.is_wait_listed is True
    assert reservation.wait_list_reason == "Sin disponibilidad inmediata"


@pytest.mark.xfail(
    reason="main difiere de BRM §2: no existe find_or_create_guest / GuestCreatePayload "
    "(dedup de huesped por documento no implementado) (gap Phase 3/5)",
    strict=False,
)
def test_guest_dedup_find_existing(db, hotel_config):
    from app.services.guest_service import GuestCreatePayload, find_or_create_guest

    payload = GuestCreatePayload(
        hotel_id=hotel_config.id,
        first_name="Ana",
        last_name="Sosa",
        document_type=DocumentTypeEnum.DNI.value,
        document_number="11222333",
    )

    guest_a, created_a = find_or_create_guest(db, payload)
    guest_b, created_b = find_or_create_guest(db, payload)

    assert created_a is True
    assert created_b is False
    assert guest_b.id == guest_a.id


@pytest.mark.xfail(
    reason="main difiere de BRM §2: no existe find_or_create_guest / GuestCreatePayload "
    "(dedup de huesped por documento no implementado) (gap Phase 3/5)",
    strict=False,
)
def test_guest_dedup_creates_new_if_no_document(db, hotel_config):
    from app.services.guest_service import GuestCreatePayload, find_or_create_guest

    payload = GuestCreatePayload(
        hotel_id=hotel_config.id,
        first_name="Sin",
        last_name="Documento",
    )

    guest_a, created_a = find_or_create_guest(db, payload)
    guest_b, created_b = find_or_create_guest(db, payload)

    assert created_a is True
    assert created_b is True
    assert guest_b.id != guest_a.id


@pytest.mark.xfail(
    reason="main difiere de BRM §2: no existe find_or_create_guest / GuestCreatePayload "
    "(dedup de huesped por documento no implementado) (gap Phase 3/5)",
    strict=False,
)
def test_guest_dedup_creates_new_for_different_document(db, hotel_config):
    from app.services.guest_service import GuestCreatePayload, find_or_create_guest

    guest_a, _ = find_or_create_guest(
        db,
        GuestCreatePayload(
            hotel_id=hotel_config.id,
            first_name="Laura",
            last_name="Mendez",
            document_type=DocumentTypeEnum.DNI.value,
            document_number="44555666",
        ),
    )
    guest_b, created_b = find_or_create_guest(
        db,
        GuestCreatePayload(
            hotel_id=hotel_config.id,
            first_name="Laura",
            last_name="Mendez",
            document_type=DocumentTypeEnum.DNI.value,
            document_number="44555667",
        ),
    )

    assert created_b is True
    assert guest_b.id != guest_a.id


@pytest.mark.xfail(
    reason="main difiere de BRM §8.4: extend_reservation_stay EXIGE accion de pago "
    "(no hay extension 'basica' sin pago) y el resultado expone extension_amount, "
    "no extra_nights/extra_amount (gap Phase 3/5)",
    strict=False,
)
def test_extend_stay_basic(db, sample_guest, sample_rooms):
    reservation = _reservation(
        db,
        code="V72-EXTEND",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=sample_guest.hotel_id,
        new_check_out=date(2026, 10, 6),
    )

    db.refresh(reservation)
    assert reservation.check_out_date == date(2026, 10, 6)
    assert reservation.total_amount == 500.0
    assert result.extra_nights == 2
    assert result.extra_amount == 200.0


def test_extend_stay_fails_on_cancelled(db, sample_guest, sample_rooms):
    reservation = _reservation(
        db,
        code="V72-EXTEND-CANCELLED",
        guest=sample_guest,
        room=sample_rooms[0],
        status=ReservationStatusEnum.CANCELLED,
    )

    # BRM §8.4: cannot extend a cancelled reservation.
    with pytest.raises(ReservationOperationsError):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=sample_guest.hotel_id,
            new_checkout_date=date(2026, 9, 6),
            client_version=reservation.version or 0,
            pricing_mode="same_rate",
            payment_action="immediate_payment",
        )


def test_extend_stay_fails_if_new_date_not_later(db, sample_guest, sample_rooms):
    reservation = _reservation(
        db,
        code="V72-EXTEND-SAME-DATE",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 4),
        total_amount=300.0,
        amount_paid=300.0,
        status=ReservationStatusEnum.FULLY_PAID,
    )

    # BRM §8.4: new checkout must be strictly later than current checkout.
    with pytest.raises(ReservationOperationsError):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=sample_guest.hotel_id,
            new_checkout_date=date(2026, 11, 4),
            client_version=reservation.version or 0,
            pricing_mode="same_rate",
            payment_action="immediate_payment",
        )


def test_allocation_mobility_restriction_prefers_lower_floor():
    reservation = ReservationSlot(
        reservation_id=1,
        category_id=10,
        check_in=date(2026, 12, 1),
        check_out=date(2026, 12, 3),
        current_room_id=None,
        is_locked=False,
        mobility_restriction=True,
    )
    # main adds a hard accessibility constraint for mobility_restriction; mark rooms
    # accessible so the BRM low-floor *preference* (floor tiebreaker) is what's tested.
    rooms = [
        RoomSlot(room_id=301, room_number="301", category_id=10, floor=3, score=9, is_accessible=True),
        RoomSlot(room_id=101, room_number="101", category_id=10, floor=1, score=5, is_accessible=True),
        RoomSlot(room_id=201, room_number="201", category_id=10, floor=2, score=7, is_accessible=True),
    ]

    result = _run_allocation_greedy([reservation], rooms)
    assert result.success is True
    assert result.assignments[1] == 101


def test_allocation_no_mobility_uses_score():
    reservation = ReservationSlot(
        reservation_id=1,
        category_id=10,
        check_in=date(2026, 12, 4),
        check_out=date(2026, 12, 6),
        current_room_id=None,
        is_locked=False,
        mobility_restriction=False,
    )
    rooms = [
        RoomSlot(room_id=301, room_number="301", category_id=10, floor=3, score=9),
        RoomSlot(room_id=101, room_number="101", category_id=10, floor=1, score=5),
    ]

    result = _run_allocation_greedy([reservation], rooms)
    assert result.success is True
    assert result.assignments[1] == 301


def test_get_guest_summary_includes_alerts_and_stays(db, sample_guest, sample_rooms):
    alert = add_tag(
        db,
        hotel_id=sample_guest.hotel_id,
        guest_id=sample_guest.id,
        tag_type=GuestTagTypeEnum.REQUIERE_DEPOSITO,
        note="Historial de reserva",
    )
    reservation = _reservation(
        db,
        code="V72-SUMMARY-STAY",
        guest=sample_guest,
        room=sample_rooms[0],
        check_in=date(2026, 8, 1),
        check_out=date(2026, 8, 2),
        status=ReservationStatusEnum.CHECKED_OUT,
    )

    # main API: quick_profile returns guest + active_tags + last_stays.
    summary = quick_profile(db, hotel_id=sample_guest.hotel_id, guest_id=sample_guest.id)

    # BRM: summary surfaces the guest, active alerts, and recent stays.
    assert summary["guest"].id == sample_guest.id
    active_tag_ids = [t.id for t in summary["active_tags"]]
    assert alert.id in active_tag_ids
    assert summary["last_stays"][0]["reservation_id"] == reservation.id
    assert summary["last_stays"][0]["room_id"] == sample_rooms[0].id
