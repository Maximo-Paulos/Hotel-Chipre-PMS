from __future__ import annotations

from bisect import bisect_left
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.rate_change_draft import RateChangeDraft
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.services import audit_log_service
from app.services.pricing_service import resolve_rate_calendar
from app.services.row_locks import lock_query

RATE_FIELDS = (
    "price",
    "price_cash",
    "price_transfer",
    "price_mercadopago",
    "price_paypal",
    "price_credit_card",
)
OPTIONAL_RATE_FIELDS = RATE_FIELDS[1:]
MAX_DRAFT_DATES = 366
PERIOD_PRICE_FIELDS = (
    "price_cash",
    "price_transfer",
    "price_mercadopago",
    "price_paypal",
    "price_credit_card",
    "price_debit_card",
    "price_booking",
    "price_expedia",
)
PERIOD_FIELDS = (
    "name",
    "start_date",
    "end_date",
    "price_per_night",
    *PERIOD_PRICE_FIELDS,
    "priority",
    "is_active",
)


class RateDraftError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _money(value: Any) -> float | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RateDraftError("La tarifa contiene un importe inválido.") from exc
    if not amount.is_finite() or amount < 0:
        raise RateDraftError("Los importes de tarifa deben ser números no negativos.")
    return float(amount)


def _effective_value(field: str, row: DailyRate | None, resolved: dict[str, Any]) -> float:
    if row is not None:
        if field == "price":
            return float(row.price)
        override = getattr(row, field)
        return float(override if override is not None else row.price)
    if field == "price":
        return float(resolved.get("price") or 0)
    override = resolved.get(field)
    return float(override if override is not None else resolved.get("price") or 0)


def _load_rate_state(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    target_dates: list[date],
    lock_rows: bool = False,
) -> tuple[dict[date, DailyRate], dict[date, dict[str, Any]]]:
    if not target_dates:
        return {}, {}
    rows_query = db.query(DailyRate).filter(
        DailyRate.hotel_id == hotel_id,
        DailyRate.category_id == category_id,
        DailyRate.date.in_(target_dates),
    )
    if lock_rows:
        rows_query = lock_query(rows_query, DailyRate)
    rows = {row.date: row for row in rows_query.all()}
    resolved_rows = resolve_rate_calendar(
        db,
        hotel_id,
        category_id,
        min(target_dates),
        max(target_dates),
    )
    resolved = {row["date"]: row for row in resolved_rows if row["date"] in set(target_dates)}
    return rows, resolved


def _validate_changes(raw_changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw_changes or len(raw_changes) > MAX_DRAFT_DATES:
        raise RateDraftError(f"El borrador debe incluir entre 1 y {MAX_DRAFT_DATES} fechas.")
    normalized: list[dict[str, Any]] = []
    seen: set[date] = set()
    for item in raw_changes:
        target_date = item.get("date")
        if isinstance(target_date, str):
            try:
                target_date = date.fromisoformat(target_date)
            except ValueError as exc:
                raise RateDraftError("Hay una fecha inválida en el borrador.") from exc
        if not isinstance(target_date, date) or isinstance(target_date, datetime):
            raise RateDraftError("Hay una fecha inválida en el borrador.")
        if target_date in seen:
            raise RateDraftError("El borrador no puede repetir fechas.")
        seen.add(target_date)
        values = item.get("values")
        if not isinstance(values, dict) or not values:
            raise RateDraftError("Cada fecha debe incluir al menos un importe para cambiar.")
        if set(values) - set(RATE_FIELDS):
            raise RateDraftError("El borrador contiene un campo de tarifa no permitido.")
        clean_values: dict[str, float | None] = {}
        for field, value in values.items():
            if field == "price" and value is None:
                raise RateDraftError("El precio base no puede quedar vacío.")
            clean_values[field] = _money(value)
        normalized.append({"date": target_date, "values": clean_values})
    return sorted(normalized, key=lambda item: item["date"])


def _period_values(period: PricePeriod) -> dict[str, Any]:
    return {
        "name": period.name,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "price_per_night": _money(period.price_per_night),
        **{field: _money(getattr(period, field)) for field in PERIOD_PRICE_FIELDS},
        "priority": period.priority,
        "is_active": bool(period.is_active),
    }


def _validate_period_values(raw_values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_values, dict) or set(raw_values) - set(PERIOD_FIELDS):
        raise RateDraftError("La temporada contiene campos no permitidos.")
    if not isinstance(raw_values.get("name"), str) or not raw_values["name"].strip():
        raise RateDraftError("La temporada debe tener un nombre.")
    if len(raw_values["name"].strip()) > 100:
        raise RateDraftError("El nombre de temporada no puede superar 100 caracteres.")

    normalized: dict[str, Any] = {"name": raw_values["name"].strip()}
    for field in ("start_date", "end_date"):
        value = raw_values.get(field)
        if isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError as exc:
                raise RateDraftError("La temporada contiene una fecha inválida.") from exc
        if not isinstance(value, date) or isinstance(value, datetime):
            raise RateDraftError("La temporada debe incluir fechas de inicio y fin válidas.")
        normalized[field] = value.isoformat()
    if normalized["end_date"] < normalized["start_date"]:
        raise RateDraftError("La fecha final debe ser igual o posterior a la inicial.")
    span = (date.fromisoformat(normalized["end_date"]) - date.fromisoformat(normalized["start_date"])).days + 1
    if span > MAX_DRAFT_DATES:
        raise RateDraftError(
            f"La temporada supera el máximo de {MAX_DRAFT_DATES} fechas; dividila en temporadas más cortas para revisar su impacto."
        )

    if "price_per_night" not in raw_values or raw_values["price_per_night"] is None:
        raise RateDraftError("La temporada debe tener un precio por noche.")
    normalized["price_per_night"] = _money(raw_values["price_per_night"])
    for field in PERIOD_PRICE_FIELDS:
        normalized[field] = _money(raw_values.get(field))
    priority = raw_values.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int) or priority < -100000:
        raise RateDraftError("La prioridad de la temporada no es válida.")
    normalized["priority"] = priority
    active = raw_values.get("is_active", True)
    if not isinstance(active, bool):
        raise RateDraftError("El estado de la temporada no es válido.")
    normalized["is_active"] = active
    return normalized


def _period_from_values(period_id: int, values: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": period_id,
        **values,
        "start_date": date.fromisoformat(values["start_date"]),
        "end_date": date.fromisoformat(values["end_date"]),
    }


def _period_snapshot_rows(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    start_date: date,
    end_date: date,
    lock_rows: bool = False,
) -> list[dict[str, Any]]:
    query = db.query(PricePeriod).filter(
        PricePeriod.hotel_id == hotel_id,
        PricePeriod.category_id == category_id,
        PricePeriod.deleted_at.is_(None),
        PricePeriod.start_date <= end_date,
        PricePeriod.end_date >= start_date,
    ).order_by(PricePeriod.id.asc())
    if lock_rows:
        query = lock_query(query, PricePeriod)
    return [{"id": period.id, "values": _period_values(period)} for period in query.all()]


def _daily_rate_scope_snapshot(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    start_date: date,
    end_date: date,
    lock_rows: bool = False,
) -> list[dict[str, Any]]:
    query = db.query(DailyRate).filter(
        DailyRate.hotel_id == hotel_id,
        DailyRate.category_id == category_id,
        DailyRate.date >= start_date,
        DailyRate.date <= end_date,
    ).order_by(DailyRate.date.asc(), DailyRate.id.asc())
    if lock_rows:
        query = lock_query(query, DailyRate)
    snapshot = []
    for row in query.all():
        snapshot.append({
            "id": row.id,
            "date": row.date.isoformat(),
            "values": {
                "price": _money(row.price),
                **{field: _money(getattr(row, field)) for field in OPTIONAL_RATE_FIELDS},
            },
        })
    return snapshot


def _effective_period_prices(
    *,
    target_date: date,
    daily_rate: DailyRate | None,
    periods: list[PricePeriod | dict[str, Any]],
    category_base: float | None,
) -> tuple[dict[str, float], str]:
    if daily_rate is not None:
        base_price = float(daily_rate.price or 0)
        values = {"price": base_price}
        for field in PERIOD_PRICE_FIELDS:
            override = getattr(daily_rate, field, None) if field in RATE_FIELDS else None
            values[field] = float(override if override is not None else base_price)
        return values, "daily_rate"

    matching = []
    for period in periods:
        read = period.get if isinstance(period, dict) else lambda field, default=None: getattr(period, field, default)
        start = read("start_date")
        end = read("end_date")
        active = read("is_active")
        if active and start <= target_date <= end:
            matching.append(period)
    matching.sort(
        key=lambda item: (
            item.get("priority", 0) if isinstance(item, dict) else item.priority,
            item.get("id", 0) if isinstance(item, dict) else item.id,
        ),
        reverse=True,
    )
    if matching:
        winner = matching[0]
        base_price = float((winner.get("price_per_night") if isinstance(winner, dict) else winner.price_per_night) or 0)
        values = {"price": base_price}
        for field in PERIOD_PRICE_FIELDS:
            override = winner.get(field) if isinstance(winner, dict) else getattr(winner, field, None)
            values[field] = float(override if override is not None else base_price)
        return values, "price_period"

    base_price = float(category_base or 0)
    return {"price": base_price, **{field: base_price for field in PERIOD_PRICE_FIELDS}}, "category_base" if category_base is not None else "none"


def _dates_for_range(start_date: date, end_date: date) -> list[date]:
    return [date.fromordinal(day) for day in range(start_date.toordinal(), end_date.toordinal() + 1)]


def _category_or_error(db: Session, hotel_id: int, category_id: int, *, lock: bool = False) -> RoomCategory:
    query = db.query(RoomCategory).filter(
        RoomCategory.hotel_id == hotel_id,
        RoomCategory.id == category_id,
    )
    if lock:
        query = lock_query(query, RoomCategory)
    category = query.one_or_none()
    if category is None:
        raise RateDraftError("La categoría no existe en este hotel.", status_code=404)
    return category


def _impact_for_dates(db: Session, *, hotel_id: int, category_id: int, dates: list[date]) -> dict[str, Any]:
    if not dates:
        return {"reservations_impacted": 0, "reservation_nights": 0, "dates_with_reservations": []}
    reservations = (
        db.query(Reservation.check_in_date, Reservation.check_out_date)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.category_id == category_id,
            Reservation.check_in_date <= max(dates),
            Reservation.check_out_date > min(dates),
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .all()
    )
    nights = 0
    reservations_impacted = 0
    dates_with_reservations: set[date] = set()
    sorted_dates = sorted(dates)
    for check_in, check_out in reservations:
        start = bisect_left(sorted_dates, check_in)
        end = bisect_left(sorted_dates, check_out)
        if end <= start:
            continue
        reservations_impacted += 1
        nights += end - start
        dates_with_reservations.update(sorted_dates[start:end])
    return {
        "reservations_impacted": reservations_impacted,
        "reservation_nights": nights,
        "dates_with_reservations": [item.isoformat() for item in sorted(dates_with_reservations)],
    }


def _audit_payload(draft: RateChangeDraft) -> dict[str, Any]:
    return {
        "category_id": draft.category_id,
        "draft_type": draft.draft_type,
        "status": draft.status,
        "version": draft.version,
        "changes": draft.changes,
        "period_operation": draft.period_operation,
        "impact": draft.impact,
    }


def serialize_draft(db: Session, draft: RateChangeDraft) -> dict[str, Any]:
    if draft.draft_type == "price_period":
        changed_dates = [
            date.fromisoformat(item["date"])
            for item in (draft.period_operation or {}).get("effective_changes", [])
        ]
        current_impact = _impact_for_dates(
            db,
            hotel_id=draft.hotel_id,
            category_id=draft.category_id,
            dates=changed_dates,
        )
        public_changes = []
        period_operation = draft.period_operation
    else:
        current_impact = _impact_for_dates(
            db,
            hotel_id=draft.hotel_id,
            category_id=draft.category_id,
            dates=[date.fromisoformat(item["date"]) for item in draft.changes],
        )
        public_changes = []
        period_operation = None
        for item in draft.changes:
            public_changes.append({
                "date": item["date"],
                "source_before": item.get("source_before"),
                "before": item.get("effective_before", {}),
                "after": item.get("effective_after", {}),
                "values": item["values"],
            })
    return {
        "id": draft.id,
        "hotel_id": draft.hotel_id,
        "category_id": draft.category_id,
        "draft_type": draft.draft_type,
        "status": draft.status,
        "version": draft.version,
        "changes": public_changes,
        "period_operation": period_operation,
        "impact": current_impact,
        "impact_at_creation": draft.impact,
        "created_by_user_id": draft.created_by_user_id,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "confirmed_at": draft.confirmed_at,
        "confirmed_by_user_id": draft.confirmed_by_user_id,
        "cancelled_at": draft.cancelled_at,
        "cancelled_by_user_id": draft.cancelled_by_user_id,
    }


def create_rate_change_draft(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    category_id: int,
    changes: list[dict[str, Any]],
) -> RateChangeDraft:
    category = _category_or_error(db, hotel_id, category_id)
    existing_draft = db.query(RateChangeDraft.id).filter(
        RateChangeDraft.hotel_id == hotel_id,
        RateChangeDraft.category_id == category_id,
        RateChangeDraft.status == "draft",
    ).first()
    if existing_draft is not None:
        raise RateDraftError("Ya hay un borrador pendiente para esta categoría. Confirmalo o cancelalo antes de crear otro.", status_code=409)
    normalized = _validate_changes(changes)
    target_dates = [item["date"] for item in normalized]
    rows, resolved = _load_rate_state(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        target_dates=target_dates,
    )
    stored_changes: list[dict[str, Any]] = []
    for item in normalized:
        target_date = item["date"]
        current = rows.get(target_date)
        baseline = resolved[target_date]
        values = item["values"]
        raw_before = {field: getattr(current, field, None) if current is not None else None for field in values}
        effective_before = {field: _effective_value(field, current, baseline) for field in values}
        effective_after: dict[str, float | None] = {}
        resulting_base = values.get("price", effective_before.get("price", _effective_value("price", current, baseline)))
        for field, value in values.items():
            if field == "price":
                effective_after[field] = value
            elif value is not None:
                effective_after[field] = value
            elif field in OPTIONAL_RATE_FIELDS:
                effective_after[field] = resulting_base
        stored_changes.append({
            "date": target_date.isoformat(),
            "source_before": baseline.get("source"),
            "row_existed_before": current is not None,
            "raw_before": raw_before,
            "effective_before": effective_before,
            "effective_after": effective_after,
            "values": values,
        })
    dates = [item["date"] for item in normalized]
    impact = _impact_for_dates(db, hotel_id=hotel_id, category_id=category_id, dates=dates)
    now = datetime.now(timezone.utc)
    draft = RateChangeDraft(
        hotel_id=hotel_id,
        category_id=category.id,
        created_by_user_id=user_id,
        draft_type="daily_rates",
        status="draft",
        version=1,
        changes=stored_changes,
        impact=impact,
        created_at=now,
        updated_at=now,
    )
    db.add(draft)
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rate_change_drafts",
        record_id=draft.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=user_id,
        payload_after=_audit_payload(draft),
    )
    return draft


def create_price_period_draft(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    category_id: int,
    action: str,
    period_id: int | None = None,
    values: dict[str, Any] | None = None,
) -> RateChangeDraft:
    category = _category_or_error(db, hotel_id, category_id, lock=True)
    existing_draft = db.query(RateChangeDraft.id).filter(
        RateChangeDraft.hotel_id == hotel_id,
        RateChangeDraft.category_id == category_id,
        RateChangeDraft.status == "draft",
    ).first()
    if existing_draft is not None:
        raise RateDraftError("Ya hay un borrador pendiente para esta categoría. Confirmalo o cancelalo antes de crear otro.", status_code=409)
    if action not in {"create", "update", "delete"}:
        raise RateDraftError("La operación de temporada no es válida.")
    if action == "create" and period_id is not None:
        raise RateDraftError("Una temporada nueva no debe incluir un identificador.")
    if action in {"update", "delete"} and (not isinstance(period_id, int) or period_id <= 0):
        raise RateDraftError("Seleccioná una temporada válida para modificar.")

    target = None
    if period_id is not None:
        target = db.query(PricePeriod).filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.id == period_id,
            PricePeriod.deleted_at.is_(None),
        ).one_or_none()
        if target is None:
            raise RateDraftError("No se encontró la temporada seleccionada.", status_code=404)
    if action == "delete" and values:
        raise RateDraftError("La baja de temporada no debe incluir valores nuevos.")
    if action != "delete" and values is None:
        raise RateDraftError("La temporada debe incluir sus valores nuevos.")

    before = _period_values(target) if target is not None else None
    after = None if action == "delete" else _validate_period_values(values or {})
    scope_dates = []
    if before is not None:
        scope_dates.extend((date.fromisoformat(before["start_date"]), date.fromisoformat(before["end_date"])))
    if after is not None:
        scope_dates.extend((date.fromisoformat(after["start_date"]), date.fromisoformat(after["end_date"])))
    scope_start, scope_end = min(scope_dates), max(scope_dates)
    if (scope_end - scope_start).days + 1 > MAX_DRAFT_DATES:
        raise RateDraftError(
            f"El cambio de temporada abarca más de {MAX_DRAFT_DATES} fechas; acotá el rango para poder calcular el impacto con precisión."
        )
    dates = _dates_for_range(scope_start, scope_end)
    period_rows = _period_snapshot_rows(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        start_date=scope_start,
        end_date=scope_end,
    )
    daily_rows_snapshot = _daily_rate_scope_snapshot(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        start_date=scope_start,
        end_date=scope_end,
    )
    period_map = {
        row["id"]: _period_from_values(row["id"], row["values"])
        for row in period_rows
    }

    simulated_after = list(period_map.values())
    if action == "update":
        simulated_after = [period for period in simulated_after if period["id"] != period_id]
    elif action == "delete":
        simulated_after = [period for period in simulated_after if period["id"] != period_id]
    if action in {"create", "update"} and after is not None:
        next_id = (max(period_map.keys()) if period_map else 0) + 1 if action == "create" else int(period_id or 0)
        simulated_after.append(_period_from_values(next_id, after))

    daily_rows = {
        row.date: row
        for row in db.query(DailyRate).filter(
            DailyRate.hotel_id == hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date >= scope_start,
            DailyRate.date <= scope_end,
        ).all()
    }
    live_periods = list(period_map.values())
    effective_changes: list[dict[str, Any]] = []
    for target_date in dates:
        effective_before, source_before = _effective_period_prices(
            target_date=target_date,
            daily_rate=daily_rows.get(target_date),
            periods=live_periods,
            category_base=category.base_price_per_night,
        )
        effective_after, source_after = _effective_period_prices(
            target_date=target_date,
            daily_rate=daily_rows.get(target_date),
            periods=simulated_after,
            category_base=category.base_price_per_night,
        )
        if effective_before != effective_after:
            effective_changes.append({
                "date": target_date.isoformat(),
                "before": effective_before,
                "after": effective_after,
                "source_before": source_before,
                "source_after": source_after,
            })
    impact_dates = [date.fromisoformat(item["date"]) for item in effective_changes]
    impact = _impact_for_dates(db, hotel_id=hotel_id, category_id=category_id, dates=impact_dates)
    now = datetime.now(timezone.utc)
    operation = {
        "action": action,
        "period_id": period_id,
        "before": before,
        "after": after,
        "scope_start": scope_start.isoformat(),
        "scope_end": scope_end.isoformat(),
        "periods_before": period_rows,
        "daily_rates_before": daily_rows_snapshot,
        "category_base_before": _money(category.base_price_per_night),
        "effective_changes": effective_changes,
    }
    draft = RateChangeDraft(
        hotel_id=hotel_id,
        category_id=category.id,
        created_by_user_id=user_id,
        draft_type="price_period",
        status="draft",
        version=1,
        changes=[],
        period_operation=operation,
        impact=impact,
        created_at=now,
        updated_at=now,
    )
    db.add(draft)
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rate_change_drafts",
        record_id=draft.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=user_id,
        payload_after=_audit_payload(draft),
    )
    return draft


def list_rate_change_drafts(db: Session, *, hotel_id: int, category_id: int | None, limit: int) -> list[RateChangeDraft]:
    query = db.query(RateChangeDraft).filter(RateChangeDraft.hotel_id == hotel_id)
    if category_id is not None:
        query = query.filter(RateChangeDraft.category_id == category_id)
    return query.order_by(RateChangeDraft.created_at.desc(), RateChangeDraft.id.desc()).limit(limit).all()


def get_rate_change_draft(db: Session, *, hotel_id: int, draft_id: int) -> RateChangeDraft:
    draft = db.query(RateChangeDraft).filter(
        RateChangeDraft.hotel_id == hotel_id,
        RateChangeDraft.id == draft_id,
    ).one_or_none()
    if draft is None:
        raise RateDraftError("No se encontró el borrador.", status_code=404)
    return draft


def _draft_for_update(db: Session, *, hotel_id: int, draft_id: int) -> RateChangeDraft:
    query = db.query(RateChangeDraft).filter(
        RateChangeDraft.hotel_id == hotel_id,
        RateChangeDraft.id == draft_id,
    )
    draft = lock_query(query, RateChangeDraft).one_or_none()
    if draft is None:
        raise RateDraftError("No se encontró el borrador.", status_code=404)
    return draft


def _check_draft_version(draft: RateChangeDraft, expected_version: int) -> None:
    if draft.status != "draft":
        raise RateDraftError("El borrador ya no está pendiente.", status_code=409)
    if draft.version != expected_version:
        raise RateDraftError("El borrador cambió en otra sesión. Actualizá la pantalla.", status_code=409)


def _confirm_price_period_draft(
    db: Session,
    *,
    draft: RateChangeDraft,
    hotel_id: int,
    user_id: int | None,
    category: RoomCategory,
) -> tuple[RateChangeDraft, list[DailyRate]]:
    operation = draft.period_operation or {}
    scope_start = date.fromisoformat(operation["scope_start"])
    scope_end = date.fromisoformat(operation["scope_end"])
    current_snapshots = _period_snapshot_rows(
        db,
        hotel_id=hotel_id,
        category_id=draft.category_id,
        start_date=scope_start,
        end_date=scope_end,
        lock_rows=True,
    )
    if current_snapshots != operation.get("periods_before", []):
        raise RateDraftError(
            "Las temporadas del rango cambiaron desde la vista previa. Cancelá este borrador y prepará uno nuevo.",
            status_code=409,
        )
    daily_snapshots = _daily_rate_scope_snapshot(
        db,
        hotel_id=hotel_id,
        category_id=draft.category_id,
        start_date=scope_start,
        end_date=scope_end,
        lock_rows=True,
    )
    if daily_snapshots != operation.get("daily_rates_before", []):
        raise RateDraftError(
            "Las tarifas diarias del rango cambiaron desde la vista previa. Cancelá este borrador y prepará uno nuevo.",
            status_code=409,
        )
    if _money(category.base_price_per_night) != _money(operation.get("category_base_before")):
        raise RateDraftError(
            "El precio base de la categoría cambió desde la vista previa. Cancelá este borrador y prepará uno nuevo.",
            status_code=409,
        )

    action = operation.get("action")
    period_id = operation.get("period_id")
    period = None
    if period_id is not None:
        period = db.query(PricePeriod).filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == draft.category_id,
            PricePeriod.id == period_id,
            PricePeriod.deleted_at.is_(None),
        ).one_or_none()
        if period is None:
            raise RateDraftError("La temporada ya no está disponible. Creá un borrador nuevo.", status_code=409)
    before_record = audit_log_service.model_snapshot(period) if period is not None else None
    now = datetime.now(timezone.utc)
    if action == "create":
        values = operation.get("after") or {}
        period = PricePeriod(
            hotel_id=hotel_id,
            category_id=draft.category_id,
            name=values["name"],
            start_date=date.fromisoformat(values["start_date"]),
            end_date=date.fromisoformat(values["end_date"]),
            price_per_night=values["price_per_night"],
            **{field: values.get(field) for field in PERIOD_PRICE_FIELDS},
            priority=values["priority"],
            is_active=values["is_active"],
        )
        db.add(period)
        db.flush()
        audit_action = AuditActionEnum.CREATE
    elif action == "update":
        values = operation.get("after") or {}
        period.name = values["name"]
        period.start_date = date.fromisoformat(values["start_date"])
        period.end_date = date.fromisoformat(values["end_date"])
        period.price_per_night = values["price_per_night"]
        for field in PERIOD_PRICE_FIELDS:
            setattr(period, field, values.get(field))
        period.priority = values["priority"]
        period.is_active = values["is_active"]
        db.flush()
        audit_action = AuditActionEnum.UPDATE
    elif action == "delete":
        period.deleted_at = now
        period.deleted_by_user_id = user_id
        db.flush()
        audit_action = AuditActionEnum.DELETE
    else:
        raise RateDraftError("El borrador contiene una operación de temporada inválida.", status_code=409)

    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="price_periods",
        record_id=period.id,
        action=audit_action,
        actor_user_id=user_id,
        payload_before=before_record,
        payload_after=audit_log_service.model_snapshot(period),
    )
    before_draft = _audit_payload(draft)
    draft.status = "confirmed"
    draft.version += 1
    draft.updated_at = now
    draft.confirmed_at = now
    draft.confirmed_by_user_id = user_id
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rate_change_drafts",
        record_id=draft.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=user_id,
        payload_before=before_draft,
        payload_after=_audit_payload(draft),
    )
    return draft, []


def confirm_rate_change_draft(
    db: Session,
    *,
    hotel_id: int,
    draft_id: int,
    expected_version: int,
    user_id: int | None,
) -> tuple[RateChangeDraft, list[DailyRate]]:
    draft = _draft_for_update(db, hotel_id=hotel_id, draft_id=draft_id)
    _check_draft_version(draft, expected_version)
    category = _category_or_error(db, hotel_id, draft.category_id, lock=True)
    if draft.draft_type == "price_period":
        db.refresh(category, attribute_names=["base_price_per_night"])
        return _confirm_price_period_draft(
            db,
            draft=draft,
            hotel_id=hotel_id,
            user_id=user_id,
            category=category,
        )
    target_dates = [date.fromisoformat(item["date"]) for item in draft.changes]
    rows, resolved = _load_rate_state(
        db,
        hotel_id=hotel_id,
        category_id=draft.category_id,
        target_dates=target_dates,
        lock_rows=True,
    )
    touched: list[DailyRate] = []
    before_draft = _audit_payload(draft)
    now = datetime.now(timezone.utc)
    for item in draft.changes:
        target_date = date.fromisoformat(item["date"])
        current = rows.get(target_date)
        if (current is not None) != bool(item.get("row_existed_before")):
            raise RateDraftError("La tarifa cambió desde que se creó el borrador. Creá uno nuevo.", status_code=409)
        baseline = resolved[target_date]
        for field in item["values"]:
            raw_value = getattr(current, field, None) if current is not None else None
            expected_raw = item.get("raw_before", {}).get(field)
            effective_value = _effective_value(field, current, baseline)
            expected_effective = item.get("effective_before", {}).get(field)
            if _money(raw_value) != _money(expected_raw) or _money(effective_value) != _money(expected_effective):
                raise RateDraftError("La tarifa cambió desde que se creó el borrador. Creá uno nuevo.", status_code=409)
        before_rate = audit_log_service.model_snapshot(current)
        if current is None:
            current = DailyRate(
                hotel_id=hotel_id,
                category_id=draft.category_id,
                date=target_date,
                price=_effective_value("price", None, baseline),
                created_by_user_id=user_id,
            )
            db.add(current)
        for field, value in item["values"].items():
            setattr(current, field, value)
        current.updated_at = now
        db.flush()
        audit_log_service.create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="daily_rates",
            record_id=current.id,
            action=AuditActionEnum.CREATE if before_rate is None else AuditActionEnum.UPDATE,
            actor_user_id=user_id,
            payload_before=before_rate,
            payload_after=audit_log_service.model_snapshot(current),
        )
        touched.append(current)
    draft.status = "confirmed"
    draft.version += 1
    draft.updated_at = now
    draft.confirmed_at = now
    draft.confirmed_by_user_id = user_id
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rate_change_drafts",
        record_id=draft.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=user_id,
        payload_before=before_draft,
        payload_after=_audit_payload(draft),
    )
    return draft, touched


def cancel_rate_change_draft(
    db: Session,
    *,
    hotel_id: int,
    draft_id: int,
    expected_version: int,
    user_id: int | None,
) -> RateChangeDraft:
    draft = _draft_for_update(db, hotel_id=hotel_id, draft_id=draft_id)
    _check_draft_version(draft, expected_version)
    before = _audit_payload(draft)
    now = datetime.now(timezone.utc)
    draft.status = "cancelled"
    draft.version += 1
    draft.updated_at = now
    draft.cancelled_at = now
    draft.cancelled_by_user_id = user_id
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rate_change_drafts",
        record_id=draft.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=user_id,
        payload_before=before,
        payload_after=_audit_payload(draft),
    )
    return draft
