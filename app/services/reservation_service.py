"""
Reservation Service ? Core booking logic.
Handles creation, state transitions, confirmation code generation, and availability checks.
Uses pessimistic locking to prevent race conditions (overbooking).
"""
import json
import logging
import string
import random
from dataclasses import dataclass, field, replace
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial import RatePlan, SellableProduct, TaxPolicy
from app.models.company import Company
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
    ReservationSourceEnum,
    reservation_additional_guests,
)
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_role_visibility_window import HotelRoleVisibilityWindow
from app.models.operations import ReservationStatusHistory
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.financial_ledger import billing_adjustment_totals_by_reservation, completed_paid_amounts_by_reservation
from app.services.pricing_policy_service import PricingPolicyError, StayPricingQuote, quote_rate_plan_stay
from app.services.pricing_service import build_pricing_revision, get_price_for_date
from app.services.quote_token_service import QuoteTokenError, verify_quote_token
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.room_block_service import blocked_room_ids_for_range, list_active_blocks, room_has_active_block
from app.services.timezones import normalize_timezone

if TYPE_CHECKING:
    from app.dependencies.auth import AuthContext


logger = logging.getLogger(__name__)


class ReservationError(Exception):
    """Custom exception for reservation business logic errors."""
    pass


@dataclass(slots=True)
class _ReservationGuestProjection:
    id: int
    first_name: str
    last_name: str
    document_type: Any = None
    document_number: str | None = None


@dataclass(slots=True)
class _ReservationListProjection:
    """Only the scalar/read-model fields needed by the reservation list API."""

    id: int
    hotel_id: int
    confirmation_code: str
    guest_id: int
    guest: _ReservationGuestProjection | None
    room_id: int | None
    category_id: int
    company_id: int | None
    sellable_product_id: int | None
    rate_plan_id: int | None
    tax_policy_id: int | None
    check_in_date: date
    check_out_date: date
    actual_check_in: Any
    actual_check_out: Any
    total_amount: Any
    amount_paid: Any
    deposit_amount: Any
    subtotal_amount: Any
    tax_amount: Any
    fee_amount: Any
    commission_amount: Any
    net_amount: Any
    currency_code: str
    fx_rate_snapshot: float | None
    quoted_amount_ars: Any
    quoted_amount_usd: Any
    status: ReservationStatusEnum
    source: ReservationSourceEnum
    source_provider_code: str | None
    external_id: str | None
    external_confirmation_code: str | None
    payment_collection_model: str
    settlement_status: str
    num_adults: int
    num_children: int
    notes: str | None
    created_at: Any
    updated_at: Any
    allocation_status: str
    requires_manual_review: bool
    mobility_restriction: bool
    is_wait_listed: bool
    wait_list_reason: str | None
    version: int
    additional_guests: list[_ReservationGuestProjection] = field(default_factory=list)

    @property
    def balance_due(self):
        return max(Decimal("0"), Decimal(str(self.total_amount or 0)) - Decimal(str(self.amount_paid or 0)))

    @property
    def nights(self) -> int:
        return (self.check_out_date - self.check_in_date).days


def active_reservations(db: Session, hotel_id: int):
    """Single place that decides which reservations 'exist'.

    Soft-deleted rows must never reach aggregation, availability or allocation.
    Restore/audit paths intentionally bypass this helper.
    """
    return db.query(Reservation).filter(
        Reservation.hotel_id == hotel_id,
        Reservation.deleted_at.is_(None),
    )


def _hotel_today_and_timezone(db: Session, hotel_id: int) -> tuple[date, ZoneInfo]:
    """Resolve the local calendar date from the hotel's stored IANA timezone."""
    config = db.get(HotelConfiguration, hotel_id)
    timezone_name = config.hotel_timezone if config is not None else "UTC"
    try:
        timezone_name = normalize_timezone(timezone_name)
        hotel_timezone = ZoneInfo(timezone_name)
    except (AttributeError, ValueError):
        # A legacy invalid configuration must not make a reservation list
        # unreadable. UTC is the narrow, deterministic fallback.
        logger.warning(
            "Invalid hotel timezone while resolving reservation visibility hotel_id=%s",
            hotel_id,
        )
        hotel_timezone = ZoneInfo("UTC")
    local_today = datetime.now(hotel_timezone).date()
    return local_today, hotel_timezone


def visible_reservations(db: Session, context: "AuthContext"):
    """Active reservations intersecting the caller role's visibility window.

    This helper is for user-facing reads only. Background jobs, analytics
    refreshes, allocation, and OTA processing deliberately use
    :func:`active_reservations` so they retain the full reservation history.
    """
    query = active_reservations(db, context.hotel_id)
    window = (
        db.query(HotelRoleVisibilityWindow)
        .filter_by(hotel_id=context.hotel_id, role=context.user_role)
        .one_or_none()
    )
    if window is None or (window.past_hours is None and window.future_hours is None):
        return query

    local_today, hotel_timezone = _hotel_today_and_timezone(db, context.hotel_id)
    local_midnight = datetime.combine(local_today, datetime.min.time(), tzinfo=hotel_timezone)
    window_start = (
        (local_midnight - timedelta(hours=window.past_hours)).date()
        if window.past_hours is not None
        else None
    )
    window_end = (
        (local_midnight + timedelta(hours=window.future_hours)).date()
        if window.future_hours is not None
        else None
    )

    if window_start is not None:
        query = query.filter(Reservation.check_out_date >= window_start)
    if window_end is not None:
        query = query.filter(Reservation.check_in_date <= window_end)
    return query


def active_reservations_select(hotel_id: int):
    """Select form of :func:`active_reservations` for explicit-column queries."""
    return select(Reservation).where(
        Reservation.hotel_id == hotel_id,
        Reservation.deleted_at.is_(None),
    )


def _active_reservations_without_hotel(db: Session):
    """Keep legacy system-wide callers from including soft-deleted rows."""
    return db.query(Reservation).filter(Reservation.deleted_at.is_(None))


_MANUAL_TELEPHONIC_CHANNELS = {
    "manual",
    "telefono",
    "phone",
    "walk_in",
}

_CHANNEL_CODE_ALIASES = {
    "phone": ReservationChannelCodeEnum.PHONE,
    "telefono": ReservationChannelCodeEnum.PHONE,
    "tel": ReservationChannelCodeEnum.PHONE,
    "telephone": ReservationChannelCodeEnum.PHONE,
    "walk_in": ReservationChannelCodeEnum.WALK_IN,
    "walkin": ReservationChannelCodeEnum.WALK_IN,
    "manual": ReservationChannelCodeEnum.OTHER_DIRECT,
}

_PRICING_PAYMENT_METHOD_ALIASES = {
    "bank_transfer": "transfer",
    "wire_transfer": "transfer",
    "mercado_pago": "mercadopago",
    "mercadopago": "mercadopago",
    "mp": "mercadopago",
    "credit": "credit_card",
    "creditcard": "credit_card",
}

_PRICING_PAYMENT_METHODS = {
    "cash",
    "transfer",
    "mercadopago",
    "paypal",
    "credit_card",
}


@dataclass(slots=True)
class ReservationPricingResult:
    nights: int
    nightly_rate: float
    total_amount: float
    deposit_amount: float
    subtotal_amount: float
    tax_amount: float
    fee_amount: float
    commission_amount: float
    net_amount: float
    currency_code: str
    fx_rate_snapshot: float | None
    pricing_source: str
    sellable_product_id: int | None
    rate_plan_id: int | None
    tax_policy_id: int | None
    pricing_snapshot: str | None


def generate_confirmation_code(prefix: str = "RES") -> str:
    """Generate a unique, human-readable confirmation code."""
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_part}"


def _invalidate_availability_cache(hotel_id: int | None) -> None:
    if hotel_id is None:
        return
    try:
        invalidate_hotel_operational_caches(hotel_id)
    except Exception as exc:  # pragma: no cover - defensive cache isolation
        logger.debug(
            "reservation.availability_cache_invalidation_failed",
            extra={"hotel_id": hotel_id, "error_type": type(exc).__name__},
        )


def _touch_facts(db: Session, hotel_id: int | None, date_from: date | None, date_to: date | None) -> None:
    """Keep FactReservationDaily/FactRoomOccupancyDaily in sync with a
    reservation write, called at the same sites as _invalidate_availability_cache.
    """
    if hotel_id is None or date_from is None or date_to is None:
        return
    from app.services.analytics_facts import touch_reservation_fact_window

    touch_reservation_fact_window(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)


def _notify_reservation_event(
    db: Session,
    *,
    hotel_id: int | None,
    reservation: "Reservation",
    event_type: str,
    title: str,
    dedupe_suffix: str,
) -> None:
    """Durable, per-recipient notification for a reservation lifecycle
    change. Best-effort: a notification failure must never roll back or
    block the reservation write it describes."""
    if hotel_id is None:
        return
    try:
        from app.models.notification import NotificationSeverityEnum
        from app.services.notification_service import enqueue_notifications_for_event
        from app.services.permission_service import ROLE_CODES

        enqueue_notifications_for_event(
            db,
            hotel_id=hotel_id,
            event_type=event_type,
            dedupe_key=f"{event_type}:{reservation.id}:{dedupe_suffix}",
            title=title,
            severity=NotificationSeverityEnum.INFO,
            entity_type="reservation",
            entity_id=reservation.id,
            payload={"reservation_id": reservation.id, "status": reservation.status.value if reservation.status else None},
            recipient_roles=list(ROLE_CODES),
        )
    except Exception as exc:
        logger.error(
            "reservation.notify_failed",
            extra={"hotel_id": hotel_id, "reservation_id": reservation.id, "error_type": type(exc).__name__},
        )


def _resolve_hotel_id(
    hotel_id: Optional[int],
    category: Optional[RoomCategory] = None,
    room: Optional[Room] = None,
) -> int:
    """
    Resolve hotel_id using explicit parameter first, then category/room ownership.
    Never fall back to a global/single-hotel default.
    """
    for candidate in (hotel_id, getattr(category, "hotel_id", None), getattr(room, "hotel_id", None)):
        if candidate is not None:
            return candidate
    raise ReservationError("hotel_id is required for reservation operations")


def _validate_stay_dates(check_in: date, check_out: date) -> None:
    if check_out <= check_in:
        raise ReservationError("Check-out date must be after check-in date")


def _validate_reservation_occupancy(
    category: RoomCategory,
    num_adults: int | None,
    num_children: int | None,
) -> None:
    total = (num_adults or 0) + (num_children or 0)
    if total < 1:
        raise ReservationError(f"La reserva debe tener al menos 1 huésped; se solicitaron {total}.")

    max_occupancy = int(category.max_occupancy or 0)
    if total > max_occupancy:
        raise ReservationError(
            f"La categoría admite hasta {max_occupancy} huéspedes; se solicitaron {total}."
        )


def compute_reservation_pricing(
    db: Session,
    category_id: int,
    check_in: date,
    check_out: date,
    hotel_id: Optional[int] = None,
    *,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int | None = None,
) -> tuple[int, float, float, float]:
    """
    Calculate nights, nightly rate, total amount, and deposit amount for a stay.
    Raises ReservationError for invalid dates or missing category.
    """
    pricing_result = calculate_reservation_pricing(
        db,
        category_id=category_id,
        check_in=check_in,
        check_out=check_out,
        hotel_id=hotel_id,
        sellable_product_id=sellable_product_id,
        rate_plan_id=rate_plan_id,
        tax_policy_id=tax_policy_id,
        pricing_channel_code=pricing_channel_code,
        pricing_payment_method=pricing_payment_method,
        guest_scope=guest_scope,
        target_currency=target_currency,
        occupancy=occupancy,
    )
    return (
        pricing_result.nights,
        pricing_result.nightly_rate,
        pricing_result.total_amount,
        pricing_result.deposit_amount,
    )


def calculate_reservation_pricing(
    db: Session,
    *,
    category_id: int,
    check_in: date,
    check_out: date,
    hotel_id: Optional[int] = None,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int | None = None,
    guest_id: int | None = None,
    company_id: int | None = None,
) -> ReservationPricingResult:
    category_query = db.query(RoomCategory).filter(RoomCategory.id == category_id)
    if hotel_id is not None:
        category_query = category_query.filter(RoomCategory.hotel_id == hotel_id)
    category = category_query.first()
    if not category:
        raise ReservationError(f"Room category with id={category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")

    nights = (check_out - check_in).days
    if nights <= 0:
        raise ReservationError("Check-out date must be after check-in date")
    if occupancy is not None:
        if occupancy <= 0:
            raise ReservationError("Occupancy must be greater than 0")
        max_occupancy = int(category.max_occupancy or 0)
        if occupancy > max_occupancy:
            raise ReservationError(
                f"La categoría admite hasta {max_occupancy} huéspedes; se solicitaron {occupancy}."
            )
    pricing_payment_method = normalize_pricing_payment_method(pricing_payment_method)

    sellable_product, rate_plan, tax_policy = _resolve_reservation_commercial_context(
        db,
        hotel_id=hotel_id,
        category=category,
        sellable_product_id=sellable_product_id,
        rate_plan_id=rate_plan_id,
        tax_policy_id=tax_policy_id,
    )

    if rate_plan is not None:
        if occupancy is not None:
            product_min = int(sellable_product.min_occupancy) if sellable_product else 1
            product_max = int(sellable_product.max_occupancy) if sellable_product else int(category.max_occupancy or 0)
            if not product_min <= occupancy <= product_max:
                raise ReservationError(
                    f"El producto admite entre {product_min} y {product_max} huéspedes; se solicitaron {occupancy}."
                )
        try:
            quote = quote_rate_plan_stay(
                db,
                hotel_id=hotel_id,
                rate_plan_id=rate_plan.id,
                check_in=check_in,
                check_out=check_out,
                occupancy=occupancy or max(category.max_occupancy, 1),
                channel_code=pricing_channel_code or "direct",
                provider_code=None,
                guest_scope=guest_scope,
                target_currency=target_currency,
                tax_policy_id=tax_policy.id if tax_policy else None,
            )
        except PricingPolicyError as exc:
            raise ReservationError(str(exc))
        return _pricing_result_from_quote(
            db,
            hotel_id=hotel_id,
            nights=nights,
            check_in=check_in,
            quote=quote,
            sellable_product=sellable_product,
            rate_plan=rate_plan,
            tax_policy=tax_policy,
            pricing_channel_code=pricing_channel_code or "direct",
            guest_scope=guest_scope,
        )

    return _daily_rate_pricing_result(
        db,
        hotel_id=hotel_id,
        category=category,
        check_in=check_in,
        check_out=check_out,
        nights=nights,
        payment_method=pricing_payment_method,
        sellable_product=sellable_product,
        tax_policy=tax_policy,
        pricing_channel_code=pricing_channel_code,
        target_currency=target_currency,
        guest_id=guest_id,
        company_id=company_id,
    )


def _pricing_result_for_explicit_total(
    db: Session,
    *,
    hotel_id: int,
    category: RoomCategory,
    check_in: date,
    check_out: date,
    sellable_product_id: int | None,
    rate_plan_id: int | None,
    tax_policy_id: int | None,
) -> ReservationPricingResult:
    """Placeholder pricing for reservations that carry an explicit
    total_amount (manual/OTA load, corporate negotiated rate). Deliberately
    does NOT call quote_rate_plan_stay: an operator-typed price already
    fixes the total, so a commercial policy restriction that would
    legitimately reject an auto-quote (channel scope, missing price for the
    occupancy, min-stay, etc.) must never block the reservation. Only the
    cheap/pure lookups (_resolve_reservation_commercial_context) run, to
    keep sellable_product_id/rate_plan_id/tax_policy_id traceable on the
    reservation; the actual amounts are filled in right after by
    _apply_manual_total_override / _apply_corporate_pricing.
    """
    nights = (check_out - check_in).days
    if nights <= 0:
        raise ReservationError("Check-out date must be after check-in date")

    sellable_product, rate_plan, tax_policy = _resolve_reservation_commercial_context(
        db,
        hotel_id=hotel_id,
        category=category,
        sellable_product_id=sellable_product_id,
        rate_plan_id=rate_plan_id,
        tax_policy_id=tax_policy_id,
    )
    return ReservationPricingResult(
        nights=nights,
        nightly_rate=0.0,
        total_amount=0.0,
        deposit_amount=0.0,
        subtotal_amount=0.0,
        tax_amount=0.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=0.0,
        currency_code=_get_hotel_default_currency(db, hotel_id=hotel_id),
        fx_rate_snapshot=None,
        pricing_source="explicit_total_pending_override",
        sellable_product_id=sellable_product.id if sellable_product else None,
        rate_plan_id=rate_plan.id if rate_plan else None,
        tax_policy_id=tax_policy.id if tax_policy else None,
        pricing_snapshot=None,
    )


def _daily_rate_pricing_result(
    db: Session,
    *,
    hotel_id: int,
    category: RoomCategory,
    check_in: date,
    check_out: date,
    nights: int,
    payment_method: str | None,
    sellable_product: SellableProduct | None,
    tax_policy: TaxPolicy | None,
    pricing_channel_code: str | None = None,
    target_currency: str | None = None,
    guest_id: int | None = None,
    company_id: int | None = None,
) -> ReservationPricingResult:
    from app.services.promotion_service import (
        PromotionMatchContext,
        apply_promotions_to_night,
        find_applicable_promotions,
    )

    booking_date = datetime.now(timezone.utc).date()
    breakdown = []
    promotions_applied_all: list[dict] = []
    current = check_in
    night_index = 0
    while current < check_out:
        night_index += 1
        configured_source = _calendar_pricing_source(
            db,
            hotel_id=hotel_id,
            category_id=category.id,
            target_date=current,
        )
        price = get_price_for_date(
            db,
            hotel_id=hotel_id,
            category_id=category.id,
            target_date=current,
            payment_method=payment_method,
        )
        source = configured_source or "category_base"
        if configured_source is None:
            price = float(category.base_price_per_night or 0.0)
        price = round(float(price), 2)

        # Step 3 of the canonical pricing order (see
        # app.services.promotion_pricing_service): promotions eligible for
        # this specific night, applied per-night, clamped at 0.
        ctx = PromotionMatchContext(
            hotel_id=hotel_id,
            night_date=current,
            night_index=night_index,
            nights_total=nights,
            booking_date=booking_date,
            category_id=category.id,
            sales_channel_code=pricing_channel_code,
            guest_id=guest_id,
            company_id=company_id,
            payment_currency=target_currency,
            payment_method=payment_method,
        )
        matched = find_applicable_promotions(db, ctx)
        post_promo, applied = apply_promotions_to_night(Decimal(str(price)), matched)
        promotions_applied_all.extend(applied)
        final_price = float(post_promo)

        breakdown.append({
            "date": current.isoformat(),
            "price": final_price,
            "base_price": price,
            "source": source,
            "promotions_applied": applied,
        })
        current += timedelta(days=1)

    total_amount = round(sum(row["price"] for row in breakdown), 2)
    nightly_rate = round(total_amount / nights, 2) if nights else 0.0
    deposit_amount = _compute_deposit_amount(db, hotel_id=hotel_id, gross_total=total_amount)
    snapshot = {
        "pricing_source": "daily_rates",
        "category_id": category.id,
        "payment_method": payment_method,
        "nights": nights,
        "nightly_rate": nightly_rate,
        "breakdown": breakdown,
        "promotions_applied": promotions_applied_all,
    }
    return ReservationPricingResult(
        nights=nights,
        nightly_rate=nightly_rate,
        total_amount=total_amount,
        deposit_amount=deposit_amount,
        subtotal_amount=total_amount,
        tax_amount=0.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=total_amount,
        currency_code=_get_hotel_default_currency(db, hotel_id=hotel_id),
        fx_rate_snapshot=None,
        pricing_source="daily_rates",
        sellable_product_id=sellable_product.id if sellable_product else None,
        rate_plan_id=None,
        tax_policy_id=tax_policy.id if tax_policy else None,
        pricing_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)),
    )


def _resolve_reservation_company(db: Session, *, hotel_id: int, company_id: int | None) -> Company | None:
    if company_id is None:
        return None
    company = (
        db.query(Company)
        .filter(Company.id == company_id, Company.hotel_id == hotel_id, Company.is_active == True)
        .first()
    )
    if company is None:
        raise ReservationError("Company does not belong to the active hotel")
    return company


def _reservation_channel_indicator(value) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    normalized = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def normalize_pricing_payment_method(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _PRICING_PAYMENT_METHOD_ALIASES.get(normalized, normalized)
    if not normalized:
        return None
    if normalized not in _PRICING_PAYMENT_METHODS:
        raise ReservationError(f"Unsupported pricing payment method: {value}")
    return normalized


def _calendar_pricing_source(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    target_date: date,
) -> str | None:
    if db.query(DailyRate.id).filter(
        DailyRate.hotel_id == hotel_id,
        DailyRate.category_id == category_id,
        DailyRate.date == target_date,
    ).first():
        return "daily_rate"

    if db.query(PricePeriod.id).filter(
        PricePeriod.hotel_id == hotel_id,
        PricePeriod.category_id == category_id,
        PricePeriod.deleted_at.is_(None),
        PricePeriod.is_active == True,
        PricePeriod.start_date <= target_date,
        PricePeriod.end_date >= target_date,
    ).first():
        return "price_period"

    return None


def _is_manual_or_telephonic_reservation(data: ReservationCreate) -> bool:
    return any(
        indicator in _MANUAL_TELEPHONIC_CHANNELS
        for indicator in (
            _reservation_channel_indicator(data.channel_code),
            _reservation_channel_indicator(data.pricing_channel_code),
            _reservation_channel_indicator(data.source),
        )
    )


def _validate_manual_telephonic_guest_requirements(guest: Guest, data: ReservationCreate) -> None:
    if not _is_manual_or_telephonic_reservation(data):
        return

    missing = []
    if not str(guest.document_number or "").strip():
        missing.append("document_number")
    if not str(guest.phone or "").strip():
        missing.append("phone")

    if missing:
        raise ReservationError(
            "Manual or telephonic reservations require guest document_number and phone; "
            f"missing: {', '.join(missing)}"
        )


def _resolve_creation_channel_code(data: ReservationCreate) -> ReservationChannelCodeEnum:
    if data.channel_code is not None:
        return data.channel_code

    indicator = _reservation_channel_indicator(data.pricing_channel_code)
    if indicator in ReservationChannelCodeEnum._value2member_map_:
        return ReservationChannelCodeEnum(indicator)
    if indicator in _CHANNEL_CODE_ALIASES:
        return _CHANNEL_CODE_ALIASES[indicator]

    if data.source == ReservationSourceEnum.BOOKING:
        return ReservationChannelCodeEnum.BOOKING
    if data.source == ReservationSourceEnum.EXPEDIA:
        return ReservationChannelCodeEnum.EXPEDIA
    if data.source == ReservationSourceEnum.OTHER_OTA:
        return ReservationChannelCodeEnum.OTHER_OTA
    return ReservationChannelCodeEnum.OTHER_DIRECT


def _pricing_with_total(
    db: Session,
    *,
    hotel_id: int,
    pricing: ReservationPricingResult,
    total_amount,
    nightly_rate,
    pricing_source: str,
    company_id: int | None = None,
    currency_code: str | None = None,
) -> ReservationPricingResult:
    total = round(float(total_amount), 2)
    nightly = round(float(nightly_rate), 2)
    snapshot = {
        "pricing_source": pricing_source,
        "company_id": company_id,
        "nightly_rate": nightly,
        "nights": pricing.nights,
        "total_amount": total,
    }
    return replace(
        pricing,
        nightly_rate=nightly,
        total_amount=total,
        currency_code=(currency_code or pricing.currency_code),
        deposit_amount=_compute_deposit_amount(db, hotel_id=hotel_id, gross_total=total),
        subtotal_amount=total,
        tax_amount=0.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=total,
        pricing_source=pricing_source,
        pricing_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
    )


# ponytail: manual-total override does not run the OTACurrencyRate/FxPolicy
# conversion pipeline (that lives in pricing_policy_service.py and only fires
# for rate_plan-priced stays) -- it just labels the reservation with the
# currency the operator typed. fx_rate_snapshot stays whatever the earlier
# rate_plan quote (if any) already computed; it is not fabricated here. If a
# hotel needs a real live conversion for manual/no-rate-plan pricing, that is
# its own feature (wiring pricing_policy_service's converter or fx_service.py
# into this path), not something to invent inside a UI wiring task.
def _apply_manual_total_override(
    db: Session,
    *,
    hotel_id: int,
    pricing: ReservationPricingResult,
    total_amount,
    target_currency: str | None,
) -> ReservationPricingResult:
    nightly = float(total_amount) / pricing.nights if pricing.nights else 0.0
    return _pricing_with_total(
        db,
        hotel_id=hotel_id,
        pricing=pricing,
        total_amount=total_amount,
        nightly_rate=nightly,
        pricing_source="manual_total_override",
        currency_code=target_currency.strip().upper() if target_currency else None,
    )


def _apply_corporate_pricing(
    db: Session,
    *,
    hotel_id: int,
    pricing: ReservationPricingResult,
    company: Company,
    explicit_total,
) -> ReservationPricingResult:
    if explicit_total is not None:
        nightly = float(explicit_total) / pricing.nights if pricing.nights else 0.0
        return _pricing_with_total(
            db,
            hotel_id=hotel_id,
            pricing=pricing,
            total_amount=explicit_total,
            nightly_rate=nightly,
            pricing_source="manual_total_override",
            company_id=company.id,
        )

    if company.base_price is None or pricing.rate_plan_id is not None:
        return pricing

    nightly = float(company.base_price)
    return _pricing_with_total(
        db,
        hotel_id=hotel_id,
        pricing=pricing,
        total_amount=nightly * pricing.nights,
        nightly_rate=nightly,
        pricing_source="company_base_price",
        company_id=company.id,
    )


def _apply_custom_deposit_amount(
    pricing: ReservationPricingResult,
    deposit_amount,
) -> ReservationPricingResult:
    if deposit_amount is None:
        return pricing

    deposit = round(float(deposit_amount), 2)
    if deposit < 0:
        raise ReservationError("Deposit amount must be greater than or equal to 0")
    if deposit > pricing.total_amount:
        raise ReservationError("Deposit amount cannot be greater than reservation total")

    snapshot = {}
    if pricing.pricing_snapshot:
        try:
            snapshot = json.loads(pricing.pricing_snapshot)
        except json.JSONDecodeError:
            snapshot = {"previous_pricing_snapshot": pricing.pricing_snapshot}
    snapshot["deposit_amount_override"] = deposit

    return replace(
        pricing,
        deposit_amount=deposit,
        pricing_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
    )


def check_room_availability(
    db: Session,
    room_id: int,
    check_in: date,
    check_out: date,
    *,
    hotel_id: Optional[int] = None,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    """
    Check if a specific room is available for the given date range.
    A room is unavailable if there is ANY overlapping active reservation.
    """
    _validate_stay_dates(check_in, check_out)
    room_query = db.query(Room).filter(Room.id == room_id)
    if hotel_id is not None:
        room_query = room_query.filter(Room.hotel_id == hotel_id)
    room = room_query.first()
    if not room:
        raise ReservationError(f"Room with id={room_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, room=room)
    if room.hotel_id != hotel_id:
        raise ReservationError("Room does not belong to the active hotel")

    if room_has_active_block(db, hotel_id=hotel_id, room_id=room_id, start_date=check_in, end_date=check_out):
        return False

    query = active_reservations(db, hotel_id).filter(
        Reservation.room_id == room_id,
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in,
    )
    if exclude_reservation_id:
        query = query.filter(Reservation.id != exclude_reservation_id)
    return query.count() == 0


def find_available_rooms(
    db: Session,
    category_id: int,
    check_in: date,
    check_out: date,
    *,
    hotel_id: Optional[int] = None,
    exclude_reservation_id: Optional[int] = None,
    lock_for_update: bool = False,
) -> list[Room]:
    """
    Find all rooms of a given category that are available in the date range.
    Only considers rooms that are active and not in maintenance/blocked.
    """
    _validate_stay_dates(check_in, check_out)
    category_query = db.query(RoomCategory).filter(RoomCategory.id == category_id)
    if hotel_id is not None:
        category_query = category_query.filter(RoomCategory.hotel_id == hotel_id)
    category = category_query.first()
    if not category:
        raise ReservationError(f"Room category with id={category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")

    candidate_query = db.query(Room).filter(
        Room.category_id == category_id,
        Room.hotel_id == hotel_id,
        Room.deleted_at.is_(None),
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    )
    if lock_for_update:
        # The caller is about to persist an assignment in this transaction.
        # Lock only room rows so concurrent auto-assignment requests cannot both
        # observe the same room as free before either reservation is committed.
        candidate_query = candidate_query.enable_eagerloads(False).with_for_update()
    candidate_rooms = candidate_query.all()

    if not candidate_rooms:
        return []

    candidate_room_ids = [room.id for room in candidate_rooms]
    blocked_room_ids = blocked_room_ids_for_range(
        db,
        hotel_id=hotel_id,
        start_date=check_in,
        end_date=check_out,
        room_ids=candidate_room_ids,
    )
    occupied_query = active_reservations(db, hotel_id).with_entities(Reservation.room_id).filter(
        Reservation.room_id.in_(candidate_room_ids),
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in,
    )
    if exclude_reservation_id:
        occupied_query = occupied_query.filter(Reservation.id != exclude_reservation_id)
    occupied_room_ids = {room_id for (room_id,) in occupied_query.all() if room_id is not None}

    return [
        room
        for room in candidate_rooms
        if room.id not in blocked_room_ids and room.id not in occupied_room_ids
    ]


def create_reservation(
    db: Session,
    data: ReservationCreate,
    hotel_id: Optional[int] = None,
    *,
    actor_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
) -> Reservation:
    """
    Create a new reservation with full validation.

    Steps:
    1. Validate guest exists
    2. Validate category exists and compute total
    3. If room_id is provided, validate availability
    4. If room_id is NOT provided, auto-assign from available rooms (with row-level locking)
    5. Create reservation in PENDING status

    Uses SELECT ... FOR UPDATE to prevent race conditions on room assignment.
    """
    category_query = db.query(RoomCategory).filter(RoomCategory.id == data.category_id)
    if hotel_id is not None:
        category_query = category_query.filter(RoomCategory.hotel_id == hotel_id)
    category = category_query.first()
    if not category:
        raise ReservationError(f"Room category with id={data.category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)

    guest = (
        db.query(Guest)
        .filter(Guest.id == data.guest_id, Guest.hotel_id == hotel_id)
        .first()
    )
    if not guest:
        raise ReservationError(f"Guest with id={data.guest_id} not found")

    if guest.hotel_id != hotel_id:
        raise ReservationError("Guest does not belong to the active hotel")
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")
    _validate_reservation_occupancy(category, data.num_adults, data.num_children)
    _validate_manual_telephonic_guest_requirements(guest, data)

    company = _resolve_reservation_company(db, hotel_id=hotel_id, company_id=data.company_id)
    channel_code = _resolve_creation_channel_code(data)

    if data.total_amount is not None:
        # Root cause of the "manual OTA load doesn't work" report: an
        # explicit total_amount (manual/OTA load, corporate negotiated rate)
        # is an operator-typed price that must never be blocked by a
        # rate-plan commercial policy restriction (channel scope, missing
        # occupancy price, min-stay, etc). Skip the auto-quote engine
        # entirely instead of running it and overriding the result
        # afterwards -- a PricingPolicyError from quote_rate_plan_stay must
        # not abort a reservation whose price was already given.
        pricing = _pricing_result_for_explicit_total(
            db,
            hotel_id=hotel_id,
            category=category,
            check_in=data.check_in_date,
            check_out=data.check_out_date,
            sellable_product_id=data.sellable_product_id,
            rate_plan_id=data.rate_plan_id,
            tax_policy_id=data.tax_policy_id,
        )
        if company is not None:
            pricing = _apply_corporate_pricing(db, hotel_id=hotel_id, pricing=pricing, company=company, explicit_total=data.total_amount)
        else:
            # B4: manual tarifa on a direct (non-corporate) reservation --
            # the same override mechanism corporate accounts already use,
            # just without requiring a Company record for a one-off
            # negotiated price.
            pricing = _apply_manual_total_override(
                db,
                hotel_id=hotel_id,
                pricing=pricing,
                total_amount=data.total_amount,
                target_currency=data.target_currency,
            )
    else:
        pricing = calculate_reservation_pricing(
            db,
            category_id=data.category_id,
            check_in=data.check_in_date,
            check_out=data.check_out_date,
            hotel_id=hotel_id,
            sellable_product_id=data.sellable_product_id,
            rate_plan_id=data.rate_plan_id,
            tax_policy_id=data.tax_policy_id,
            pricing_channel_code=data.pricing_channel_code,
            pricing_payment_method=data.pricing_payment_method,
            guest_scope=data.guest_scope,
            target_currency=data.target_currency,
            occupancy=data.num_adults + data.num_children,
            guest_id=data.guest_id,
            company_id=data.company_id,
        )
        if company is not None:
            pricing = _apply_corporate_pricing(db, hotel_id=hotel_id, pricing=pricing, company=company, explicit_total=None)
    pricing = _apply_custom_deposit_amount(pricing, data.deposit_amount)
    pricing_revision = build_pricing_revision(
        db,
        hotel_id=hotel_id,
        category_id=data.category_id,
        check_in=data.check_in_date,
        check_out=data.check_out_date,
        sellable_product_id=data.sellable_product_id,
        rate_plan_id=data.rate_plan_id,
        tax_policy_id=data.tax_policy_id,
        pricing_channel_code=data.pricing_channel_code,
        pricing_payment_method=normalize_pricing_payment_method(data.pricing_payment_method),
        guest_scope=data.guest_scope,
        target_currency=data.target_currency,
        occupancy=data.num_adults + data.num_children,
    )
    _validate_quote_token_for_reservation(
        db,
        data=data,
        hotel_id=hotel_id,
        pricing=pricing,
        revision=pricing_revision,
    )
    pricing.pricing_snapshot = _with_pricing_revision(pricing.pricing_snapshot, pricing_revision)

    # Waitlist / overbooking (v72 §9): a wait-listed reservation is created with
    # room_id=None and the denormalized flag set, so availability queries never
    # count it as occupying a room. The caller (or §9.1 overbooking path) is
    # responsible for requesting waitlist placement explicitly.
    is_wait_listed = bool(getattr(data, "is_wait_listed", False))
    wait_list_reason = getattr(data, "wait_list_reason", None)

    room_id = data.room_id
    if room_id:
        room = (
            db.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .enable_eagerloads(False)
            .with_for_update()
            .first()
        )
        if not room:
            raise ReservationError(f"Room with id={room_id} not found")
        if room.category_id != data.category_id:
            raise ReservationError(
                f"Room {room.room_number} belongs to category {room.category_id}, "
                f"not {data.category_id}"
            )
        if not check_room_availability(
            db,
            room_id,
            data.check_in_date,
            data.check_out_date,
            hotel_id=hotel_id,
        ):
            raise ReservationError(
                f"Room {room.room_number} is not available for the requested dates"
            )
    elif is_wait_listed:
        # Overbooking accepted / explicit waitlist placement: no room is assigned.
        room_id = None
    else:
        available = find_available_rooms(
            db,
            data.category_id,
            data.check_in_date,
            data.check_out_date,
            hotel_id=hotel_id,
            lock_for_update=True,
        )
        if not available:
            config = db.get(HotelConfiguration, hotel_id)
            if config is not None and config.allow_overbooking:
                room_id = None
                is_wait_listed = True
                wait_list_reason = wait_list_reason or "Overbooking permitido por la configuración del hotel"
            else:
                raise ReservationError(
                    f"No rooms available in category {category.name} for the requested dates"
                )
        else:
            room_id = available[0].id

    # Corporate deferred billing (v72 §3.5): "a cobrar" / pago a N días.
    # The reservation is settled later (off-system invoicing), so we flag it as
    # deferred and compute a due date = check_out + company.deferred_days.
    settlement_status = (
        "not_applicable" if data.source == ReservationSourceEnum.DIRECT else "pending"
    )
    settlement_due_date = None
    if company is not None and company.payment_deferred:
        settlement_status = "deferred"
        deferred_days = int(company.deferred_days or 0)
        settlement_due_date = data.check_out_date + timedelta(days=deferred_days)

    # Revalidate inside the same transaction, right before persisting: a
    # restriction created after the quote (or after this call started) must
    # still block the write. See app/services/guest_restriction_service.py.
    from app.services.guest_restriction_service import record_restriction_override, validate_no_active_restriction

    overridden_restriction = validate_no_active_restriction(
        db,
        hotel_id=hotel_id,
        guest_id=data.guest_id,
        restriction_override=data.restriction_override,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )

    confirmation_code = generate_confirmation_code()
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel_id,
        guest_id=data.guest_id,
        room_id=room_id,
        category_id=data.category_id,
        company_id=data.company_id,
        sellable_product_id=pricing.sellable_product_id,
        rate_plan_id=pricing.rate_plan_id,
        tax_policy_id=pricing.tax_policy_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        total_amount=pricing.total_amount,
        amount_paid=0.0,
        deposit_amount=pricing.deposit_amount,
        subtotal_amount=pricing.subtotal_amount,
        tax_amount=pricing.tax_amount,
        fee_amount=pricing.fee_amount,
        commission_amount=pricing.commission_amount,
        net_amount=pricing.net_amount,
        currency_code=pricing.currency_code,
        fx_rate_snapshot=pricing.fx_rate_snapshot,
        status=ReservationStatusEnum.PENDING,
        source=data.source,
        channel_code=channel_code,
        external_id=data.external_id,
        num_adults=data.num_adults,
        num_children=data.num_children,
        is_wait_listed=is_wait_listed,
        wait_list_reason=wait_list_reason if is_wait_listed else None,
        notes=data.notes,
        mobility_restriction=data.mobility_restriction,
        pricing_snapshot=pricing.pricing_snapshot,
        allocation_locked=bool(company and (company.requires_signature or company.payment_deferred)),
        requires_manual_review=bool(company and (company.requires_signature or company.payment_deferred)),
        payment_collection_model="hotel_collect" if data.source == ReservationSourceEnum.DIRECT else "unknown",
        settlement_status=settlement_status,
        settlement_due_date=settlement_due_date,
    )
    db.add(reservation)
    db.flush()
    if overridden_restriction is not None:
        record_restriction_override(
            db,
            hotel_id=hotel_id,
            actor_user_id=actor_user_id,
            restriction=overridden_restriction,
            reason=data.restriction_override.reason,
            reservation_id=reservation.id,
        )
    _invalidate_availability_cache(hotel_id)
    _touch_facts(db, hotel_id, reservation.check_in_date, reservation.check_out_date)
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.created",
        title=f"New reservation {reservation.confirmation_code}", dedupe_suffix="created",
    )
    return reservation


def register_company_settlement(
    db: Session,
    reservation: Reservation,
    hotel_id: int,
    *,
    actor_user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Reservation:
    """Register the deferred corporate collection (v72 §3.5).

    Transitions settlement_status -> 'settled' for a company reservation that was
    created with payment_deferred. Idempotent: re-registering a settled reservation
    is a no-op. Audited via audit_log_service (best-effort).
    """
    if reservation.hotel_id != hotel_id:
        raise ReservationError("Cross-hotel settlement is not allowed")
    if reservation.company_id is None:
        raise ReservationError("Solo las reservas de empresa admiten cobro diferido")
    if reservation.settlement_status == "settled":
        return reservation
    if reservation.settlement_status not in {"deferred", "pending"}:
        raise ReservationError(
            f"La reserva no tiene un cobro diferido pendiente (settlement_status={reservation.settlement_status})"
        )

    before = {"settlement_status": reservation.settlement_status}
    reservation.settlement_status = "settled"
    db.flush()

    try:
        from app.services.audit_log_service import safe_create_audit_log

        safe_create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action="update",
            actor_user_id=actor_user_id,
            payload_before=before,
            payload_after={
                "settlement_status": reservation.settlement_status,
                "notes": notes,
            },
        )
    except Exception:  # pragma: no cover - audit is best-effort
        logging.getLogger(__name__).exception("settlement audit failed")
    return reservation


def transition_reservation_status(
    db: Session,
    reservation: Reservation,
    new_status: ReservationStatusEnum,
    hotel_id: Optional[int] = None,
    *,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    changed_by_user_id: Optional[int] = None,
) -> Reservation:
    """
    Transition a reservation to a new status following the state machine rules.
    Raises ReservationError if the transition is invalid.
    """
    # A newly-created Reservation may have room_id set while its relationship
    # is not populated yet. Its own tenant key is the authoritative fallback.
    resolved_hotel_id = _resolve_hotel_id(
        hotel_id or reservation.hotel_id,
        room=reservation.room if hasattr(reservation, "room") else None,
    )
    if reservation.hotel_id not in (None, resolved_hotel_id):
        raise ReservationError("Cross-hotel status transition is not allowed")
    reservation.hotel_id = reservation.hotel_id or resolved_hotel_id
    if not reservation.can_transition_to(new_status):
        raise ReservationError(
            f"Cannot transition from {reservation.status.value} to {new_status.value}"
        )
    previous_status = reservation.status
    reservation.status = new_status
    db.add(
        ReservationStatusHistory(
            hotel_id=reservation.hotel_id,
            reservation_id=reservation.id,
            from_status=previous_status.value if previous_status else None,
            to_status=new_status.value,
            reason_code=reason_code,
            notes=notes,
            changed_by_user_id=changed_by_user_id,
        )
    )
    db.flush()
    _invalidate_availability_cache(reservation.hotel_id)
    _touch_facts(db, reservation.hotel_id, reservation.check_in_date, reservation.check_out_date)
    if new_status == ReservationStatusEnum.CANCELLED:
        _notify_reservation_event(
            db, hotel_id=reservation.hotel_id, reservation=reservation, event_type="reservation.cancelled",
            title=f"Reservation {reservation.confirmation_code} cancelled", dedupe_suffix=f"cancelled:{reservation.version}",
        )
    return reservation


def list_reservations(
    db: Session,
    hotel_id: int,
    status_filter: str = "",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    order: str = "recent",
    *,
    context: "AuthContext | None" = None,
) -> list[_ReservationListProjection]:
    if context is not None and context.hotel_id != hotel_id:
        raise ValueError("El contexto autenticado no pertenece al hotel solicitado")
    query = visible_reservations(db, context) if context is not None else active_reservations(db, hotel_id)
    # Keep the tenant predicate owned by active/visible_reservations and load
    # only fields needed by ReservationRead. Hydrating Reservation would also
    # trigger six joined relationships plus two selectin loaders.
    query = query.outerjoin(
        Guest,
        (Guest.id == Reservation.guest_id) & (Guest.hotel_id == hotel_id),
    )
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    if from_date:
        query = query.filter(Reservation.check_in_date >= from_date)
    if to_date:
        query = query.filter(Reservation.check_out_date <= to_date)
    if search:
        term = search.strip()
        if term:
            # Global reservation search (B1 header search): match confirmation
            # code or guest last name. Guest is joined scoped to the same
            # hotel_id so a search can never leak a match from another hotel.
            like = f"%{term}%"
            query = query.filter(
                (Reservation.confirmation_code.ilike(like)) | (Guest.last_name.ilike(like)),
            )
    # A2: "recent" (created_at DESC, id DESC) is the new default -- dashboards
    # and any "recent activity" view want newest-first. "check_in" preserves
    # the pre-A2 ordering (check_in_date ASC) for operational views that
    # already assume arrivals are sorted by stay date, not creation date.
    if order == "check_in":
        query = query.order_by(Reservation.check_in_date.asc())
    else:
        query = query.order_by(Reservation.created_at.desc(), Reservation.id.desc())
    rows = query.with_entities(
        Reservation.id,
        Reservation.hotel_id,
        Reservation.confirmation_code,
        Reservation.guest_id,
        Reservation.room_id,
        Reservation.category_id,
        Reservation.company_id,
        Reservation.sellable_product_id,
        Reservation.rate_plan_id,
        Reservation.tax_policy_id,
        Reservation.check_in_date,
        Reservation.check_out_date,
        Reservation.actual_check_in,
        Reservation.actual_check_out,
        Reservation.total_amount,
        Reservation.amount_paid,
        Reservation.deposit_amount,
        Reservation.subtotal_amount,
        Reservation.tax_amount,
        Reservation.fee_amount,
        Reservation.commission_amount,
        Reservation.net_amount,
        Reservation.currency_code,
        Reservation.fx_rate_snapshot,
        Reservation.quoted_amount_ars,
        Reservation.quoted_amount_usd,
        Reservation.status,
        Reservation.source,
        Reservation.source_provider_code,
        Reservation.external_id,
        Reservation.external_confirmation_code,
        Reservation.payment_collection_model,
        Reservation.settlement_status,
        Reservation.num_adults,
        Reservation.num_children,
        Reservation.notes,
        Reservation.created_at,
        Reservation.updated_at,
        Reservation.allocation_status,
        Reservation.requires_manual_review,
        Reservation.mobility_restriction,
        Reservation.is_wait_listed,
        Reservation.wait_list_reason,
        Reservation.version,
        Guest.id.label("guest_profile_id"),
        Guest.first_name.label("guest_first_name"),
        Guest.last_name.label("guest_last_name"),
        Guest.document_type.label("guest_document_type"),
        Guest.document_number.label("guest_document_number"),
    ).offset(max(skip, 0)).limit(max(limit, 1)).all()

    reservation_ids = [row.id for row in rows]
    additional_by_reservation: dict[int, list[_ReservationGuestProjection]] = {}
    if reservation_ids:
        additional_rows = (
            db.query(
                reservation_additional_guests.c.reservation_id,
                Guest.id,
                Guest.first_name,
                Guest.last_name,
                Guest.document_type,
                Guest.document_number,
            )
            .join(
                Guest,
                (Guest.id == reservation_additional_guests.c.guest_id)
                & (Guest.hotel_id == hotel_id),
            )
            .filter(reservation_additional_guests.c.reservation_id.in_(reservation_ids))
            .order_by(
                reservation_additional_guests.c.reservation_id.asc(),
                Guest.id.asc(),
            )
            .all()
        )
        for row in additional_rows:
            additional_by_reservation.setdefault(row.reservation_id, []).append(
                _ReservationGuestProjection(
                    id=row.id,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    document_type=row.document_type,
                    document_number=row.document_number,
                )
            )

    return [
        _ReservationListProjection(
            id=row.id,
            hotel_id=row.hotel_id,
            confirmation_code=row.confirmation_code,
            guest_id=row.guest_id,
            guest=(
                _ReservationGuestProjection(
                    id=row.guest_profile_id,
                    first_name=row.guest_first_name,
                    last_name=row.guest_last_name,
                    document_type=row.guest_document_type,
                    document_number=row.guest_document_number,
                )
                if row.guest_profile_id is not None
                else None
            ),
            room_id=row.room_id,
            category_id=row.category_id,
            company_id=row.company_id,
            sellable_product_id=row.sellable_product_id,
            rate_plan_id=row.rate_plan_id,
            tax_policy_id=row.tax_policy_id,
            check_in_date=row.check_in_date,
            check_out_date=row.check_out_date,
            actual_check_in=row.actual_check_in,
            actual_check_out=row.actual_check_out,
            total_amount=row.total_amount,
            amount_paid=row.amount_paid,
            deposit_amount=row.deposit_amount,
            subtotal_amount=row.subtotal_amount,
            tax_amount=row.tax_amount,
            fee_amount=row.fee_amount,
            commission_amount=row.commission_amount,
            net_amount=row.net_amount,
            currency_code=row.currency_code,
            fx_rate_snapshot=row.fx_rate_snapshot,
            quoted_amount_ars=row.quoted_amount_ars,
            quoted_amount_usd=row.quoted_amount_usd,
            status=row.status,
            source=row.source,
            source_provider_code=row.source_provider_code,
            external_id=row.external_id,
            external_confirmation_code=row.external_confirmation_code,
            payment_collection_model=row.payment_collection_model,
            settlement_status=row.settlement_status,
            num_adults=row.num_adults,
            num_children=row.num_children,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
            allocation_status=row.allocation_status,
            requires_manual_review=row.requires_manual_review,
            mobility_restriction=row.mobility_restriction,
            is_wait_listed=row.is_wait_listed,
            wait_list_reason=row.wait_list_reason,
            version=row.version,
            additional_guests=additional_by_reservation.get(row.id, []),
        )
        for row in rows
    ]


def get_occupancy_grid(
    db: Session,
    hotel_id: int,
    date_from: date,
    date_to: date,
    *,
    context: "AuthContext | None" = None,
) -> dict:
    """B2: occupancy grid data for the planilla — rooms x days.

    Explicit-column query throughout: Room/RoomCategory/Reservation all
    carry lazy="selectin" relationships (see A2's fan-out fix) that a plain
    ORM `.query(Reservation).all()` would trigger per-row. This stays at a
    fixed, small query count regardless of how many rooms/reservations exist
    (verified by tests/test_occupancy_grid.py's query-count test).
    """
    room_rows = db.execute(
        select(
            Room.id,
            Room.room_number,
            Room.floor,
            Room.category_id,
            RoomCategory.name.label("category_name"),
            Room.status,
        )
        .join(RoomCategory, RoomCategory.id == Room.category_id)
        .where(
            Room.hotel_id == hotel_id,
            RoomCategory.hotel_id == hotel_id,
            Room.deleted_at.is_(None),
        )
        .order_by(RoomCategory.name.asc(), Room.room_number.asc())
    ).all()

    # Overlap test: a stay overlaps [date_from, date_to) unless it ends at/
    # before date_from or starts at/after date_to. Cancelled/deleted excluded.
    if context is not None and context.hotel_id != hotel_id:
        raise ValueError("El contexto autenticado no pertenece al hotel solicitado")
    reservation_scope = (
        visible_reservations(db, context)
        if context is not None
        else active_reservations(db, hotel_id)
    )
    reservation_rows = (
        reservation_scope
        .join(Guest, Guest.id == Reservation.guest_id)
        .with_entities(
            Reservation.id,
            Reservation.room_id,
            Reservation.confirmation_code,
            Reservation.check_in_date,
            Reservation.check_out_date,
            Reservation.status,
            Reservation.num_adults,
            Reservation.num_children,
            Reservation.total_amount,
            Reservation.amount_paid,
            Guest.first_name,
            Guest.last_name,
        )
        .filter(
            Guest.hotel_id == hotel_id,
            Reservation.status != ReservationStatusEnum.CANCELLED,
            Reservation.check_in_date < date_to,
            Reservation.check_out_date > date_from,
        )
        .all()
    )

    reservation_ids = [row.id for row in reservation_rows]
    # Same bulk pattern as operational_report_service.daily_report: confirmed
    # transactions win, materialized amount_paid is only the fallback for
    # legacy rows with no ledger entries at all.
    paid_by_reservation = completed_paid_amounts_by_reservation(db, hotel_id, reservation_ids)
    for row in reservation_rows:
        paid_by_reservation.setdefault(row.id, Decimal(row.amount_paid or 0))
    adjustments_by_reservation = billing_adjustment_totals_by_reservation(db, hotel_id, reservation_ids)

    reservations: list[dict] = []
    unassigned: list[dict] = []
    for row in reservation_rows:
        balance = max(
            Decimal("0.00"),
            Decimal(row.total_amount or 0)
            + adjustments_by_reservation.get(row.id, Decimal("0"))
            - paid_by_reservation.get(row.id, Decimal("0")),
        )
        item = {
            "id": row.id,
            "room_id": row.room_id,
            "confirmation_code": row.confirmation_code,
            "check_in_date": row.check_in_date,
            "check_out_date": row.check_out_date,
            "status": row.status.value,
            "guest_name": f"{row.first_name} {row.last_name}",
            "num_adults": row.num_adults,
            "num_children": row.num_children,
            "operational_balance_due": float(balance),
        }
        (unassigned if row.room_id is None else reservations).append(item)

    # ends_at nullable = indefinite; the frontend clips indefinite blocks to
    # the requested window (date_to) for display, this returns the raw value.
    blocks = [
        {
            "room_id": block.room_id,
            "starts_at": block.starts_at,
            "ends_at": block.ends_at,
            "reason_code": block.reason_code.value,
        }
        for block in list_active_blocks(db, hotel_id=hotel_id, start_date=date_from, end_date=date_to)
    ]

    rooms = [
        {
            "id": row.id,
            "room_number": row.room_number,
            "floor": row.floor,
            "category_id": row.category_id,
            "category_name": row.category_name,
            "status": row.status.value,
        }
        for row in room_rows
    ]

    return {"rooms": rooms, "reservations": reservations, "unassigned": unassigned, "blocks": blocks}


def get_reservation_by_id(db: Session, reservation_id: int, hotel_id: int) -> Reservation | None:
    return (
        active_reservations(db, hotel_id)
        .filter(Reservation.id == reservation_id)
        .first()
    )


def update_reservation_fields(
    db: Session,
    reservation: Reservation,
    data: ReservationUpdate,
    hotel_id: Optional[int] = None,
    *,
    changed_by_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    room_move_reason_code: Optional[str] = None,
    room_move_notes: Optional[str] = None,
    client_version: Optional[int] = None,
) -> Reservation:
    # Optimistic locking — reject stale writes (v72 security-audit §6)
    if client_version is not None and reservation.version != client_version:
        raise ReservationError(
            f"Reservation was modified concurrently (expected version {client_version}, "
            f"got {reservation.version}). Reload and retry."
        )

    hotel_id = _resolve_hotel_id(hotel_id, room=reservation.room if hasattr(reservation, "room") else None)

    # Reject-before-mutate: revalidate the guest restriction before touching
    # any other field, so a blocked update never partially persists (e.g.
    # `notes`) ahead of raising.
    from app.services.guest_restriction_service import record_restriction_override, validate_no_active_restriction

    overridden_restriction = validate_no_active_restriction(
        db,
        hotel_id=hotel_id,
        guest_id=reservation.guest_id,
        restriction_override=data.restriction_override,
        actor_user_id=changed_by_user_id,
        actor_role=actor_role,
    )
    if overridden_restriction is not None:
        record_restriction_override(
            db,
            hotel_id=hotel_id,
            actor_user_id=changed_by_user_id,
            restriction=overridden_restriction,
            reason=data.restriction_override.reason,
            reservation_id=reservation.id,
        )

    update_data = data.model_dump(exclude_unset=True)
    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date

    new_ci = update_data.get("check_in_date", reservation.check_in_date)
    new_co = update_data.get("check_out_date", reservation.check_out_date)

    if "num_adults" in update_data or "num_children" in update_data:
        category_query = db.query(RoomCategory).filter(RoomCategory.id == reservation.category_id)
        if hotel_id is not None:
            category_query = category_query.filter(RoomCategory.hotel_id == hotel_id)
        category = category_query.first()
        if not category:
            raise ReservationError(f"Room category with id={reservation.category_id} not found")
        _validate_reservation_occupancy(
            category,
            update_data.get("num_adults", reservation.num_adults),
            update_data.get("num_children", reservation.num_children),
        )

    if "check_in_date" in update_data or "check_out_date" in update_data:
        if new_co <= new_ci:
            raise ReservationError("Check-out must be after check-in")
        if reservation.room_id and not check_room_availability(
            db,
            reservation.room_id,
            new_ci,
            new_co,
            hotel_id=hotel_id,
            exclude_reservation_id=reservation.id,
        ):
            raise ReservationError("Room is not available for the new dates")
        pricing = calculate_reservation_pricing(
            db,
            category_id=reservation.category_id,
            check_in=new_ci,
            check_out=new_co,
            hotel_id=hotel_id,
            sellable_product_id=reservation.sellable_product_id,
            rate_plan_id=reservation.rate_plan_id,
            tax_policy_id=reservation.tax_policy_id,
            pricing_channel_code=reservation.source_provider_code or reservation.source.value,
            guest_scope="all",
            target_currency=reservation.currency_code,
            occupancy=reservation.num_adults + reservation.num_children,
        )
        reservation.check_in_date = new_ci
        reservation.check_out_date = new_co
        _apply_pricing_result_to_reservation(reservation, pricing)

    if "room_id" in update_data and update_data["room_id"] is not None:
        previous_room_id = reservation.room_id
        new_room = db.query(Room).filter(
            Room.id == update_data["room_id"],
            Room.hotel_id == hotel_id,
        ).enable_eagerloads(False).with_for_update().first()
        if not new_room:
            raise ReservationError("Room not found")
        if new_room.category_id != reservation.category_id:
            raise ReservationError("New room must be in the same category")
        if not check_room_availability(
            db,
            new_room.id,
            reservation.check_in_date,
            reservation.check_out_date,
            hotel_id=hotel_id,
            exclude_reservation_id=reservation.id,
        ):
            raise ReservationError("New room is not available for these dates")
        reservation.room_id = update_data["room_id"]
        if previous_room_id != reservation.room_id:
            # A room selected by staff through the edit endpoint is a manual
            # decision and must remain stable during later reoptimization.
            reservation.allocation_locked = True
            from app.models.operations import RoomMoveEvent, RoomMoveTypeEnum

            db.add(
                RoomMoveEvent(
                    hotel_id=reservation.hotel_id,
                    reservation_id=reservation.id,
                    from_room_id=previous_room_id,
                    to_room_id=reservation.room_id,
                    move_type=RoomMoveTypeEnum.MANUAL_MOVE,
                    reason_code=room_move_reason_code,
                    notes=room_move_notes,
                    created_by_user_id=changed_by_user_id,
                )
            )

    for field in ("num_adults", "num_children", "notes", "mobility_restriction"):
        if field in update_data:
            setattr(reservation, field, update_data[field])

    reservation.version = (reservation.version or 0) + 1
    db.flush()
    _invalidate_availability_cache(hotel_id)
    # Touch the union of old+new stay range: a date/room change can move a
    # reservation out of a window that was already materialized, and the
    # narrow self-heal on read only fires for windows with zero rows.
    _touch_facts(
        db,
        hotel_id,
        min(original_check_in, reservation.check_in_date),
        max(original_check_out, reservation.check_out_date),
    )
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.updated",
        title=f"Reservation {reservation.confirmation_code} updated", dedupe_suffix=f"updated:{reservation.version}",
    )
    return reservation


def assert_reservation_version(reservation: Reservation, client_version: int | None) -> None:
    if client_version is None:
        raise ReservationError("client_version is required for this reservation mutation")
    if reservation.version != client_version:
        raise ReservationError(
            f"Reservation was modified concurrently (expected version {client_version}, "
            f"got {reservation.version}). Reload and retry."
        )


def mark_reservation_no_show(
    db: Session,
    reservation: Reservation,
    *,
    hotel_id: int,
    client_version: int,
    changed_by_user_id: int | None = None,
    notes: str | None = None,
) -> Reservation:
    """Mark a reservation no-show without creating any automatic charge."""
    if reservation.hotel_id != hotel_id:
        raise ReservationError("Reservation does not belong to the active hotel")
    assert_reservation_version(reservation, client_version)
    if reservation.status in (
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationError(f"Cannot mark no-show from status '{reservation.status.value}'")

    previous_status = reservation.status
    reservation.status = ReservationStatusEnum.NO_SHOW
    reservation.outcome = ReservationOutcomeEnum.NO_SHOW
    reservation.no_show_confirmed_at = datetime.now(timezone.utc)
    reservation.no_show_policy_applied = ReservationNoShowPolicyAppliedEnum.NONE
    if notes:
        reservation.notes = ((reservation.notes or "") + f"\n[NO-SHOW] {notes}").strip()
    db.add(
        ReservationStatusHistory(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            from_status=previous_status.value if previous_status else None,
            to_status=ReservationStatusEnum.NO_SHOW.value,
            reason_code="no_show",
            notes="Marked no-show without automatic charge",
            changed_by_user_id=changed_by_user_id,
        )
    )
    reservation.version = (reservation.version or 0) + 1
    db.flush()
    _invalidate_availability_cache(hotel_id)
    _touch_facts(db, hotel_id, reservation.check_in_date, reservation.check_out_date)
    _notify_reservation_event(
        db, hotel_id=hotel_id, reservation=reservation, event_type="reservation.no_show",
        title=f"Reservation {reservation.confirmation_code} marked no-show", dedupe_suffix=f"no_show:{reservation.version}",
    )
    return reservation


def _resolve_reservation_commercial_context(
    db: Session,
    *,
    hotel_id: int,
    category: RoomCategory,
    sellable_product_id: int | None,
    rate_plan_id: int | None,
    tax_policy_id: int | None,
) -> tuple[SellableProduct | None, RatePlan | None, TaxPolicy | None]:
    sellable_product = None
    rate_plan = None
    tax_policy = None

    if rate_plan_id is not None:
        rate_plan = (
            db.query(RatePlan)
            .filter(RatePlan.id == rate_plan_id, RatePlan.hotel_id == hotel_id, RatePlan.is_active == True)
            .first()
        )
        if not rate_plan:
            raise ReservationError("Rate plan does not belong to the active hotel")
        sellable_product = rate_plan.sellable_product

    if sellable_product_id is not None:
        sellable_product = (
            db.query(SellableProduct)
            .filter(
                SellableProduct.id == sellable_product_id,
                SellableProduct.hotel_id == hotel_id,
                SellableProduct.is_active == True,
            )
            .first()
        )
        if not sellable_product:
            raise ReservationError("Sellable product does not belong to the active hotel")
        if rate_plan and rate_plan.sellable_product_id != sellable_product.id:
            raise ReservationError("Rate plan does not belong to the selected sellable product")

    if sellable_product is None:
        inferred_products = (
            db.query(SellableProduct)
            .filter(
                SellableProduct.hotel_id == hotel_id,
                SellableProduct.primary_room_category_id == category.id,
                SellableProduct.is_active == True,
            )
            .order_by(SellableProduct.sort_order.asc(), SellableProduct.id.asc())
            .all()
        )
        if len(inferred_products) == 1:
            sellable_product = inferred_products[0]

    if rate_plan is None and sellable_product is not None:
        inferred_rate_plans = (
            db.query(RatePlan)
            .filter(
                RatePlan.hotel_id == hotel_id,
                RatePlan.sellable_product_id == sellable_product.id,
                RatePlan.is_active == True,
            )
            .order_by(RatePlan.id.asc())
            .all()
        )
        if len(inferred_rate_plans) == 1:
            rate_plan = inferred_rate_plans[0]

    if sellable_product and sellable_product.primary_room_category_id not in (None, category.id):
        compatible = any(item.room_category_id == category.id for item in sellable_product.compatibilities)
        if not compatible:
            raise ReservationError("Sellable product is not compatible with the requested category")

    if tax_policy_id is not None:
        tax_policy = (
            db.query(TaxPolicy)
            .filter(TaxPolicy.id == tax_policy_id, TaxPolicy.hotel_id == hotel_id, TaxPolicy.is_active == True)
            .first()
        )
        if not tax_policy:
            raise ReservationError("Tax policy does not belong to the active hotel")
        if rate_plan is None:
            raise ReservationError("A rate plan is required to apply a tax policy to the reservation")

    return sellable_product, rate_plan, tax_policy


def _pricing_result_from_quote(
    db: Session,
    *,
    hotel_id: int,
    nights: int,
    check_in: date,
    quote: StayPricingQuote,
    sellable_product: SellableProduct | None,
    rate_plan: RatePlan,
    tax_policy: TaxPolicy | None,
    pricing_channel_code: str,
    guest_scope: str,
) -> ReservationPricingResult:
    nightly_rate = round(quote.gross_total / nights, 2) if nights > 0 else 0.0
    deposit_amount = _compute_deposit_amount(db, hotel_id=hotel_id, gross_total=quote.gross_total)
    snapshot = {
        "pricing_source": "rate_plan_quote",
        "rate_plan_id": rate_plan.id,
        "sellable_product_id": sellable_product.id if sellable_product else None,
        "tax_policy_id": tax_policy.id if tax_policy else None,
        "pricing_channel_code": pricing_channel_code,
        "guest_scope": guest_scope,
        "tax_breakdown": quote.tax_breakdown,
        "breakdown": [
            {
                "date": (check_in + timedelta(days=offset)).isoformat(),
                "price": quote.nightly_amount,
            }
            for offset in range(nights)
        ],
    }
    return ReservationPricingResult(
        nights=nights,
        nightly_rate=nightly_rate,
        total_amount=quote.gross_total,
        deposit_amount=deposit_amount,
        subtotal_amount=quote.subtotal_amount,
        tax_amount=quote.tax_amount,
        fee_amount=quote.fee_amount,
        commission_amount=quote.commission_amount,
        net_amount=quote.net_amount,
        currency_code=quote.output_currency,
        fx_rate_snapshot=quote.fx_rate_snapshot,
        pricing_source="rate_plan_quote",
        sellable_product_id=sellable_product.id if sellable_product else None,
        rate_plan_id=rate_plan.id,
        tax_policy_id=tax_policy.id if tax_policy else None,
        pricing_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)),
    )


def _get_hotel_default_currency(db: Session, *, hotel_id: int) -> str:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    currency_code = getattr(config, "default_currency", None)
    return str(currency_code or "ARS").strip().upper()[:3] or "ARS"


def _apply_pricing_result_to_reservation(reservation: Reservation, pricing: ReservationPricingResult) -> None:
    reservation.sellable_product_id = pricing.sellable_product_id
    reservation.rate_plan_id = pricing.rate_plan_id
    reservation.tax_policy_id = pricing.tax_policy_id
    reservation.total_amount = pricing.total_amount
    reservation.subtotal_amount = pricing.subtotal_amount
    reservation.tax_amount = pricing.tax_amount
    reservation.fee_amount = pricing.fee_amount
    reservation.commission_amount = pricing.commission_amount
    reservation.net_amount = pricing.net_amount
    reservation.deposit_amount = pricing.deposit_amount
    reservation.currency_code = pricing.currency_code
    reservation.fx_rate_snapshot = pricing.fx_rate_snapshot
    reservation.pricing_snapshot = pricing.pricing_snapshot


def _compute_deposit_amount(db: Session, *, hotel_id: int, gross_total) -> float:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    deposit_pct = config.deposit_percentage if config else 30.0
    return round(float(gross_total) * (deposit_pct / 100.0), 2)


def _with_pricing_revision(snapshot: str | None, revision: str) -> str:
    try:
        decoded = json.loads(snapshot or "{}")
        if not isinstance(decoded, dict):
            decoded = {}
    except json.JSONDecodeError:
        decoded = {}
    decoded["pricing_revision"] = revision
    return json.dumps(decoded, ensure_ascii=True, sort_keys=True, default=str)


def _validate_quote_token_for_reservation(
    db: Session,
    *,
    data: ReservationCreate,
    hotel_id: int,
    pricing: ReservationPricingResult,
    revision: str,
) -> None:
    if not data.quote_token:
        return
    try:
        payload = verify_quote_token(data.quote_token)
    except QuoteTokenError as exc:
        raise ReservationError(str(exc)) from exc

    expected = {
        "hotel_id": hotel_id,
        "category_id": data.category_id,
        "check_in_date": data.check_in_date.isoformat(),
        "check_out_date": data.check_out_date.isoformat(),
        "sellable_product_id": data.sellable_product_id,
        "rate_plan_id": data.rate_plan_id,
        "tax_policy_id": data.tax_policy_id,
        "pricing_channel_code": data.pricing_channel_code,
        "pricing_payment_method": normalize_pricing_payment_method(data.pricing_payment_method),
        "guest_scope": data.guest_scope,
        "target_currency": data.target_currency,
        "occupancy": data.num_adults + data.num_children,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise ReservationError("La cotización no coincide con los datos de la reserva")
    if payload.get("pricing_revision") != revision:
        raise ReservationError("La cotización venció porque cambió la tarifa; recotizá antes de reservar")

    try:
        quoted_total = Decimal(str(payload.get("total_amount")))
        quoted_currency = str(payload.get("currency_code") or "").upper()
        calculated_total = Decimal(str(pricing.total_amount))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ReservationError("La cotización contiene importes inválidos") from exc
    if quoted_currency != str(pricing.currency_code or "").upper() or abs(quoted_total - calculated_total) > Decimal("0.01"):
        raise ReservationError("La cotización no coincide con el total actual")
