from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.analytics import FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)
from app.models.room import Room
from app.services.timezones import normalize_timezone

MONEY_QUANTUM = Decimal("0.01")
FX_QUANTUM = Decimal("0.000001")

_CHANNEL_ALIASES: dict[str, ReservationChannelCodeEnum] = {
    "website": ReservationChannelCodeEnum.WEBSITE_DIRECT,
    "web": ReservationChannelCodeEnum.WEBSITE_DIRECT,
    "website_direct": ReservationChannelCodeEnum.WEBSITE_DIRECT,
    "direct_web": ReservationChannelCodeEnum.WEBSITE_DIRECT,
    "whatsapp": ReservationChannelCodeEnum.WHATSAPP,
    "wa": ReservationChannelCodeEnum.WHATSAPP,
    "phone": ReservationChannelCodeEnum.PHONE,
    "call": ReservationChannelCodeEnum.PHONE,
    "tel": ReservationChannelCodeEnum.PHONE,
    "telephone": ReservationChannelCodeEnum.PHONE,
    "walk_in": ReservationChannelCodeEnum.WALK_IN,
    "walkin": ReservationChannelCodeEnum.WALK_IN,
    "in_person": ReservationChannelCodeEnum.WALK_IN,
    "booking": ReservationChannelCodeEnum.BOOKING,
    "booking.com": ReservationChannelCodeEnum.BOOKING,
    "bookingcom": ReservationChannelCodeEnum.BOOKING,
    "expedia": ReservationChannelCodeEnum.EXPEDIA,
    "despegar": ReservationChannelCodeEnum.DESPEGAR,
    "other_ota": ReservationChannelCodeEnum.OTHER_OTA,
    "ota": ReservationChannelCodeEnum.OTHER_OTA,
    "other_direct": ReservationChannelCodeEnum.OTHER_DIRECT,
    "direct": ReservationChannelCodeEnum.OTHER_DIRECT,
}


@dataclass(frozen=True, slots=True)
class ComparisonWindow:
    requested: bool
    available: bool
    date_from: date | None
    date_to: date | None


@dataclass(frozen=True, slots=True)
class ComparisonState:
    previous: ComparisonWindow
    yoy: ComparisonWindow


@dataclass(frozen=True, slots=True)
class MonetaryTotals:
    revenue_gross_ars: Decimal = Decimal("0")
    revenue_gross_usd: Decimal = Decimal("0")
    revenue_net_ars: Decimal = Decimal("0")
    revenue_net_usd: Decimal = Decimal("0")
    tax_ars: Decimal = Decimal("0")
    tax_usd: Decimal = Decimal("0")
    fee_ars: Decimal = Decimal("0")
    fee_usd: Decimal = Decimal("0")
    commission_ars: Decimal = Decimal("0")
    commission_usd: Decimal = Decimal("0")
    variable_cost_ars: Decimal = Decimal("0")
    variable_cost_usd: Decimal = Decimal("0")
    margin_operating_ars: Decimal = Decimal("0")
    margin_operating_usd: Decimal = Decimal("0")
    source_currency: str = "ARS"
    fx_rate_snapshot: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ReservationNightFactDraft:
    stay_date: date
    hotel_id: int
    reservation_id: int | None
    room_id: int | None
    category_id: int
    company_id: int | None
    channel_code: ReservationChannelCodeEnum
    guest_segment: ReservationGuestSegmentEnum
    guest_segment_source: ReservationGuestSegmentSourceEnum
    status: ReservationStatusEnum
    outcome: ReservationOutcomeEnum
    row_kind: FactReservationRowKindEnum
    occupied_night: bool
    chargeable_night: bool
    revenue_gross_ars: Decimal
    revenue_gross_usd: Decimal
    revenue_net_ars: Decimal
    revenue_net_usd: Decimal
    tax_ars: Decimal
    tax_usd: Decimal
    fee_ars: Decimal
    fee_usd: Decimal
    commission_ars: Decimal
    commission_usd: Decimal
    variable_cost_ars: Decimal
    variable_cost_usd: Decimal
    margin_operating_ars: Decimal
    margin_operating_usd: Decimal
    source_currency: str
    fx_rate_snapshot: Decimal | None


@dataclass(frozen=True, slots=True)
class RoomOccupancyNightFactDraft:
    stay_date: date
    hotel_id: int
    room_id: int
    category_id: int
    status_at_night: FactRoomOccupancyStatusAtNightEnum
    is_sellable_night: bool
    is_occupied: bool
    reservation_id: int | None
    revenue_net_ars: Decimal
    revenue_net_usd: Decimal
    margin_operating_ars: Decimal
    margin_operating_usd: Decimal


def reservation_status_to_outcome(status: ReservationStatusEnum | str) -> ReservationOutcomeEnum:
    value = _enum_value(status)
    mapping = {
        ReservationStatusEnum.PENDING.value: ReservationOutcomeEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID.value: ReservationOutcomeEnum.PENDING,
        ReservationStatusEnum.FULLY_PAID.value: ReservationOutcomeEnum.PENDING,
        ReservationStatusEnum.CHECKED_IN.value: ReservationOutcomeEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT.value: ReservationOutcomeEnum.COMPLETED,
        ReservationStatusEnum.CANCELLED.value: ReservationOutcomeEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW.value: ReservationOutcomeEnum.NO_SHOW,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"Unknown reservation status: {status}") from exc


def infer_guest_segment_from_company(company: Company | None) -> ReservationGuestSegmentEnum:
    if company is None:
        return ReservationGuestSegmentEnum.LEISURE
    return ReservationGuestSegmentEnum.BUSINESS


def resolve_guest_segment(
    reservation: Reservation | SimpleNamespace,
    company: Company | None = None,
) -> tuple[ReservationGuestSegmentEnum, ReservationGuestSegmentSourceEnum]:
    current_segment = _maybe_enum(
        getattr(reservation, "guest_segment", None),
        ReservationGuestSegmentEnum,
    )
    current_source = _maybe_enum(
        getattr(reservation, "guest_segment_source", None),
        ReservationGuestSegmentSourceEnum,
    )

    if current_source == ReservationGuestSegmentSourceEnum.MANUAL and current_segment is not None:
        return current_segment, current_source

    inferred_segment = infer_guest_segment_from_company(company)
    if company is not None:
        return inferred_segment, ReservationGuestSegmentSourceEnum.INFERRED_FROM_COMPANY

    if current_segment is not None and current_source is not None:
        return current_segment, current_source

    return ReservationGuestSegmentEnum.LEISURE, ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT


def normalize_channel_code(
    value: ReservationChannelCodeEnum | str | None,
    *,
    source: Any | None = None,
    source_provider_code: str | None = None,
) -> ReservationChannelCodeEnum:
    candidates: list[str] = []
    for candidate in (value, source_provider_code, source):
        normalized = _normalize_text(candidate)
        if normalized:
            candidates.append(normalized)

    for candidate in candidates:
        alias = _CHANNEL_ALIASES.get(candidate)
        if alias is not None:
            return alias
        if candidate in ReservationChannelCodeEnum._value2member_map_:
            return ReservationChannelCodeEnum(candidate)

    if _enum_value(source) == "direct":
        return ReservationChannelCodeEnum.OTHER_DIRECT
    if _enum_value(source) == "booking":
        return ReservationChannelCodeEnum.BOOKING
    if _enum_value(source) == "expedia":
        return ReservationChannelCodeEnum.EXPEDIA
    if _enum_value(source) == "other_ota":
        return ReservationChannelCodeEnum.OTHER_OTA
    return ReservationChannelCodeEnum.OTHER_DIRECT


def backfill_channel_code(reservation: Reservation | SimpleNamespace) -> ReservationChannelCodeEnum:
    return normalize_channel_code(
        getattr(reservation, "channel_code", None),
        source=getattr(reservation, "source", None),
        source_provider_code=getattr(reservation, "source_provider_code", None),
    )


def split_amount_evenly(amount: Decimal | float | int | str, parts: int) -> list[Decimal]:
    if parts <= 0:
        raise ValueError("parts must be greater than zero")
    quantized_total = _money(amount)
    cents_total = int((quantized_total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    quotient, remainder = divmod(cents_total, parts)
    return [
        (Decimal(quotient + (1 if index < remainder else 0)) / Decimal(100)).quantize(MONEY_QUANTUM)
        for index in range(parts)
    ]


def build_reservation_nightly_facts(
    *,
    reservation: Reservation | SimpleNamespace,
    stay_dates: Sequence[date],
    totals: MonetaryTotals,
    row_kind: FactReservationRowKindEnum | str | None = None,
    no_show_policy_applied: ReservationNoShowPolicyAppliedEnum | str | None = None,
    channel_code: ReservationChannelCodeEnum | str | None = None,
    guest_segment: ReservationGuestSegmentEnum | str | None = None,
    guest_segment_source: ReservationGuestSegmentSourceEnum | str | None = None,
) -> list[ReservationNightFactDraft]:
    stay_dates = list(stay_dates)
    if not stay_dates:
        return []

    resolved_row_kind = _resolve_row_kind(row_kind, no_show_policy_applied)
    if resolved_row_kind == FactReservationRowKindEnum.NO_SHOW_WAIVED:
        nightly_totals = [
            MonetaryTotals(source_currency=totals.source_currency, fx_rate_snapshot=totals.fx_rate_snapshot)
            for _ in stay_dates
        ]
    else:
        nightly_totals = _allocate_monetary_totals(totals, len(stay_dates))

    room_id = getattr(reservation, "room_id", None)
    category_id = int(getattr(reservation, "category_id"))
    company_id = getattr(reservation, "company_id", None)
    status = _maybe_enum(getattr(reservation, "status", None), ReservationStatusEnum) or ReservationStatusEnum.PENDING
    outcome = _maybe_enum(getattr(reservation, "outcome", None), ReservationOutcomeEnum) or reservation_status_to_outcome(status)
    resolved_channel = normalize_channel_code(
        channel_code,
        source=getattr(reservation, "source", None),
        source_provider_code=getattr(reservation, "source_provider_code", None),
    )
    resolved_guest_segment = _maybe_enum(guest_segment, ReservationGuestSegmentEnum)
    resolved_guest_segment_source = _maybe_enum(guest_segment_source, ReservationGuestSegmentSourceEnum)
    if resolved_guest_segment is None or resolved_guest_segment_source is None:
        resolved_guest_segment, resolved_guest_segment_source = resolve_guest_segment(reservation)

    return [
        ReservationNightFactDraft(
            stay_date=stay_date,
            hotel_id=int(getattr(reservation, "hotel_id")),
            reservation_id=getattr(reservation, "id", None),
            room_id=room_id,
            category_id=category_id,
            company_id=company_id,
            channel_code=resolved_channel,
            guest_segment=resolved_guest_segment,
            guest_segment_source=resolved_guest_segment_source,
            status=status,
            outcome=outcome,
            row_kind=resolved_row_kind,
            occupied_night=resolved_row_kind == FactReservationRowKindEnum.OCCUPIED,
            chargeable_night=resolved_row_kind != FactReservationRowKindEnum.NO_SHOW_WAIVED,
            revenue_gross_ars=nightly_totals[index].revenue_gross_ars,
            revenue_gross_usd=nightly_totals[index].revenue_gross_usd,
            revenue_net_ars=nightly_totals[index].revenue_net_ars,
            revenue_net_usd=nightly_totals[index].revenue_net_usd,
            tax_ars=nightly_totals[index].tax_ars,
            tax_usd=nightly_totals[index].tax_usd,
            fee_ars=nightly_totals[index].fee_ars,
            fee_usd=nightly_totals[index].fee_usd,
            commission_ars=nightly_totals[index].commission_ars,
            commission_usd=nightly_totals[index].commission_usd,
            variable_cost_ars=nightly_totals[index].variable_cost_ars,
            variable_cost_usd=nightly_totals[index].variable_cost_usd,
            margin_operating_ars=nightly_totals[index].margin_operating_ars,
            margin_operating_usd=nightly_totals[index].margin_operating_usd,
            source_currency=totals.source_currency,
            fx_rate_snapshot=totals.fx_rate_snapshot,
        )
        for index, stay_date in enumerate(stay_dates)
    ]


def build_room_occupancy_nightly_fact(
    *,
    hotel_id: int,
    room_id: int,
    stay_date: date,
    category_id: int,
    status_at_night: FactRoomOccupancyStatusAtNightEnum | str | Any,
    is_sellable_night: bool,
    is_occupied: bool,
    reservation_id: int | None = None,
    revenue_net_ars: Decimal | float | int | str = Decimal("0"),
    revenue_net_usd: Decimal | float | int | str = Decimal("0"),
    margin_operating_ars: Decimal | float | int | str = Decimal("0"),
    margin_operating_usd: Decimal | float | int | str = Decimal("0"),
) -> RoomOccupancyNightFactDraft:
    status_enum = _maybe_enum(status_at_night, FactRoomOccupancyStatusAtNightEnum)
    if status_enum is None:
        raise ValueError(f"Unknown room status at night: {status_at_night}")

    return RoomOccupancyNightFactDraft(
        stay_date=stay_date,
        hotel_id=hotel_id,
        room_id=room_id,
        category_id=category_id,
        status_at_night=status_enum,
        is_sellable_night=is_sellable_night,
        is_occupied=is_occupied,
        reservation_id=reservation_id,
        revenue_net_ars=_money(revenue_net_ars),
        revenue_net_usd=_money(revenue_net_usd),
        margin_operating_ars=_money(margin_operating_ars),
        margin_operating_usd=_money(margin_operating_usd),
    )


def calculate_pickup_30d_count_from_rows(
    reservations: Iterable[Any],
    *,
    date_from: date,
    date_to: date,
    hotel_timezone: str,
) -> int:
    timezone_name = normalize_timezone(hotel_timezone)
    anchor_date = date_to
    pickup_window_end = anchor_date + timedelta(days=29)
    count = 0
    for reservation in reservations:
        local_created_date = _local_date(getattr(reservation, "created_at", None), timezone_name)
        if local_created_date is None:
            continue
        if not (date_from <= local_created_date <= date_to):
            continue
        check_in_date = getattr(reservation, "check_in_date", None)
        if check_in_date is None:
            continue
        if not (anchor_date <= check_in_date <= pickup_window_end):
            continue
        if _enum_value(getattr(reservation, "outcome", None)) == ReservationOutcomeEnum.CANCELLED.value:
            continue
        count += 1
    return count


def calculate_pickup_30d_count(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    hotel_timezone: str | None = None,
) -> int:
    timezone_name = hotel_timezone or _hotel_timezone(db, hotel_id)
    reservations = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id)
        .all()
    )
    return calculate_pickup_30d_count_from_rows(
        reservations,
        date_from=date_from,
        date_to=date_to,
        hotel_timezone=timezone_name,
    )


def calculate_physical_room_nights(
    *,
    active_room_count: int,
    date_from: date,
    date_to: date,
) -> int:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    return active_room_count * ((date_to - date_from).days + 1)


def calculate_physical_room_nights_for_hotel(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> int:
    active_room_count = (
        db.query(Room)
        .filter(Room.hotel_id == hotel_id, Room.is_active.is_(True))
        .count()
    )
    return calculate_physical_room_nights(
        active_room_count=active_room_count,
        date_from=date_from,
        date_to=date_to,
    )


def build_comparison_window(
    *,
    requested: bool,
    date_from: date | None,
    date_to: date | None,
    available: bool | None = None,
) -> ComparisonWindow:
    if not requested or date_from is None or date_to is None:
        return ComparisonWindow(requested=False, available=False, date_from=None, date_to=None)
    return ComparisonWindow(
        requested=True,
        available=bool(requested if available is None else available),
        date_from=date_from,
        date_to=date_to,
    )


def build_comparison_state(
    date_from: date,
    date_to: date,
    *,
    compare_previous: bool,
    compare_yoy: bool,
) -> ComparisonState:
    span_days = (date_to - date_from).days + 1
    previous = build_comparison_window(
        requested=compare_previous,
        date_from=date_from - timedelta(days=span_days),
        date_to=date_from - timedelta(days=1),
    )
    yoy = build_comparison_window(
        requested=compare_yoy,
        date_from=_shift_year_back(date_from),
        date_to=_shift_year_back(date_to),
    )
    return ComparisonState(previous=previous, yoy=yoy)


def build_analytics_window(
    date_from: date,
    date_to: date,
    *,
    compare_previous: bool,
    compare_yoy: bool,
) -> dict[str, Any]:
    comparison = build_comparison_state(
        date_from,
        date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )
    return {
        "date_from": date_from,
        "date_to": date_to,
        "comparison": comparison,
    }


def _resolve_row_kind(
    row_kind: FactReservationRowKindEnum | str | None,
    no_show_policy_applied: ReservationNoShowPolicyAppliedEnum | str | None,
) -> FactReservationRowKindEnum:
    if row_kind:
        normalized = _normalize_text(row_kind)
        if normalized == FactReservationRowKindEnum.NO_SHOW_CHARGEABLE.value:
            return FactReservationRowKindEnum.NO_SHOW_CHARGEABLE
        if normalized == FactReservationRowKindEnum.NO_SHOW_WAIVED.value:
            return FactReservationRowKindEnum.NO_SHOW_WAIVED
        if normalized == FactReservationRowKindEnum.OCCUPIED.value:
            return FactReservationRowKindEnum.OCCUPIED
        raise ValueError(f"Unknown reservation row kind: {row_kind}")
    policy = _maybe_enum(no_show_policy_applied, ReservationNoShowPolicyAppliedEnum)
    if policy == ReservationNoShowPolicyAppliedEnum.WAIVED:
        return FactReservationRowKindEnum.NO_SHOW_WAIVED
    if policy in (
        ReservationNoShowPolicyAppliedEnum.FULL_CHARGE,
        ReservationNoShowPolicyAppliedEnum.PARTIAL_CHARGE,
    ):
        return FactReservationRowKindEnum.NO_SHOW_CHARGEABLE
    return FactReservationRowKindEnum.OCCUPIED


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _allocate_monetary_totals(totals: MonetaryTotals, parts: int) -> list[MonetaryTotals]:
    gross_ars = split_amount_evenly(totals.revenue_gross_ars, parts)
    gross_usd = split_amount_evenly(totals.revenue_gross_usd, parts)
    net_ars = split_amount_evenly(totals.revenue_net_ars, parts)
    net_usd = split_amount_evenly(totals.revenue_net_usd, parts)
    tax_ars = split_amount_evenly(totals.tax_ars, parts)
    tax_usd = split_amount_evenly(totals.tax_usd, parts)
    fee_ars = split_amount_evenly(totals.fee_ars, parts)
    fee_usd = split_amount_evenly(totals.fee_usd, parts)
    commission_ars = split_amount_evenly(totals.commission_ars, parts)
    commission_usd = split_amount_evenly(totals.commission_usd, parts)
    variable_cost_ars = split_amount_evenly(totals.variable_cost_ars, parts)
    variable_cost_usd = split_amount_evenly(totals.variable_cost_usd, parts)
    margin_operating_ars = split_amount_evenly(totals.margin_operating_ars, parts)
    margin_operating_usd = split_amount_evenly(totals.margin_operating_usd, parts)
    return [
        MonetaryTotals(
            revenue_gross_ars=gross_ars[index],
            revenue_gross_usd=gross_usd[index],
            revenue_net_ars=net_ars[index],
            revenue_net_usd=net_usd[index],
            tax_ars=tax_ars[index],
            tax_usd=tax_usd[index],
            fee_ars=fee_ars[index],
            fee_usd=fee_usd[index],
            commission_ars=commission_ars[index],
            commission_usd=commission_usd[index],
            variable_cost_ars=variable_cost_ars[index],
            variable_cost_usd=variable_cost_usd[index],
            margin_operating_ars=margin_operating_ars[index],
            margin_operating_usd=margin_operating_usd[index],
            source_currency=totals.source_currency,
            fx_rate_snapshot=totals.fx_rate_snapshot,
        )
        for index in range(parts)
    ]


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    if value is None:
        return ""
    return str(value).strip().lower()


def _maybe_enum(value: Any, enum_cls):
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    raw = _enum_value(value)
    try:
        return enum_cls(raw)
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    raw = _enum_value(value)
    if not raw:
        return ""
    return raw.replace(" ", "_").replace("-", "_").strip().lower()


def _shift_year_back(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, month=2, day=28)


def _local_date(value: datetime | None, timezone_name: str) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name)).date()


def _hotel_timezone(db: Session, hotel_id: int) -> str:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        raise ValueError(f"Hotel {hotel_id} not found")
    return normalize_timezone(hotel.hotel_timezone)
