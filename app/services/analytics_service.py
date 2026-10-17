from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.analytics import (
    AnalyticsAlertSetting,
    AnalyticsAlertSnooze,
    AnalyticsAIUsageMonthly,
    FactReservationDaily,
    FactRoomOccupancyDaily,
    HotelAuditEvent,
    RoomStateEvent,
)
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationOutcomeEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.schemas.analytics import AnalyticsComparisonStateRead, AnalyticsComparisonWindowRead, AnalyticsMetricCardRead
from app.schemas.analytics_api import (
    AnalyticsAIConfigRead,
    AnalyticsAIConfigUpdate,
    AnalyticsAlertSettingsRead,
    AnalyticsAlertSettingsUpdate,
    AnalyticsAlertSnoozeCreate,
    AnalyticsAlertSnoozeRead,
    CompanyCreate,
    CompanyUpdate,
    RoomStateEventCreate,
)
from app.services.analytics_ai_providers import build_analytics_ai_config, get_analytics_ai_provider
from app.services.analytics_contracts import build_analytics_window, calculate_physical_room_nights_for_hotel, calculate_pickup_30d_count
from app.services.analytics_facts import (
    touch_room_state_event_fact_window,
)
from app.services.reservation_service import active_reservations
from app.services.room_service import active_rooms
from app.services.subscription_entitlements import get_subscription_snapshot
from app.services.timezones import hotel_today, normalize_timezone

MONEY_QUANTUM = Decimal("0.01")
PLAN_ORDER = {"starter": 0, "pro": 1, "ultra": 2}
AI_MONTHLY_QUOTA_FALLBACK = 20


class _MappedQueryRows:
    """Re-iterable, bounded-memory projection over a SQLAlchemy query."""

    def __init__(
        self,
        query,
        mapper: Callable[[Any], Any],
        *,
        column_names: tuple[str, ...],
        batch_size: int = 500,
    ):
        self._query = query
        self._mapper = mapper
        self.column_names = column_names
        self._batch_size = batch_size

    def __iter__(self):
        query = self._query.enable_eagerloads(False).yield_per(self._batch_size)
        for row in query:
            yield self._mapper(row)


@dataclass(frozen=True, slots=True)
class DateWindow:
    date_from: date
    date_to: date
    comparison: AnalyticsComparisonStateRead


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _facts_data_as_of(*fact_row_groups: list[Any]) -> datetime | None:
    """Return the oldest materialization timestamp among the facts used.

    This is a conservative fact-refresh timestamp, not an independent
    watermark of source-table writes. Reservation write paths update their
    affected fact windows transactionally. Returning the oldest row keeps
    mixed-age windows visibly stale instead of letting a newer row mask an
    older one. An empty window returns None because it has no fact rows.
    """
    timestamps = [row.updated_at for group in fact_row_groups for row in group if getattr(row, "updated_at", None)]
    return min(timestamps) if timestamps else None


def _hotel_local_now(db: Session, hotel_id: int) -> datetime:
    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = normalize_timezone(hotel.hotel_timezone if hotel and hotel.hotel_timezone else get_settings().HOTEL_TIMEZONE)
    return datetime.now(ZoneInfo(timezone_name))


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _money(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _money_str(value: Decimal | float | int | str | None) -> str:
    return f"{_money(value):.2f}"


def _utc_date_range(db: Session, hotel_id: int, date_from: date | None, date_to: date | None) -> DateWindow:
    if date_from is not None and date_to is not None:
        if date_to < date_from:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_to debe ser mayor o igual a date_from")
        return DateWindow(
            date_from=date_from,
            date_to=date_to,
            comparison=AnalyticsComparisonStateRead.model_validate(
                build_analytics_window(
                    date_from,
                    date_to,
                    compare_previous=True,
                    compare_yoy=False,
                )["comparison"]
            ),
        )

    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = normalize_timezone(hotel.hotel_timezone if hotel and hotel.hotel_timezone else get_settings().HOTEL_TIMEZONE)
    today = hotel_today(db, hotel_id)
    default_from = today.replace(day=1)
    return DateWindow(
        date_from=default_from,
        date_to=today,
        comparison=_comparison_read(default_from, today, compare_previous=True, compare_yoy=False),
    )


def _analytics_window(
    db: Session,
    hotel_id: int,
    *,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
) -> DateWindow:
    resolved = _utc_date_range(db, hotel_id, date_from, date_to)
    if date_from is None or date_to is None:
        return DateWindow(
            date_from=resolved.date_from,
            date_to=resolved.date_to,
            comparison=AnalyticsComparisonStateRead.model_validate(
                build_analytics_window(
                    resolved.date_from,
                    resolved.date_to,
                    compare_previous=compare_previous,
                    compare_yoy=compare_yoy,
                )["comparison"]
            ),
        )
    return DateWindow(
        date_from=resolved.date_from,
        date_to=resolved.date_to,
        comparison=_comparison_read(resolved.date_from, resolved.date_to, compare_previous=compare_previous, compare_yoy=compare_yoy),
    )


def _comparison_read(date_from: date, date_to: date, *, compare_previous: bool, compare_yoy: bool) -> AnalyticsComparisonStateRead:
    comparison = build_analytics_window(
        date_from,
        date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )["comparison"]
    return AnalyticsComparisonStateRead(
        previous=AnalyticsComparisonWindowRead(
            requested=bool(comparison.previous.requested),
            available=bool(comparison.previous.available),
            date_from=comparison.previous.date_from,
            date_to=comparison.previous.date_to,
        ),
        yoy=AnalyticsComparisonWindowRead(
            requested=bool(comparison.yoy.requested),
            available=bool(comparison.yoy.available),
            date_from=comparison.yoy.date_from,
            date_to=comparison.yoy.date_to,
        ),
    )


def _plan_rank(plan_code: str | None) -> int:
    return PLAN_ORDER.get((plan_code or "starter").lower(), 0)


def require_analytics_plan(db: Session, hotel_id: int, minimum_plan: str) -> None:
    snapshot = get_subscription_snapshot(db, hotel_id)
    if _plan_rank(snapshot.get("plan")) < _plan_rank(minimum_plan):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Tu plan actual no incluye esta funcionalidad de Analytics ({minimum_plan}+ requerido).",
        )


def metric_card(
    card_code: str,
    label: str,
    *,
    value_ars: Decimal | float | int | str | None = None,
    value_ars_available: bool | None = None,
    value_pct: float | None = None,
    value_count: int | None = None,
) -> AnalyticsMetricCardRead:
    payload: dict[str, Any] = {"card_code": card_code, "label": label}
    if value_ars is not None:
        payload["value_ars"] = _money_str(value_ars)
        if value_ars_available is not None:
            payload["value_ars_available"] = value_ars_available
    if value_pct is not None:
        payload["value_pct"] = round(float(value_pct), 2)
    if value_count is not None:
        payload["value_count"] = int(value_count)
    return AnalyticsMetricCardRead(**payload)


def _serialize_company(company: Company) -> dict[str, Any]:
    return {
        "id": company.id,
        "hotel_id": company.hotel_id,
        "legal_name": company.legal_name,
        "display_name": company.display_name,
        "tax_id": company.tax_id,
        "country_code": company.country_code,
        "contact_name": company.contact_name,
        "email": company.contact_email,
        "phone": company.contact_phone,
        "administrative_contact": company.administrative_contact,
        "base_price": float(company.base_price) if company.base_price is not None else None,
        "payment_deferred": company.payment_deferred,
        "deferred_days": company.deferred_days,
        "requires_voucher": company.requires_voucher,
        "requires_signature": company.requires_signature,
        "notes": company.notes,
        "is_active": company.is_active,
        "created_at": company.created_at,
        "updated_at": company.updated_at,
        "deactivated_at": company.deactivated_at,
        "deactivated_by_user_id": company.deactivated_by_user_id,
    }


def _serialize_room_state_event(event: RoomStateEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "hotel_id": event.hotel_id,
        "room_id": event.room_id,
        "event_type": event.event_type,
        "reason_code": event.reason_code,
        "reason_note": event.reason_note,
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "created_by_user_id": event.created_by_user_id,
        "closed_by_user_id": event.closed_by_user_id,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def _serialize_alert_settings(settings: AnalyticsAlertSetting) -> dict[str, Any]:
    return {
        "hotel_id": settings.hotel_id,
        "cancellation_rate_threshold_pct": float(settings.cancellation_rate_threshold_pct),
        "commission_gap_threshold_pct": float(settings.commission_gap_threshold_pct),
        "subutilization_threshold_pct": float(settings.subutilization_threshold_pct),
        "pickup_drop_threshold_pct": float(settings.pickup_drop_threshold_pct),
        "updated_by_user_id": settings.updated_by_user_id,
        "created_at": settings.created_at,
        "updated_at": settings.updated_at,
    }


def _serialize_alert_snooze(snooze: AnalyticsAlertSnooze) -> dict[str, Any]:
    return {
        "id": snooze.id,
        "hotel_id": snooze.hotel_id,
        "alert_code": snooze.alert_code,
        "scope_key": snooze.scope_key,
        "snooze_until": snooze.snooze_until,
        "created_by_user_id": snooze.created_by_user_id,
        "created_at": snooze.created_at,
    }


def _record_audit_event(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    action_code: str,
    entity_type: str,
    entity_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> HotelAuditEvent:
    event = HotelAuditEvent(
        hotel_id=hotel_id,
        user_id=user_id,
        action_code=action_code,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=json.dumps(before, default=str, ensure_ascii=False) if before is not None else None,
        after_json=json.dumps(after, default=str, ensure_ascii=False) if after is not None else None,
    )
    db.add(event)
    return event


def record_hotel_audit_event(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    action_code: str,
    entity_type: str,
    entity_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> HotelAuditEvent:
    return _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code=action_code,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )


def _validate_company_uniques(db: Session, *, hotel_id: int, display_name: str, tax_id: str | None, exclude_id: int | None = None) -> None:
    conflict = db.query(Company.id).filter(Company.hotel_id == hotel_id, Company.display_name == display_name)
    if exclude_id is not None:
        conflict = conflict.filter(Company.id != exclude_id)
    if conflict.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una company con ese nombre en el hotel")

    if tax_id:
        conflict = db.query(Company.id).filter(Company.hotel_id == hotel_id, Company.tax_id == tax_id)
        if exclude_id is not None:
            conflict = conflict.filter(Company.id != exclude_id)
        if conflict.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una company con ese tax_id en el hotel")


def list_companies(db: Session, hotel_id: int) -> list[Company]:
    return (
        db.query(Company)
        .filter(Company.hotel_id == hotel_id)
        .order_by(Company.is_active.desc(), Company.display_name.asc(), Company.id.asc())
        .all()
    )


def get_company_or_404(db: Session, hotel_id: int, company_id: int) -> Company:
    company = db.query(Company).filter(Company.hotel_id == hotel_id, Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company no encontrada")
    return company


def create_company(db: Session, *, hotel_id: int, user_id: int, payload: CompanyCreate) -> Company:
    _validate_company_uniques(db, hotel_id=hotel_id, display_name=payload.display_name, tax_id=payload.tax_id)
    company = Company(
        hotel_id=hotel_id,
        legal_name=payload.legal_name,
        display_name=payload.display_name,
        tax_id=payload.tax_id,
        country_code=payload.country_code,
        contact_name=payload.contact_name,
        contact_email=payload.email,
        contact_phone=payload.phone,
        administrative_contact=payload.administrative_contact,
        # Off-system invoicing is intentionally not represented as a stored
        # reservation or company amount in the PMS.
        base_price=None if payload.payment_deferred else payload.base_price,
        extra_person_nightly_surcharge=payload.extra_person_nightly_surcharge,
        payment_deferred=payload.payment_deferred,
        deferred_days=payload.deferred_days,
        requires_voucher=payload.requires_voucher,
        requires_signature=payload.requires_signature,
        notes=payload.notes,
        is_active=True,
    )
    db.add(company)
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.company.created",
        entity_type="company",
        entity_id=company.id,
        after=_serialize_company(company),
    )
    return company


def update_company(db: Session, *, hotel_id: int, user_id: int, company_id: int, payload: CompanyUpdate) -> Company:
    company = get_company_or_404(db, hotel_id, company_id)
    before = _serialize_company(company)
    update_data = payload.model_dump(exclude_unset=True)
    if "display_name" in update_data or "tax_id" in update_data:
        next_display_name = update_data.get("display_name", company.display_name)
        next_tax_id = update_data.get("tax_id", company.tax_id)
        _validate_company_uniques(db, hotel_id=hotel_id, display_name=next_display_name, tax_id=next_tax_id, exclude_id=company.id)
    field_map = {
        "email": "contact_email",
        "phone": "contact_phone",
    }
    for field, value in update_data.items():
        setattr(company, field_map.get(field, field), value)
    if company.payment_deferred:
        company.base_price = None
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.company.updated",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after=_serialize_company(company),
    )
    return company


def deactivate_company(db: Session, *, hotel_id: int, user_id: int, company_id: int) -> Company:
    company = get_company_or_404(db, hotel_id, company_id)
    before = _serialize_company(company)
    company.is_active = False
    company.deactivated_at = _now()
    company.deactivated_by_user_id = user_id
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.company.deactivated",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after=_serialize_company(company),
    )
    return company


def reactivate_company(db: Session, *, hotel_id: int, user_id: int, company_id: int) -> Company:
    company = get_company_or_404(db, hotel_id, company_id)
    before = _serialize_company(company)
    company.is_active = True
    company.deactivated_at = None
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.company.reactivated",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after=_serialize_company(company),
    )
    return company


def get_company_fact_detail(
    db: Session,
    *,
    hotel_id: int,
    company_id: int,
    date_from: date,
    date_to: date,
    stream_details: bool = False,
) -> dict[str, Any]:
    company = get_company_or_404(db, hotel_id, company_id)
    facts_query = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.company_id == company_id,
            FactReservationDaily.stay_date.between(date_from, date_to),
        )
        .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
    )
    reservations_query = (
        active_reservations(db, hotel_id)
        .filter(
            Reservation.company_id == company_id,
            Reservation.check_in_date <= date_to,
            Reservation.check_out_date > date_from,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
    )
    if stream_details:
        fact_stats = (
            db.query(
                func.count(FactReservationDaily.id).label("nights_count"),
                func.coalesce(func.sum(FactReservationDaily.revenue_net_ars), 0).label("revenue_net_ars"),
                func.coalesce(_currency_unavailable_aggregate("ARS"), 0).label("ars_unavailable"),
                func.min(FactReservationDaily.updated_at).label("oldest_updated_at"),
            )
            .filter(
                FactReservationDaily.hotel_id == hotel_id,
                FactReservationDaily.company_id == company_id,
                FactReservationDaily.stay_date.between(date_from, date_to),
            )
            .one()
        )
        reservations_count = reservations_query.with_entities(Reservation.id).count()
        fact_count = int(fact_stats.nights_count or 0)
        revenue_net_ars = _money(fact_stats.revenue_net_ars)
        ars_available = not bool(fact_stats.ars_unavailable)
        data_as_of = fact_stats.oldest_updated_at
        facts = _MappedQueryRows(
            facts_query,
            _company_fact_read,
            column_names=(
                "stay_date", "reservation_id", "room_id", "category_id", "channel_code", "guest_segment",
                "outcome", "row_kind", "revenue_net_ars", "revenue_net_usd", "margin_operating_ars",
                "margin_operating_usd", "unavailable_currencies",
            ),
        )
        reservations = _MappedQueryRows(
            reservations_query.with_entities(
                Reservation.id,
                Reservation.confirmation_code,
                Reservation.status,
                Reservation.outcome,
                Reservation.check_in_date,
                Reservation.check_out_date,
                Reservation.room_id,
                Reservation.category_id,
                Reservation.company_id,
            ),
            _company_reservation_read,
            column_names=(
                "id", "confirmation_code", "status", "outcome", "check_in_date", "check_out_date",
                "room_id", "category_id", "company_id",
            ),
        )
    else:
        facts = facts_query.all()
        reservations = reservations_query.all()
        fact_count = len(facts)
        reservations_count = len(reservations)
        revenue_net_ars = sum((_money(fact.revenue_net_ars) for fact in facts), Decimal("0"))
        ars_available = not _currency_unavailable_for(facts, "ARS")
        data_as_of = _facts_data_as_of(facts)
    return {
        "company": _serialize_company(company),
        "facts": facts if stream_details else [_company_fact_read(fact) for fact in facts],
        "reservations": reservations if stream_details else [_company_reservation_read(reservation) for reservation in reservations],
        "cards": [
            metric_card("company_nights", "Noches del período", value_count=fact_count).model_dump(),
            metric_card(
                "company_revenue_net",
                "Revenue neto del período",
                value_ars=revenue_net_ars,
                value_ars_available=ars_available,
            ).model_dump(),
            metric_card("company_reservations", "Reservas asociadas", value_count=reservations_count).model_dump(),
        ],
        # Internal-only: consumed and popped by the /companies/{id} endpoint to
        # set honest envelope freshness. analytics_exports.py, the other
        # caller, pops and discards it so it never leaks into export files.
        "_data_as_of": data_as_of,
    }


def _company_fact_read(fact: FactReservationDaily) -> dict[str, Any]:
    return {
        "stay_date": fact.stay_date,
        "reservation_id": fact.reservation_id,
        "room_id": fact.room_id,
        "category_id": fact.category_id,
        "channel_code": fact.channel_code.value if hasattr(fact.channel_code, "value") else str(fact.channel_code),
        "guest_segment": fact.guest_segment.value if hasattr(fact.guest_segment, "value") else str(fact.guest_segment),
        "outcome": fact.outcome.value if hasattr(fact.outcome, "value") else str(fact.outcome),
        "row_kind": fact.row_kind.value if hasattr(fact.row_kind, "value") else str(fact.row_kind),
        "revenue_net_ars": _money_str(fact.revenue_net_ars),
        "revenue_net_usd": _money_str(fact.revenue_net_usd),
        "margin_operating_ars": _money_str(fact.margin_operating_ars),
        "margin_operating_usd": _money_str(fact.margin_operating_usd),
        "unavailable_currencies": _unavailable_currencies([fact]),
    }


def _company_reservation_read(reservation: Any) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status),
        "outcome": reservation.outcome.value if hasattr(reservation.outcome, "value") else str(reservation.outcome),
        "check_in_date": reservation.check_in_date,
        "check_out_date": reservation.check_out_date,
        "room_id": reservation.room_id,
        "category_id": reservation.category_id,
        "company_id": reservation.company_id,
    }


def _current_month_usage_key(db: Session, hotel_id: int) -> tuple[str, datetime]:
    now = _hotel_local_now(db, hotel_id)
    return now.strftime("%Y-%m"), now.astimezone(timezone.utc)


def _current_month_usage_row(db: Session, hotel_id: int) -> AnalyticsAIUsageMonthly | None:
    year_month, _ = _current_month_usage_key(db, hotel_id)
    return (
        db.query(AnalyticsAIUsageMonthly)
        .filter(AnalyticsAIUsageMonthly.hotel_id == hotel_id, AnalyticsAIUsageMonthly.year_month == year_month)
        .first()
    )


def reserve_ai_usage(
    db: Session,
    hotel_id: int,
    *,
    quota_monthly: int,
    units: int = 1,
) -> AnalyticsAIUsageMonthly:
    """Atomically reserve quota so concurrent requests cannot exceed the hotel limit."""
    units = int(units)
    quota_monthly = max(int(quota_monthly), 0)
    if units <= 0:
        raise ValueError("AI usage units must be positive")
    if units > quota_monthly:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Se alcanzó el límite mensual de solicitudes de IA.",
        )

    year_month, now_utc = _current_month_usage_key(db, hotel_id)

    def _try_reserve_existing() -> int:
        return db.query(AnalyticsAIUsageMonthly).filter(
            AnalyticsAIUsageMonthly.hotel_id == hotel_id,
            AnalyticsAIUsageMonthly.year_month == year_month,
            AnalyticsAIUsageMonthly.calls_used <= quota_monthly - units,
        ).update(
            {
                AnalyticsAIUsageMonthly.calls_used: AnalyticsAIUsageMonthly.calls_used + units,
                AnalyticsAIUsageMonthly.last_call_at: now_utc,
                AnalyticsAIUsageMonthly.updated_at: now_utc,
            },
            synchronize_session=False,
        )

    if _try_reserve_existing():
        db.expire_all()
        return db.query(AnalyticsAIUsageMonthly).filter(
            AnalyticsAIUsageMonthly.hotel_id == hotel_id,
            AnalyticsAIUsageMonthly.year_month == year_month,
        ).one()

    existing = db.query(AnalyticsAIUsageMonthly).filter(
        AnalyticsAIUsageMonthly.hotel_id == hotel_id,
        AnalyticsAIUsageMonthly.year_month == year_month,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Se alcanzó el límite mensual de solicitudes de IA.",
        )

    try:
        with db.begin_nested():
            row = AnalyticsAIUsageMonthly(
                hotel_id=hotel_id,
                year_month=year_month,
                calls_used=units,
                last_call_at=now_utc,
            )
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        # A concurrent first request inserted this hotel/month row. Retry as a
        # conditional update; the unique key plus the quota predicate decide
        # which request gets the final available unit.
        if _try_reserve_existing():
            db.expire_all()
            return db.query(AnalyticsAIUsageMonthly).filter(
                AnalyticsAIUsageMonthly.hotel_id == hotel_id,
                AnalyticsAIUsageMonthly.year_month == year_month,
            ).one()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Se alcanzó el límite mensual de solicitudes de IA.",
        )


def get_ai_config(db: Session, hotel_id: int) -> AnalyticsAIConfigRead:
    config = db.get(HotelConfiguration, hotel_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel no encontrado")

    runtime = get_analytics_ai_provider().status()
    usage = _current_month_usage_row(db, hotel_id)
    provider_config = build_analytics_ai_config(get_settings())
    quota_monthly = int(provider_config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK)
    quota_used = int(usage.calls_used or 0) if usage else 0
    quota_remaining = max(quota_monthly - quota_used, 0)
    return AnalyticsAIConfigRead(
        hotel_id=hotel_id,
        analytics_ai_enabled=bool(config.analytics_ai_enabled),
        provider=runtime.provider,
        runtime_healthy=runtime.runtime_healthy,
        effective_model=runtime.effective_model or provider_config.model or None,
        quota_monthly=quota_monthly,
        quota_used=quota_used,
        quota_remaining=quota_remaining,
    )


def patch_ai_config(db: Session, *, hotel_id: int, user_id: int, payload: AnalyticsAIConfigUpdate) -> AnalyticsAIConfigRead:
    config = db.get(HotelConfiguration, hotel_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel no encontrado")
    before = {"hotel_id": hotel_id, "analytics_ai_enabled": bool(config.analytics_ai_enabled)}
    config.analytics_ai_enabled = payload.analytics_ai_enabled
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.ai.settings.updated",
        entity_type="analytics_ai_config",
        entity_id=hotel_id,
        before=before,
        after={"hotel_id": hotel_id, "analytics_ai_enabled": bool(config.analytics_ai_enabled)},
    )
    return get_ai_config(db, hotel_id)


def get_alert_settings(db: Session, *, hotel_id: int, user_id: int) -> AnalyticsAlertSettingsRead:
    settings_row = db.get(AnalyticsAlertSetting, hotel_id)
    if not settings_row:
        settings_row = AnalyticsAlertSetting(
            hotel_id=hotel_id,
            cancellation_rate_threshold_pct=15.00,
            commission_gap_threshold_pct=25.00,
            subutilization_threshold_pct=40.00,
            pickup_drop_threshold_pct=20.00,
            updated_by_user_id=user_id,
        )
        db.add(settings_row)
        db.flush()
    return AnalyticsAlertSettingsRead.model_validate(settings_row)


def patch_alert_settings(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    payload: AnalyticsAlertSettingsUpdate,
) -> AnalyticsAlertSettingsRead:
    settings_row = db.get(AnalyticsAlertSetting, hotel_id)
    if not settings_row:
        settings_row = AnalyticsAlertSetting(
            hotel_id=hotel_id,
            cancellation_rate_threshold_pct=15.00,
            commission_gap_threshold_pct=25.00,
            subutilization_threshold_pct=40.00,
            pickup_drop_threshold_pct=20.00,
            updated_by_user_id=user_id,
        )
        db.add(settings_row)
        db.flush()
    before = _serialize_alert_settings(settings_row)
    payload_data = payload.model_dump(exclude_unset=True)
    for field, value in payload_data.items():
        setattr(settings_row, field, value)
    settings_row.updated_by_user_id = user_id
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.alert_settings.updated",
        entity_type="analytics_alert_settings",
        entity_id=hotel_id,
        before=before,
        after=_serialize_alert_settings(settings_row),
    )
    return AnalyticsAlertSettingsRead.model_validate(settings_row)


def snooze_alert(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    alert_code: str,
    payload: AnalyticsAlertSnoozeCreate,
) -> AnalyticsAlertSnoozeRead:
    duration_map = {"24h": timedelta(hours=24), "72h": timedelta(hours=72), "7d": timedelta(days=7)}
    snooze_until = _now() + duration_map[payload.duration_code]
    snooze = (
        db.query(AnalyticsAlertSnooze)
        .filter(
            AnalyticsAlertSnooze.hotel_id == hotel_id,
            AnalyticsAlertSnooze.alert_code == alert_code,
            AnalyticsAlertSnooze.scope_key == payload.scope_key,
        )
        .first()
    )
    before = _serialize_alert_snooze(snooze) if snooze else None
    if snooze:
        snooze.snooze_until = snooze_until
        snooze.created_by_user_id = user_id
    else:
        snooze = AnalyticsAlertSnooze(
            hotel_id=hotel_id,
            alert_code=alert_code,
            scope_key=payload.scope_key,
            snooze_until=snooze_until,
            created_by_user_id=user_id,
        )
        db.add(snooze)
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.alert.snoozed",
        entity_type="analytics_alert_snooze",
        entity_id=snooze.id,
        before=before,
        after=_serialize_alert_snooze(snooze),
    )
    return AnalyticsAlertSnoozeRead.model_validate(snooze)


def unsnooze_alert(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    alert_code: str,
    scope_key: str,
) -> dict[str, Any]:
    snooze = (
        db.query(AnalyticsAlertSnooze)
        .filter(
            AnalyticsAlertSnooze.hotel_id == hotel_id,
            AnalyticsAlertSnooze.alert_code == alert_code,
            AnalyticsAlertSnooze.scope_key == scope_key,
        )
        .first()
    )
    if not snooze:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snooze no encontrado")
    before = _serialize_alert_snooze(snooze)
    db.delete(snooze)
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.alert.unsnoozed",
        entity_type="analytics_alert_snooze",
        entity_id=snooze.id,
        before=before,
        after=None,
    )
    return {"deleted": True, "alert_code": alert_code, "scope_key": scope_key}


def _fetch_room_state_events(db: Session, *, hotel_id: int, room_id: int) -> list[RoomStateEvent]:
    return (
        db.query(RoomStateEvent)
        .filter(RoomStateEvent.hotel_id == hotel_id, RoomStateEvent.room_id == room_id)
        .order_by(RoomStateEvent.started_at.asc(), RoomStateEvent.id.asc())
        .all()
    )


def create_room_state_event(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    payload: RoomStateEventCreate,
) -> RoomStateEvent:
    room = db.query(Room).filter(Room.hotel_id == hotel_id, Room.id == payload.room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room no encontrada")

    started_at = _ensure_utc(payload.started_at or _now())
    now = _ensure_utc(_now())
    if started_at and now and started_at > now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="started_at no puede ser futuro")

    open_event = (
        db.query(RoomStateEvent)
        .filter(
            RoomStateEvent.hotel_id == hotel_id,
            RoomStateEvent.room_id == payload.room_id,
            RoomStateEvent.ended_at.is_(None),
        )
        .first()
    )
    if open_event:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un evento abierto para esta habitacion")

    latest_event = (
        db.query(RoomStateEvent)
        .filter(RoomStateEvent.hotel_id == hotel_id, RoomStateEvent.room_id == payload.room_id)
        .order_by(RoomStateEvent.started_at.desc(), RoomStateEvent.id.desc())
        .first()
    )
    latest_event_ended_at = _ensure_utc(latest_event.ended_at) if latest_event else None
    if latest_event and latest_event_ended_at and latest_event_ended_at > started_at:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El nuevo evento se superpone con el historial existente")

    event = RoomStateEvent(
        hotel_id=hotel_id,
        room_id=payload.room_id,
        event_type=payload.event_type,
        reason_code=payload.reason_code,
        reason_note=payload.reason_note,
        started_at=started_at,
        created_by_user_id=user_id,
        closed_by_user_id=None,
    )
    db.add(event)
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.room_state_event.created",
        entity_type="room_state_event",
        entity_id=event.id,
        after=_serialize_room_state_event(event),
    )
    touch_room_state_event_fact_window(
        db,
        hotel_id=hotel_id,
        room_id=event.room_id,
        event_started_at=event.started_at,
    )
    return event


def close_room_state_event(db: Session, *, hotel_id: int, user_id: int, event_id: int) -> RoomStateEvent:
    event = (
        db.query(RoomStateEvent)
        .filter(RoomStateEvent.hotel_id == hotel_id, RoomStateEvent.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room state event no encontrado")
    if event.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El evento ya fue cerrado")

    before = _serialize_room_state_event(event)
    ended_at = _ensure_utc(_now())
    started_at = _ensure_utc(event.started_at)
    if ended_at and started_at and ended_at <= started_at:
        ended_at = started_at + timedelta(microseconds=1)
    event.ended_at = ended_at
    event.closed_by_user_id = user_id
    db.flush()
    _record_audit_event(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        action_code="analytics.room_state_event.closed",
        entity_type="room_state_event",
        entity_id=event.id,
        before=before,
        after=_serialize_room_state_event(event),
    )
    touch_room_state_event_fact_window(
        db,
        hotel_id=hotel_id,
        room_id=event.room_id,
        event_started_at=event.started_at,
    )
    return event


def _group_rows(rows: list[Any], key: str) -> dict[Any, list[Any]]:
    grouped: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, key)].append(row)
    return grouped


def _room_lookup_map(db: Session, hotel_id: int) -> dict[int, Any]:
    # This report needs only scalar room fields. Selecting columns avoids ORM
    # relationship loaders pulling every reservation attached to each room.
    rows = active_rooms(db, hotel_id).with_entities(
        Room.id,
        Room.room_number,
        Room.floor,
        Room.category_id,
        Room.is_active,
        Room.status,
    ).all()
    return {row.id: row for row in rows}


def _category_lookup_map(db: Session, hotel_id: int) -> dict[int, Any]:
    rows = (
        db.query(RoomCategory.id, RoomCategory.name)
        .filter(RoomCategory.hotel_id == hotel_id)
        .all()
    )
    return {row.id: row for row in rows}


def _company_lookup_map(db: Session, hotel_id: int) -> dict[int, Company]:
    companies = db.query(Company).filter(Company.hotel_id == hotel_id).all()
    return {company.id: company for company in companies}


def _load_reservation_facts(db: Session, hotel_id: int, date_from: date, date_to: date) -> list[FactReservationDaily]:
    return (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.stay_date.between(date_from, date_to),
        )
        .all()
    )


def _load_room_facts(db: Session, hotel_id: int, date_from: date, date_to: date) -> list[FactRoomOccupancyDaily]:
    active_room_ids = active_rooms(db, hotel_id).with_entities(Room.id).statement
    return (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.stay_date.between(date_from, date_to),
            FactRoomOccupancyDaily.room_id.in_(active_room_ids),
        )
        .all()
    )


def _sum_money(rows: list[Any], attr: str) -> Decimal:
    return sum((_money(getattr(row, attr)) for row in rows), Decimal("0.00"))


def _currency_unavailable_for(rows: list[Any], target_currency: str) -> bool:
    target = target_currency.upper()
    if target not in {"ARS", "USD"}:
        return True
    money_fields = ("revenue_gross", "revenue_net", "tax", "fee", "commission", "variable_cost", "margin_operating")
    for row in rows:
        source = str(getattr(row, "source_currency", "") or "").strip().upper()
        if source not in {"ARS", "USD"}:
            return True
        if source == target:
            continue
        fx_rate = _money(getattr(row, "fx_rate_snapshot", None))
        if fx_rate > 0:
            continue
        source_fields = (
            (f"{field}_{source.lower()}" for field in money_fields)
        )
        if any(_money(getattr(row, field, None)) != 0 for field in source_fields):
            return True
    return False


def _unavailable_currencies(rows: list[Any]) -> list[str]:
    return [currency for currency in ("ARS", "USD") if _currency_unavailable_for(rows, currency)]


def _unavailable_currency_metadata(rows: list[Any]) -> dict[str, list[str]]:
    return {"unavailable_currencies": _unavailable_currencies(rows)}


def _currency_unavailable_aggregate(target_currency: str, *, condition=None):
    """Build a SQL aggregate matching `_currency_unavailable_for` semantics."""
    target = target_currency.upper()
    if target not in {"ARS", "USD"}:
        raise ValueError("target_currency must be ARS or USD")
    source = func.upper(func.trim(FactReservationDaily.source_currency))
    fx_available = func.coalesce(FactReservationDaily.fx_rate_snapshot, 0) > 0
    unsupported_source = or_(
        FactReservationDaily.source_currency.is_(None),
        source.notin_(["ARS", "USD"]),
    )
    opposite = "USD" if target == "ARS" else "ARS"
    money_fields = (
        "revenue_gross",
        "revenue_net",
        "tax",
        "fee",
        "commission",
        "variable_cost",
        "margin_operating",
    )
    has_source_amount = or_(
        *(
            func.coalesce(getattr(FactReservationDaily, f"{field}_{opposite.lower()}"), 0) != 0
            for field in money_fields
        )
    )
    unavailable = or_(
        unsupported_source,
        and_(source == opposite, ~fx_available, has_source_amount),
    )
    if condition is not None:
        unavailable = and_(condition, unavailable)
    return func.max(case((unavailable, 1), else_=0))


def _reservation_fact_breakdown(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    group_column,
    output_key: str,
    facts: list[FactReservationDaily] | None,
    include_totals: bool = True,
) -> tuple[list[dict[str, Any]], datetime | None]:
    """Aggregate reservation facts in SQL unless a caller already has rows.

    Grouped counts and money are optional when a caller needs only currency
    availability by group, as in the room overview.
    """
    if facts is not None:
        grouped = _group_rows(facts, group_column.key)
        result = []
        for group, rows in grouped.items():
            item = {
                output_key: group.value if hasattr(group, "value") else group,
                **_unavailable_currency_metadata(rows),
            }
            if include_totals:
                item.update(
                    {
                        "reservations_count": len({row.reservation_id for row in rows}),
                        "nights_count": len(rows),
                        "revenue_gross_ars": _money_str(_sum_money(rows, "revenue_gross_ars")),
                        "revenue_net_ars": _money_str(_sum_money(rows, "revenue_net_ars")),
                    }
                )
            result.append(item)
        return sorted(result, key=lambda item: item[output_key]), _facts_data_as_of(facts)

    ars_unavailable = _currency_unavailable_aggregate("ARS").label("ars_unavailable")
    usd_unavailable = _currency_unavailable_aggregate("USD").label("usd_unavailable")

    query_columns = [group_column.label("group_key"), ars_unavailable, usd_unavailable]
    if include_totals:
        query_columns.extend(
            [
                func.count(func.distinct(FactReservationDaily.reservation_id)).label("reservations_count"),
                func.count(FactReservationDaily.id).label("nights_count"),
                func.coalesce(func.sum(FactReservationDaily.revenue_gross_ars), 0).label("revenue_gross_ars"),
                func.coalesce(func.sum(FactReservationDaily.revenue_net_ars), 0).label("revenue_net_ars"),
            ]
        )
    query_columns.append(func.min(FactReservationDaily.updated_at).label("oldest_updated_at"))
    rows = (
        db.query(*query_columns)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.stay_date.between(date_from, date_to),
        )
        .group_by(group_column)
        .all()
    )
    result = []
    timestamps = []
    for row in rows:
        if row.oldest_updated_at is not None:
            timestamps.append(row.oldest_updated_at)
        item = {
            output_key: (
                row.group_key.value
                if hasattr(row.group_key, "value")
                else str(row.group_key) if isinstance(row.group_key, str) else row.group_key
            ),
            "unavailable_currencies": [
                currency
                for currency, unavailable in (("ARS", row.ars_unavailable), ("USD", row.usd_unavailable))
                if bool(unavailable)
            ],
        }
        if include_totals:
            item.update(
                {
                    "reservations_count": int(row.reservations_count or 0),
                    "nights_count": int(row.nights_count or 0),
                    "revenue_gross_ars": _money_str(row.revenue_gross_ars),
                    "revenue_net_ars": _money_str(row.revenue_net_ars),
                }
            )
        result.append(item)
    return sorted(result, key=lambda item: (item[output_key] is None, str(item[output_key]))), min(timestamps) if timestamps else None


def _reservation_fact_summary(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    room_revenue = and_(
        FactReservationDaily.occupied_night.is_(True),
        FactReservationDaily.chargeable_night.is_(True),
    )
    row = (
        db.query(
            func.coalesce(func.sum(FactReservationDaily.revenue_gross_ars), 0).label("revenue_gross_ars"),
            func.coalesce(func.sum(FactReservationDaily.revenue_net_ars), 0).label("revenue_net_ars"),
            func.coalesce(
                func.sum(case((room_revenue, FactReservationDaily.revenue_net_ars), else_=0)), 0
            ).label("room_revenue_net_ars"),
            func.coalesce(func.sum(case((room_revenue, 1), else_=0)), 0).label("occupied_chargeable_nights"),
            func.coalesce(
                func.sum(case((FactReservationDaily.outcome == ReservationOutcomeEnum.NO_SHOW, 1), else_=0)), 0
            ).label("no_show_count"),
            func.coalesce(_currency_unavailable_aggregate("ARS"), 0).label("ars_unavailable"),
            func.coalesce(_currency_unavailable_aggregate("ARS", condition=room_revenue), 0).label(
                "room_ars_unavailable"
            ),
            func.min(FactReservationDaily.updated_at).label("oldest_updated_at"),
        )
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.stay_date.between(date_from, date_to),
        )
        .one()
    )
    return {
        "revenue_gross_ars": _money(row.revenue_gross_ars),
        "revenue_net_ars": _money(row.revenue_net_ars),
        "room_revenue_net_ars": _money(row.room_revenue_net_ars),
        "occupied_chargeable_nights": int(row.occupied_chargeable_nights or 0),
        "no_show_count": int(row.no_show_count or 0),
        "ars_available": not bool(row.ars_unavailable),
        "room_ars_available": not bool(row.room_ars_unavailable),
        "data_as_of": row.oldest_updated_at,
    }


def _room_occupancy_summary(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    active_room_ids = active_rooms(db, hotel_id).with_entities(Room.id).statement
    row = (
        db.query(
            func.count(FactRoomOccupancyDaily.id).label("row_count"),
            func.coalesce(func.sum(case((FactRoomOccupancyDaily.is_occupied.is_(True), 1), else_=0)), 0).label(
                "occupied_count"
            ),
            func.coalesce(
                func.sum(case((FactRoomOccupancyDaily.is_sellable_night.is_(True), 1), else_=0)), 0
            ).label("sellable_count"),
            func.min(FactRoomOccupancyDaily.updated_at).label("oldest_updated_at"),
        )
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.stay_date.between(date_from, date_to),
            FactRoomOccupancyDaily.room_id.in_(active_room_ids),
        )
        .one()
    )
    return {
        "row_count": int(row.row_count or 0),
        "occupied_count": int(row.occupied_count or 0),
        "sellable_count": int(row.sellable_count or 0),
        "data_as_of": row.oldest_updated_at,
    }


def _minimum_timestamp(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def build_starter_summary_payload(db: Session, *, hotel_id: int, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    window = _utc_date_range(db, hotel_id, date_from, date_to)
    reservation_summary = _reservation_fact_summary(
        db,
        hotel_id=hotel_id,
        date_from=window.date_from,
        date_to=window.date_to,
    )
    occupancy_summary = _room_occupancy_summary(
        db,
        hotel_id=hotel_id,
        date_from=window.date_to,
        date_to=window.date_to,
    )
    arrivals = (
        active_reservations(db, hotel_id)
        .filter(
            Reservation.check_in_date == window.date_to,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .count()
    )
    total_rooms = active_rooms(db, hotel_id).filter(Room.is_active.is_(True)).count()
    occupied_rooms = occupancy_summary["occupied_count"]
    occupancy_pct = (occupied_rooms / total_rooms * 100.0) if total_rooms else 0.0
    cards = [
        metric_card(
            "starter_revenue_month",
            "Revenue del mes",
            value_ars=reservation_summary["revenue_gross_ars"],
            value_ars_available=reservation_summary["ars_available"],
        ).model_dump(),
        metric_card("starter_occupancy_today", "Ocupación hoy", value_pct=occupancy_pct).model_dump(),
        metric_card("starter_arrivals_today", "Llegadas hoy", value_count=arrivals).model_dump(),
    ]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "data": {"cards": cards},
        "generated_at": _now(),
        "data_as_of": _minimum_timestamp(reservation_summary["data_as_of"], occupancy_summary["data_as_of"]),
    }


def build_home_payload(
    db: Session,
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    resolved_window: DateWindow | None = None,
    reservation_facts: list[FactReservationDaily] | None = None,
    room_facts: list[FactRoomOccupancyDaily] | None = None,
) -> dict[str, Any]:
    window = resolved_window or _analytics_window(
        db,
        hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )
    facts = reservation_facts
    room_rows = room_facts
    reservation_summary = None
    room_summary = None
    if facts is None:
        reservation_summary = _reservation_fact_summary(
            db,
            hotel_id=hotel_id,
            date_from=window.date_from,
            date_to=window.date_to,
        )
    if room_rows is None:
        room_summary = _room_occupancy_summary(
            db,
            hotel_id=hotel_id,
            date_from=window.date_from,
            date_to=window.date_to,
        )
    pickup_30d = calculate_pickup_30d_count(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
    physical_room_nights = calculate_physical_room_nights_for_hotel(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
    room_revenue_facts = [fact for fact in facts if fact.occupied_night and fact.chargeable_night] if facts is not None else []
    if facts is not None:
        revenue_gross_ars = _sum_money(facts, "revenue_gross_ars")
        revenue_net_ars = _sum_money(facts, "revenue_net_ars")
        revenue_ars_available = not _currency_unavailable_for(facts, "ARS")
        room_revenue_net_ars = _sum_money(room_revenue_facts, "revenue_net_ars")
        occupied_chargeable_nights = len(room_revenue_facts)
        room_revenue_ars_available = not _currency_unavailable_for(room_revenue_facts, "ARS")
        no_show_count = len(
            [fact for fact in facts if getattr(fact.outcome, "value", fact.outcome) == ReservationOutcomeEnum.NO_SHOW.value]
        )
        reservation_data_as_of = _facts_data_as_of(facts)
    else:
        revenue_gross_ars = reservation_summary["revenue_gross_ars"]
        revenue_net_ars = reservation_summary["revenue_net_ars"]
        revenue_ars_available = reservation_summary["ars_available"]
        room_revenue_net_ars = reservation_summary["room_revenue_net_ars"]
        occupied_chargeable_nights = reservation_summary["occupied_chargeable_nights"]
        room_revenue_ars_available = reservation_summary["room_ars_available"]
        no_show_count = reservation_summary["no_show_count"]
        reservation_data_as_of = reservation_summary["data_as_of"]

    if room_rows is not None:
        room_row_count = len(room_rows)
        occupied_room_nights = sum(1 for row in room_rows if row.is_occupied)
        sellable_room_nights = sum(1 for row in room_rows if row.is_sellable_night)
        room_data_as_of = _facts_data_as_of(room_rows)
    else:
        room_row_count = room_summary["row_count"]
        occupied_room_nights = room_summary["occupied_count"]
        sellable_room_nights = room_summary["sellable_count"]
        room_data_as_of = room_summary["data_as_of"]
    adr_ars = (
        _money(room_revenue_net_ars / Decimal(occupied_chargeable_nights))
        if occupied_chargeable_nights
        else None
    )
    revpar_ars = (
        _money(room_revenue_net_ars / Decimal(sellable_room_nights))
        if sellable_room_nights
        else None
    )
    cards = [
        metric_card(
            "home_revenue_gross",
            "Revenue bruto",
            value_ars=revenue_gross_ars,
            value_ars_available=revenue_ars_available,
        ).model_dump(),
        metric_card(
            "home_revenue_net",
            "Revenue neto",
            value_ars=revenue_net_ars,
            value_ars_available=revenue_ars_available,
        ).model_dump(),
        metric_card(
            "home_adr",
            "ADR",
            value_ars=adr_ars,
            value_ars_available=room_revenue_ars_available,
        ).model_dump(),
        metric_card(
            "home_revpar",
            "RevPAR",
            value_ars=revpar_ars,
            value_ars_available=room_revenue_ars_available,
        ).model_dump(),
        metric_card(
            "home_occupancy",
            "Ocupación promedio",
            value_pct=((occupied_room_nights / room_row_count) * 100.0) if room_row_count else 0.0,
        ).model_dump(),
        metric_card(
            "home_no_shows",
            "No-shows",
            value_count=no_show_count,
        ).model_dump(),
        metric_card("home_pickup_30d", "Pickup 30 días", value_count=pickup_30d).model_dump(),
        metric_card("home_physical_room_nights", "Noches-habitación disponibles", value_count=physical_room_nights).model_dump(),
    ]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": cards,
            "top_channels": build_channels_breakdown(
                db,
                hotel_id=hotel_id,
                date_from=window.date_from,
                date_to=window.date_to,
                facts=facts,
            ),
            "segments": build_segments_breakdown(
                db,
                hotel_id=hotel_id,
                date_from=window.date_from,
                date_to=window.date_to,
                facts=facts,
            ),
        },
        "generated_at": _now(),
        "data_as_of": _minimum_timestamp(reservation_data_as_of, room_data_as_of),
    }


def build_rooms_overview_payload(
    db: Session,
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    rooms = _room_lookup_map(db, hotel_id)
    categories = _category_lookup_map(db, hotel_id)
    active_room_ids = active_rooms(db, hotel_id).with_entities(Room.id).statement
    occupancy_rows = (
        db.query(
            FactRoomOccupancyDaily.room_id.label("room_id"),
            func.count(FactRoomOccupancyDaily.id).label("night_count"),
            func.coalesce(
                func.sum(case((FactRoomOccupancyDaily.is_occupied.is_(True), 1), else_=0)), 0
            ).label("occupied_nights"),
            func.coalesce(func.sum(FactRoomOccupancyDaily.revenue_net_ars), 0).label("revenue_net_ars"),
            func.coalesce(func.sum(FactRoomOccupancyDaily.revenue_net_usd), 0).label("revenue_net_usd"),
            func.coalesce(func.sum(FactRoomOccupancyDaily.margin_operating_ars), 0).label(
                "margin_operating_ars"
            ),
            func.coalesce(func.sum(FactRoomOccupancyDaily.margin_operating_usd), 0).label(
                "margin_operating_usd"
            ),
            func.min(FactRoomOccupancyDaily.updated_at).label("oldest_updated_at"),
        )
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.stay_date.between(window.date_from, window.date_to),
            FactRoomOccupancyDaily.room_id.in_(active_room_ids),
        )
        .group_by(FactRoomOccupancyDaily.room_id)
        .all()
    )
    occupancy_by_room = {row.room_id: row for row in occupancy_rows}
    currency_facts_by_room_rows, currency_data_as_of = _reservation_fact_breakdown(
        db,
        hotel_id=hotel_id,
        date_from=window.date_from,
        date_to=window.date_to,
        group_column=FactReservationDaily.room_id,
        output_key="room_id",
        facts=None,
        include_totals=False,
    )
    currency_facts_by_room = {row["room_id"]: row for row in currency_facts_by_room_rows}
    payload_rooms = []
    for room in rooms.values():
        room_facts = occupancy_by_room.get(room.id)
        currency_metadata = currency_facts_by_room.get(room.id, {}).get("unavailable_currencies", [])
        payload_rooms.append(
            {
                "room_id": room.id,
                "room_number": room.room_number,
                "floor": room.floor,
                "category_id": room.category_id,
                "category_name": categories.get(room.category_id).name if categories.get(room.category_id) else None,
                "is_active": room.is_active,
                "status": room.status.value if hasattr(room.status, "value") else str(room.status),
                "occupied_nights": int(room_facts.occupied_nights or 0) if room_facts else 0,
                "revenue_net_ars": _money_str(room_facts.revenue_net_ars if room_facts else 0),
                "revenue_net_usd": _money_str(room_facts.revenue_net_usd if room_facts else 0),
                "margin_operating_ars": _money_str(room_facts.margin_operating_ars if room_facts else 0),
                "margin_operating_usd": _money_str(room_facts.margin_operating_usd if room_facts else 0),
                "unavailable_currencies": currency_metadata,
            }
        )
    room_count = sum(int(row.night_count or 0) for row in occupancy_rows)
    occupied_nights = sum(int(row.occupied_nights or 0) for row in occupancy_rows)
    room_data_as_of = min(
        (row.oldest_updated_at for row in occupancy_rows if row.oldest_updated_at is not None),
        default=None,
    )
    cards = [
        metric_card("rooms_total", "Habitaciones activas", value_count=len([room for room in rooms.values() if room.is_active])).model_dump(),
        metric_card("rooms_occupied", "Noches ocupadas", value_count=occupied_nights).model_dump(),
        metric_card("rooms_occupancy", "Ocupación promedio", value_pct=((occupied_nights / room_count) * 100.0) if room_count else 0.0).model_dump(),
    ]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": cards,
            "rooms": payload_rooms,
        },
        "generated_at": _now(),
        "data_as_of": _minimum_timestamp(room_data_as_of, currency_data_as_of),
    }


def build_room_detail_payload(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    stream_details: bool = False,
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    room = db.query(Room).filter(Room.hotel_id == hotel_id, Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room no encontrada")
    category = db.get(RoomCategory, room.category_id) if room.category_id else None
    facts_query = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.room_id == room_id,
            FactRoomOccupancyDaily.stay_date.between(window.date_from, window.date_to),
        )
        .order_by(FactRoomOccupancyDaily.stay_date.asc())
    )
    currency_facts_query = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.room_id == room_id,
            FactReservationDaily.stay_date.between(window.date_from, window.date_to),
        )
        .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
    )
    events_query = (
        db.query(RoomStateEvent)
        .filter(RoomStateEvent.hotel_id == hotel_id, RoomStateEvent.room_id == room_id)
        .order_by(RoomStateEvent.started_at.asc(), RoomStateEvent.id.asc())
    )
    if stream_details:
        fact_query = (
            db.query(FactRoomOccupancyDaily, FactReservationDaily)
            .outerjoin(
                FactReservationDaily,
                and_(
                    FactReservationDaily.hotel_id == FactRoomOccupancyDaily.hotel_id,
                    FactReservationDaily.reservation_id == FactRoomOccupancyDaily.reservation_id,
                    FactReservationDaily.stay_date == FactRoomOccupancyDaily.stay_date,
                    FactReservationDaily.room_id == FactRoomOccupancyDaily.room_id,
                ),
            )
            .filter(
                FactRoomOccupancyDaily.hotel_id == hotel_id,
                FactRoomOccupancyDaily.room_id == room_id,
                FactRoomOccupancyDaily.stay_date.between(window.date_from, window.date_to),
            )
            .order_by(FactRoomOccupancyDaily.stay_date.asc())
        )
        fact_as_of = (
            db.query(func.min(FactRoomOccupancyDaily.updated_at))
            .filter(
                FactRoomOccupancyDaily.hotel_id == hotel_id,
                FactRoomOccupancyDaily.room_id == room_id,
                FactRoomOccupancyDaily.stay_date.between(window.date_from, window.date_to),
            )
            .scalar()
        )
        currency_as_of = (
            db.query(func.min(FactReservationDaily.updated_at))
            .filter(
                FactReservationDaily.hotel_id == hotel_id,
                FactReservationDaily.room_id == room_id,
                FactReservationDaily.stay_date.between(window.date_from, window.date_to),
            )
            .scalar()
        )
        facts = _MappedQueryRows(
            fact_query,
            _room_detail_fact_read,
            column_names=(
                "stay_date", "status_at_night", "is_sellable_night", "is_occupied", "reservation_id",
                "revenue_net_ars", "revenue_net_usd", "margin_operating_ars", "margin_operating_usd",
                "unavailable_currencies",
            ),
        )
        events = _MappedQueryRows(
            events_query,
            _serialize_room_state_event,
            column_names=(
                "id", "hotel_id", "room_id", "event_type", "reason_code", "reason_note", "started_at",
                "ended_at", "created_by_user_id", "closed_by_user_id", "created_at", "updated_at",
            ),
        )
        data_as_of = _minimum_timestamp(fact_as_of, currency_as_of)
    else:
        facts_rows = facts_query.all()
        currency_facts = currency_facts_query.all()
        currency_facts_by_night = {
            (fact.reservation_id, fact.stay_date): fact
            for fact in currency_facts
            if fact.room_id == room_id
        }
        events = events_query.all()
        facts = [
            _room_detail_fact_read((fact, currency_facts_by_night.get((fact.reservation_id, fact.stay_date))))
            for fact in facts_rows
        ]
        events = [_serialize_room_state_event(event) for event in events]
        data_as_of = _facts_data_as_of(facts_rows, currency_facts)
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "room": {
                "room_id": room.id,
                "room_number": room.room_number,
                "floor": room.floor,
                "category_id": room.category_id,
                "category_name": category.name if category else None,
                "status": room.status.value if hasattr(room.status, "value") else str(room.status),
                "is_active": room.is_active,
                "notes": room.notes,
            },
            "facts": facts,
            "events": events,
        },
        "generated_at": _now(),
        "data_as_of": data_as_of,
    }


def _room_detail_fact_read(row: Any) -> dict[str, Any]:
    fact, currency_fact = row
    return {
        "stay_date": fact.stay_date,
        "status_at_night": fact.status_at_night.value if hasattr(fact.status_at_night, "value") else str(fact.status_at_night),
        "is_sellable_night": fact.is_sellable_night,
        "is_occupied": fact.is_occupied,
        "reservation_id": fact.reservation_id,
        "revenue_net_ars": _money_str(fact.revenue_net_ars),
        "revenue_net_usd": _money_str(fact.revenue_net_usd),
        "margin_operating_ars": _money_str(fact.margin_operating_ars),
        "margin_operating_usd": _money_str(fact.margin_operating_usd),
        **_unavailable_currency_metadata([currency_fact] if currency_fact is not None else []),
    }


def build_category_detail_payload(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    stream_details: bool = False,
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    category = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id, RoomCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category no encontrada")
    rooms_query = (
        active_rooms(db, hotel_id)
        .filter(Room.category_id == category_id)
        .order_by(Room.room_number.asc())
    )
    facts_query = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.category_id == category_id,
            FactReservationDaily.stay_date.between(window.date_from, window.date_to),
        )
        .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
    )
    if stream_details:
        rooms = _MappedQueryRows(
            rooms_query,
            _category_room_read,
            column_names=("room_id", "room_number", "floor", "is_active", "status"),
        )
        facts = _MappedQueryRows(
            facts_query,
            _category_fact_read,
            column_names=(
                "stay_date", "reservation_id", "room_id", "outcome", "revenue_net_ars", "revenue_net_usd",
                "unavailable_currencies",
            ),
        )
        data_as_of = (
            db.query(func.min(FactReservationDaily.updated_at))
            .filter(
                FactReservationDaily.hotel_id == hotel_id,
                FactReservationDaily.category_id == category_id,
                FactReservationDaily.stay_date.between(window.date_from, window.date_to),
            )
            .scalar()
        )
    else:
        rooms = [_category_room_read(room) for room in rooms_query.all()]
        fact_rows = facts_query.all()
        facts = [_category_fact_read(fact) for fact in fact_rows]
        data_as_of = _facts_data_as_of(fact_rows)
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "category": {
                "category_id": category.id,
                "name": category.name,
                "code": category.code,
                "description": category.description,
                "base_price_per_night": float(category.base_price_per_night),
                "variable_cost_per_night": _money_str(category.variable_cost_per_night),
                "max_occupancy": category.max_occupancy,
            },
            "rooms": rooms,
            "facts": facts,
        },
        "generated_at": _now(),
        "data_as_of": data_as_of,
    }


def _category_room_read(room: Room) -> dict[str, Any]:
    return {
        "room_id": room.id,
        "room_number": room.room_number,
        "floor": room.floor,
        "is_active": room.is_active,
        "status": room.status.value if hasattr(room.status, "value") else str(room.status),
    }


def _category_fact_read(fact: FactReservationDaily) -> dict[str, Any]:
    return {
        "stay_date": fact.stay_date,
        "reservation_id": fact.reservation_id,
        "room_id": fact.room_id,
        "outcome": fact.outcome.value if hasattr(fact.outcome, "value") else str(fact.outcome),
        "revenue_net_ars": _money_str(fact.revenue_net_ars),
        "revenue_net_usd": _money_str(fact.revenue_net_usd),
        **_unavailable_currency_metadata([fact]),
    }


def build_segments_breakdown(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    facts: list[FactReservationDaily] | None = None,
) -> list[dict[str, Any]]:
    result, _ = _reservation_fact_breakdown(
        db,
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        group_column=FactReservationDaily.guest_segment,
        output_key="guest_segment",
        facts=facts,
    )
    return result


def build_channels_breakdown(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    facts: list[FactReservationDaily] | None = None,
) -> list[dict[str, Any]]:
    result, _ = _reservation_fact_breakdown(
        db,
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        group_column=FactReservationDaily.channel_code,
        output_key="channel_code",
        facts=facts,
    )
    return result


def build_segments_payload(
    db: Session,
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    resolved_window: DateWindow | None = None,
    reservation_facts: list[FactReservationDaily] | None = None,
) -> dict[str, Any]:
    window = resolved_window or _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    segments, data_as_of = _reservation_fact_breakdown(
        db,
        hotel_id=hotel_id,
        date_from=window.date_from,
        date_to=window.date_to,
        group_column=FactReservationDaily.guest_segment,
        output_key="guest_segment",
        facts=reservation_facts,
    )
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": [
                metric_card("segments_total", "Segmentos con actividad", value_count=len(segments)).model_dump(),
            ],
            "segments": segments,
        },
        "generated_at": _now(),
        "data_as_of": data_as_of,
    }


def build_channels_payload(
    db: Session,
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    resolved_window: DateWindow | None = None,
    reservation_facts: list[FactReservationDaily] | None = None,
) -> dict[str, Any]:
    window = resolved_window or _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    channels, data_as_of = _reservation_fact_breakdown(
        db,
        hotel_id=hotel_id,
        date_from=window.date_from,
        date_to=window.date_to,
        group_column=FactReservationDaily.channel_code,
        output_key="channel_code",
        facts=reservation_facts,
    )
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": [
                metric_card("channels_total", "Canales con actividad", value_count=len(channels)).model_dump(),
            ],
            "channels": channels,
        },
        "generated_at": _now(),
        "data_as_of": data_as_of,
    }


def build_operations_payload(
    db: Session,
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    compare_previous: bool,
    compare_yoy: bool,
    currency_display: str,
    resolved_window: DateWindow | None = None,
    reservation_facts: list[FactReservationDaily] | None = None,
    stream_details: bool = False,
) -> dict[str, Any]:
    window = resolved_window or _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    room_events_query = (
        db.query(RoomStateEvent)
        .filter(
            RoomStateEvent.hotel_id == hotel_id,
            RoomStateEvent.started_at >= datetime.combine(window.date_from, datetime.min.time(), tzinfo=timezone.utc),
            RoomStateEvent.started_at <= datetime.combine(window.date_to, datetime.max.time(), tzinfo=timezone.utc),
        )
    )
    reservations_query = (
        active_reservations(db, hotel_id)
        .with_entities(
            Reservation.id,
            Reservation.confirmation_code,
            Reservation.status,
            Reservation.outcome,
            Reservation.check_in_date,
            Reservation.room_id,
            Reservation.category_id,
            Reservation.company_id,
        )
        .filter(Reservation.check_in_date.between(window.date_from, window.date_to))
    )
    if stream_details:
        room_events_open_query = room_events_query.filter(RoomStateEvent.ended_at.is_(None))
        open_events_count = room_events_open_query.with_entities(func.count(RoomStateEvent.id)).scalar() or 0
        no_shows_count = reservations_query.filter(Reservation.status == ReservationStatusEnum.NO_SHOW).with_entities(
            func.count(Reservation.id)
        ).scalar() or 0
        event_fields = (
            "id", "hotel_id", "room_id", "event_type", "reason_code", "reason_note", "started_at",
            "ended_at", "created_by_user_id", "closed_by_user_id", "created_at", "updated_at",
        )
        room_events_open = _MappedQueryRows(
            room_events_open_query,
            _serialize_room_state_event,
            column_names=event_fields,
        )
        room_events = _MappedQueryRows(room_events_query, _serialize_room_state_event, column_names=event_fields)
        reservations = _MappedQueryRows(
            reservations_query,
            _operations_reservation_read,
            column_names=("id", "confirmation_code", "status", "outcome", "check_in_date", "room_id", "category_id"),
        )
        if reservation_facts is None:
            facts_query = (
                db.query(FactReservationDaily)
                .filter(
                    FactReservationDaily.hotel_id == hotel_id,
                    FactReservationDaily.stay_date.between(window.date_from, window.date_to),
                )
            )
            facts = _MappedQueryRows(
                facts_query,
                _operations_fact_read,
                column_names=(
                    "stay_date", "reservation_id", "room_id", "row_kind", "revenue_net_ars",
                    "margin_operating_ars", "unavailable_currencies",
                ),
            )
            data_as_of = (
                db.query(func.min(FactReservationDaily.updated_at))
                .filter(
                    FactReservationDaily.hotel_id == hotel_id,
                    FactReservationDaily.stay_date.between(window.date_from, window.date_to),
                )
                .scalar()
            )
        else:
            facts = [_operations_fact_read(fact) for fact in reservation_facts]
            data_as_of = _facts_data_as_of(reservation_facts)
    else:
        room_event_rows = room_events_query.all()
        reservation_rows = reservations_query.all()
        facts_rows = reservation_facts if reservation_facts is not None else _load_reservation_facts(
            db, hotel_id, window.date_from, window.date_to
        )
        open_event_rows = [event for event in room_event_rows if event.ended_at is None]
        no_show_rows = [
            reservation
            for reservation in reservation_rows
            if getattr(reservation.status, "value", reservation.status) == "no_show"
        ]
        room_events_open = [_serialize_room_state_event(event) for event in open_event_rows]
        room_events = [_serialize_room_state_event(event) for event in room_event_rows]
        reservations = [_operations_reservation_read(reservation) for reservation in reservation_rows]
        facts = [_operations_fact_read(fact) for fact in facts_rows]
        open_events_count = len(open_event_rows)
        no_shows_count = len(no_show_rows)
        data_as_of = _facts_data_as_of(facts_rows)
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": [
                metric_card("operations_open_room_events", "Eventos de habitación abiertos", value_count=open_events_count).model_dump(),
                metric_card("operations_no_shows", "No-shows del período", value_count=no_shows_count).model_dump(),
                metric_card("operations_pickup_30d", "Pickup 30 días", value_count=calculate_pickup_30d_count(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)).model_dump(),
                metric_card("operations_physical_room_nights", "Noches-habitación disponibles", value_count=calculate_physical_room_nights_for_hotel(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)).model_dump(),
            ],
            "room_events_open": room_events_open,
            "room_events": room_events,
            "reservations": reservations,
            "facts": facts,
        },
        "generated_at": _now(),
        "data_as_of": data_as_of,
    }


def _operations_reservation_read(reservation: Any) -> dict[str, Any]:
    return {
        "id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status),
        "outcome": reservation.outcome.value if hasattr(reservation.outcome, "value") else str(reservation.outcome),
        "check_in_date": reservation.check_in_date,
        "room_id": reservation.room_id,
        "category_id": reservation.category_id,
    }


def _operations_fact_read(fact: FactReservationDaily) -> dict[str, Any]:
    return {
        "stay_date": fact.stay_date,
        "reservation_id": fact.reservation_id,
        "room_id": fact.room_id,
        "row_kind": fact.row_kind.value if hasattr(fact.row_kind, "value") else str(fact.row_kind),
        "revenue_net_ars": _money_str(fact.revenue_net_ars),
        "margin_operating_ars": _money_str(fact.margin_operating_ars),
        **_unavailable_currency_metadata([fact]),
    }


def build_rooms_detail_breakdown(db: Session, *, hotel_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    facts = _load_room_facts(db, hotel_id, date_from, date_to)
    grouped = _group_rows(facts, "room_id")
    currency_facts = _load_reservation_facts(db, hotel_id, date_from, date_to)
    currency_facts_by_room = _group_rows(currency_facts, "room_id")
    rooms = _room_lookup_map(db, hotel_id)
    result = []
    for room_id, rows in grouped.items():
        room = rooms.get(room_id)
        result.append(
            {
                "room_id": room_id,
                "room_number": room.room_number if room else None,
                "occupied_nights": len([row for row in rows if row.is_occupied]),
                "revenue_net_ars": _money_str(_sum_money(rows, "revenue_net_ars")),
                "margin_operating_ars": _money_str(_sum_money(rows, "margin_operating_ars")),
                **_unavailable_currency_metadata(currency_facts_by_room.get(room_id, [])),
            }
        )
    return sorted(result, key=lambda item: item["room_number"] or "")
