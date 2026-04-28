from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.analytics import (
    AnalyticsExportJob,
    FactReservationDaily,
    FactReservationRowKindEnum,
    FactRoomOccupancyDaily,
    FactRoomOccupancyStatusAtNightEnum,
    HotelAuditEvent,
)
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)
from app.models.room import Room, RoomCategory
from app.services.analytics_contracts import (
    MonetaryTotals,
    backfill_channel_code,
    build_comparison_state,
    build_reservation_nightly_facts,
    build_room_occupancy_nightly_fact,
    calculate_physical_room_nights,
    resolve_guest_segment,
)
from app.services.timezones import normalize_timezone


@dataclass(frozen=True, slots=True)
class NoShowDetectionResult:
    hotel_id: int
    scanned: int
    marked: int
    reservation_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FactRefreshResult:
    hotel_id: int
    date_from: date
    date_to: date
    deleted: int
    inserted: int


def detect_no_shows(
    db: Session,
    *,
    hotel_id: int,
    now: datetime | None = None,
    performed_by_user_id: int | None = None,
) -> NoShowDetectionResult:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        raise ValueError(f"Hotel {hotel_id} not found")

    timezone_name = normalize_timezone(hotel.hotel_timezone)
    current_utc = now or datetime.now(timezone.utc)
    current_local = current_utc.astimezone(ZoneInfo(timezone_name))
    cutoff_hours = int(getattr(hotel, "no_show_cutoff_hours", 24) or 24)

    candidates = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.status.in_(
                [
                    ReservationStatusEnum.PENDING,
                    ReservationStatusEnum.DEPOSIT_PAID,
                    ReservationStatusEnum.FULLY_PAID,
                ]
            ),
            Reservation.check_in_date <= current_local.date(),
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )

    marked_ids: list[int] = []
    audit_user_id = performed_by_user_id or _resolve_audit_user_id(db, hotel_id)
    for reservation in candidates:
        cutoff_moment = datetime.combine(reservation.check_in_date, time.min, tzinfo=ZoneInfo(timezone_name))
        cutoff_moment = cutoff_moment + timedelta(hours=cutoff_hours)
        if current_local < cutoff_moment:
            continue

        before = _reservation_audit_snapshot(reservation)
        reservation.status = ReservationStatusEnum.NO_SHOW
        reservation.outcome = ReservationOutcomeEnum.NO_SHOW
        if reservation.no_show_policy_applied == ReservationNoShowPolicyAppliedEnum.NONE:
            reservation.no_show_policy_applied = ReservationNoShowPolicyAppliedEnum.FULL_CHARGE
        reservation.no_show_confirmed_at = current_utc
        db.flush()
        marked_ids.append(reservation.id)

        if audit_user_id is not None:
            db.add(
                HotelAuditEvent(
                    hotel_id=hotel_id,
                    user_id=audit_user_id,
                    action_code="analytics.reservation.no_show_marked",
                    entity_type="reservation",
                    entity_id=reservation.id,
                    before_json=json.dumps(before, ensure_ascii=True, sort_keys=True),
                    after_json=json.dumps(_reservation_audit_snapshot(reservation), ensure_ascii=True, sort_keys=True),
                )
            )

    db.flush()
    return NoShowDetectionResult(
        hotel_id=hotel_id,
        scanned=len(candidates),
        marked=len(marked_ids),
        reservation_ids=tuple(marked_ids),
    )


def refresh_fact_reservation_daily(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> FactRefreshResult:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")

    deleted = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.stay_date >= date_from,
            FactReservationDaily.stay_date <= date_to,
        )
        .delete(synchronize_session=False)
    )

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.check_in_date <= date_to,
            Reservation.check_out_date > date_from,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )

    inserted = 0
    for reservation in reservations:
        category = db.get(RoomCategory, reservation.category_id)
        if category is None:
            continue
        company = db.get(Company, reservation.company_id) if reservation.company_id else None
        stay_dates = _reservation_dates_in_window(reservation, date_from=date_from, date_to=date_to)
        if not stay_dates:
            continue
        policy = _resolve_no_show_policy(reservation)
        row_kind = _reservation_row_kind(reservation, policy)
        totals = _reservation_monetary_totals(
            reservation,
            category=category,
            nights=len(stay_dates),
            row_kind=row_kind,
            policy=policy,
        )
        guest_segment, guest_segment_source = resolve_guest_segment(reservation, company)
        channel_code = backfill_channel_code(reservation)
        facts = build_reservation_nightly_facts(
            reservation=reservation,
            stay_dates=stay_dates,
            totals=totals,
            row_kind=row_kind,
            no_show_policy_applied=policy,
            channel_code=channel_code,
            guest_segment=guest_segment,
            guest_segment_source=guest_segment_source,
        )
        for fact in facts:
            db.add(
                FactReservationDaily(
                    hotel_id=fact.hotel_id,
                    reservation_id=fact.reservation_id,
                    stay_date=fact.stay_date,
                    room_id=fact.room_id,
                    category_id=fact.category_id,
                    company_id=fact.company_id,
                    channel_code=fact.channel_code,
                    guest_segment=fact.guest_segment,
                    status=fact.status,
                    outcome=fact.outcome,
                    row_kind=fact.row_kind,
                    occupied_night=fact.occupied_night,
                    chargeable_night=fact.chargeable_night,
                    revenue_gross_ars=fact.revenue_gross_ars,
                    revenue_gross_usd=fact.revenue_gross_usd,
                    revenue_net_ars=fact.revenue_net_ars,
                    revenue_net_usd=fact.revenue_net_usd,
                    tax_ars=fact.tax_ars,
                    tax_usd=fact.tax_usd,
                    fee_ars=fact.fee_ars,
                    fee_usd=fact.fee_usd,
                    commission_ars=fact.commission_ars,
                    commission_usd=fact.commission_usd,
                    variable_cost_ars=fact.variable_cost_ars,
                    variable_cost_usd=fact.variable_cost_usd,
                    margin_operating_ars=fact.margin_operating_ars,
                    margin_operating_usd=fact.margin_operating_usd,
                    source_currency=fact.source_currency,
                    fx_rate_snapshot=fact.fx_rate_snapshot,
                )
            )
            inserted += 1

    db.flush()
    return FactRefreshResult(
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        deleted=deleted,
        inserted=inserted,
    )


def refresh_fact_room_occupancy_daily(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> FactRefreshResult:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")

    deleted = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.stay_date >= date_from,
            FactRoomOccupancyDaily.stay_date <= date_to,
        )
        .delete(synchronize_session=False)
    )

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.check_in_date <= date_to,
            Reservation.check_out_date > date_from,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    rooms = (
        db.query(Room)
        .filter(Room.hotel_id == hotel_id)
        .order_by(Room.id.asc())
        .all()
    )

    reservation_map = _occupied_nightly_fact_map(db, reservations, date_from=date_from, date_to=date_to)
    room_events = _room_state_events_map(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)

    inserted = 0
    for room in rooms:
        for stay_date in _date_range(date_from, date_to):
            event_status = room_events.get((room.id, stay_date))
            occupancy_fact = reservation_map.get((room.id, stay_date))
            if event_status is not None:
                status_at_night = event_status
                is_occupied = False
                reservation_id = occupancy_fact.reservation_id if occupancy_fact else None
                revenue_net_ars = Decimal("0")
                revenue_net_usd = Decimal("0")
                margin_operating_ars = Decimal("0")
                margin_operating_usd = Decimal("0")
            elif occupancy_fact is not None:
                status_at_night = FactRoomOccupancyStatusAtNightEnum.OCCUPIED
                is_occupied = True
                reservation_id = occupancy_fact.reservation_id
                revenue_net_ars = occupancy_fact.revenue_net_ars
                revenue_net_usd = occupancy_fact.revenue_net_usd
                margin_operating_ars = occupancy_fact.margin_operating_ars
                margin_operating_usd = occupancy_fact.margin_operating_usd
            elif room.is_active:
                status_at_night = FactRoomOccupancyStatusAtNightEnum.AVAILABLE
                is_occupied = False
                reservation_id = None
                revenue_net_ars = Decimal("0")
                revenue_net_usd = Decimal("0")
                margin_operating_ars = Decimal("0")
                margin_operating_usd = Decimal("0")
            else:
                status_at_night = FactRoomOccupancyStatusAtNightEnum.OUT_OF_SERVICE
                is_occupied = False
                reservation_id = None
                revenue_net_ars = Decimal("0")
                revenue_net_usd = Decimal("0")
                margin_operating_ars = Decimal("0")
                margin_operating_usd = Decimal("0")

            is_sellable_night = room.is_active and status_at_night in (
                FactRoomOccupancyStatusAtNightEnum.AVAILABLE,
                FactRoomOccupancyStatusAtNightEnum.OCCUPIED,
            )
            fact = build_room_occupancy_nightly_fact(
                hotel_id=hotel_id,
                room_id=room.id,
                stay_date=stay_date,
                category_id=room.category_id,
                status_at_night=status_at_night,
                is_sellable_night=is_sellable_night,
                is_occupied=is_occupied,
                reservation_id=reservation_id,
                revenue_net_ars=revenue_net_ars,
                revenue_net_usd=revenue_net_usd,
                margin_operating_ars=margin_operating_ars,
                margin_operating_usd=margin_operating_usd,
            )
            db.add(
                FactRoomOccupancyDaily(
                    hotel_id=fact.hotel_id,
                    room_id=fact.room_id,
                    stay_date=fact.stay_date,
                    category_id=fact.category_id,
                    status_at_night=fact.status_at_night,
                    is_sellable_night=fact.is_sellable_night,
                    is_occupied=fact.is_occupied,
                    reservation_id=fact.reservation_id,
                    revenue_net_ars=fact.revenue_net_ars,
                    revenue_net_usd=fact.revenue_net_usd,
                    margin_operating_ars=fact.margin_operating_ars,
                    margin_operating_usd=fact.margin_operating_usd,
                )
            )
            inserted += 1

    db.flush()
    return FactRefreshResult(
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        deleted=deleted,
        inserted=inserted,
    )


def calculate_pickup_30d(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> int:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        raise ValueError(f"Hotel {hotel_id} not found")

    timezone_name = normalize_timezone(hotel.hotel_timezone)
    anchor_date = date_to
    pickup_window_end = anchor_date + timedelta(days=29)
    rows = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .all()
    )
    count = 0
    for reservation in rows:
        created_date = _local_date(getattr(reservation, "created_at", None), timezone_name)
        if created_date is None or not (date_from <= created_date <= date_to):
            continue
        if not (anchor_date <= reservation.check_in_date <= pickup_window_end):
            continue
        if reservation.outcome == ReservationOutcomeEnum.CANCELLED:
            continue
        count += 1
    return count


def calculate_physical_room_nights_for_window(
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


def build_analytics_comparison(
    date_from: date,
    date_to: date,
    *,
    compare_previous: bool,
    compare_yoy: bool,
):
    return build_comparison_state(
        date_from,
        date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )


def _reservation_row_kind(
    reservation: Reservation,
    policy: ReservationNoShowPolicyAppliedEnum,
) -> FactReservationRowKindEnum:
    if reservation.status != ReservationStatusEnum.NO_SHOW:
        return FactReservationRowKindEnum.OCCUPIED
    if policy == ReservationNoShowPolicyAppliedEnum.WAIVED:
        return FactReservationRowKindEnum.NO_SHOW_WAIVED
    return FactReservationRowKindEnum.NO_SHOW_CHARGEABLE


def _resolve_no_show_policy(reservation: Reservation) -> ReservationNoShowPolicyAppliedEnum:
    policy = reservation.no_show_policy_applied or ReservationNoShowPolicyAppliedEnum.NONE
    if policy == ReservationNoShowPolicyAppliedEnum.NONE and reservation.status == ReservationStatusEnum.NO_SHOW:
        return ReservationNoShowPolicyAppliedEnum.FULL_CHARGE
    return policy


def _reservation_monetary_totals(
    reservation: Reservation,
    *,
    category: RoomCategory,
    nights: int,
    row_kind: FactReservationRowKindEnum,
    policy: ReservationNoShowPolicyAppliedEnum,
) -> MonetaryTotals:
    source_currency = str(reservation.currency_code or "ARS").strip().upper()[:3] or "ARS"
    fx_rate = _decimal_or_none(getattr(reservation, "fx_rate_snapshot", None))
    base_ratio = Decimal("1")
    if row_kind == FactReservationRowKindEnum.NO_SHOW_WAIVED:
        base_ratio = Decimal("0")
    elif row_kind == FactReservationRowKindEnum.NO_SHOW_CHARGEABLE and policy == ReservationNoShowPolicyAppliedEnum.PARTIAL_CHARGE:
        total = _decimal_or_zero(getattr(reservation, "total_amount", None))
        paid = _decimal_or_zero(getattr(reservation, "amount_paid", None))
        if total > 0:
            base_ratio = min(Decimal("1"), paid / total)
        else:
            base_ratio = Decimal("0")

    gross_total = _decimal_or_zero(getattr(reservation, "total_amount", None)) * base_ratio
    subtotal_total = _decimal_or_zero(getattr(reservation, "subtotal_amount", None)) * base_ratio
    tax_total = _decimal_or_zero(getattr(reservation, "tax_amount", None)) * base_ratio
    fee_total = _decimal_or_zero(getattr(reservation, "fee_amount", None)) * base_ratio
    commission_total = _decimal_or_zero(getattr(reservation, "commission_amount", None)) * base_ratio
    net_total = _decimal_or_zero(getattr(reservation, "net_amount", None)) * base_ratio
    variable_cost_total = _decimal_or_zero(category.variable_cost_per_night) * Decimal(str(nights))
    if row_kind != FactReservationRowKindEnum.OCCUPIED:
        variable_cost_total = Decimal("0")

    revenue_gross_ars, revenue_gross_usd = _currency_pair(gross_total, source_currency, fx_rate)
    revenue_net_ars, revenue_net_usd = _currency_pair(net_total, source_currency, fx_rate)
    tax_ars, tax_usd = _currency_pair(tax_total, source_currency, fx_rate)
    fee_ars, fee_usd = _currency_pair(fee_total, source_currency, fx_rate)
    commission_ars, commission_usd = _currency_pair(commission_total, source_currency, fx_rate)
    variable_cost_ars, variable_cost_usd = _currency_pair(variable_cost_total, source_currency, fx_rate)
    margin_operating_ars = revenue_net_ars - variable_cost_ars
    margin_operating_usd = revenue_net_usd - variable_cost_usd
    return MonetaryTotals(
        revenue_gross_ars=revenue_gross_ars,
        revenue_gross_usd=revenue_gross_usd,
        revenue_net_ars=revenue_net_ars,
        revenue_net_usd=revenue_net_usd,
        tax_ars=tax_ars,
        tax_usd=tax_usd,
        fee_ars=fee_ars,
        fee_usd=fee_usd,
        commission_ars=commission_ars,
        commission_usd=commission_usd,
        variable_cost_ars=variable_cost_ars,
        variable_cost_usd=variable_cost_usd,
        margin_operating_ars=margin_operating_ars,
        margin_operating_usd=margin_operating_usd,
        source_currency=source_currency,
        fx_rate_snapshot=fx_rate,
    )


def _reservation_dates_in_window(
    reservation: Reservation,
    *,
    date_from: date,
    date_to: date,
) -> list[date]:
    start = max(reservation.check_in_date, date_from)
    end = min(reservation.check_out_date, date_to + timedelta(days=1))
    result: list[date] = []
    current = start
    while current < end:
        result.append(current)
        current += timedelta(days=1)
    return result


def _occupied_nightly_fact_map(
    db: Session,
    reservations: list[Reservation],
    *,
    date_from: date,
    date_to: date,
) -> dict[tuple[int, date], object]:
    room_map: dict[tuple[int, date], object] = {}
    for reservation in reservations:
        if reservation.room_id is None:
            continue
        if reservation.status == ReservationStatusEnum.NO_SHOW:
            continue
        stay_dates = _reservation_dates_in_window(reservation, date_from=date_from, date_to=date_to)
        if not stay_dates:
            continue
        category = reservation.category or db.get(RoomCategory, reservation.category_id)
        if category is None:
            continue
        company = db.get(Company, reservation.company_id) if reservation.company_id else None
        policy = _resolve_no_show_policy(reservation)
        row_kind = _reservation_row_kind(reservation, policy)
        totals = _reservation_monetary_totals(
            reservation,
            category=category,
            nights=len(stay_dates),
            row_kind=row_kind,
            policy=policy,
        )
        guest_segment, guest_segment_source = resolve_guest_segment(reservation, company)
        channel_code = backfill_channel_code(reservation)
        for fact in build_reservation_nightly_facts(
            reservation=reservation,
            stay_dates=stay_dates,
            totals=totals,
            row_kind=row_kind,
            no_show_policy_applied=policy,
            channel_code=channel_code,
            guest_segment=guest_segment,
            guest_segment_source=guest_segment_source,
        ):
            if fact.row_kind != FactReservationRowKindEnum.OCCUPIED:
                continue
            room_map[(fact.room_id or reservation.room_id, fact.stay_date)] = fact
    return room_map


def _room_state_events_map(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> dict[tuple[int, date], FactRoomOccupancyStatusAtNightEnum]:
    from app.models.analytics import RoomStateEvent, RoomStateEventTypeEnum

    events = (
        db.query(RoomStateEvent)
        .filter(
            RoomStateEvent.hotel_id == hotel_id,
            RoomStateEvent.started_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc),
            (RoomStateEvent.ended_at.is_(None) | (RoomStateEvent.ended_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))),
        )
        .all()
    )
    mapped: dict[tuple[int, date], FactRoomOccupancyStatusAtNightEnum] = {}
    for event in events:
        for stay_date in _date_range(date_from, date_to):
            if not _event_overlaps_date(event.started_at, event.ended_at, stay_date):
                continue
            status = _room_event_status(event.event_type)
            current = mapped.get((event.room_id, stay_date))
            if current is None or _room_event_priority(status) > _room_event_priority(current):
                mapped[(event.room_id, stay_date)] = status
    return mapped


def _event_overlaps_date(started_at: datetime, ended_at: datetime | None, stay_date: date) -> bool:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if ended_at is not None and ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=timezone.utc)
    day_start = datetime.combine(stay_date, time.min, tzinfo=started_at.tzinfo or timezone.utc)
    day_end = day_start + timedelta(days=1)
    if started_at >= day_end:
        return False
    if ended_at is not None and ended_at <= day_start:
        return False
    return True


def _room_event_status(event_type) -> FactRoomOccupancyStatusAtNightEnum:
    value = getattr(event_type, "value", event_type)
    mapping = {
        "out_of_service": FactRoomOccupancyStatusAtNightEnum.OUT_OF_SERVICE,
        "maintenance": FactRoomOccupancyStatusAtNightEnum.MAINTENANCE,
        "housekeeping_block": FactRoomOccupancyStatusAtNightEnum.HOUSEKEEPING_BLOCK,
        "renovation": FactRoomOccupancyStatusAtNightEnum.RENOVATION,
    }
    return mapping[str(value)]


def _room_event_priority(status: FactRoomOccupancyStatusAtNightEnum) -> int:
    return {
        FactRoomOccupancyStatusAtNightEnum.RENOVATION: 4,
        FactRoomOccupancyStatusAtNightEnum.OUT_OF_SERVICE: 3,
        FactRoomOccupancyStatusAtNightEnum.MAINTENANCE: 2,
        FactRoomOccupancyStatusAtNightEnum.HOUSEKEEPING_BLOCK: 1,
        FactRoomOccupancyStatusAtNightEnum.AVAILABLE: 0,
        FactRoomOccupancyStatusAtNightEnum.OCCUPIED: 0,
    }[status]


def _date_range(date_from: date, date_to: date):
    current = date_from
    while current <= date_to:
        yield current
        current += timedelta(days=1)


def _currency_pair(
    amount: Decimal,
    source_currency: str,
    fx_rate: Decimal | None,
) -> tuple[Decimal, Decimal]:
    normalized = source_currency.upper()
    rate = fx_rate if fx_rate and fx_rate > 0 else Decimal("1")
    if normalized == "USD":
        usd = amount.quantize(Decimal("0.01"))
        ars = (amount * rate).quantize(Decimal("0.01"))
    else:
        ars = amount.quantize(Decimal("0.01"))
        usd = (amount / rate).quantize(Decimal("0.01"))
    return ars, usd


def _decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _decimal_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _local_date(value: datetime | None, timezone_name: str) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name)).date()


def _reservation_audit_snapshot(reservation: Reservation) -> dict[str, object]:
    return {
        "reservation_id": reservation.id,
        "status": getattr(reservation.status, "value", reservation.status),
        "outcome": getattr(reservation.outcome, "value", reservation.outcome),
        "no_show_policy_applied": getattr(
            reservation.no_show_policy_applied,
            "value",
            reservation.no_show_policy_applied,
        ),
        "room_id": reservation.room_id,
        "check_in_date": reservation.check_in_date.isoformat() if reservation.check_in_date else None,
        "check_out_date": reservation.check_out_date.isoformat() if reservation.check_out_date else None,
    }


def _resolve_audit_user_id(db: Session, hotel_id: int) -> int | None:
    membership = (
        db.query(HotelMembership)
        .join(HotelMembership.user)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.status == "active",
            HotelMembership.role.in_(["owner", "co_owner"]),
        )
        .order_by(
            (HotelMembership.role == "owner").desc(),
            HotelMembership.id.asc(),
        )
        .first()
    )
    return membership.user_id if membership else None
