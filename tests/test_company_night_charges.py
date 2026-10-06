from datetime import timedelta
from decimal import Decimal

import pytest

from app.models.company import Company
from app.models.guest import Guest
from app.models.company_night_charge import (
    CompanyNightCharge,
    CompanyNightChargeAmountAdjustment,
    CompanyNightChargePaymentAllocation,
    CompanyNightlySurchargeRate,
)
from app.models.operations import BillingAdjustment
from app.models.reservation import ReservationStatusEnum
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
    correct_company_night_charge_amounts,
    create_company_nightly_surcharge_rate,
    get_company_night_charges,
    prepare_company_night_charge_payment,
    record_company_night_charge_payment_allocations,
)
from app.services.payment_service import PaymentError, get_reservation_financial_summary, process_payment
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
    extra_guest_count=1,
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
        db.add(
            CompanyNightlySurchargeRate(
                hotel_id=1,
                company_id=company.id,
                effective_from=today - timedelta(days=2),
                amount=Decimal("75.00"),
            )
        )
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
    if extra_guest_count:
        reservation.additional_guests.extend(
            [
                Guest(
                    hotel_id=sample_guest.hotel_id,
                    first_name=f"Extra {index + 1}",
                    last_name="Company Charge QA",
                )
                for index in range(extra_guest_count)
            ]
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


def test_company_night_charges_use_effective_rate_and_extra_person_quantity(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
        extra_guest_count=2,
    )
    tomorrow_rate = create_company_nightly_surcharge_rate(
        db,
        hotel_id=1,
        company_id=company.id,
        effective_from=today + timedelta(days=1),
        amount=Decimal("110.00"),
        actor_user_id=None,
    )
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today, today + timedelta(days=1)],
        extra_person_count=2,
        actor_user_id=None,
    )

    assert [item.unit_amount for item in summary.charges] == [Decimal("75.00"), Decimal("110.00")]
    assert [item.quantity for item in summary.charges] == [2, 2]
    assert [item.amount for item in summary.charges] == [Decimal("150.00"), Decimal("220.00")]
    assert [item.rate_effective_from for item in summary.charges] == [today - timedelta(days=2), tomorrow_rate.effective_from]


def test_company_charge_quantity_cannot_exceed_registered_additional_people(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )

    with pytest.raises(CompanyNightChargeError, match="supera las personas registradas"):
        add_company_night_charges(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            stay_dates=[today],
            extra_person_count=2,
            actor_user_id=None,
        )


@pytest.mark.parametrize(
    "terminal_status",
    [
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.NO_SHOW,
    ],
)
def test_terminal_company_reservations_cannot_receive_new_nightly_charges(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, terminal_status
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    reservation.status = terminal_status
    db.flush()

    with pytest.raises(CompanyNightChargeError, match="reserva cerrada o cancelada"):
        add_company_night_charges(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            stay_dates=[today],
            actor_user_id=None,
        )

    assert db.query(CompanyNightCharge).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(BillingAdjustment).filter_by(reservation_id=reservation.id).count() == 0


def test_legacy_rate_does_not_price_a_night_before_safe_cutover(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    db.query(CompanyNightlySurchargeRate).filter_by(company_id=company.id).delete()
    db.flush()

    with pytest.raises(CompanyNightChargeError, match="No hay una tarifa.*vigente"):
        add_company_night_charges(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            stay_dates=[today - timedelta(days=1)],
            actor_user_id=None,
        )


def test_explicit_charge_correction_audits_delta_without_rewriting_payment_history(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
    )
    created = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today],
        actor_user_id=None,
    )
    charge = created.charges[0]
    transaction = _transaction(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        status=TransactionStatusEnum.COMPLETED,
        key="partial-extra-payment",
    )
    allocation = CompanyNightChargePaymentAllocation(
        hotel_id=1,
        transaction_id=transaction.id,
        company_night_charge_id=charge.id,
        amount=Decimal("30.00"),
    )
    db.add(allocation)
    db.flush()

    corrected = correct_company_night_charge_amounts(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        items=[{"charge_id": charge.id, "new_amount": Decimal("90.00"), "reason": "Ajuste autorizado de esa noche"}],
        actor_user_id=None,
    )

    db.refresh(transaction)
    db.refresh(allocation)
    adjustment = db.query(CompanyNightChargeAmountAdjustment).filter_by(company_night_charge_id=charge.id).one()
    current_charge = db.query(CompanyNightCharge).filter_by(id=charge.id, hotel_id=1).one()
    billing_adjustment = db.query(BillingAdjustment).filter_by(id=current_charge.billing_adjustment_id, hotel_id=1).one()
    assert corrected.charges[0].amount == Decimal("90.00")
    assert corrected.charges[0].paid_amount == Decimal("30.00")
    assert corrected.charges[0].remaining_due == Decimal("60.00")
    assert corrected.charges[0].adjustments[0].previous_amount == Decimal("75.00")
    assert corrected.charges[0].adjustments[0].new_amount == Decimal("90.00")
    assert corrected.charges[0].adjustments[0].delta_amount == Decimal("15.00")
    assert adjustment.reason == "Ajuste autorizado de esa noche"
    assert transaction.amount == Decimal("30.00")
    assert allocation.amount == Decimal("30.00")
    assert db.query(CompanyNightChargePaymentAllocation).filter_by(company_night_charge_id=charge.id).count() == 1
    assert billing_adjustment.amount == Decimal("90.00")
    assert billing_adjustment.total_amount == Decimal("90.00")


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

    different_night_retry = selected_night_payment.model_copy(
        update={"company_night_charge_ids": [summary.charges[1].id]}
    )
    with pytest.raises(PaymentError, match="clave de idempotencia"):
        process_payment(
            db,
            different_night_retry,
            hotel_id=1,
            idempotency_key="company-night-payment-001",
            manual_confirmation=True,
        )
    assert db.query(Transaction).filter_by(idempotency_key="company-night-payment-001").count() == 1


def test_company_night_refund_reduces_only_the_selected_night(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    from app.services import cash_register_service

    monkeypatch.setattr(cash_register_service, "require_open_session_for_currency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cash_register_service, "record_cash_payment_movement", lambda *args, **kwargs: None)
    _company, reservation, today = _company_reservation(
        db,
        sample_guest=sample_guest,
        sample_rooms=sample_rooms,
        sample_categories=sample_categories,
        extra_guest_count=2,
    )
    first_summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[today],
        actor_user_id=None,
    )
    first_night = next(charge for charge in first_summary.charges if charge.stay_date == today)
    second_date = today + timedelta(days=1)
    second_summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[second_date],
        actor_user_id=None,
        extra_person_count=2,
    )
    second_night = next(charge for charge in second_summary.charges if charge.stay_date == second_date)
    outside_date = today + timedelta(days=2)
    outside_summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[outside_date],
        actor_user_id=None,
    )
    outside_night = next(charge for charge in outside_summary.charges if charge.stay_date == outside_date)
    assert first_night.amount == Decimal("75.00")
    assert second_night.amount == Decimal("150.00")

    source = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=225.00,
            payment_method=PaymentMethodEnum.CREDIT_CARD,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            manual_reference="POS-COMPANY-EXTRAS-1",
            company_night_charge_ids=[first_night.id, second_night.id],
        ),
        hotel_id=1,
        idempotency_key="company-night-refund-source",
        manual_confirmation=True,
    )

    refund_request = PaymentRequest(
        reservation_id=reservation.id,
        amount=75.00,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.REFUND,
        refund_of_transaction_id=source.id,
        refund_reason="Se cancela la noche del martes",
        company_night_charge_refund_allocations=[{"charge_id": first_night.id, "amount": "75.00"}],
    )
    refund = process_payment(
        db,
        refund_request,
        hotel_id=1,
        idempotency_key="company-night-refund-tuesday",
    )

    assert refund.status == TransactionStatusEnum.COMPLETED
    refund_allocation = db.query(CompanyNightChargePaymentAllocation).filter_by(transaction_id=refund.id).one()
    assert refund_allocation.company_night_charge_id == first_night.id
    assert refund_allocation.amount == Decimal("75.00")
    after_refund = get_company_night_charges(db, hotel_id=1, reservation_id=reservation.id)
    charge_by_id = {charge.id: charge for charge in after_refund.charges}
    assert charge_by_id[first_night.id].paid_amount == Decimal("0.00")
    assert charge_by_id[first_night.id].remaining_due == Decimal("75.00")
    assert charge_by_id[second_night.id].paid_amount == Decimal("150.00")
    assert charge_by_id[second_night.id].remaining_due == Decimal("0.00")

    payment_summary = get_reservation_financial_summary(db, 1, reservation.id)
    source_summary = next(row for row in payment_summary["transactions"] if row["id"] == source.id)
    assert source_summary["company_night_charge_refundable_allocations"] == [
        {"charge_id": second_night.id, "stay_date": second_night.stay_date, "remaining_amount": Decimal("150.00")},
    ]

    with pytest.raises(PaymentError, match="no pertenece al pago original"):
        process_payment(
            db,
            refund_request.model_copy(
                update={
                    "company_night_charge_refund_allocations": [
                        {"charge_id": outside_night.id, "amount": Decimal("75.00")}
                    ]
                }
            ),
            hotel_id=1,
            idempotency_key="company-night-refund-invalid-night",
        )
    with pytest.raises(PaymentError, match="saldo disponible de 0.00"):
        process_payment(
            db,
            refund_request,
            hotel_id=1,
            idempotency_key="company-night-refund-tuesday-second",
        )

    changed_night_retry = refund_request.model_copy(
        update={
            "company_night_charge_refund_allocations": [
                {"charge_id": second_night.id, "amount": Decimal("75.00")}
            ]
        }
    )
    with pytest.raises(PaymentError, match="clave de idempotencia"):
        process_payment(
            db,
            changed_night_retry,
            hotel_id=1,
            idempotency_key="company-night-refund-tuesday",
        )


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
