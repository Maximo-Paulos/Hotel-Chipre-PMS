from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.api import reports as reports_api
from app.api import reservations as reservations_api
from app.dependencies.auth import AuthContext
from app.models.analytics import FactReservationDaily
from app.models.company import Company
from app.models.company_night_charge import CompanyNightCharge, CompanyNightChargePaymentAllocation
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.reservation_group import ReservationGroup
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.schemas.reservation_operations import ReservationFinancialSummaryRead
from app.services.analytics_facts import refresh_fact_reservation_daily
from app.services.operational_report_service import company_night_extra_balances_by_reservation
from app.services.payment_service import get_reservation_financial_summary
from app.services.reservation_group_service import list_reservation_groups
from app.services.reservation_service import ReservationError, create_reservation, update_reservation_fields


def _legacy_deferred_reservation(db, sample_guest, sample_categories, sample_rooms, hotel_config):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Empresa diferida SA",
        display_name="Empresa diferida",
        payment_deferred=True,
        deferred_days=30,
    )
    db.add(company)
    db.flush()
    today = date.today()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=today,
            check_out_date=today + timedelta(days=1),
            company_id=company.id,
        ),
        hotel_id=hotel_config.id,
    )
    # Reproduce a legacy row whose base lodging amount was stored before the
    # deferred-company policy was applied. The company flag has since changed.
    company.payment_deferred = False
    reservation.settlement_status = "settled"
    reservation.total_amount = Decimal("15000.00")
    reservation.amount_paid = Decimal("500.00")
    reservation.external_paid_amount = Decimal("250.00")
    reservation.external_paid_reference = "external-invoice-reference"
    reservation.external_paid_confirmed = True
    reservation.deposit_amount = Decimal("4500.00")
    reservation.subtotal_amount = Decimal("14000.00")
    reservation.tax_amount = Decimal("1000.00")
    reservation.fee_amount = Decimal("300.00")
    reservation.commission_amount = Decimal("400.00")
    reservation.net_amount = Decimal("14300.00")
    reservation.quoted_amount_ars = Decimal("15000.00")
    reservation.quoted_amount_usd = Decimal("15.00")
    reservation.status = ReservationStatusEnum.CHECKED_IN
    db.flush()
    return company, reservation


def _payment(
    db,
    *,
    hotel_id: int,
    reservation_id: int,
    amount: Decimal,
    transaction_type: TransactionTypeEnum = TransactionTypeEnum.PARTIAL_PAYMENT,
    status: TransactionStatusEnum = TransactionStatusEnum.COMPLETED,
) -> Transaction:
    transaction = Transaction(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency="ARS",
        transaction_type=transaction_type,
        payment_method=PaymentMethodEnum.CASH,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_deferred_reservation_read_and_list_mask_legacy_lodging_money(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    context = AuthContext(hotel_id=hotel_config.id, user_id=1, user_role="owner", is_verified=True)

    detail = reservations_api.get_reservation(reservation.id, db=db, context=context)
    listed = reservations_api.list_reservations(
        status_filter="",
        from_date=None,
        to_date=None,
        search="",
        skip=0,
        limit=50,
        order="recent",
        upcoming_only=False,
        company_id=company.id,
        db=db,
        context=context,
    )[0]

    for read in (detail, listed):
        assert read.company_billing_deferred is True
        assert read.total_amount is None
        assert read.amount_paid is None
        assert read.external_paid_amount is None
        assert read.external_paid_reference is None
        assert read.external_paid_confirmed is False
        assert read.deposit_amount is None
        assert read.subtotal_amount is None
        assert read.tax_amount is None
        assert read.fee_amount is None
        assert read.commission_amount is None
        assert read.net_amount is None
        assert read.quoted_amount_ars is None
        assert read.quoted_amount_usd is None
        assert read.balance_due is None

    db.refresh(reservation)
    assert reservation.total_amount == Decimal("15000.00")
    assert reservation.amount_paid == Decimal("500.00")


def test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    base_payment = _payment(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        amount=Decimal("500.00"),
    )
    adjustment = BillingAdjustment(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=Decimal("1200.00"),
        currency_code="ARS",
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1200.00"),
        effective_at=datetime.now(timezone.utc),
        notes="Adicional corporativo por noche",
    )
    db.add(adjustment)
    db.flush()
    night_charge = CompanyNightCharge(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        company_id=company.id,
        billing_adjustment_id=adjustment.id,
        stay_date=reservation.check_in_date,
        amount=Decimal("1200.00"),
        currency_code="ARS",
    )
    db.add(night_charge)
    db.flush()
    extra_payment = _payment(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        amount=Decimal("1200.00"),
    )
    db.add(
        CompanyNightChargePaymentAllocation(
            hotel_id=hotel_config.id,
            transaction_id=extra_payment.id,
            company_night_charge_id=night_charge.id,
            amount=Decimal("1200.00"),
        )
    )
    db.flush()

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    validated = ReservationFinancialSummaryRead.model_validate(summary)

    assert validated.company_billing_deferred is True
    assert validated.total_amount is None
    assert validated.deposit_required is None
    assert validated.amount_paid is None
    assert validated.balance_due is None
    assert validated.financial_reconciliation_gap is None
    assert validated.operational_total_amount == Decimal("1200.00")
    assert validated.operational_balance_due == Decimal("0.00")
    assert validated.billing_adjustment_total == Decimal("1200.00")
    assert [tx.id for tx in validated.transactions] == [extra_payment.id]
    assert [item.id for item in validated.billing_adjustments] == [adjustment.id]
    assert all(tx.id != base_payment.id for tx in validated.transactions)
    # The ledger remains complete even though the summary projection masks
    # legacy lodging receipts.
    assert db.query(Transaction).filter_by(id=base_payment.id).one().amount == Decimal("500.00")


def test_pending_company_night_extra_remains_due_until_payment_completes(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    adjustment = BillingAdjustment(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=Decimal("1200.00"),
        currency_code="ARS",
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1200.00"),
        effective_at=datetime.now(timezone.utc),
        notes="Adicional corporativo por noche",
    )
    db.add(adjustment)
    db.flush()
    night_charge = CompanyNightCharge(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        company_id=company.id,
        billing_adjustment_id=adjustment.id,
        stay_date=reservation.check_in_date,
        amount=Decimal("1200.00"),
        currency_code="ARS",
    )
    db.add(night_charge)
    db.flush()
    pending_payment = _payment(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        amount=Decimal("1200.00"),
        status=TransactionStatusEnum.PENDING,
    )
    db.add(
        CompanyNightChargePaymentAllocation(
            hotel_id=hotel_config.id,
            transaction_id=pending_payment.id,
            company_night_charge_id=night_charge.id,
            amount=Decimal("1200.00"),
        )
    )
    db.flush()

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    _, due_by_reservation = company_night_extra_balances_by_reservation(
        db,
        hotel_id=hotel_config.id,
        reservation_ids={reservation.id},
        stay_date_from=reservation.check_in_date,
        stay_date_to=reservation.check_in_date,
    )

    assert summary["company_billing_deferred"] is True
    assert summary["operational_total_amount"] == Decimal("1200.00")
    assert summary["operational_balance_due"] == Decimal("1200.00")
    assert summary["completed_payments"] == Decimal("0.00")
    assert [item["id"] for item in summary["transactions"]] == [pending_payment.id]
    assert due_by_reservation == {reservation.id: Decimal("1200.00")}


def test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    base_payment = _payment(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        amount=Decimal("500.00"),
    )
    adjustment = BillingAdjustment(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=Decimal("1200.00"),
        currency_code="ARS",
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1200.00"),
        effective_at=datetime.now(timezone.utc),
        notes="Adicional corporativo por noche",
    )
    db.add(adjustment)
    db.flush()
    night_charge = CompanyNightCharge(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        company_id=company.id,
        billing_adjustment_id=adjustment.id,
        stay_date=reservation.check_in_date,
        amount=Decimal("1200.00"),
        currency_code="ARS",
    )
    db.add(night_charge)
    db.flush()
    extra_payment = _payment(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        amount=Decimal("1200.00"),
    )
    db.add(
        CompanyNightChargePaymentAllocation(
            hotel_id=hotel_config.id,
            transaction_id=extra_payment.id,
            company_night_charge_id=night_charge.id,
            amount=Decimal("1200.00"),
        )
    )
    db.flush()
    context = AuthContext(hotel_id=hotel_config.id, user_id=1, user_role="owner", is_verified=True)

    daily = reports_api.daily_report(
        report_date=reservation.check_in_date,
        db=db,
        context=context,
    )
    revenue = reports_api.revenue_report(
        start_date=reservation.check_in_date,
        end_date=reservation.check_in_date,
        db=db,
        context=context,
    )

    arrival = daily["arrivals"]["reservations"][0]
    assert daily["occupancy"]["occupied"] == 1
    assert arrival["company_billing_deferred"] is True
    assert arrival["total_amount"] is None
    assert arrival["balance_due"] is None
    assert arrival["company_night_extra_due"] == 0
    assert daily["revenue"]["total"] == 1200
    assert daily["pending_payments"]["total_balance"] == 0
    assert revenue["expected"]["total"] == 1200
    assert revenue["expected"]["pending"] == 0
    assert revenue["collected"]["total"] == 1200
    # Reporting masks the base amount but never deletes the historical ledger row.
    assert db.query(Transaction).filter_by(id=base_payment.id).one().amount == Decimal("500.00")


def test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    _company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=reservation.check_in_date,
        date_to=reservation.check_in_date,
    )
    fact = db.query(FactReservationDaily).filter_by(reservation_id=reservation.id).one()

    assert fact.occupied_night is True
    assert fact.chargeable_night is False
    assert fact.revenue_gross_ars == Decimal("0.00")
    assert fact.revenue_net_ars == Decimal("0.00")


def test_deferred_reservation_group_masks_legacy_group_total(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    group = ReservationGroup(
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        company_id=company.id,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
    )
    db.add(group)
    db.flush()
    reservation.group_id = group.id
    db.flush()

    result = list_reservation_groups(db, hotel_id=hotel_config.id, group_id=group.id)[0]

    assert result["company_billing_deferred"] is True
    assert result["total_amount"] is None
    assert result["amount_paid"] is None
    assert result["balance_due"] is None
    assert result["reservation_count"] == 1


def test_paid_total_adjustment_cannot_restore_a_deferred_lodging_amount(
    db, sample_guest, sample_categories, sample_rooms, hotel_config
):
    _company, reservation = _legacy_deferred_reservation(
        db, sample_guest, sample_categories, sample_rooms, hotel_config
    )
    with pytest.raises(ReservationError, match="se factura fuera del PMS"):
        update_reservation_fields(
            db,
            reservation,
            ReservationUpdate(
                total_amount=Decimal("20000.00"),
                paid_total_change_reason="corrección de reserva antigua",
            ),
            hotel_id=hotel_config.id,
        )

    assert reservation.total_amount == Decimal("15000.00")
