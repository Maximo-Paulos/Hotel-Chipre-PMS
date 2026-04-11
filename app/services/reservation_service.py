"""
Reservation Service ? Core booking logic.
Handles creation, state transitions, confirmation code generation, and availability checks.
Uses pessimistic locking to prevent race conditions (overbooking).
"""
import json
import string
import random
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.commercial import RatePlan, SellableProduct, TaxPolicy
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.hotel_config import HotelConfiguration
from app.models.pricing import CategoryPricing
from app.models.operations import ReservationStatusHistory
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.pricing_policy_service import PricingPolicyError, StayPricingQuote, quote_rate_plan_stay


class ReservationError(Exception):
    """Custom exception for reservation business logic errors."""
    pass


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
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int | None = None,
) -> ReservationPricingResult:
    category = db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
    if not category:
        raise ReservationError(f"Room category with id={category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")

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

    if rate_plan is not None:
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
            quote=quote,
            sellable_product=sellable_product,
            rate_plan=rate_plan,
            tax_policy=tax_policy,
            pricing_channel_code=pricing_channel_code or "direct",
            guest_scope=guest_scope,
        )

    pricing = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    nightly_rate = pricing.price_cash if pricing and pricing.price_cash is not None else category.base_price_per_night
    total_amount = round(nightly_rate * nights, 2)
    deposit_amount = _compute_deposit_amount(db, hotel_id=hotel_id, gross_total=total_amount)
    snapshot = {
        "pricing_source": "category_legacy",
        "category_id": category.id,
        "nightly_rate": nightly_rate,
        "nights": nights,
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
        pricing_source="category_legacy",
        sellable_product_id=sellable_product.id if sellable_product else None,
        rate_plan_id=None,
        tax_policy_id=tax_policy.id if tax_policy else None,
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
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise ReservationError(f"Room with id={room_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, room=room)
    if room.hotel_id != hotel_id:
        raise ReservationError("Room does not belong to the active hotel")

    query = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.hotel_id == hotel_id,
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
) -> list[Room]:
    """
    Find all rooms of a given category that are available in the date range.
    Only considers rooms that are active and not in maintenance/blocked.
    """
    category = db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
    if not category:
        raise ReservationError(f"Room category with id={category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")

    candidate_rooms = db.query(Room).filter(
        Room.category_id == category_id,
        Room.hotel_id == hotel_id,
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    ).all()

    available = []
    for room in candidate_rooms:
        if check_room_availability(
            db,
            room.id,
            check_in,
            check_out,
            hotel_id=hotel_id,
            exclude_reservation_id=exclude_reservation_id,
        ):
            available.append(room)

    return available


def create_reservation(db: Session, data: ReservationCreate, hotel_id: Optional[int] = None) -> Reservation:
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
    guest = db.query(Guest).filter(Guest.id == data.guest_id).first()
    if not guest:
        raise ReservationError(f"Guest with id={data.guest_id} not found")

    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id).first()
    if not category:
        raise ReservationError(f"Room category with id={data.category_id} not found")

    hotel_id = _resolve_hotel_id(hotel_id, category)
    if guest.hotel_id != hotel_id:
        raise ReservationError("Guest does not belong to the active hotel")
    if category.hotel_id != hotel_id:
        raise ReservationError("Room category does not belong to the active hotel")

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
        guest_scope=data.guest_scope,
        target_currency=data.target_currency,
        occupancy=data.num_adults + data.num_children,
    )

    room_id = data.room_id
    if room_id:
        room = (
            db.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
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
    else:
        available = find_available_rooms(
            db,
            data.category_id,
            data.check_in_date,
            data.check_out_date,
            hotel_id=hotel_id,
        )
        if not available:
            raise ReservationError(
                f"No rooms available in category {category.name} for the requested dates"
            )
        room_id = available[0].id

    confirmation_code = generate_confirmation_code()
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel_id,
        guest_id=data.guest_id,
        room_id=room_id,
        category_id=data.category_id,
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
        external_id=data.external_id,
        num_adults=data.num_adults,
        num_children=data.num_children,
        notes=data.notes,
        pricing_snapshot=pricing.pricing_snapshot,
        payment_collection_model="hotel_collect" if data.source == ReservationSourceEnum.DIRECT else "unknown",
        settlement_status="not_applicable" if data.source == ReservationSourceEnum.DIRECT else "pending",
    )
    db.add(reservation)
    db.flush()
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
    resolved_hotel_id = _resolve_hotel_id(hotel_id, room=reservation.room if hasattr(reservation, "room") else None)
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
    return reservation


def list_reservations(
    db: Session,
    hotel_id: int,
    status_filter: str = "",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> list[Reservation]:
    query = db.query(Reservation).filter(Reservation.hotel_id == hotel_id)
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    if from_date:
        query = query.filter(Reservation.check_in_date >= from_date)
    if to_date:
        query = query.filter(Reservation.check_out_date <= to_date)
    return query.order_by(Reservation.check_in_date).all()


def get_reservation_by_id(db: Session, reservation_id: int, hotel_id: int) -> Reservation | None:
    return (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )


def update_reservation_fields(
    db: Session,
    reservation: Reservation,
    data: ReservationUpdate,
    hotel_id: Optional[int] = None,
    *,
    changed_by_user_id: Optional[int] = None,
    room_move_reason_code: Optional[str] = None,
    room_move_notes: Optional[str] = None,
) -> Reservation:
    update_data = data.model_dump(exclude_unset=True)
    hotel_id = _resolve_hotel_id(hotel_id, room=reservation.room if hasattr(reservation, "room") else None)

    new_ci = update_data.get("check_in_date", reservation.check_in_date)
    new_co = update_data.get("check_out_date", reservation.check_out_date)

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
        ).first()
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

    for field in ("num_adults", "num_children", "notes"):
        if field in update_data:
            setattr(reservation, field, update_data[field])

    db.flush()
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
        pricing_snapshot=json.dumps(snapshot, ensure_ascii=True, sort_keys=True),
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


def _compute_deposit_amount(db: Session, *, hotel_id: int, gross_total: float) -> float:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    deposit_pct = config.deposit_percentage if config else 30.0
    return round(gross_total * (deposit_pct / 100.0), 2)
