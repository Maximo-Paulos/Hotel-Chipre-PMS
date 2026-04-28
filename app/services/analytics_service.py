from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
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
from app.models.reservation import Reservation, ReservationStatusEnum
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
    CompanyRead,
    CompanyUpdate,
    RoomStateEventCreate,
    RoomStateEventRead,
)
from app.services.analytics_ai_providers import build_analytics_ai_config, get_analytics_ai_provider
from app.services.analytics_contracts import build_analytics_window, calculate_physical_room_nights_for_hotel, calculate_pickup_30d_count
from app.services.subscription_entitlements import get_subscription_snapshot
from app.services.timezones import normalize_timezone

MONEY_QUANTUM = Decimal("0.01")
PLAN_ORDER = {"starter": 0, "pro": 1, "ultra": 2}
AI_MONTHLY_QUOTA_FALLBACK = 20


@dataclass(frozen=True, slots=True)
class DateWindow:
    date_from: date
    date_to: date
    comparison: AnalyticsComparisonStateRead


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    today = datetime.now(ZoneInfo(timezone_name)).date()
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
    value_pct: float | None = None,
    value_count: int | None = None,
) -> AnalyticsMetricCardRead:
    payload: dict[str, Any] = {"card_code": card_code, "label": label}
    if value_ars is not None:
        payload["value_ars"] = _money_str(value_ars)
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
    for field, value in update_data.items():
        setattr(company, field, value)
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


def get_company_fact_detail(db: Session, *, hotel_id: int, company_id: int, date_from: date, date_to: date) -> dict[str, Any]:
    company = get_company_or_404(db, hotel_id, company_id)
    facts = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.company_id == company_id,
            FactReservationDaily.stay_date.between(date_from, date_to),
        )
        .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
        .all()
    )
    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.company_id == company_id,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    return {
        "company": _serialize_company(company),
        "facts": [
            {
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
            }
            for fact in facts
        ],
        "reservations": [
            {
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
            for reservation in reservations
        ],
        "cards": [
            metric_card("company_nights", "Noches del período", value_count=len(facts)).model_dump(),
            metric_card("company_revenue_net", "Revenue neto del período", value_ars=sum((_money(f.revenue_net_ars) for f in facts), Decimal("0"))).model_dump(),
            metric_card("company_reservations", "Reservas asociadas", value_count=len(reservations)).model_dump(),
        ],
    }


def _current_month_usage_row(db: Session, hotel_id: int) -> AnalyticsAIUsageMonthly:
    now = _hotel_local_now(db, hotel_id)
    year_month = now.strftime("%Y-%m")
    row = (
        db.query(AnalyticsAIUsageMonthly)
        .filter(AnalyticsAIUsageMonthly.hotel_id == hotel_id, AnalyticsAIUsageMonthly.year_month == year_month)
        .first()
    )
    if row:
        return row
    row = AnalyticsAIUsageMonthly(hotel_id=hotel_id, year_month=year_month, calls_used=0)
    db.add(row)
    db.flush()
    return row


def increment_ai_usage(db: Session, hotel_id: int, *, units: int = 1) -> AnalyticsAIUsageMonthly:
    row = _current_month_usage_row(db, hotel_id)
    row.calls_used = int(row.calls_used or 0) + max(int(units or 0), 0)
    db.flush()
    return row


def get_ai_config(db: Session, hotel_id: int) -> AnalyticsAIConfigRead:
    config = db.get(HotelConfiguration, hotel_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel no encontrado")

    runtime = get_analytics_ai_provider().status()
    usage = _current_month_usage_row(db, hotel_id)
    provider_config = build_analytics_ai_config(get_settings())
    quota_monthly = int(provider_config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK)
    quota_remaining = max(quota_monthly - int(usage.calls_used or 0), 0)
    return AnalyticsAIConfigRead(
        hotel_id=hotel_id,
        analytics_ai_enabled=bool(config.analytics_ai_enabled),
        provider=runtime.provider,
        runtime_healthy=runtime.runtime_healthy,
        effective_model=runtime.effective_model or provider_config.model or None,
        quota_monthly=quota_monthly,
        quota_used=int(usage.calls_used or 0),
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
    return event


def _group_rows(rows: list[Any], key: str) -> dict[Any, list[Any]]:
    grouped: dict[Any, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, key)].append(row)
    return grouped


def _room_lookup_map(db: Session, hotel_id: int) -> dict[int, Room]:
    rooms = db.query(Room).filter(Room.hotel_id == hotel_id).all()
    return {room.id: room for room in rooms}


def _category_lookup_map(db: Session, hotel_id: int) -> dict[int, RoomCategory]:
    categories = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).all()
    return {category.id: category for category in categories}


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
    return (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.stay_date.between(date_from, date_to),
        )
        .all()
    )


def _sum_money(rows: list[Any], attr: str) -> Decimal:
    return sum((_money(getattr(row, attr)) for row in rows), Decimal("0.00"))


def build_starter_summary_payload(db: Session, *, hotel_id: int, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    window = _utc_date_range(db, hotel_id, date_from, date_to)
    facts = _load_reservation_facts(db, hotel_id, window.date_from, window.date_to)
    occupancy_rows = (
        db.query(FactRoomOccupancyDaily)
        .filter(FactRoomOccupancyDaily.hotel_id == hotel_id, FactRoomOccupancyDaily.stay_date == window.date_to)
        .all()
    )
    arrivals = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.check_in_date == window.date_to,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .count()
    )
    total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id, Room.is_active.is_(True)).count()
    occupied_rooms = len([row for row in occupancy_rows if row.is_occupied])
    occupancy_pct = (occupied_rooms / len(occupancy_rows) * 100.0) if occupancy_rows else 0.0
    revenue = _sum_money(facts, "revenue_gross_ars")
    cards = [
        metric_card("starter_revenue_month", "Revenue del mes", value_ars=revenue).model_dump(),
        metric_card("starter_occupancy_today", "Ocupación hoy", value_pct=occupancy_pct).model_dump(),
        metric_card("starter_arrivals_today", "Llegadas hoy", value_count=arrivals).model_dump(),
    ]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "data": {"cards": cards},
        "generated_at": _now(),
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
) -> dict[str, Any]:
    window = _analytics_window(
        db,
        hotel_id,
        date_from=date_from,
        date_to=date_to,
        compare_previous=compare_previous,
        compare_yoy=compare_yoy,
    )
    facts = _load_reservation_facts(db, hotel_id, window.date_from, window.date_to)
    room_rows = _load_room_facts(db, hotel_id, window.date_from, window.date_to)
    pickup_30d = calculate_pickup_30d_count(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
    physical_room_nights = calculate_physical_room_nights_for_hotel(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
    cards = [
        metric_card("home_revenue_gross", "Revenue bruto", value_ars=_sum_money(facts, "revenue_gross_ars")).model_dump(),
        metric_card("home_revenue_net", "Revenue neto", value_ars=_sum_money(facts, "revenue_net_ars")).model_dump(),
        metric_card(
            "home_occupancy",
            "Ocupación promedio",
            value_pct=((sum(1 for row in room_rows if row.is_occupied) / len(room_rows)) * 100.0) if room_rows else 0.0,
        ).model_dump(),
        metric_card(
            "home_no_shows",
            "No-shows",
            value_count=len([fact for fact in facts if getattr(fact.outcome, "value", fact.outcome) == "no_show"]),
        ).model_dump(),
        metric_card("home_pickup_30d", "Pickup 30d", value_count=pickup_30d).model_dump(),
        metric_card("home_physical_room_nights", "Physical room nights", value_count=physical_room_nights).model_dump(),
    ]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": cards,
            "top_channels": build_channels_breakdown(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to),
            "segments": build_segments_breakdown(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to),
        },
        "generated_at": _now(),
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
    facts = _load_room_facts(db, hotel_id, window.date_from, window.date_to)
    facts_by_room = _group_rows(facts, "room_id")
    payload_rooms = []
    for room in rooms.values():
        room_facts = facts_by_room.get(room.id, [])
        payload_rooms.append(
            {
                "room_id": room.id,
                "room_number": room.room_number,
                "floor": room.floor,
                "category_id": room.category_id,
                "category_name": categories.get(room.category_id).name if categories.get(room.category_id) else None,
                "is_active": room.is_active,
                "status": room.status.value if hasattr(room.status, "value") else str(room.status),
                "occupied_nights": len([fact for fact in room_facts if fact.is_occupied]),
                "revenue_net_ars": _money_str(_sum_money(room_facts, "revenue_net_ars")),
                "revenue_net_usd": _money_str(_sum_money(room_facts, "revenue_net_usd")),
                "margin_operating_ars": _money_str(_sum_money(room_facts, "margin_operating_ars")),
                "margin_operating_usd": _money_str(_sum_money(room_facts, "margin_operating_usd")),
            }
        )
    cards = [
        metric_card("rooms_total", "Habitaciones activas", value_count=len([room for room in rooms.values() if room.is_active])).model_dump(),
        metric_card("rooms_occupied", "Noches ocupadas", value_count=len([fact for fact in facts if fact.is_occupied])).model_dump(),
        metric_card("rooms_occupancy", "Ocupación promedio", value_pct=((len([fact for fact in facts if fact.is_occupied]) / len(facts)) * 100.0) if facts else 0.0).model_dump(),
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
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    room = db.query(Room).filter(Room.hotel_id == hotel_id, Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room no encontrada")
    category = db.get(RoomCategory, room.category_id) if room.category_id else None
    facts = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_id,
            FactRoomOccupancyDaily.room_id == room_id,
            FactRoomOccupancyDaily.stay_date.between(window.date_from, window.date_to),
        )
        .order_by(FactRoomOccupancyDaily.stay_date.asc())
        .all()
    )
    events = _fetch_room_state_events(db, hotel_id=hotel_id, room_id=room_id)
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
            "facts": [
                {
                    "stay_date": fact.stay_date,
                    "status_at_night": fact.status_at_night.value if hasattr(fact.status_at_night, "value") else str(fact.status_at_night),
                    "is_sellable_night": fact.is_sellable_night,
                    "is_occupied": fact.is_occupied,
                    "reservation_id": fact.reservation_id,
                    "revenue_net_ars": _money_str(fact.revenue_net_ars),
                    "revenue_net_usd": _money_str(fact.revenue_net_usd),
                    "margin_operating_ars": _money_str(fact.margin_operating_ars),
                    "margin_operating_usd": _money_str(fact.margin_operating_usd),
                }
                for fact in facts
            ],
            "events": [_serialize_room_state_event(event) for event in events],
        },
        "generated_at": _now(),
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
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    category = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id, RoomCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category no encontrada")
    rooms = (
        db.query(Room)
        .filter(Room.hotel_id == hotel_id, Room.category_id == category_id)
        .order_by(Room.room_number.asc())
        .all()
    )
    facts = (
        db.query(FactReservationDaily)
        .filter(
            FactReservationDaily.hotel_id == hotel_id,
            FactReservationDaily.category_id == category_id,
            FactReservationDaily.stay_date.between(window.date_from, window.date_to),
        )
        .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
        .all()
    )
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
            "rooms": [
                {
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "floor": room.floor,
                    "is_active": room.is_active,
                    "status": room.status.value if hasattr(room.status, "value") else str(room.status),
                }
                for room in rooms
            ],
            "facts": [
                {
                    "stay_date": fact.stay_date,
                    "reservation_id": fact.reservation_id,
                    "room_id": fact.room_id,
                    "outcome": fact.outcome.value if hasattr(fact.outcome, "value") else str(fact.outcome),
                    "revenue_net_ars": _money_str(fact.revenue_net_ars),
                    "revenue_net_usd": _money_str(fact.revenue_net_usd),
                }
                for fact in facts
            ],
        },
        "generated_at": _now(),
    }


def build_segments_breakdown(db: Session, *, hotel_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    facts = _load_reservation_facts(db, hotel_id, date_from, date_to)
    grouped = _group_rows(facts, "guest_segment")
    result = []
    for segment, rows in grouped.items():
        result.append(
            {
                "guest_segment": segment.value if hasattr(segment, "value") else str(segment),
                "reservations_count": len({row.reservation_id for row in rows}),
                "nights_count": len(rows),
                "revenue_gross_ars": _money_str(_sum_money(rows, "revenue_gross_ars")),
                "revenue_net_ars": _money_str(_sum_money(rows, "revenue_net_ars")),
            }
        )
    return sorted(result, key=lambda item: item["guest_segment"])


def build_channels_breakdown(db: Session, *, hotel_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    facts = _load_reservation_facts(db, hotel_id, date_from, date_to)
    grouped = _group_rows(facts, "channel_code")
    result = []
    for channel, rows in grouped.items():
        result.append(
            {
                "channel_code": channel.value if hasattr(channel, "value") else str(channel),
                "reservations_count": len({row.reservation_id for row in rows}),
                "nights_count": len(rows),
                "revenue_gross_ars": _money_str(_sum_money(rows, "revenue_gross_ars")),
                "revenue_net_ars": _money_str(_sum_money(rows, "revenue_net_ars")),
            }
        )
    return sorted(result, key=lambda item: item["channel_code"])


def build_segments_payload(
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
    segments = build_segments_breakdown(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
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
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    channels = build_channels_breakdown(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)
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
) -> dict[str, Any]:
    window = _analytics_window(db, hotel_id, date_from=date_from, date_to=date_to, compare_previous=compare_previous, compare_yoy=compare_yoy)
    room_events = (
        db.query(RoomStateEvent)
        .filter(
            RoomStateEvent.hotel_id == hotel_id,
            RoomStateEvent.started_at >= datetime.combine(window.date_from, datetime.min.time(), tzinfo=timezone.utc),
            RoomStateEvent.started_at <= datetime.combine(window.date_to, datetime.max.time(), tzinfo=timezone.utc),
        )
        .all()
    )
    reservations = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id, Reservation.check_in_date.between(window.date_from, window.date_to))
        .all()
    )
    facts = _load_reservation_facts(db, hotel_id, window.date_from, window.date_to)
    open_events = [event for event in room_events if event.ended_at is None]
    no_shows = [reservation for reservation in reservations if getattr(reservation.status, "value", reservation.status) == "no_show"]
    return {
        "hotel_id": hotel_id,
        "date_from": window.date_from,
        "date_to": window.date_to,
        "currency_display": currency_display,
        "comparison": window.comparison,
        "data": {
            "cards": [
                metric_card("operations_open_room_events", "Eventos de habitación abiertos", value_count=len(open_events)).model_dump(),
                metric_card("operations_no_shows", "No-shows del período", value_count=len(no_shows)).model_dump(),
                metric_card("operations_pickup_30d", "Pickup 30d", value_count=calculate_pickup_30d_count(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)).model_dump(),
                metric_card("operations_physical_room_nights", "Physical room nights", value_count=calculate_physical_room_nights_for_hotel(db, hotel_id=hotel_id, date_from=window.date_from, date_to=window.date_to)).model_dump(),
            ],
            "room_events_open": [_serialize_room_state_event(event) for event in open_events],
            "room_events": [_serialize_room_state_event(event) for event in room_events],
            "reservations": [
                {
                    "id": reservation.id,
                    "confirmation_code": reservation.confirmation_code,
                    "status": reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status),
                    "outcome": reservation.outcome.value if hasattr(reservation.outcome, "value") else str(reservation.outcome),
                    "check_in_date": reservation.check_in_date,
                    "room_id": reservation.room_id,
                    "category_id": reservation.category_id,
                }
                for reservation in reservations
            ],
            "facts": [
                {
                    "stay_date": fact.stay_date,
                    "reservation_id": fact.reservation_id,
                    "room_id": fact.room_id,
                    "row_kind": fact.row_kind.value if hasattr(fact.row_kind, "value") else str(fact.row_kind),
                    "revenue_net_ars": _money_str(fact.revenue_net_ars),
                    "margin_operating_ars": _money_str(fact.margin_operating_ars),
                }
                for fact in facts
            ],
        },
        "generated_at": _now(),
    }


def build_rooms_detail_breakdown(db: Session, *, hotel_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    facts = _load_room_facts(db, hotel_id, date_from, date_to)
    grouped = _group_rows(facts, "room_id")
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
            }
        )
    return sorted(result, key=lambda item: item["room_number"] or "")
