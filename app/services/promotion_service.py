"""
Promotion CRUD, versioning, matching and per-night application.

Versioning contract: a Promotion row is immutable once other rows (reservation
pricing snapshots) may reference it. ``update_promotion`` never mutates an
existing row's rule fields -- it creates a brand-new row with
``version = old.version + 1`` and ``previous_version_id`` pointing at the row
it replaces, then deactivates the old row. This guarantees an already-booked
reservation's stored pricing_snapshot (which freezes the promotion id/version
used) can never change when someone edits or deactivates the promotion later.

Priority convention: higher ``priority`` wins on conflict, matching the
existing ``PricePeriod.priority`` convention (app/models/daily_rate.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app.models.guest import GuestTag
from app.models.promotion import Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum

MONEY_QUANTUM = Decimal("0.01")


class PromotionError(ValueError):
    """Raised on invalid promotion CRUD input."""


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _get_active_or_404(db: Session, hotel_id: int, promotion_id: int) -> Promotion:
    promo = (
        db.query(Promotion)
        .filter(Promotion.id == promotion_id, Promotion.hotel_id == hotel_id)
        .first()
    )
    if promo is None:
        raise PromotionError(f"Promotion {promotion_id} not found for hotel {hotel_id}")
    return promo


def list_promotions(db: Session, *, hotel_id: int, include_inactive: bool = False) -> list[Promotion]:
    query = db.query(Promotion).filter(Promotion.hotel_id == hotel_id)
    if not include_inactive:
        query = query.filter(Promotion.is_active.is_(True))
    return query.order_by(Promotion.code.asc(), Promotion.version.desc()).all()


def get_promotion(db: Session, *, hotel_id: int, promotion_id: int) -> Promotion:
    return _get_active_or_404(db, hotel_id, promotion_id)


def create_promotion(db: Session, *, hotel_id: int, payload, created_by_user_id: Optional[int]) -> Promotion:
    from app.schemas.promotion import weekdays_to_mask  # local import avoids a schema<->service cycle

    existing = (
        db.query(Promotion)
        .filter(Promotion.hotel_id == hotel_id, Promotion.code == payload.code)
        .first()
    )
    if existing is not None:
        raise PromotionError(
            f"A promotion with code '{payload.code}' already exists for this hotel. "
            "Use PATCH to create a new version."
        )

    promo = Promotion(
        hotel_id=hotel_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        benefit_type=payload.benefit_type,
        benefit_value=payload.benefit_value,
        scope=payload.scope,
        from_night_number=payload.from_night_number,
        priority=payload.priority,
        stackable=payload.stackable,
        is_active=True,
        version=1,
        created_by_user_id=created_by_user_id,
        **_conditions_kwargs(payload.conditions, weekdays_to_mask),
    )
    db.add(promo)
    db.flush()
    return promo


def _conditions_kwargs(conditions, weekdays_to_mask) -> dict:
    return {
        "booking_from": conditions.booking_from,
        "booking_to": conditions.booking_to,
        "stay_from": conditions.stay_from,
        "stay_to": conditions.stay_to,
        "min_nights": conditions.min_nights,
        "max_nights": conditions.max_nights,
        "weekdays_mask": weekdays_to_mask(conditions.weekdays),
        "category_id": conditions.category_id,
        "room_id": conditions.room_id,
        "sales_channel_code": conditions.sales_channel_code,
        "guest_id": conditions.guest_id,
        "company_id": conditions.company_id,
        "guest_tag_type": conditions.guest_tag_type,
        "payment_currency": conditions.payment_currency.upper() if conditions.payment_currency else None,
        "payment_method": conditions.payment_method,
    }


def update_promotion(
    db: Session, *, hotel_id: int, promotion_id: int, payload, actor_user_id: Optional[int]
) -> Promotion:
    from app.schemas.promotion import weekdays_to_mask

    current = _get_active_or_404(db, hotel_id, promotion_id)

    benefit_type = payload.benefit_type if payload.benefit_type is not None else current.benefit_type
    benefit_value = payload.benefit_value if payload.benefit_value is not None else current.benefit_value
    if benefit_type == PromotionBenefitTypeEnum.PERCENTAGE and benefit_value > 100:
        raise PromotionError("Percentage benefit_value must be <= 100")

    scope = payload.scope if payload.scope is not None else current.scope
    from_night_number = (
        payload.from_night_number if payload.from_night_number is not None else current.from_night_number
    )
    if scope == PromotionScopeEnum.FROM_NIGHT_N and from_night_number is None:
        raise PromotionError("from_night_number is required when scope is from_night_n")

    if payload.conditions is not None:
        conditions_kwargs = _conditions_kwargs(payload.conditions, weekdays_to_mask)
    else:
        # No conditions block sent: carry every condition column over as-is
        # (weekdays_mask is copied directly, bypassing the name<->mask
        # round trip since it is already stored as a mask).
        conditions_kwargs = {
            "booking_from": current.booking_from,
            "booking_to": current.booking_to,
            "stay_from": current.stay_from,
            "stay_to": current.stay_to,
            "min_nights": current.min_nights,
            "max_nights": current.max_nights,
            "weekdays_mask": current.weekdays_mask,
            "category_id": current.category_id,
            "room_id": current.room_id,
            "sales_channel_code": current.sales_channel_code,
            "guest_id": current.guest_id,
            "company_id": current.company_id,
            "guest_tag_type": current.guest_tag_type,
            "payment_currency": current.payment_currency,
            "payment_method": current.payment_method,
        }

    new_version = Promotion(
        hotel_id=hotel_id,
        code=current.code,
        name=payload.name if payload.name is not None else current.name,
        description=payload.description if payload.description is not None else current.description,
        benefit_type=benefit_type,
        benefit_value=benefit_value,
        scope=scope,
        from_night_number=from_night_number,
        priority=payload.priority if payload.priority is not None else current.priority,
        stackable=payload.stackable if payload.stackable is not None else current.stackable,
        is_active=True,
        version=current.version + 1,
        previous_version_id=current.id,
        created_by_user_id=actor_user_id,
        **conditions_kwargs,
    )
    db.add(new_version)
    current.is_active = False
    current.deactivated_by_user_id = actor_user_id
    db.flush()
    return new_version


def deactivate_promotion(db: Session, *, hotel_id: int, promotion_id: int, actor_user_id: Optional[int]) -> Promotion:
    from datetime import datetime, timezone

    promo = _get_active_or_404(db, hotel_id, promotion_id)
    promo.is_active = False
    promo.deactivated_at = datetime.now(timezone.utc)
    promo.deactivated_by_user_id = actor_user_id
    db.flush()
    return promo


def reactivate_promotion(db: Session, *, hotel_id: int, promotion_id: int) -> Promotion:
    promo = _get_active_or_404(db, hotel_id, promotion_id)
    promo.is_active = True
    promo.deactivated_at = None
    promo.deactivated_by_user_id = None
    db.flush()
    return promo


# --------------------------------------------------------------------------
# Matching + application
# --------------------------------------------------------------------------

@dataclass(slots=True)
class PromotionMatchContext:
    hotel_id: int
    night_date: date
    night_index: int  # 1-based index of this night within the stay
    nights_total: int
    booking_date: date
    category_id: Optional[int] = None
    room_id: Optional[int] = None
    sales_channel_code: Optional[str] = None
    guest_id: Optional[int] = None
    company_id: Optional[int] = None
    payment_currency: Optional[str] = None
    payment_method: Optional[str] = None


def _guest_tag_types(db: Session, *, hotel_id: int, guest_id: Optional[int]) -> set[str]:
    if guest_id is None:
        return set()
    rows = (
        db.query(GuestTag.tag_type)
        .filter(GuestTag.hotel_id == hotel_id, GuestTag.guest_id == guest_id)
        .all()
    )
    return {row[0].value if hasattr(row[0], "value") else str(row[0]) for row in rows}


def _promotion_matches(promo: Promotion, ctx: PromotionMatchContext, guest_tags: set[str]) -> bool:
    if promo.scope == PromotionScopeEnum.FROM_NIGHT_N:
        if promo.from_night_number and ctx.night_index < promo.from_night_number:
            return False

    if promo.booking_from and ctx.booking_date < promo.booking_from:
        return False
    if promo.booking_to and ctx.booking_date > promo.booking_to:
        return False
    if promo.stay_from and ctx.night_date < promo.stay_from:
        return False
    if promo.stay_to and ctx.night_date > promo.stay_to:
        return False
    if promo.min_nights and ctx.nights_total < promo.min_nights:
        return False
    if promo.max_nights and ctx.nights_total > promo.max_nights:
        return False
    if promo.weekdays_mask is not None:
        weekday_bit = 1 << ctx.night_date.weekday()  # Monday=0
        if not (promo.weekdays_mask & weekday_bit):
            return False
    if promo.category_id is not None and promo.category_id != ctx.category_id:
        return False
    if promo.room_id is not None and promo.room_id != ctx.room_id:
        return False
    if promo.sales_channel_code is not None and promo.sales_channel_code != ctx.sales_channel_code:
        return False
    if promo.guest_id is not None and promo.guest_id != ctx.guest_id:
        return False
    if promo.company_id is not None and promo.company_id != ctx.company_id:
        return False
    if promo.guest_tag_type is not None and promo.guest_tag_type not in guest_tags:
        return False
    if promo.payment_currency is not None and promo.payment_currency != ctx.payment_currency:
        return False
    if promo.payment_method is not None and promo.payment_method != ctx.payment_method:
        return False
    return True


def find_applicable_promotions(db: Session, ctx: PromotionMatchContext) -> list[Promotion]:
    """Return active promotions eligible for a single night, matching every
    typed condition set on the row (NULL = wildcard)."""
    candidates = (
        db.query(Promotion)
        .filter(Promotion.hotel_id == ctx.hotel_id, Promotion.is_active.is_(True))
        .all()
    )
    guest_tags = _guest_tag_types(db, hotel_id=ctx.hotel_id, guest_id=ctx.guest_id)
    return [promo for promo in candidates if _promotion_matches(promo, ctx, guest_tags)]


def select_promotions_to_apply(promotions: list[Promotion]) -> list[Promotion]:
    """Pick which matched promotions actually apply together.

    Higher ``priority`` wins first. A non-stackable promotion, once selected,
    excludes every other candidate for that night. Stackable promotions only
    combine with other stackable promotions.
    """
    ordered = sorted(promotions, key=lambda p: (-p.priority, p.id))
    selected: list[Promotion] = []
    for promo in ordered:
        if not selected:
            selected.append(promo)
            if not promo.stackable:
                break
            continue
        if promo.stackable and all(existing.stackable for existing in selected):
            selected.append(promo)
    return selected


def apply_promotions_to_night(
    base_amount: Decimal, promotions: list[Promotion]
) -> tuple[Decimal, list[dict]]:
    """Apply the selected promotions (already priority-ordered) to a single
    night's base amount. Each benefit is computed against the *running*
    amount (cascading). The result is clamped at 0 -- a promotion may never
    make a night negative."""
    selected = select_promotions_to_apply(promotions)
    running = base_amount
    applied: list[dict] = []
    for promo in selected:
        if promo.benefit_type == PromotionBenefitTypeEnum.PERCENTAGE:
            discount = _quantize(running * Decimal(promo.benefit_value) / Decimal("100"))
        else:
            discount = _quantize(Decimal(promo.benefit_value))
        new_running = running - discount
        if new_running < 0:
            discount = running  # clamp: never charge negative for a night
            new_running = Decimal("0.00")
        running = new_running
        applied.append(
            {
                "promotion_id": promo.id,
                "code": promo.code,
                "version": promo.version,
                "benefit_type": promo.benefit_type.value,
                "benefit_value": str(promo.benefit_value),
                "amount_deducted": str(discount),
            }
        )
    return running, applied
