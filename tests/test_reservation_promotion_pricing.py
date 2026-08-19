from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from app.models.daily_rate import DailyRate
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.promotion import PromotionConditions, PromotionCreate
from app.schemas.reservation import ReservationCreate
from app.services.promotion_service import create_promotion, deactivate_promotion, update_promotion
from app.services.reservation_service import create_reservation


def _seed_hotel(db, hotel_id: int):
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    category = RoomCategory(
        hotel_id=hotel_id, name="Standard", code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"), max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(hotel_id=hotel_id, category_id=category.id, room_number="101", status=RoomStatusEnum.AVAILABLE)
    guest = Guest(hotel_id=hotel_id, first_name="Ana", last_name="Reservante")
    db.add_all([room, guest])
    db.flush()
    for offset in range(2):
        db.add(DailyRate(hotel_id=hotel_id, category_id=category.id, date=date(2026, 6, 1 + offset), price=100.0))
    db.flush()
    return category, room, guest


def test_promotion_reduces_reservation_total_amount(db):
    category, room, guest = _seed_hotel(db, 91)
    create_promotion(
        db, hotel_id=91,
        payload=PromotionCreate(
            code="OPENING", name="Opening discount", benefit_type="percentage", benefit_value=Decimal("10"),
            conditions=PromotionConditions(category_id=category.id),
        ),
        created_by_user_id=None,
    )

    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id, category_id=category.id, room_id=room.id,
            check_in_date=date(2026, 6, 1), check_out_date=date(2026, 6, 3),
        ),
        hotel_id=91,
    )
    db.flush()

    # 2 nights * 100 - 10% each = 180.
    assert reservation.total_amount == Decimal("180.00") or float(reservation.total_amount) == 180.0
    snapshot = json.loads(reservation.pricing_snapshot)
    assert len(snapshot["promotions_applied"]) == 2


def test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation(db):
    category, room, guest = _seed_hotel(db, 92)
    promo = create_promotion(
        db, hotel_id=92,
        payload=PromotionCreate(
            code="LOCKED_IN", name="Locked in", benefit_type="fixed", benefit_value=Decimal("20"),
            conditions=PromotionConditions(category_id=category.id),
        ),
        created_by_user_id=None,
    )

    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id, category_id=category.id, room_id=room.id,
            check_in_date=date(2026, 6, 1), check_out_date=date(2026, 6, 3),
        ),
        hotel_id=92,
    )
    db.flush()
    booked_total = float(reservation.total_amount)
    booked_snapshot = reservation.pricing_snapshot
    assert booked_total == 160.0  # 2 nights * (100 - 20)

    # Edit the promotion's benefit (creates a new version) and deactivate the
    # version that was actually used at booking time.
    from app.schemas.promotion import PromotionUpdate

    update_promotion(
        db, hotel_id=92, promotion_id=promo.id,
        payload=PromotionUpdate(benefit_value=Decimal("500")),
        actor_user_id=None,
    )
    deactivate_promotion(db, hotel_id=92, promotion_id=promo.id, actor_user_id=None)
    db.flush()

    db.refresh(reservation)
    assert float(reservation.total_amount) == booked_total
    assert reservation.pricing_snapshot == booked_snapshot
