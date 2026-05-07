from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.analytics import RoomStateEvent, RoomStateEventReasonCodeEnum, RoomStateEventTypeEnum
from app.models.commercial import RatePlan, RatePlanPrice, SellableProduct
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTAInventoryRule, OTAPriceRule, OTAProvider, OTARatePlanMapping, OTARoomMapping
from app.models.reservation import Reservation, ReservationChannelCodeEnum, ReservationGuestSegmentEnum, ReservationGuestSegmentSourceEnum, ReservationOutcomeEnum, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.rate_calendar_service import get_daily_calendar


def _ensure_hotel(db, hotel_id: int = 1, currency: str = "ARS") -> HotelConfiguration:
    config = db.get(HotelConfiguration, hotel_id)
    if config is None:
        config = HotelConfiguration(id=hotel_id, subscription_active=True, default_currency=currency)
        db.add(config)
        db.flush()
    else:
        config.default_currency = currency
        db.flush()
    return config


def _seed_user_and_guest(db, hotel_id: int = 1) -> tuple[User, Guest]:
    user = User(email=f"owner-{hotel_id}@test.com", password_hash="x", role="owner", is_verified=True, is_active=True)
    guest = Guest(first_name="Test", last_name="Guest", email=f"guest-{hotel_id}@test.com", hotel_id=hotel_id)
    db.add_all([user, guest])
    db.flush()
    return user, guest


def _seed_category(db, hotel_id: int = 1, *, code: str = "STD", name: str = "Standard") -> RoomCategory:
    _ensure_hotel(db, hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=name,
        code=code,
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _seed_rooms(db, category: RoomCategory, total: int) -> list[Room]:
    rooms: list[Room] = []
    for index in range(total):
        room = Room(
            hotel_id=category.hotel_id,
            room_number=f"{category.code}-{index + 1}",
            floor=1,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
        rooms.append(room)
    db.add_all(rooms)
    db.flush()
    return rooms


def _seed_rate_plan(db, category: RoomCategory, *, code: str = "FLEX", name: str = "Flexible") -> tuple[SellableProduct, RatePlan]:
    product = SellableProduct(
        hotel_id=category.hotel_id,
        primary_room_category_id=category.id,
        code=f"{category.code}_PROD_{code}",
        name=f"{name} Product",
        min_occupancy=1,
        max_occupancy=2,
        is_active=True,
    )
    db.add(product)
    db.flush()

    plan = RatePlan(
        hotel_id=category.hotel_id,
        sellable_product_id=product.id,
        code=code,
        name=name,
        currency_code="ARS",
        is_active=True,
    )
    db.add(plan)
    db.flush()
    return product, plan


def _seed_reservation(
    db,
    *,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int,
    check_in: date,
    check_out: date,
    code: str,
) -> Reservation:
    reservation = Reservation(
        confirmation_code=code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=0.0,
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _seed_provider(db, code: str, name: str) -> OTAProvider:
    provider = OTAProvider(code=code, name=name, auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    return provider


def test_zero_rooms_returns_closed_days_and_expected_missing_mapping(db):
    category = _seed_category(db)

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 2),
    )

    assert result["meta"]["total_rooms"] == 0
    assert len(result["days"]) == 2
    for day in result["days"]:
        assert day["status"] == "closed"
        assert day["total_rooms"] == 0
        assert day["reserved"] == 0
        assert day["blocked"] == 0
        assert day["for_sale"] == 0
        assert day["occupancy_pct"] == 0
        assert [channel["provider_code"] for channel in day["channels"]] == ["direct", "booking", "expedia"]
        assert day["channels"][0]["missing_mapping"] is False
        assert day["channels"][1]["missing_mapping"] is True
        assert day["channels"][2]["missing_mapping"] is True


def test_no_reservations_keeps_days_open(db):
    category = _seed_category(db)
    _seed_rooms(db, category, 5)

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 6, 10),
        date_to=date(2026, 6, 12),
    )

    assert [day["status"] for day in result["days"]] == ["open", "open", "open"]
    assert all(day["for_sale"] == 5 for day in result["days"])
    assert all(day["occupancy_pct"] == 0 for day in result["days"])


def test_active_reservations_reduce_inventory_for_one_day(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 5)
    _user, guest = _seed_user_and_guest(db, category.hotel_id)
    target_date = date(2026, 7, 2)
    for index in range(4):
        _seed_reservation(
            db,
            hotel_id=category.hotel_id,
            guest_id=guest.id,
            category_id=category.id,
            room_id=rooms[index].id,
            check_in=target_date,
            check_out=target_date + timedelta(days=1),
            code=f"RES-{index}",
        )

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=target_date,
        date_to=target_date,
    )

    day = result["days"][0]
    assert day["reserved"] == 4
    assert day["blocked"] == 0
    assert day["for_sale"] == 1
    assert day["occupancy_pct"] == 80
    assert day["status"] == "open"


def test_room_state_event_blocks_room_for_spanned_days(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 5)
    user, _guest = _seed_user_and_guest(db, category.hotel_id)
    db.add(
        RoomStateEvent(
            hotel_id=category.hotel_id,
            room_id=rooms[0].id,
            event_type=RoomStateEventTypeEnum.MAINTENANCE,
            reason_code=RoomStateEventReasonCodeEnum.INSPECTION,
            started_at=datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc),
            created_by_user_id=user.id,
        )
    )
    db.flush()

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 8, 10),
        date_to=date(2026, 8, 11),
    )

    assert [day["blocked"] for day in result["days"]] == [1, 1]
    assert [day["for_sale"] for day in result["days"]] == [4, 4]


def test_direct_channel_uses_rate_plan_price(db):
    category = _seed_category(db)
    _seed_rooms(db, category, 2)
    _, rate_plan = _seed_rate_plan(db, category)
    db.add(
        RatePlanPrice(
            hotel_id=category.hotel_id,
            rate_plan_id=rate_plan.id,
            sales_channel_code=None,
            occupancy=2,
            currency_code="ARS",
            base_amount=12345.0,
            valid_from=date(2026, 9, 1),
            valid_to=date(2026, 9, 30),
            is_active=True,
        )
    )
    db.flush()

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 10),
    )

    prices = result["days"][0]["channels"][0]["prices"]
    assert len(prices) == 1
    assert prices[0]["rate_plan_id"] == rate_plan.id
    assert prices[0]["base_amount"] == 12345.0


def test_booking_channel_prefers_ota_price_rule_when_mapped(db):
    category = _seed_category(db)
    _seed_rooms(db, category, 2)
    product, rate_plan = _seed_rate_plan(db, category)
    provider = _seed_provider(db, "booking", "Booking.com")
    db.add(
        OTARoomMapping(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            sellable_product_id=product.id,
            room_category_id=category.id,
            external_room_type_id="booking-room",
            is_active=True,
        )
    )
    db.add(
        OTARatePlanMapping(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            external_rate_plan_id="booking-plan",
            is_active=True,
        )
    )
    db.add(
        OTAPriceRule(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            stay_date=date(2026, 10, 5),
            occupancy=2,
            currency_code="ARS",
            gross_amount=22222.0,
        )
    )
    db.flush()

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 10, 5),
        date_to=date(2026, 10, 5),
    )

    booking = result["days"][0]["channels"][1]
    assert booking["missing_mapping"] is False
    assert booking["prices"][0]["rate_plan_id"] == rate_plan.id
    assert booking["prices"][0]["base_amount"] == 22222.0


def test_expedia_without_rate_plan_mapping_reports_missing_mapping(db):
    category = _seed_category(db)
    _seed_rooms(db, category, 2)
    product, rate_plan = _seed_rate_plan(db, category)
    provider = _seed_provider(db, "expedia", "Expedia")
    db.add(
        OTARoomMapping(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            sellable_product_id=product.id,
            room_category_id=category.id,
            external_room_type_id="expedia-room",
            is_active=True,
        )
    )
    db.add(
        RatePlanPrice(
            hotel_id=category.hotel_id,
            rate_plan_id=rate_plan.id,
            currency_code="ARS",
            base_amount=9999.0,
            is_active=True,
        )
    )
    db.flush()

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 11, 1),
        date_to=date(2026, 11, 1),
    )

    expedia = result["days"][0]["channels"][2]
    assert expedia["missing_mapping"] is True
    assert expedia["prices"] == []


def test_service_rejects_ranges_longer_than_366_days(db):
    category = _seed_category(db)

    with pytest.raises(ValueError, match="366"):
        get_daily_calendar(
            db,
            hotel_id=category.hotel_id,
            category_id=category.id,
            date_from=date(2026, 1, 1),
            date_to=date(2027, 1, 3),
        )


def test_booking_restrictions_reflect_inventory_rules(db):
    category = _seed_category(db)
    _seed_rooms(db, category, 2)
    product, rate_plan = _seed_rate_plan(db, category)
    provider = _seed_provider(db, "booking", "Booking.com")
    db.add(
        OTARoomMapping(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            sellable_product_id=product.id,
            room_category_id=category.id,
            external_room_type_id="booking-room",
            is_active=True,
        )
    )
    db.add(
        OTARatePlanMapping(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            external_rate_plan_id="booking-plan",
            is_active=True,
        )
    )
    db.add(
        OTAInventoryRule(
            hotel_id=category.hotel_id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            stay_date=date(2026, 12, 24),
            closed_to_arrival=True,
            min_stay=3,
            allotment=2,
        )
    )
    db.flush()

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=date(2026, 12, 24),
        date_to=date(2026, 12, 24),
    )

    restrictions = result["days"][0]["channels"][1]["restrictions"]
    assert restrictions["closed_to_arrival"] is True
    assert restrictions["min_stay"] == 3
    assert restrictions["allotment"] == 2
