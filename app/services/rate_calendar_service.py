from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.analytics import RoomStateEvent
from app.models.commercial import ProductRoomCompatibility, RatePlan, RatePlanPrice, SellableProduct
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTAInventoryRule, OTAPriceRule, OTAProvider, OTARatePlanMapping, OTARoomMapping
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory


_PROVIDER_ORDER = (
    ("direct", "Direct"),
    ("booking", "Booking.com"),
    ("expedia", "Expedia"),
)
_ACTIVE_RESERVATION_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.CHECKED_IN,
)


def get_daily_calendar(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    date_from: date,
    date_to: date,
) -> dict:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    if (date_to - date_from).days > 366:
        raise ValueError("Date range cannot exceed 366 days")

    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not category:
        raise ValueError("Category not found")

    hotel_config = db.get(HotelConfiguration, hotel_id)
    hotel_currency = (hotel_config.default_currency if hotel_config else None) or "ARS"

    products = (
        db.query(SellableProduct)
        .outerjoin(
            ProductRoomCompatibility,
            ProductRoomCompatibility.sellable_product_id == SellableProduct.id,
        )
        .filter(
            SellableProduct.hotel_id == hotel_id,
            SellableProduct.is_active == True,
            or_(
                SellableProduct.primary_room_category_id == category_id,
                ProductRoomCompatibility.room_category_id == category_id,
            ),
        )
        .distinct()
        .order_by(SellableProduct.sort_order.asc(), SellableProduct.id.asc())
        .all()
    )
    product_ids = [product.id for product in products]

    rate_plans = []
    if product_ids:
        rate_plans = (
            db.query(RatePlan)
            .filter(
                RatePlan.hotel_id == hotel_id,
                RatePlan.sellable_product_id.in_(product_ids),
                RatePlan.is_active == True,
            )
            .order_by(RatePlan.id.asc())
            .all()
        )
    rate_plan_ids = [plan.id for plan in rate_plans]

    rooms = (
        db.query(Room)
        .filter(
            Room.hotel_id == hotel_id,
            Room.category_id == category_id,
            Room.is_active == True,
        )
        .order_by(Room.id.asc())
        .all()
    )
    room_ids = [room.id for room in rooms]
    total_rooms = len(rooms)

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.category_id == category_id,
            Reservation.status.in_(_ACTIVE_RESERVATION_STATUSES),
            Reservation.check_in_date <= date_to,
            Reservation.check_out_date > date_from,
        )
        .all()
    )

    window_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    window_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    room_state_events = []
    if room_ids:
        room_state_events = (
            db.query(RoomStateEvent)
            .filter(
                RoomStateEvent.hotel_id == hotel_id,
                RoomStateEvent.room_id.in_(room_ids),
                RoomStateEvent.started_at < window_end,
                or_(RoomStateEvent.ended_at.is_(None), RoomStateEvent.ended_at > window_start),
            )
            .all()
        )

    rate_plan_prices = []
    if rate_plan_ids:
        rate_plan_prices = (
            db.query(RatePlanPrice)
            .filter(
                RatePlanPrice.hotel_id == hotel_id,
                RatePlanPrice.rate_plan_id.in_(rate_plan_ids),
                RatePlanPrice.is_active == True,
                or_(RatePlanPrice.valid_from.is_(None), RatePlanPrice.valid_from <= date_to),
                or_(RatePlanPrice.valid_to.is_(None), RatePlanPrice.valid_to >= date_from),
            )
            .all()
        )

    providers = db.query(OTAProvider).filter(OTAProvider.code.in_(["booking", "expedia"])).all()
    provider_by_code = {provider.code: provider for provider in providers}
    provider_ids = [provider.id for provider in providers]

    room_mappings = []
    rate_plan_mappings = []
    ota_price_rules = []
    inventory_rules = []
    if provider_ids:
        room_mapping_query = (
            db.query(OTARoomMapping)
            .filter(
                OTARoomMapping.hotel_id == hotel_id,
                OTARoomMapping.provider_id.in_(provider_ids),
                OTARoomMapping.is_active == True,
            )
        )
        room_mapping_filters = [OTARoomMapping.room_category_id == category_id]
        if product_ids:
            room_mapping_filters.append(OTARoomMapping.sellable_product_id.in_(product_ids))
        room_mappings = room_mapping_query.filter(or_(*room_mapping_filters)).all()

        if rate_plan_ids:
            rate_plan_mappings = (
                db.query(OTARatePlanMapping)
                .filter(
                    OTARatePlanMapping.hotel_id == hotel_id,
                    OTARatePlanMapping.provider_id.in_(provider_ids),
                    OTARatePlanMapping.rate_plan_id.in_(rate_plan_ids),
                    OTARatePlanMapping.is_active == True,
                )
                .all()
            )
            ota_price_rules = (
                db.query(OTAPriceRule)
                .filter(
                    OTAPriceRule.hotel_id == hotel_id,
                    OTAPriceRule.provider_id.in_(provider_ids),
                    OTAPriceRule.rate_plan_id.in_(rate_plan_ids),
                    OTAPriceRule.stay_date >= date_from,
                    OTAPriceRule.stay_date <= date_to,
                )
                .all()
            )
            inventory_rules = (
                db.query(OTAInventoryRule)
                .filter(
                    OTAInventoryRule.hotel_id == hotel_id,
                    OTAInventoryRule.provider_id.in_(provider_ids),
                    OTAInventoryRule.rate_plan_id.in_(rate_plan_ids),
                    OTAInventoryRule.stay_date >= date_from,
                    OTAInventoryRule.stay_date <= date_to,
                )
                .all()
            )

    reservations_by_day: dict[date, int] = defaultdict(int)
    for reservation in reservations:
        current = max(date_from, reservation.check_in_date)
        end = min(date_to + timedelta(days=1), reservation.check_out_date)
        while current < end:
            reservations_by_day[current] += 1
            current += timedelta(days=1)

    blocked_rooms_by_day: dict[date, set[int]] = defaultdict(set)
    for event in room_state_events:
        current = max(date_from, event.started_at.astimezone(timezone.utc).date())
        event_end_exclusive = date_to + timedelta(days=1)
        if event.ended_at is not None:
            event_end_exclusive = min(event_end_exclusive, event.ended_at.astimezone(timezone.utc).date())
        while current < event_end_exclusive:
            blocked_rooms_by_day[current].add(event.room_id)
            current += timedelta(days=1)

    prices_by_plan: dict[int, list[RatePlanPrice]] = defaultdict(list)
    for price in rate_plan_prices:
        prices_by_plan[price.rate_plan_id].append(price)

    room_mapping_by_provider: dict[int, list[OTARoomMapping]] = defaultdict(list)
    for mapping in room_mappings:
        room_mapping_by_provider[mapping.provider_id].append(mapping)

    mapped_rate_plans_by_provider: dict[int, set[int]] = defaultdict(set)
    for mapping in rate_plan_mappings:
        mapped_rate_plans_by_provider[mapping.provider_id].add(mapping.rate_plan_id)

    ota_price_by_key: dict[tuple[int, int, date], list[OTAPriceRule]] = defaultdict(list)
    for rule in ota_price_rules:
        ota_price_by_key[(rule.provider_id, rule.rate_plan_id, rule.stay_date)].append(rule)

    inventory_by_key: dict[tuple[int, date], list[OTAInventoryRule]] = defaultdict(list)
    for rule in inventory_rules:
        inventory_by_key[(rule.provider_id, rule.stay_date)].append(rule)

    today = date.today()
    days: list[dict] = []
    current_date = date_from
    while current_date <= date_to:
        reserved = reservations_by_day[current_date]
        blocked = len(blocked_rooms_by_day[current_date])
        for_sale = max(total_rooms - reserved - blocked, 0)
        occupancy_pct = int(round((reserved / total_rooms) * 100)) if total_rooms else 0

        channels: list[dict] = []
        for provider_code, provider_label in _PROVIDER_ORDER:
            if provider_code == "direct":
                channels.append(
                    {
                        "provider_code": provider_code,
                        "provider_label": provider_label,
                        "currency_code": hotel_currency,
                        "missing_mapping": False,
                        "prices": _build_direct_prices(rate_plans, prices_by_plan, current_date, hotel_currency),
                        "restrictions": _default_restrictions(),
                    }
                )
                continue

            provider = provider_by_code.get(provider_code)
            if provider is None:
                channels.append(_build_missing_channel(provider_code, provider_label, hotel_currency))
                continue

            has_room_mapping = bool(room_mapping_by_provider.get(provider.id))
            mapped_plan_ids = mapped_rate_plans_by_provider.get(provider.id, set())
            if not has_room_mapping or not mapped_plan_ids:
                channels.append(_build_missing_channel(provider_code, provider_label, hotel_currency))
                continue

            channel_prices = _build_ota_prices(
                rate_plans=rate_plans,
                mapped_plan_ids=mapped_plan_ids,
                prices_by_plan=prices_by_plan,
                ota_price_by_key=ota_price_by_key,
                provider_id=provider.id,
                provider_code=provider_code,
                stay_date=current_date,
                hotel_currency=hotel_currency,
            )
            restrictions = _aggregate_inventory_rules(
                inventory_by_key=inventory_by_key,
                provider_id=provider.id,
                stay_date=current_date,
                mapped_plan_ids=mapped_plan_ids,
            )
            channel_currency = channel_prices[0]["currency_code"] if channel_prices else hotel_currency
            channels.append(
                {
                    "provider_code": provider_code,
                    "provider_label": provider_label,
                    "currency_code": channel_currency,
                    "missing_mapping": False,
                    "prices": channel_prices,
                    "restrictions": restrictions,
                }
            )

        days.append(
            {
                "date": current_date,
                "is_today": current_date == today,
                "total_rooms": total_rooms,
                "reserved": reserved,
                "blocked": blocked,
                "for_sale": for_sale,
                "status": "open" if for_sale > 0 else "closed",
                "occupancy_pct": occupancy_pct,
                "channels": channels,
            }
        )
        current_date += timedelta(days=1)

    return {
        "meta": {
            "category_id": category.id,
            "category_name": category.name,
            "category_code": category.code,
            "total_rooms": total_rooms,
            "hotel_currency_code": hotel_currency,
            "date_from": date_from,
            "date_to": date_to,
        },
        "days": days,
    }


def _build_direct_prices(rate_plans, prices_by_plan, stay_date: date, hotel_currency: str) -> list[dict]:
    prices: list[dict] = []
    for rate_plan in rate_plans:
        selected = _select_rate_plan_price(prices_by_plan.get(rate_plan.id, []), stay_date, preferred_channel="direct")
        if selected is None:
            continue
        prices.append(
            {
                "rate_plan_id": rate_plan.id,
                "rate_plan_code": rate_plan.code,
                "rate_plan_name": rate_plan.name,
                "base_amount": float(selected.base_amount),
                "sales_channel_code": selected.sales_channel_code,
                "currency_code": selected.currency_code or hotel_currency,
            }
        )
    return prices


def _build_ota_prices(*, rate_plans, mapped_plan_ids: set[int], prices_by_plan, ota_price_by_key, provider_id: int, provider_code: str, stay_date: date, hotel_currency: str) -> list[dict]:
    prices: list[dict] = []
    for rate_plan in rate_plans:
        if rate_plan.id not in mapped_plan_ids:
            continue
        ota_rules = ota_price_by_key.get((provider_id, rate_plan.id, stay_date), [])
        selected_ota_rule = _select_ota_price_rule(ota_rules)
        if selected_ota_rule is not None:
            prices.append(
                {
                    "rate_plan_id": rate_plan.id,
                    "rate_plan_code": rate_plan.code,
                    "rate_plan_name": rate_plan.name,
                    "base_amount": float(selected_ota_rule.gross_amount),
                    "sales_channel_code": provider_code,
                    "currency_code": selected_ota_rule.currency_code or hotel_currency,
                }
            )
            continue

        fallback = _select_rate_plan_price(prices_by_plan.get(rate_plan.id, []), stay_date, preferred_channel=provider_code)
        if fallback is None:
            continue
        prices.append(
            {
                "rate_plan_id": rate_plan.id,
                "rate_plan_code": rate_plan.code,
                "rate_plan_name": rate_plan.name,
                "base_amount": float(fallback.base_amount),
                "sales_channel_code": provider_code,
                "currency_code": fallback.currency_code or hotel_currency,
            }
        )
    return prices


def _select_rate_plan_price(prices: list[RatePlanPrice], stay_date: date, *, preferred_channel: str) -> RatePlanPrice | None:
    valid_prices = [
        price
        for price in prices
        if (price.valid_from is None or price.valid_from <= stay_date)
        and (price.valid_to is None or price.valid_to >= stay_date)
    ]
    if not valid_prices:
        return None

    def score(price: RatePlanPrice) -> tuple[int, int, date, int]:
        channel_score = 2 if price.sales_channel_code == preferred_channel else (1 if price.sales_channel_code in (None, "") else 0)
        occupancy_score = 1 if price.occupancy is not None else 0
        valid_from = price.valid_from or date.min
        return (channel_score, occupancy_score, valid_from.toordinal(), price.id)

    selected = max(valid_prices, key=score)
    if score(selected)[0] == 0:
        return None
    return selected


def _select_ota_price_rule(rules: list[OTAPriceRule]) -> OTAPriceRule | None:
    if not rules:
        return None
    return max(rules, key=lambda rule: ((1 if rule.occupancy is not None else 0), rule.id))


def _aggregate_inventory_rules(*, inventory_by_key, provider_id: int, stay_date: date, mapped_plan_ids: set[int]) -> dict:
    relevant_rules = [
        rule
        for rule in inventory_by_key.get((provider_id, stay_date), [])
        if rule.rate_plan_id in mapped_plan_ids
    ]
    if not relevant_rules:
        return _default_restrictions()

    min_stays = [rule.min_stay for rule in relevant_rules if rule.min_stay is not None]
    max_stays = [rule.max_stay for rule in relevant_rules if rule.max_stay is not None]
    allotments = [rule.allotment for rule in relevant_rules if rule.allotment is not None]
    return {
        "min_stay": max(min_stays) if min_stays else None,
        "max_stay": max(max_stays) if max_stays else None,
        "closed_to_arrival": any(rule.closed_to_arrival for rule in relevant_rules),
        "closed_to_departure": any(rule.closed_to_departure for rule in relevant_rules),
        "allotment": sum(allotments) if allotments else None,
        "stop_sell": any(rule.stop_sell for rule in relevant_rules),
    }


def _default_restrictions() -> dict:
    return {
        "min_stay": None,
        "max_stay": None,
        "closed_to_arrival": False,
        "closed_to_departure": False,
        "allotment": None,
        "stop_sell": False,
    }


def _build_missing_channel(provider_code: str, provider_label: str, hotel_currency: str) -> dict:
    return {
        "provider_code": provider_code,
        "provider_label": provider_label,
        "currency_code": hotel_currency,
        "missing_mapping": True,
        "prices": [],
        "restrictions": _default_restrictions(),
    }
