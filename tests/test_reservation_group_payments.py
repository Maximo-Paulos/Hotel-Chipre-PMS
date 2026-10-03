"""One operator-entered collection stays idempotent across grouped reservations."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import BackgroundTasks
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api import reservation_groups as reservation_groups_api
from app.api.cash_register import list_cash_movements
from app.dependencies.auth import AuthContext
from app.models.audit_log import AuditLog
from app.models.cash_register import CashMovement
from app.models.reservation import Reservation
from app.models.reservation_group import ReservationGroup
from app.models.reservation_group_payment import (
    ReservationGroupPaymentAllocation,
    ReservationGroupPaymentBatch,
)
from app.models.transaction import PaymentMethodEnum, Transaction
from app.schemas.reservation import ReservationCreate, ReservationGroupCreate
from app.schemas.cash_register import CashMovementRead
from app.schemas.reservation_group_payment import (
    ReservationGroupPaymentAllocationRequest,
    ReservationGroupPaymentCreate,
)
from app.services.cash_register_service import list_movements, open_session
from app.services.reservation_group_payment_service import create_reservation_group_payment
from app.services.reservation_group_service import create_reservation_group
from app.services.reservation_quote_service import build_reservation_quote


def test_group_payment_is_one_idempotent_cash_collection_with_manual_allocations(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    check_in = date(2030, 1, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=sample_categories[0].id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )
    children = [
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        )
        for _ in range(2)
    ]
    group, reservations = create_reservation_group(
        db,
        hotel_id=1,
        reservations=children,
        actor_user_id=None,
        actor_role=None,
    )
    open_session(db, hotel_id=1, opened_by_user_id=None, opening_balance=Decimal("0.00"))
    child_amount = Decimal(str(reservations[0].total_amount)).quantize(Decimal("0.01"))
    amount = child_amount * 2
    payload = ReservationGroupPaymentCreate(
        received_amount=amount,
        currency="ARS",
        payment_method=PaymentMethodEnum.CASH,
        allocations=[
            ReservationGroupPaymentAllocationRequest(reservation_id=item.id, received_amount=child_amount)
            for item in reservations
        ],
    )

    first, replayed = create_reservation_group_payment(
        db,
        hotel_id=1,
        group_id=group.id,
        payload=payload,
        idempotency_key="group-payment-attempt-001",
        actor_user_id=None,
    )
    db.flush()
    assert replayed is False
    assert first["received_amount"] == amount
    assert len(first["allocations"]) == 2
    assert db.query(ReservationGroupPaymentBatch).filter_by(hotel_id=1, group_id=group.id).count() == 1
    assert db.query(ReservationGroupPaymentAllocation).filter_by(hotel_id=1).count() == 2
    assert db.query(Transaction).filter(Transaction.group_payment_batch_id == first["id"]).count() == 2
    movements = db.query(CashMovement).filter(CashMovement.hotel_id == 1).all()
    assert len(movements) == 2
    assert sum((Decimal(str(row.amount)) for row in movements), Decimal("0.00")) == amount
    grouped_movements = list_movements(
        db,
        hotel_id=1,
        session_id=movements[0].session_id,
    )
    assert len(grouped_movements) == 2
    assert {row.group_payment_batch_id for row in grouped_movements} == {first["id"]}
    assert {row.group_payment_total for row in grouped_movements} == {amount}
    assert {row.group_payment_reservation_count for row in grouped_movements} == {2}
    serialized_movements = [CashMovementRead.model_validate(row) for row in grouped_movements]
    assert all(row.group_payment_batch_id == first["id"] for row in serialized_movements)
    assert all(row.group_payment_total == amount for row in serialized_movements)
    assert all(row.group_payment_reservation_count == 2 for row in serialized_movements)

    api_movements = list_cash_movements(
        session_id=movements[0].session_id,
        db=db,
        context=AuthContext(hotel_id=1, user_role="owner", permissions={"cash:view"}),
    )
    response_movements = [CashMovementRead.model_validate(row).model_dump() for row in api_movements]
    assert len(response_movements) == 2
    assert {row["group_payment_batch_id"] for row in response_movements} == {first["id"]}
    assert {row["group_payment_total"] for row in response_movements} == {amount}
    assert {row["group_payment_reservation_count"] for row in response_movements} == {2}

    replay, replayed = create_reservation_group_payment(
        db,
        hotel_id=1,
        group_id=group.id,
        payload=payload,
        idempotency_key="group-payment-attempt-001",
        actor_user_id=None,
    )
    assert replayed is True
    assert replay["id"] == first["id"]
    assert db.query(Transaction).filter(Transaction.group_payment_batch_id == first["id"]).count() == 2
    assert db.query(CashMovement).filter(CashMovement.hotel_id == 1).count() == 2


def test_group_payment_requires_exact_child_allocation_sum():
    with pytest.raises(ValidationError, match="suma de las asignaciones"):
        ReservationGroupPaymentCreate(
            received_amount=Decimal("100.00"),
            currency="ARS",
            payment_method=PaymentMethodEnum.CASH,
            allocations=[
                ReservationGroupPaymentAllocationRequest(
                    reservation_id=1,
                    received_amount=Decimal("99.99"),
                )
            ],
        )


def test_group_creation_rolls_back_if_group_audit_insert_fails(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    check_in = date(2030, 4, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=sample_categories[0].id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )
    children = [
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        )
        for _ in range(2)
    ]

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("app.api.reservation_groups.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        reservation_groups_api.create_reservation_group_route(
            data=ReservationGroupCreate(reservations=children),
            background_tasks=BackgroundTasks(),
            request=None,
            db=db,
            context=AuthContext(hotel_id=1, user_id=None, user_role="owner"),
        )

    assert db.query(ReservationGroup).filter_by(hotel_id=1).count() == 0
    assert db.query(Reservation).filter_by(hotel_id=1).count() == 0
    assert db.query(ReservationGroupPaymentBatch).count() == 0
    assert db.query(ReservationGroupPaymentAllocation).count() == 0
    assert db.query(Transaction).filter(Transaction.hotel_id == 1).count() == 0
    assert db.query(AuditLog).filter_by(hotel_id=1, table_name="reservation_groups").count() == 0


def test_group_payment_rolls_back_everything_when_audit_insert_fails(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    check_in = date(2030, 2, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=sample_categories[0].id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )
    child_requests = [
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        )
        for _ in range(2)
    ]
    group, reservations = create_reservation_group(
        db,
        hotel_id=1,
        reservations=child_requests,
        actor_user_id=None,
        actor_role=None,
    )
    open_session(db, hotel_id=1, opened_by_user_id=None, opening_balance=Decimal("0.00"))
    db.commit()

    def fail_audit_insert(db_session, **kwargs):
        db_session.add(
            AuditLog(
                hotel_id=kwargs["hotel_id"],
                table_name=kwargs["table_name"],
                record_id=kwargs["record_id"],
                action=None,
            )
        )
        db_session.flush()

    monkeypatch.setattr("app.api.reservation_groups.create_audit_log", fail_audit_insert)

    child_amounts = [Decimal(str(item.total_amount)).quantize(Decimal("0.01")) for item in reservations]
    received_amount = sum(child_amounts, Decimal("0.00"))
    reservation_ids = [item.id for item in reservations]
    data = ReservationGroupPaymentCreate(
        received_amount=received_amount,
        currency="ARS",
        payment_method=PaymentMethodEnum.CASH,
        allocations=[
            ReservationGroupPaymentAllocationRequest(reservation_id=item.id, received_amount=amount)
            for item, amount in zip(reservations, child_amounts)
        ],
    )

    # SQLite's in-memory test engine does not emit BEGIN before SAVEPOINT by
    # default; make the outer transaction explicit so nested payment savepoints
    # remain rollbackable like they are on PostgreSQL.
    db.connection().exec_driver_sql("BEGIN")
    with pytest.raises(IntegrityError):
        reservation_groups_api.create_reservation_group_payment_route(
            group_id=group.id,
            data=data,
            request=None,
            idempotency_key="audit-failure-attempt-001",
            db=db,
            context=AuthContext(
                hotel_id=1,
                user_role="owner",
                is_verified=True,
                permissions=set(),
            ),
        )

    assert db.query(ReservationGroupPaymentBatch).filter_by(hotel_id=1, group_id=group.id).count() == 0
    assert db.query(ReservationGroupPaymentAllocation).filter_by(hotel_id=1).count() == 0
    assert db.query(Transaction).filter(Transaction.hotel_id == 1, Transaction.reservation_id.in_(reservation_ids)).count() == 0
    assert db.query(CashMovement).filter(CashMovement.hotel_id == 1).count() == 0
    assert db.query(AuditLog).filter_by(hotel_id=1, table_name="reservation_group_payment_batches").count() == 0
