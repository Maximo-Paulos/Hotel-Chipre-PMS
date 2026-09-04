"""Unified, tenant-scoped read projection for material hotel operations.

The projection intentionally reads the existing append-only audit streams and
transaction/cash ledgers. It is not a second financial ledger and it never
mutates source records.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.analytics import HotelAuditEvent
from app.models.audit_log import AuditLog
from app.models.cash_register import CashCloseReport, CashCustodyHandoff, CashMovement, CashSession
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment, ReservationAdjustment, ReservationStatusHistory, RoomMoveEvent
from app.models.security_audit_log import SecurityAuditLog
from app.models.transaction import Transaction, TransactionTypeEnum
from app.models.user import User
from app.services.audit_timeline_service import _parse_redacted_json, _redact_text, _safe_resource_id
from app.services.timezones import normalize_timezone


_SPECIALIZED_TABLES = {
    "transactions",
    "cash_sessions",
    "cash_movements",
    "cash_close_reports",
    "cash_custody_handoffs",
}
_MAX_CANDIDATES = 20_000

_AREA_BY_TABLE = {
    "reservations": "reservations",
    "reservation": "reservations",
    "reservation_status_history": "reservations",
    "reservation_adjustments": "reservations",
    "rooms": "rooms",
    "room": "rooms",
    "room_categories": "rooms",
    "room_state_events": "rooms",
    "guests": "guests",
    "guest": "guests",
    "guest_tags": "guests",
    "guest_documents": "guests",
    "transactions": "payments",
    "transaction": "payments",
    "payment_proofs": "payments",
    "billing_adjustments": "payments",
    "cash_sessions": "cash",
    "cash_movements": "cash",
    "cash_close_reports": "cash",
    "cash_custody_handoffs": "cash",
    "stock_items": "inventory",
    "stock_locations": "inventory",
    "stock_movements": "inventory",
    "linen_items": "laundry",
    "linen_locations": "laundry",
    "linen_movements": "laundry",
    "rate_plans": "commercial",
    "daily_rates": "commercial",
    "price_periods": "commercial",
    "promotions": "commercial",
    "sellable_products": "commercial",
    "tax_policies": "commercial",
    "users": "users",
    "user_sessions": "users",
    "permissions": "permissions",
    "role_permission_defaults": "permissions",
    "hotel_permission_overrides": "permissions",
    "user_permission_overrides": "permissions",
    "hotel_configuration": "configuration",
    "hotel_configurations": "configuration",
}


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _bounds(from_date: date | None, to_date: date | None, timezone_name: str) -> tuple[datetime | None, datetime | None]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(from_date, time.min, tzinfo=zone).astimezone(timezone.utc) if from_date else None
    end = (
        datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
        if to_date
        else None
    )
    return start, end


def _date_filter(model: Any, start: datetime | None, end: datetime | None, field_name: str) -> list[Any]:
    field = getattr(model, field_name)
    filters: list[Any] = []
    if start is not None:
        filters.append(field >= start)
    if end is not None:
        filters.append(field < end)
    return filters


def _actor_name(user: User | None, *, provider_code: str | None = None) -> str:
    if user is not None:
        return user.display_name or user.email
    return "Sistema/Proveedor" if provider_code else "Sistema"


def _area_for(entity_type: str | None) -> str:
    normalized = (entity_type or "other").strip().lower()
    return _AREA_BY_TABLE.get(normalized, normalized)


def _row(
    *,
    source: str,
    source_id: int,
    area: str,
    action: str,
    summary: str,
    actor_user_id: int | None,
    occurred_at: datetime,
    details: dict[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "area": area,
        "action": action,
        "summary": summary,
        "actor_user_id": actor_user_id,
        "actor_name": fields.pop("actor_name", "Sistema"),
        "occurred_at": _utc(occurred_at),
        "details": details or {},
        **fields,
    }


def _matches(item: dict[str, Any], *, actor_user_id: int | None, category: str | None, reservation_id: int | None, room_id: int | None, action: str | None) -> bool:
    if actor_user_id is not None and item["actor_user_id"] != actor_user_id:
        return False
    if category is not None and item["area"] != category:
        return False
    if reservation_id is not None and item.get("reservation_id") != reservation_id:
        return False
    if room_id is not None and room_id not in {item.get("room_id"), item.get("from_room_id"), item.get("to_room_id")}:
        return False
    if action is not None and item["action"] != action:
        return False
    return True


def list_operational_audit(
    db: Session,
    *,
    hotel_id: int,
    limit: int,
    offset: int,
    from_date: date | None = None,
    to_date: date | None = None,
    actor_user_id: int | None = None,
    category: str | None = None,
    reservation_id: int | None = None,
    room_id: int | None = None,
    action: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = normalize_timezone((hotel.hotel_timezone if hotel else None) or "UTC")
    start, end = _bounds(from_date, to_date, timezone_name)
    rows: list[dict[str, Any]] = []
    user_cache: dict[int, User | None] = {}

    def _user(user_id: int | None, fallback: User | None = None) -> User | None:
        if user_id is None:
            return fallback
        if user_id not in user_cache:
            user_cache[user_id] = db.get(User, user_id)
        return user_cache[user_id] or fallback

    audit_query = db.query(AuditLog).filter(AuditLog.hotel_id == hotel_id)
    if _SPECIALIZED_TABLES:
        audit_query = audit_query.filter(~AuditLog.table_name.in_(_SPECIALIZED_TABLES))
    audit_query = audit_query.filter(*_date_filter(AuditLog, start, end, "created_at"))
    for event in audit_query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(_MAX_CANDIDATES).all():
        after_payload = _parse_redacted_json(event.payload_after)
        system_actor = "Sistema"
        if isinstance(after_payload, dict):
            source_marker = after_payload.get("source")
            if source_marker in {"ota", "manual_ota"}:
                system_actor = "Sistema/OTA"
            elif source_marker in {"public_api", "whatsapp"}:
                system_actor = "Sistema/Canal público"
        row = _row(
            source="row_mutation",
            source_id=event.id,
            area=_area_for(event.table_name),
            action=_value(event.action),
            summary=f"{event.table_name}: {_value(event.action)} #{event.record_id}",
            actor_user_id=event.actor_user_id,
            actor_name=(
                _actor_name(_user(event.actor_user_id, event.actor))
                if event.actor_user_id is not None
                else system_actor
            ),
            occurred_at=event.created_at,
            details={
                "record_id": event.record_id,
                "before": _parse_redacted_json(event.payload_before),
                "after": after_payload,
            },
        )
        if event.table_name == "reservations":
            row["reservation_id"] = event.record_id
        if event.table_name == "rooms":
            row["room_id"] = event.record_id
        rows.append(row)

    business_query = db.query(HotelAuditEvent).filter(
        HotelAuditEvent.hotel_id == hotel_id,
        *_date_filter(HotelAuditEvent, start, end, "created_at"),
    )
    for event in business_query.order_by(HotelAuditEvent.created_at.desc(), HotelAuditEvent.id.desc()).limit(_MAX_CANDIDATES).all():
        rows.append(
            _row(
                source="business_event",
                source_id=event.id,
                area=_area_for(event.entity_type),
                action=event.action_code,
                summary=f"{event.action_code} ({event.entity_type} #{event.entity_id})",
                actor_user_id=event.user_id,
                actor_name=_actor_name(_user(event.user_id)),
                occurred_at=event.created_at,
                reservation_id=event.entity_id if event.entity_type in {"reservation", "reservations"} else None,
                room_id=event.entity_id if event.entity_type in {"room", "rooms"} else None,
                details={
                    "entity_id": event.entity_id,
                    "before": _parse_redacted_json(event.before_json),
                    "after": _parse_redacted_json(event.after_json),
                },
            )
        )

    security_query = db.query(SecurityAuditLog).filter(
        SecurityAuditLog.hotel_id == hotel_id,
        *_date_filter(SecurityAuditLog, start, end, "created_at"),
    )
    for event in security_query.order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc()).limit(_MAX_CANDIDATES).all():
        rows.append(
            _row(
                source="security_event",
                source_id=event.id,
                area="security",
                action=event.action,
                summary=f"Evento de seguridad: {event.action}",
                actor_user_id=event.user_id,
                actor_name=_actor_name(_user(event.user_id)),
                occurred_at=event.created_at,
                details={
                    "resource_type": event.resource_type,
                    "resource_id": _safe_resource_id("security_event", event.resource_type, event.resource_id),
                    "event_details": _parse_redacted_json(event.details),
                },
            )
        )

    move_query = db.query(RoomMoveEvent).filter(
        RoomMoveEvent.hotel_id == hotel_id,
        *_date_filter(RoomMoveEvent, start, end, "occurred_at"),
    )
    for event in move_query.order_by(RoomMoveEvent.occurred_at.desc(), RoomMoveEvent.id.desc()).limit(_MAX_CANDIDATES).all():
        from_number = event.from_room.room_number if event.from_room else event.from_room_id
        to_number = event.to_room.room_number if event.to_room else event.to_room_id
        disposition = event.origin_room_disposition
        rows.append(
            _row(
                source="room_move_event",
                source_id=event.id,
                area="rooms",
                action="room.move",
                summary=f"Reserva #{event.reservation_id}: habitación {from_number} → {to_number}",
                actor_user_id=event.created_by_user_id,
                actor_name=_actor_name(_user(event.created_by_user_id, event.created_by)),
                occurred_at=event.occurred_at,
                reservation_id=event.reservation_id,
                room_id=event.to_room_id,
                from_room_id=event.from_room_id,
                to_room_id=event.to_room_id,
                reason_code=event.reason_code,
                reason_note=event.reason_note,
                origin_room_disposition=disposition,
                origin_room_status_before=event.origin_room_status_before,
                origin_room_status_after=event.origin_room_status_after,
                details={
                    "move_type": _value(event.move_type),
                    "trigger_event": event.trigger_event,
                    "origin_room_disposition": disposition,
                    "origin_room_disposition_note": event.origin_room_disposition_note,
                    "state_before": event.state_before,
                    "state_after": event.state_after,
                },
            )
        )

    status_query = db.query(ReservationStatusHistory).filter(
        ReservationStatusHistory.hotel_id == hotel_id,
        *_date_filter(ReservationStatusHistory, start, end, "changed_at"),
    )
    for event in status_query.order_by(ReservationStatusHistory.changed_at.desc(), ReservationStatusHistory.id.desc()).limit(_MAX_CANDIDATES).all():
        target = "check-in" if event.to_status == "checked_in" else "check-out" if event.to_status == "checked_out" else "reserva"
        rows.append(
            _row(
                source="reservation_status_history",
                source_id=event.id,
                area="reservations",
                action=f"reservation.status.{event.to_status}",
                summary=f"{target.capitalize()} de reserva #{event.reservation_id}",
                actor_user_id=event.changed_by_user_id,
                actor_name=_actor_name(_user(event.changed_by_user_id, event.changed_by)),
                occurred_at=event.changed_at,
                reservation_id=event.reservation_id,
                reason_code=event.reason_code,
                reason_note=event.notes,
                details={"from_status": event.from_status, "to_status": event.to_status},
            )
        )

    transaction_time_filters = []
    if start is not None:
        transaction_time_filters.append(
            or_(Transaction.created_at >= start, Transaction.processed_at >= start)
        )
    if end is not None:
        transaction_time_filters.append(
            or_(Transaction.created_at < end, Transaction.processed_at < end)
        )
    transaction_query = db.query(Transaction).filter(Transaction.hotel_id == hotel_id, *transaction_time_filters)
    for transaction in transaction_query.order_by(Transaction.created_at.desc(), Transaction.id.desc()).limit(_MAX_CANDIDATES).all():
        transaction_type = _value(transaction.transaction_type)
        signed_amount = -abs(_money(transaction.gross_amount or transaction.amount)) if transaction_type == TransactionTypeEnum.REFUND.value else abs(_money(transaction.gross_amount or transaction.amount))
        rows.append(
            _row(
                source="transaction",
                source_id=transaction.id,
                area="payments",
                action=f"payment.{transaction_type}",
                summary=f"{'Devolución' if transaction_type == 'refund' else 'Cobro'} de reserva #{transaction.reservation_id}",
                actor_user_id=transaction.created_by_user_id,
                actor_name=_actor_name(
                    _user(transaction.created_by_user_id),
                    provider_code=transaction.provider_code,
                ),
                occurred_at=transaction.processed_at or transaction.created_at,
                reservation_id=transaction.reservation_id,
                payment_method=_value(transaction.payment_method),
                transaction_type=transaction_type,
                transaction_status=_value(transaction.status),
                amount=signed_amount,
                currency_code=transaction.currency,
                details={"description": _redact_text(transaction.description or ""), "provider_code": transaction.provider_code},
            )
        )

    movement_query = db.query(CashMovement).filter(
        CashMovement.hotel_id == hotel_id,
        *_date_filter(CashMovement, start, end, "recorded_at"),
    )
    for movement in movement_query.order_by(CashMovement.recorded_at.desc(), CashMovement.id.desc()).limit(_MAX_CANDIDATES).all():
        signed_amount = -_money(movement.amount) if _value(movement.movement_type) == "expense" else _money(movement.amount)
        rows.append(
            _row(
                source="cash_movement",
                source_id=movement.id,
                area="cash",
                action=f"cash.{_value(movement.movement_type)}",
                summary=f"Movimiento de caja #{movement.id}",
                actor_user_id=movement.recorded_by_user_id,
                actor_name=_actor_name(_user(movement.recorded_by_user_id)),
                occurred_at=movement.recorded_at,
                reservation_id=movement.reservation_id,
                movement_type=_value(movement.movement_type),
                amount=signed_amount,
                currency_code="ARS",
                details={"session_id": movement.session_id, "transaction_id": movement.transaction_id, "description": _redact_text(movement.description or "")},
            )
        )

    for model, source, area, action_prefix, time_field in (
        (CashSession, "cash_session", "cash", "cash.session", "opened_at"),
        (CashCloseReport, "cash_close_report", "cash", "cash.close", "closed_at"),
        (CashCustodyHandoff, "cash_custody_handoff", "cash", "cash.custody", "delivered_at"),
        (BillingAdjustment, "billing_adjustment", "payments", "billing.adjustment", "effective_at"),
        (ReservationAdjustment, "reservation_adjustment", "reservations", "reservation.adjustment", "requested_at"),
    ):
        query = db.query(model).filter(model.hotel_id == hotel_id, *_date_filter(model, start, end, time_field))
        for event in query.order_by(getattr(model, time_field).desc(), model.id.desc()).limit(_MAX_CANDIDATES).all():
            if isinstance(event, CashSession):
                actor_id = event.opened_by_user_id
                actor = _user(event.opened_by_user_id)
                occurred = event.opened_at
                event_action = f"{action_prefix}.{_value(event.status)}"
                details = {"status": _value(event.status), "opening_balance": _money(event.opening_balance), "closed_by_user_id": event.closed_by_user_id}
            elif isinstance(event, CashCloseReport):
                actor_id = event.closed_by_user_id
                actor = _user(event.closed_by_user_id)
                occurred = event.closed_at
                event_action = action_prefix
                details = {"session_id": event.session_id, "expected_balance": _money(event.expected_balance), "declared_balance": _money(event.declared_balance), "difference": _money(event.difference), "difference_approved": event.difference_approved}
            elif isinstance(event, CashCustodyHandoff):
                actor_id = event.delivered_by_user_id
                actor = _user(event.delivered_by_user_id)
                occurred = event.delivered_at
                event_action = f"{action_prefix}.{_value(event.status)}"
                details = {"close_report_id": event.close_report_id, "delivered_amount": _money(event.delivered_amount), "received_by_user_id": event.received_by_user_id}
            else:
                actor_id = getattr(event, "created_by_user_id", None)
                actor = _user(getattr(event, "created_by_user_id", None), getattr(event, "created_by", None))
                occurred = getattr(event, time_field)
                event_action = action_prefix
                details = {"reservation_id": getattr(event, "reservation_id", None), "amount": _money(getattr(event, "total_amount", getattr(event, "amount_delta", 0))), "status": _value(getattr(event, "status", ""))}
            rows.append(
                _row(
                    source=source,
                    source_id=event.id,
                    area=area,
                    action=event_action,
                    summary=f"{event_action} #{event.id}",
                    actor_user_id=actor_id,
                    actor_name=_actor_name(actor),
                    occurred_at=occurred,
                    reservation_id=getattr(event, "reservation_id", None),
                    amount=details.get("amount") if "amount" in details else None,
                    currency_code=getattr(event, "currency_code", None),
                    details=details,
                )
            )

    filtered = [
        item
        for item in rows
        if _matches(
            item,
            actor_user_id=actor_user_id,
            category=category,
            reservation_id=reservation_id,
            room_id=room_id,
            action=action,
        )
    ]
    filtered.sort(key=lambda item: (_utc(item["occurred_at"]), item["source"], item["source_id"]), reverse=True)
    total = len(filtered)
    return filtered[offset : offset + limit], total
