"""Focused coverage for the operational audit and hotel-local cash projection."""

import json
from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.analytics import HotelAuditEvent
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.cash_register import CashCloseReport, CashMovement, CashMovementTypeEnum, CashSession, CashSessionStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent, RoomMoveTypeEnum
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.models.user import User
from app.services.cash_daily_summary_service import get_daily_summary
from app.services.operational_audit_service import list_operational_audit


def _user(db, user_id: int, name: str) -> User:
    user = User(
        id=user_id,
        email=f"audit-cash-{user_id}@example.test",
        password_hash="test-hash",
        display_name=name,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _reservation(db, hotel_config, sample_guest, sample_categories) -> Reservation:
    reservation = Reservation(
        confirmation_code="AUDIT-CASH-RESERVATION",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 4),
        check_out_date=date(2026, 9, 6),
        total_amount=Decimal("500.00"),
        subtotal_amount=Decimal("500.00"),
        net_amount=Decimal("500.00"),
        amount_paid=Decimal("500.00"),
        deposit_amount=Decimal("150.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _transaction(
    db,
    *,
    hotel_id: int,
    reservation_id: int,
    actor_id: int | None,
    amount: str,
    method: PaymentMethodEnum,
    transaction_type: TransactionTypeEnum = TransactionTypeEnum.PARTIAL_PAYMENT,
    status: TransactionStatusEnum = TransactionStatusEnum.COMPLETED,
    processed_at: datetime,
    provider_code: str | None = None,
) -> Transaction:
    transaction = Transaction(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        amount=Decimal(amount),
        gross_amount=Decimal(amount),
        currency="ARS",
        transaction_type=transaction_type,
        payment_method=method,
        status=status,
        created_by_user_id=actor_id,
        provider_code=provider_code,
        created_at=processed_at,
        processed_at=processed_at if status == TransactionStatusEnum.COMPLETED else None,
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
):
    hotel_config.hotel_timezone = "America/Argentina/Buenos_Aires"
    collector = _user(db, 9101, "Recepción de prueba")
    reservation = _reservation(db, hotel_config, sample_guest, sample_categories)
    local_day_start = datetime(2026, 9, 4, 3, 0, tzinfo=timezone.utc)

    cash = _transaction(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_id=collector.id,
        amount="100.00",
        method=PaymentMethodEnum.CASH,
        processed_at=local_day_start.replace(hour=4),
    )
    card = _transaction(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_id=collector.id,
        amount="200.00",
        method=PaymentMethodEnum.CREDIT_CARD,
        processed_at=local_day_start.replace(hour=5),
    )
    refund = _transaction(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_id=None,
        amount="50.00",
        method=PaymentMethodEnum.MERCADO_PAGO,
        transaction_type=TransactionTypeEnum.REFUND,
        processed_at=local_day_start.replace(hour=6),
        provider_code="mercado_pago",
    )
    _transaction(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_id=collector.id,
        amount="999.00",
        method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.PENDING,
        processed_at=local_day_start.replace(hour=7),
    )
    previous_local_day = _transaction(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        actor_id=collector.id,
        amount="75.00",
        method=PaymentMethodEnum.CASH,
        processed_at=local_day_start.replace(minute=59, hour=2),
    )

    session = CashSession(
        hotel_id=hotel_config.id,
        opened_by_user_id=collector.id,
        status=CashSessionStatusEnum.CLOSED,
        opening_balance=Decimal("50.00"),
        currency_code="ARS",
        opened_at=local_day_start,
        closed_at=local_day_start.replace(hour=8),
    )
    db.add(session)
    db.flush()
    db.add_all(
        [
            CashMovement(
                hotel_id=hotel_config.id,
                session_id=session.id,
                reservation_id=reservation.id,
                transaction_id=cash.id,
                recorded_by_user_id=collector.id,
                movement_type=CashMovementTypeEnum.INCOME,
                amount=Decimal("100.00"),
                description="Cobro físico",
                recorded_at=local_day_start.replace(hour=4),
            ),
            CashMovement(
                hotel_id=hotel_config.id,
                session_id=session.id,
                recorded_by_user_id=collector.id,
                movement_type=CashMovementTypeEnum.INCOME,
                amount=Decimal("20.00"),
                description="Ingreso manual",
                recorded_at=local_day_start.replace(hour=5),
            ),
            CashMovement(
                hotel_id=hotel_config.id,
                session_id=session.id,
                recorded_by_user_id=collector.id,
                movement_type=CashMovementTypeEnum.EXPENSE,
                amount=Decimal("5.00"),
                description="Compra operativa",
                recorded_at=local_day_start.replace(hour=6),
            ),
        ]
    )
    db.add(
        CashCloseReport(
            hotel_id=hotel_config.id,
            session_id=session.id,
            closed_by_user_id=collector.id,
            expected_balance=Decimal("165.00"),
            declared_balance=Decimal("160.00"),
            difference=Decimal("-5.00"),
            closed_at=local_day_start.replace(hour=8),
        )
    )
    db.flush()

    summary = get_daily_summary(db, hotel_id=hotel_config.id, report_date=date(2026, 9, 4))

    assert summary["gross_collected"] == Decimal("300.00")
    assert summary["refunds"] == Decimal("50.00")
    assert summary["net_collected"] == Decimal("250.00")
    assert summary["physical_cash_net_collected"] == Decimal("100.00")
    assert summary["digital_net_collected"] == Decimal("150.00")
    assert summary["physical_cash"]["expected_balance"] == Decimal("165.00")
    assert summary["physical_cash"]["declared_balance"] == Decimal("160.00")
    assert summary["physical_cash"]["difference"] == Decimal("-5.00")
    assert {entry["transaction_id"] for entry in summary["entries"] if entry["entry_type"] == "payment"} == {
        cash.id,
        card.id,
        refund.id,
    }
    assert previous_local_day.id not in {entry.get("transaction_id") for entry in summary["entries"]}
    assert all(entry.get("transaction_id") is not None for entry in summary["entries"] if entry["entry_type"] == "payment")
    assert any(entry["entry_type"] == "manual_movement" for entry in summary["entries"])
    assert summary["by_collector"][0]["collector_name"] == "Recepción de prueba"


def test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    actor = _user(db, 9102, "Dueño auditor")
    reservation = _reservation(db, hotel_config, sample_guest, sample_categories)
    db.add(
        AuditLog(
            hotel_id=hotel_config.id,
            table_name="guests",
            record_id=sample_guest.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=actor.id,
            payload_before=json.dumps({"email": "old@example.test"}),
            payload_after=json.dumps({"email": "new@example.test"}),
            created_at=datetime(2026, 9, 4, 12, tzinfo=timezone.utc),
        )
    )
    db.add(
        HotelAuditEvent(
            hotel_id=hotel_config.id,
            user_id=actor.id,
            action_code="guest.updated",
            entity_type="guest",
            entity_id=sample_guest.id,
            before_json=json.dumps({"first_name": "Ana"}),
            after_json=json.dumps({"first_name": "Ana María"}),
            created_at=datetime(2026, 9, 4, 13, tzinfo=timezone.utc),
        )
    )
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_config.id,
            user_id=actor.id,
            action="permission.denied",
            resource_type="cash",
            resource_id="sensitive-resource",
            details=json.dumps({"password": "must-not-be-exposed"}),
            created_at=datetime(2026, 9, 4, 14, tzinfo=timezone.utc),
        )
    )
    db.add(
        RoomMoveEvent(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            from_room_id=sample_rooms[0].id,
            to_room_id=sample_rooms[1].id,
            move_type=RoomMoveTypeEnum.MANUAL_MOVE,
            reason_code="guest_preference",
            reason_note="Solicitó cambio",
            origin_room_disposition="cleaning",
            origin_room_status_before="occupied",
            origin_room_status_after="cleaning",
            created_by_user_id=actor.id,
            occurred_at=datetime(2026, 9, 4, 15, tzinfo=timezone.utc),
        )
    )
    db.flush()

    all_items, total = list_operational_audit(db, hotel_id=hotel_config.id, limit=100, offset=0)
    room_items, room_total = list_operational_audit(
        db,
        hotel_id=hotel_config.id,
        limit=20,
        offset=0,
        category="rooms",
        reservation_id=reservation.id,
        action="room.move",
    )
    guest_items, _ = list_operational_audit(
        db,
        hotel_id=hotel_config.id,
        limit=20,
        offset=0,
        category="guests",
        actor_user_id=actor.id,
    )

    assert total >= 4
    assert {item["source"] for item in all_items} >= {"row_mutation", "business_event", "security_event", "room_move_event"}
    assert room_total == 1
    assert room_items[0]["origin_room_disposition"] == "cleaning"
    assert room_items[0]["from_room_id"] == sample_rooms[0].id
    assert guest_items
    assert all(item["area"] == "guests" for item in guest_items)
    security_item = next(item for item in all_items if item["source"] == "security_event")
    assert "must-not-be-exposed" not in json.dumps(security_item["details"])
