"""Regression coverage for manager-approved, atomic payment corrections."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func

from app.models.audit_log import AuditLog
from app.models.cash_register import (
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
    CashSessionStatusEnum,
)
from app.models.guest import Guest
from app.models.payment_correction import PaymentCorrection
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user import User
from app.services import payment_correction_service
from app.services.cash_register_service import get_session_summary, list_movements
from tests.test_payment_links_api import _reservation

pytest_plugins = ("tests.test_payment_links_api",)


def _add_manager_actor(db):
    actor = User(
        id=1,
        email="payment-manager@example.test",
        password_hash="test-only-not-a-login-hash",
        is_active=True,
        is_verified=True,
    )
    db.add(actor)
    db.flush()
    return actor


def _target_reservation(db, hotel_id: int, code: str, *, total_amount: int = 100):
    guest = Guest(first_name="Target", last_name="Guest", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Target room {code}",
        code=f"T-{code[-8:]}",
        base_price_per_night=total_amount,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 11, 12),
        check_out_date=date(2026, 11, 13),
        total_amount=total_amount,
        deposit_amount=min(30, total_amount),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _payment(
    db,
    reservation: Reservation,
    *,
    method: PaymentMethodEnum = PaymentMethodEnum.CREDIT_CARD,
    reference: str = "BANK-OP-104",
    amount: int = 30,
):
    transaction = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=amount,
        tender_amount=amount,
        tender_currency="ARS",
        gross_amount=amount,
        net_amount=amount,
        currency="ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=method,
        status=TransactionStatusEnum.COMPLETED,
        manual_reference=reference if method != PaymentMethodEnum.CASH else None,
        created_by_user_id=1,
        processed_at=datetime.now(timezone.utc),
    )
    reservation.amount_paid = amount
    db.add(transaction)
    db.commit()
    return transaction


def test_manager_can_atomically_reassign_manual_payment_and_replay_idempotently(client_with_db):
    client, db, context = client_with_db
    source_reservation = _reservation(db, 1, "PAY-CORR-104")
    target_reservation = _target_reservation(db, 1, "PAY-CORR-105")
    _add_manager_actor(db)
    source = _payment(db, source_reservation)
    context["role"] = "manager"
    payload = {
        "correction_type": "reassign",
        "destination_confirmation_code": target_reservation.confirmation_code,
        "reason": "El comprobante corresponde a R-105",
    }
    headers = {"Idempotency-Key": "payment-correction-104-105"}

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["correction_type"] == "reassign"
    assert result["source_transaction_id"] == source.id
    assert result["source_reservation_id"] == source_reservation.id
    assert result["target_reservation_id"] == target_reservation.id
    assert result["replacement_transaction_id"] is not None
    assert result["reason"] == payload["reason"]
    assert result["replayed"] is False

    db.refresh(source)
    replacement = db.get(Transaction, result["replacement_transaction_id"])
    assert source.status == TransactionStatusEnum.CANCELLED
    assert replacement is not None
    assert replacement.status == TransactionStatusEnum.COMPLETED
    assert replacement.reservation_id == target_reservation.id
    assert replacement.amount == source.amount
    assert replacement.manual_reference == source.manual_reference
    assert db.query(PaymentCorrection).count() == 1
    assert db.query(AuditLog).filter(AuditLog.table_name == "payment_corrections").count() == 1

    source_summary = client.get(f"/api/payments/summary/{source_reservation.id}")
    target_summary = client.get(f"/api/payments/summary/{target_reservation.id}")
    assert source_summary.status_code == 200, source_summary.text
    assert target_summary.status_code == 200, target_summary.text
    assert source_summary.json()["amount_paid"] == 0
    assert target_summary.json()["amount_paid"] == 30
    assert source_summary.json()["payment_corrections"][0]["reason"] == payload["reason"]
    assert target_summary.json()["payment_corrections"][0]["replacement_transaction_id"] == replacement.id

    replay = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json=payload,
        headers=headers,
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["correction_id"] == result["correction_id"]
    assert replay.json()["replacement_transaction_id"] == replacement.id
    assert replay.json()["replayed"] is True
    assert db.query(Transaction).filter(Transaction.reservation_id == target_reservation.id).count() == 1

    conflict = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={**payload, "reason": "Motivo distinto"},
        headers=headers,
    )
    assert conflict.status_code == 409


def test_receptionist_cannot_correct_payment(client_with_db):
    client, db, context = client_with_db
    reservation = _reservation(db, 1, "PAY-CORR-DENY")
    _add_manager_actor(db)
    source = _payment(db, reservation)
    context["role"] = "receptionist"

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={"correction_type": "duplicate_reversal", "reason": "Registro repetido"},
        headers={"Idempotency-Key": "payment-correction-denied"},
    )

    assert response.status_code == 403
    db.refresh(source)
    assert source.status == TransactionStatusEnum.COMPLETED
    assert db.query(PaymentCorrection).count() == 0


def test_duplicate_reversal_keeps_history_without_creating_a_replacement(client_with_db):
    client, db, context = client_with_db
    reservation = _reservation(db, 1, "PAY-CORR-DUP")
    _add_manager_actor(db)
    source = _payment(db, reservation, method=PaymentMethodEnum.BANK_TRANSFER, reference="DUP-104")
    context["role"] = "manager"

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={"correction_type": "duplicate_reversal", "reason": "Se cargó dos veces"},
        headers={"Idempotency-Key": "payment-correction-duplicate"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["replacement_transaction_id"] is None
    assert response.json()["target_reservation_id"] is None
    assert db.query(Transaction).count() == 1
    db.refresh(source)
    assert source.status == TransactionStatusEnum.CANCELLED
    summary = client.get(f"/api/payments/summary/{reservation.id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["amount_paid"] == 0
    assert summary.json()["payment_corrections"][0]["correction_type"] == "duplicate_reversal"


def test_cash_reassignment_moves_existing_movement_and_preserves_drawer_totals(client_with_db):
    client, db, context = client_with_db
    source_reservation = _reservation(db, 1, "PAY-CASH-104")
    target_reservation = _target_reservation(db, 1, "PAY-CASH-105")
    _add_manager_actor(db)
    session = CashSession(
        hotel_id=1,
        opened_by_user_id=1,
        status=CashSessionStatusEnum.OPEN,
        opening_balance=0,
        currency_code="ARS",
    )
    db.add(session)
    db.flush()
    source = _payment(db, source_reservation, method=PaymentMethodEnum.CASH)
    movement = CashMovement(
        hotel_id=1,
        session_id=session.id,
        reservation_id=source_reservation.id,
        transaction_id=source.id,
        recorded_by_user_id=1,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=30,
        description="Cobro de reserva de origen",
    )
    db.add(movement)
    db.commit()
    context["role"] = "manager"

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={
            "correction_type": "reassign",
            "destination_confirmation_code": target_reservation.confirmation_code,
            "reason": "El efectivo corresponde a la reserva de destino",
        },
        headers={"Idempotency-Key": "payment-correction-cash"},
    )

    assert response.status_code == 201, response.text
    replacement_id = response.json()["replacement_transaction_id"]
    db.refresh(movement)
    assert movement.session_id == session.id
    assert movement.reservation_id == target_reservation.id
    assert movement.transaction_id == replacement_id
    assert movement.amount == 30
    assert db.query(CashMovement).filter(CashMovement.session_id == session.id).count() == 1
    assert db.query(func.sum(CashMovement.amount)).filter(CashMovement.session_id == session.id).scalar() == 30


def test_cash_duplicate_reversal_voids_movement_and_excludes_it_from_drawer_totals(client_with_db):
    client, db, context = client_with_db
    reservation = _reservation(db, 1, "PAY-CASH-DUP")
    _add_manager_actor(db)
    session = CashSession(
        hotel_id=1,
        opened_by_user_id=1,
        status=CashSessionStatusEnum.OPEN,
        opening_balance=0,
        currency_code="ARS",
    )
    db.add(session)
    db.flush()
    source = _payment(db, reservation, method=PaymentMethodEnum.CASH)
    movement = CashMovement(
        hotel_id=1,
        session_id=session.id,
        reservation_id=reservation.id,
        transaction_id=source.id,
        recorded_by_user_id=1,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=30,
        description="Cobro duplicado",
    )
    db.add(movement)
    db.commit()
    context["role"] = "manager"

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={"correction_type": "duplicate_reversal", "reason": "Se registró dos veces"},
        headers={"Idempotency-Key": "payment-cash-duplicate"},
    )

    assert response.status_code == 201, response.text
    correction_id = response.json()["correction_id"]
    db.refresh(source)
    db.refresh(movement)
    assert source.status == TransactionStatusEnum.CANCELLED
    assert movement.voided_at is not None
    assert movement.voided_by_payment_correction_id == correction_id
    assert db.query(AuditLog).filter(
        AuditLog.table_name == "cash_movements",
        AuditLog.record_id == movement.id,
    ).count() == 1

    summary = get_session_summary(db, hotel_id=1, session_id=session.id)
    assert summary["expected_balance"] == 0
    assert summary["income_total"] == 0
    assert summary["movements_count"] == 0
    history = list_movements(db, hotel_id=1, session_id=session.id)
    assert len(history) == 1
    assert history[0].voided_by_payment_correction_id == correction_id


@pytest.mark.parametrize(
    "session_status",
    [CashSessionStatusEnum.CLOSED, CashSessionStatusEnum.PENDING_APPROVAL],
)
def test_cash_duplicate_reversal_is_rejected_when_session_is_not_open(client_with_db, session_status):
    client, db, context = client_with_db
    reservation = _reservation(db, 1, f"PAY-CASH-CLOSED-{session_status.value}")
    _add_manager_actor(db)
    session = CashSession(
        hotel_id=1,
        opened_by_user_id=1,
        status=session_status,
        opening_balance=0,
        currency_code="ARS",
    )
    db.add(session)
    db.flush()
    source = _payment(db, reservation, method=PaymentMethodEnum.CASH)
    movement = CashMovement(
        hotel_id=1,
        session_id=session.id,
        reservation_id=reservation.id,
        transaction_id=source.id,
        recorded_by_user_id=1,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=30,
    )
    db.add(movement)
    db.commit()
    context["role"] = "manager"

    response = client.post(
        f"/api/payments/transactions/{source.id}/correction",
        json={"correction_type": "duplicate_reversal", "reason": "Se registró dos veces"},
        headers={"Idempotency-Key": f"payment-cash-not-open-{session_status.value}"},
    )

    assert response.status_code == 409, response.text
    db.refresh(source)
    db.refresh(movement)
    assert source.status == TransactionStatusEnum.COMPLETED
    assert movement.voided_at is None
    assert movement.voided_by_payment_correction_id is None
    assert db.query(PaymentCorrection).count() == 0


def test_audit_failure_rolls_back_the_entire_correction(client_with_db, monkeypatch):
    _client, db, _context = client_with_db
    source_reservation = _reservation(db, 1, "PAY-CORR-ATOMIC")
    target_reservation = _target_reservation(db, 1, "PAY-CORR-ATOMIC-TARGET")
    _add_manager_actor(db)
    source = _payment(db, source_reservation)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("synthetic audit write failure")

    monkeypatch.setattr(payment_correction_service.audit_log_service, "create_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit write failure"):
        payment_correction_service.correct_payment(
            db,
            hotel_id=1,
            source_transaction_id=source.id,
            correction_type="reassign",
            target_reservation_id=target_reservation.id,
            reason="El comprobante corresponde a otra reserva",
            idempotency_key="payment-correction-audit-failure",
            actor_user_id=1,
        )

    db.expire_all()
    assert db.get(Transaction, source.id).status == TransactionStatusEnum.COMPLETED
    assert db.query(PaymentCorrection).count() == 0
    assert db.query(Transaction).count() == 1
