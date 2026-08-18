from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.promotion import Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum
from app.models.room import RoomCategory
from app.schemas.promotion import PromotionConditions, PromotionCreate, PromotionUpdate
from app.services.promotion_service import (
    PromotionError,
    PromotionMatchContext,
    apply_promotions_to_night,
    create_promotion,
    deactivate_promotion,
    find_applicable_promotions,
    get_promotion,
    list_promotions,
    reactivate_promotion,
    update_promotion,
)


def _seed_hotel(db, hotel_id: int) -> RoomCategory:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _ctx(hotel_id: int, night_date: date, **overrides) -> PromotionMatchContext:
    base = dict(
        hotel_id=hotel_id,
        night_date=night_date,
        night_index=1,
        nights_total=1,
        booking_date=date(2026, 1, 1),
    )
    base.update(overrides)
    return PromotionMatchContext(**base)


def test_create_promotion_rejects_percentage_over_100(db):
    _seed_hotel(db, 61)
    with pytest.raises(ValueError):
        PromotionCreate(
            code="TOO_BIG",
            name="Too big",
            benefit_type=PromotionBenefitTypeEnum.PERCENTAGE,
            benefit_value=Decimal("150"),
        )


def test_create_promotion_requires_from_night_number_for_scoped_promos(db):
    with pytest.raises(ValueError):
        PromotionCreate(
            code="FROM_N",
            name="From night",
            benefit_type=PromotionBenefitTypeEnum.FIXED,
            benefit_value=Decimal("10"),
            scope=PromotionScopeEnum.FROM_NIGHT_N,
        )


def test_create_promotion_rejects_duplicate_code(db):
    _seed_hotel(db, 62)
    payload = PromotionCreate(
        code="SUMMER",
        name="Summer",
        benefit_type=PromotionBenefitTypeEnum.PERCENTAGE,
        benefit_value=Decimal("10"),
    )
    create_promotion(db, hotel_id=62, payload=payload, created_by_user_id=None)
    with pytest.raises(PromotionError):
        create_promotion(db, hotel_id=62, payload=payload, created_by_user_id=None)


def test_find_applicable_promotions_matches_typed_conditions(db):
    category = _seed_hotel(db, 63)
    payload = PromotionCreate(
        code="CAT_ONLY",
        name="Category only",
        benefit_type=PromotionBenefitTypeEnum.FIXED,
        benefit_value=Decimal("15"),
        conditions=PromotionConditions(category_id=category.id),
    )
    create_promotion(db, hotel_id=63, payload=payload, created_by_user_id=None)

    matched = find_applicable_promotions(db, _ctx(63, date(2026, 3, 1), category_id=category.id))
    assert len(matched) == 1

    unmatched = find_applicable_promotions(db, _ctx(63, date(2026, 3, 1), category_id=category.id + 999))
    assert unmatched == []


def test_find_applicable_promotions_respects_weekday_and_date_range(db):
    category = _seed_hotel(db, 64)
    payload = PromotionCreate(
        code="WEEKEND",
        name="Weekend only",
        benefit_type=PromotionBenefitTypeEnum.PERCENTAGE,
        benefit_value=Decimal("20"),
        conditions=PromotionConditions(
            weekdays=["sat", "sun"],
            stay_from=date(2026, 3, 1),
            stay_to=date(2026, 3, 31),
        ),
    )
    create_promotion(db, hotel_id=64, payload=payload, created_by_user_id=None)

    saturday = date(2026, 3, 7)  # a Saturday
    assert saturday.weekday() == 5
    monday = date(2026, 3, 9)
    assert monday.weekday() == 0

    assert len(find_applicable_promotions(db, _ctx(64, saturday))) == 1
    assert find_applicable_promotions(db, _ctx(64, monday)) == []
    assert find_applicable_promotions(db, _ctx(64, date(2026, 4, 4))) == []  # outside stay range


def test_find_applicable_promotions_matches_guest_tag_type(db):
    _seed_hotel(db, 65)
    guest = Guest(hotel_id=65, first_name="Vip", last_name="Guest")
    db.add(guest)
    db.flush()
    db.add(GuestTag(hotel_id=65, guest_id=guest.id, tag_type=GuestTagTypeEnum.VIP))
    db.flush()

    payload = PromotionCreate(
        code="VIP_DEAL",
        name="VIP",
        benefit_type=PromotionBenefitTypeEnum.PERCENTAGE,
        benefit_value=Decimal("5"),
        conditions=PromotionConditions(guest_tag_type="vip"),
    )
    create_promotion(db, hotel_id=65, payload=payload, created_by_user_id=None)

    assert len(find_applicable_promotions(db, _ctx(65, date(2026, 3, 1), guest_id=guest.id))) == 1
    assert find_applicable_promotions(db, _ctx(65, date(2026, 3, 1), guest_id=None)) == []


def test_apply_promotions_never_goes_negative(db):
    _seed_hotel(db, 66)
    payload = PromotionCreate(
        code="HUGE_DISCOUNT",
        name="Huge discount",
        benefit_type=PromotionBenefitTypeEnum.FIXED,
        benefit_value=Decimal("500"),
    )
    promo = create_promotion(db, hotel_id=66, payload=payload, created_by_user_id=None)

    result, applied = apply_promotions_to_night(Decimal("100.00"), [promo])
    assert result == Decimal("0.00")
    assert applied[0]["amount_deducted"] == "100.00"


def test_non_stackable_promotion_excludes_others_stacking_promotions_combine(db):
    _seed_hotel(db, 67)
    exclusive = create_promotion(
        db,
        hotel_id=67,
        payload=PromotionCreate(
            code="EXCLUSIVE", name="Exclusive", benefit_type=PromotionBenefitTypeEnum.FIXED,
            benefit_value=Decimal("10"), priority=10, stackable=False,
        ),
        created_by_user_id=None,
    )
    stackable_a = create_promotion(
        db,
        hotel_id=67,
        payload=PromotionCreate(
            code="STACK_A", name="Stack A", benefit_type=PromotionBenefitTypeEnum.FIXED,
            benefit_value=Decimal("5"), priority=5, stackable=True,
        ),
        created_by_user_id=None,
    )
    stackable_b = create_promotion(
        db,
        hotel_id=67,
        payload=PromotionCreate(
            code="STACK_B", name="Stack B", benefit_type=PromotionBenefitTypeEnum.FIXED,
            benefit_value=Decimal("3"), priority=1, stackable=True,
        ),
        created_by_user_id=None,
    )

    # exclusive has the highest priority and is non-stackable -> wins alone.
    result, applied = apply_promotions_to_night(Decimal("100.00"), [exclusive, stackable_a, stackable_b])
    assert result == Decimal("90.00")
    assert len(applied) == 1
    assert applied[0]["code"] == "EXCLUSIVE"

    # Without the exclusive promo, the two stackable ones combine (5 + 3 = 8 off).
    result2, applied2 = apply_promotions_to_night(Decimal("100.00"), [stackable_a, stackable_b])
    assert result2 == Decimal("92.00")
    assert {row["code"] for row in applied2} == {"STACK_A", "STACK_B"}


def test_update_promotion_creates_new_version_and_deactivates_old(db):
    _seed_hotel(db, 68)
    v1 = create_promotion(
        db,
        hotel_id=68,
        payload=PromotionCreate(
            code="EVOLVING", name="v1", benefit_type=PromotionBenefitTypeEnum.PERCENTAGE, benefit_value=Decimal("10"),
        ),
        created_by_user_id=None,
    )
    v1_id = v1.id

    v2 = update_promotion(
        db,
        hotel_id=68,
        promotion_id=v1_id,
        payload=PromotionUpdate(benefit_value=Decimal("20")),
        actor_user_id=None,
    )

    assert v2.id != v1_id
    assert v2.version == 2
    assert v2.previous_version_id == v1_id
    assert v2.benefit_value == Decimal("20.0000")
    assert v2.is_active is True

    old = get_promotion(db, hotel_id=68, promotion_id=v1_id)
    assert old.is_active is False

    # The old, now-inactive row is still readable directly by id -- an
    # already-booked reservation that froze v1's id/version in its
    # pricing_snapshot is unaffected by the edit.
    assert old.benefit_value == Decimal("10.0000")
    assert old.version == 1


def test_deactivate_and_reactivate_promotion(db):
    _seed_hotel(db, 69)
    promo = create_promotion(
        db,
        hotel_id=69,
        payload=PromotionCreate(
            code="TOGGLE", name="Toggle", benefit_type=PromotionBenefitTypeEnum.FIXED, benefit_value=Decimal("5"),
        ),
        created_by_user_id=None,
    )

    deactivate_promotion(db, hotel_id=69, promotion_id=promo.id, actor_user_id=None)
    assert list_promotions(db, hotel_id=69) == []
    assert len(list_promotions(db, hotel_id=69, include_inactive=True)) == 1

    reactivate_promotion(db, hotel_id=69, promotion_id=promo.id)
    assert len(list_promotions(db, hotel_id=69)) == 1


def test_promotions_are_tenant_isolated(db):
    _seed_hotel(db, 70)
    _seed_hotel(db, 71)
    create_promotion(
        db,
        hotel_id=70,
        payload=PromotionCreate(
            code="SAME_CODE", name="Hotel A", benefit_type=PromotionBenefitTypeEnum.FIXED, benefit_value=Decimal("1"),
        ),
        created_by_user_id=None,
    )
    create_promotion(
        db,
        hotel_id=71,
        payload=PromotionCreate(
            code="SAME_CODE", name="Hotel B", benefit_type=PromotionBenefitTypeEnum.FIXED, benefit_value=Decimal("2"),
        ),
        created_by_user_id=None,
    )

    hotel_a = list_promotions(db, hotel_id=70)
    hotel_b = list_promotions(db, hotel_id=71)
    assert len(hotel_a) == 1 and len(hotel_b) == 1
    assert hotel_a[0].name == "Hotel A"
    assert hotel_b[0].name == "Hotel B"
    assert hotel_a[0].id != hotel_b[0].id

    with pytest.raises(PromotionError):
        get_promotion(db, hotel_id=71, promotion_id=hotel_a[0].id)
