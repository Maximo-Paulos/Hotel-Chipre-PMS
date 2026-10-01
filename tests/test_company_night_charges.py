from datetime import timedelta
from decimal import Decimal

import pytest

from app.models.company import Company
from app.models.company_night_charge import CompanyNightChargePaymentAllocation
from app.models.operations import BillingAdjustment
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest
from app.services.company_night_charge_service import (
    CompanyNightChargeError,
    add_company_night_charges,
    get_company_night_charges,
    prepare_company_night_charge_payment,
    record_company_night_charge_payment_allocations,
)
from app.services.payment_service import PaymentError, process_payment
from app.services.reservation_service import create_reservation
from app.services.timezones import hotel_today


def _company_reservation(
    db,
    *,
    sample_guest,
    sample_rooms,
    sample_categories,
    with_company=True,
    payment_deferred=True,
):
    today = hotel_today(db, 1)
    company = None
    if with_company:
        company = Company(
            hotel_id=1,
            legal_name="Acme QA SA",
            display_name="Acme QA",
            payment_deferred=payment_deferred,
            extra_person_nightly_surcharge=Decimal("75.00"),
        )
        db.add(company)
        db.flush()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            company_id=company.id if company else None,
            check_in_date=today - timedelta(days=2),
            check_out_date=today + timedelta(days=3),
        ),
        hotel_id=1,
    )
    db.flush()
    return company, reservation, today


def _transaction(db, *, hotel_id: int, reservation_id: int, amount: Decimal, status=TransactionStatusEnum.PENDING, key=None):
    transaction = Transaction(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency="ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=status,
        idempotency_key=key,
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    selected_dates = [today, today + timedelta(days=1)]

    first = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=selected_dates,
        actor_user_id=None,
    )
    company.extra_person_nightly_surcharge = Decimal("110.00")
    db.flush()
    repeated = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=selected_dates,
        actor_user_id=None,
    )

    assert [charge.stay_date for charge in first.charges] == selected_dates
    assert [charge.amount for charge in repeated.charges] == [Decimal("75.00"), Decimal("75.00")]
    assert db.query(BillingAdjustment).filter_by(hotel_id=1, reservation_id=reservation.id).count() == 2


def test_company_night_payment_requires_exact_selected_nights_and_tracks_pending_then_paid(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today, today + timedelta(days=1)],
        actor_user_id=None,
    )
    charge_ids = [charge.id for charge in summary.charges]

    with pytest.raises(CompanyNightChargeError, match="Seleccioná las noches"):
        prepare_company_night_charge_payment(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            amount=Decimal("75.00"),
            charge_ids=[],
            idempotency_key="missing-night-selection",
        )
    with pytest.raises(CompanyNightChargeError, match="debe coincidir"):
        prepare_company_night_charge_payment(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            amount=Decimal("74.99"),
            charge_ids=[charge_ids[0]],
            idempotency_key="wrong-night-amount",
        )

    allocation_plan = prepare_company_night_charge_payment(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("75.00"),
        charge_ids=[charge_ids[0]],
        idempotency_key="selected-night-payment",
    )
    transaction = _transaction(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("75.00"),
        key="selected-night-payment",
    )
    record_company_night_charge_payment_allocations(
        db,
        hotel_id=1,
        transaction=transaction,
        allocation_plan=allocation_plan,
    )

    pending = get_company_night_charges(db, hotel_id=1, reservation_id=reservation.id)
    assert pending.charges[0].payment_pending is True
    assert pending.charges[0].paid_amount == Decimal("0.00")
    assert pending.charges[0].remaining_due == Decimal("75.00")
    with pytest.raises(CompanyNightChargeError, match="pendiente de confirmación"):
        prepare_company_night_charge_payment(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            amount=Decimal("75.00"),
            charge_ids=[charge_ids[0]],
            idempotency_key="another-payment-attempt",
        )

    transaction.status = TransactionStatusEnum.COMPLETED
    db.flush()
    paid = get_company_night_charges(db, hotel_id=1, reservation_id=reservation.id)
    assert paid.charges[0].payment_pending is False
    assert paid.charges[0].paid_amount == Decimal("75.00")
    assert paid.charges[0].remaining_due == Decimal("0.00")
    assert db.query(CompanyNightChargePaymentAllocation).filter_by(transaction_id=transaction.id).count() == 1
    assert prepare_company_night_charge_payment(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("75.00"),
        charge_ids=[charge_ids[0]],
        idempotency_key="selected-night-payment",
    ) is None


def test_overdue_company_night_charge_is_review_only_and_cannot_be_collected(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today - timedelta(days=1)],
        actor_user_id=None,
    )
    charge = summary.charges[0]

    assert charge.review_only is True
    with pytest.raises(CompanyNightChargeError, match="vencidas quedan como revisión"):
        prepare_company_night_charge_payment(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            amount=Decimal("75.00"),
            charge_ids=[charge.id],
            idempotency_key="overdue-night-payment",
        )


def test_night_charges_are_limited_to_company_reservations_and_stay_dates(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
        with_company=False,
    )
    assert prepare_company_night_charge_payment(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("10.00"),
        charge_ids=[],
        idempotency_key="ordinary-reservation-payment",
    ) == []
    with pytest.raises(CompanyNightChargeError, match="solo se usan en reservas de empresas"):
        add_company_night_charges(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            stay_dates=[today],
            actor_user_id=None,
        )

    company = Company(
        hotel_id=1,
        legal_name="Another QA SA",
        display_name="Another QA",
        extra_person_nightly_surcharge=Decimal("50.00"),
    )
    db.add(company)
    db.flush()
    reservation.company_id = company.id
    db.flush()
    with pytest.raises(CompanyNightChargeError, match="corresponder a una noche"):
        add_company_night_charges(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            stay_dates=[today + timedelta(days=10)],
            actor_user_id=None,
        )


def test_payment_service_enforces_and_persists_company_night_allocations(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today, today + timedelta(days=1)],
        actor_user_id=None,
    )
    first_night = summary.charges[0]

    missing_selection = PaymentRequest(
        reservation_id=reservation.id,
        amount=75,
        payment_method=PaymentMethodEnum.CREDIT_CARD,
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        manual_reference="POS-NIGHT-REQUIRED",
    )
    with pytest.raises(PaymentError, match="Seleccioná las noches"):
        process_payment(db, missing_selection, hotel_id=1, manual_confirmation=True)
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0

    selected_night_payment = missing_selection.model_copy(
        update={"company_night_charge_ids": [first_night.id]}
    )
    payment = process_payment(
        db,
        selected_night_payment,
        hotel_id=1,
        idempotency_key="company-night-payment-001",
        manual_confirmation=True,
    )
    retry = process_payment(
        db,
        selected_night_payment,
        hotel_id=1,
        idempotency_key="company-night-payment-001",
        manual_confirmation=True,
    )

    assert retry.id == payment.id
    assert reservation.status.value != "fully_paid"
    allocation = db.query(CompanyNightChargePaymentAllocation).filter_by(transaction_id=payment.id).one()
    assert allocation.company_night_charge_id == first_night.id
    assert allocation.amount == Decimal("75.00")


def test_adding_company_night_due_removes_stale_fully_paid_status(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
        payment_deferred=False,
    )
    payment = PaymentRequest(
        reservation_id=reservation.id,
        amount=float(reservation.total_amount),
        payment_method=PaymentMethodEnum.CREDIT_CARD,
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        manual_reference="POS-COMPANY-BASE-FULL",
    )
    process_payment(db, payment, hotel_id=1, manual_confirmation=True)
    assert reservation.status.value == "fully_paid"

    add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today],
        actor_user_id=None,
    )

    assert reservation.status.value != "fully_paid"


def test_regular_company_balance_payment_does_not_consume_night_extras(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
        payment_deferred=False,
    )
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today],
        actor_user_id=None,
    )
    base_payment_amount = min(Decimal("10.00"), Decimal(str(reservation.total_amount)))
    if base_payment_amount <= 0:
        pytest.skip("The fixture room has no standard company balance to collect")

    allocation_plan = prepare_company_night_charge_payment(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=base_payment_amount,
        charge_ids=[],
        idempotency_key="company-base-payment-001",
    )

    assert allocation_plan == []
    assert summary.charges[0].paid_amount == Decimal("0.00")
