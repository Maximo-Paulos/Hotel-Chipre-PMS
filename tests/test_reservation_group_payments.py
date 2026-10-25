"""One operator-entered collection stays idempotent across grouped reservations."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import BackgroundTasks
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api import reservation_groups as reservation_groups_api
from app.api.cash_register import list_cash_movements
from app.dependencies.auth import AuthContext
from app.models.audit_log import AuditLog
from app.models.cash_register import CashMovement
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.reservation import Reservation
from app.models.reservation_group import ReservationGroup
from app.models.reservation_group_payment import (
    ReservationGroupPaymentAllocation,
    ReservationGroupPaymentBatch,
)
from app.models.transaction import PaymentMethodEnum, Transaction
from app.schemas.cash_register import CashMovementRead
from app.schemas.reservation import ReservationCreate, ReservationGroupCreate
from app.schemas.reservation_group_payment import (
    ReservationGroupPaymentAllocationRequest,
    ReservationGroupPaymentCreate,
)
from app.services import payment_service as payment_service_module
from app.services.cash_register_service import list_movements, open_session
from app.services.reservation_group_payment_service import (
    create_reservation_group_payment,
)
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
    db.add(
        PaymentSurcharge(
            hotel_id=1,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.PERCENTAGE,
            amount=5.0,
            is_active=True,
        )
    )
    db.flush()
    from app.services.payment_service import PaymentError, calculate_payment_surcharge

    total_surcharge = calculate_payment_surcharge(
        db,
        hotel_id=1,
        payment_method=PaymentMethodEnum.CASH,
        base_amount=amount,
    )["surcharge_amount"]
    expected_gross = (amount + Decimal(str(total_surcharge))).quantize(Decimal("0.01"))
    payload = ReservationGroupPaymentCreate(
        received_amount=amount,
        cash_received_amount=expected_gross + Decimal("100.00"),
        cash_tip_amount=Decimal("100.00"),
        currency="ARS",
        payment_method=PaymentMethodEnum.CASH,
        allocations=[
            ReservationGroupPaymentAllocationRequest(reservation_id=item.id, received_amount=child_amount)
            for item in reservations
        ],
    )

    underpaid_payload = payload.model_copy(
        update={"cash_received_amount": expected_gross - Decimal("1.00")}
    )
    with pytest.raises(PaymentError, match="menor al importe total"):
        create_reservation_group_payment(
            db,
            hotel_id=1,
            group_id=group.id,
            payload=underpaid_payload,
            idempotency_key="group-payment-under-tender-001",
            actor_user_id=None,
        )
    assert db.query(ReservationGroupPaymentBatch).filter_by(hotel_id=1, group_id=group.id).count() == 0

    with pytest.raises(PaymentError, match="propina"):
        create_reservation_group_payment(
            db,
            hotel_id=1,
            group_id=group.id,
            payload=payload.model_copy(update={"cash_tip_amount": Decimal("100.01")}),
            idempotency_key="group-payment-tip-too-high-001",
            actor_user_id=None,
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
    assert first["cash_received_amount"] == expected_gross + Decimal("100.00")
    assert first["gross_amount"] == expected_gross
    assert first["cash_tip_amount"] == Decimal("100.00")
    assert first["cash_change_amount"] == Decimal("0.00")
    assert len(first["allocations"]) == 2
    assert db.query(ReservationGroupPaymentBatch).filter_by(hotel_id=1, group_id=group.id).count() == 1
    assert db.query(ReservationGroupPaymentAllocation).filter_by(hotel_id=1).count() == 2
    assert db.query(Transaction).filter(Transaction.group_payment_batch_id == first["id"]).count() == 2
    movements = db.query(CashMovement).filter(CashMovement.hotel_id == 1).all()
    assert len(movements) == 2
    assert sum((Decimal(str(row.amount)) for row in movements), Decimal("0.00")) == expected_gross + Decimal("100.00")
    child_transactions = db.query(Transaction).filter(Transaction.group_payment_batch_id == first["id"]).all()
    assert len(child_transactions) == 2
    assert all(row.cash_received_amount is None for row in child_transactions)
    assert all(row.cash_change_amount is None for row in child_transactions)
    grouped_movements = list_movements(
        db,
        hotel_id=1,
        session_id=movements[0].session_id,
    )
    assert len(grouped_movements) == 2
    assert {row.group_payment_batch_id for row in grouped_movements} == {first["id"]}
    assert {row.group_payment_total for row in grouped_movements} == {expected_gross}
    assert {row.group_payment_reservation_count for row in grouped_movements} == {2}
    serialized_movements = [CashMovementRead.model_validate(row) for row in grouped_movements]
    assert all(row.group_payment_batch_id == first["id"] for row in serialized_movements)
    assert all(row.group_payment_total == expected_gross for row in serialized_movements)
    assert sum((row.cash_tip_amount for row in serialized_movements), Decimal("0.00")) == Decimal("100.00")
    assert all(row.group_payment_reservation_count == 2 for row in serialized_movements)

    api_movements = list_cash_movements(
        session_id=movements[0].session_id,
        db=db,
        context=AuthContext(hotel_id=1, user_role="owner", permissions={"cash:view"}),
    )
    response_movements = [CashMovementRead.model_validate(row).model_dump() for row in api_movements]
    assert len(response_movements) == 2
    assert {row["group_payment_batch_id"] for row in response_movements} == {first["id"]}
    assert {row["group_payment_total"] for row in response_movements} == {expected_gross}
    assert sum((row["cash_tip_amount"] for row in response_movements), Decimal("0.00")) == Decimal("100.00")

    from app.services.cash_daily_summary_service import get_daily_summary
    from app.services.timezones import hotel_today

    daily = get_daily_summary(
        db,
        hotel_id=1,
        report_date=hotel_today(db, 1),
        currency_code="ARS",
    )
    grouped_entries = [
        row for row in daily["entries"] if row["group_payment_batch_id"] == first["id"]
    ]
    tender_entries = [row for row in grouped_entries if row["cash_received_amount"] is not None]
    assert len(grouped_entries) == 2
    assert len(tender_entries) == 1
    assert tender_entries[0]["cash_received_amount"] == expected_gross + Decimal("100.00")
    assert tender_entries[0]["cash_tip_amount"] == Decimal("100.00")
    assert tender_entries[0]["cash_change_amount"] == Decimal("0.00")
    assert sum((row["amount"] for row in grouped_entries), Decimal("0.00")) == expected_gross
    assert daily["gross_collected"] == expected_gross
    assert daily["cash_tips_total"] == Decimal("100.00")
    assert daily["physical_cash_net_collected"] == expected_gross + Decimal("100.00")
    assert daily["physical_cash"]["income_total"] == expected_gross + Decimal("100.00")
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
    assert replay["cash_received_amount"] == expected_gross + Decimal("100.00")
    assert replay["cash_tip_amount"] == Decimal("100.00")
    assert db.query(Transaction).filter(Transaction.group_payment_batch_id == first["id"]).count() == 2
    assert db.query(CashMovement).filter(CashMovement.hotel_id == 1).count() == 2
    with pytest.raises(PaymentError, match="clave de idempotencia"):
        create_reservation_group_payment(
            db,
            hotel_id=1,
            group_id=group.id,
            payload=payload.model_copy(
                update={"cash_received_amount": expected_gross + Decimal("101.00")}
            ),
            idempotency_key="group-payment-attempt-001",
            actor_user_id=None,
        )
    with pytest.raises(PaymentError, match="clave de idempotencia"):
        create_reservation_group_payment(
            db,
            hotel_id=1,
            group_id=group.id,
            payload=payload.model_copy(update={"cash_tip_amount": Decimal("99.00")}),
            idempotency_key="group-payment-attempt-001",
            actor_user_id=None,
        )


def test_group_fixed_surcharge_converts_to_group_tender_currency_and_preserves_fx_provenance(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    check_in = date(2030, 3, 10)
    check_out = check_in + timedelta(days=1)
    quote = build_reservation_quote(
        db,
        hotel_id=hotel_config.id,
        category_id=sample_categories[0].id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=1,
    )
    group, reservations = create_reservation_group(
        db,
        hotel_id=hotel_config.id,
        reservations=[
            ReservationCreate(
                guest_id=sample_guest.id,
                category_id=sample_categories[0].id,
                check_in_date=check_in,
                check_out_date=check_out,
                num_adults=1,
                quote_token=quote["quote_token"],
            )
            for _ in range(2)
        ],
        actor_user_id=None,
        actor_role=None,
    )
    for reservation in reservations:
        reservation.currency_code = "USD"
        reservation.total_amount = Decimal("100.00")
        reservation.deposit_amount = Decimal("30.00")
    db.add(
        PaymentSurcharge(
            hotel_id=hotel_config.id,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    def quote_surcharge(_db, *, amount, from_currency, to_currency, **_kwargs):
        assert (from_currency, to_currency) == ("ARS", "USD")
        return amount * 0.02, 0.02, {"source": "group_surcharge_quote", "applied_rate": 0.02}

    monkeypatch.setattr(payment_service_module, "_convert_amount", quote_surcharge)
    open_session(
        db,
        hotel_id=hotel_config.id,
        opened_by_user_id=None,
        opening_balance=Decimal("0.00"),
        currency_code="USD",
    )
    payload = ReservationGroupPaymentCreate(
        received_amount=Decimal("20.00"),
        currency="USD",
        payment_method=PaymentMethodEnum.CASH,
        allocations=[
            ReservationGroupPaymentAllocationRequest(reservation_id=item.id, received_amount=Decimal("10.00"))
            for item in reservations
        ],
    )

    result, replayed = create_reservation_group_payment(
        db,
        hotel_id=hotel_config.id,
        group_id=group.id,
        payload=payload,
        idempotency_key="group-fixed-surcharge-fx-001",
        actor_user_id=None,
    )
    db.flush()

    transactions = (
        db.query(Transaction)
        .filter(Transaction.group_payment_batch_id == result["id"])
        .order_by(Transaction.reservation_id)
        .all()
    )
    assert replayed is False
    assert result["gross_amount"] == Decimal("40.00")
    assert len(transactions) == 2
    assert [item.fee_amount for item in transactions] == [Decimal("10.00"), Decimal("10.00")]
    assert [item.gross_amount for item in transactions] == [Decimal("20.00"), Decimal("20.00")]
    assert all(
        item.fx_quote_details["payment_surcharge_quote"]["source"] == "group_surcharge_quote"
        for item in transactions
    )


def test_group_cash_idempotency_defaults_omitted_tender_to_expected_gross(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
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
    session = open_session(db, hotel_id=1, opened_by_user_id=None, opening_balance=Decimal("0.00"))
    allocations = [
        ReservationGroupPaymentAllocationRequest(reservation_id=item.id, received_amount=Decimal("1.00"))
        for item in reservations
    ]
    payload = ReservationGroupPaymentCreate(
        received_amount=Decimal("2.00"),
        currency="ARS",
        payment_method=PaymentMethodEnum.CASH,
        allocations=allocations,
    )

    first, replayed = create_reservation_group_payment(
        db,
        hotel_id=1,
        group_id=group.id,
        payload=payload,
        idempotency_key="group-default-tender-001",
        actor_user_id=None,
    )
    replay, replayed_again = create_reservation_group_payment(
        db,
        hotel_id=1,
        group_id=group.id,
        payload=payload,
        idempotency_key="group-default-tender-001",
        actor_user_id=None,
    )

    assert replayed is False
    assert replayed_again is True
    assert replay["id"] == first["id"]
    assert first["cash_received_amount"] == Decimal("2.00")
    assert first["cash_change_amount"] == Decimal("0.00")
    assert db.query(ReservationGroupPaymentBatch).filter_by(id=first["id"]).count() == 1
    movements = db.query(CashMovement).filter_by(hotel_id=1, session_id=session.id).all()
    assert len(movements) == 2
    assert sum((Decimal(str(row.amount)) for row in movements), Decimal("0.00")) == Decimal("2.00")


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
