"""Company-only nightly extras and payment allocations."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_night_charge import CompanyNightCharge, CompanyNightChargePaymentAllocation
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation
from app.models.security_audit_log import SecurityAuditLog
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.company_night_charge import CompanyNightChargeRead, CompanyNightChargesSummaryRead
from app.services.timezones import hotel_today
from app.services.financial_ledger import paid_amount_with_legacy_fallback


CENT = Decimal("0.01")


class CompanyNightChargeError(ValueError):
    """Raised when a corporate nightly extra is invalid or unavailable."""


def _reservation(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    lock: bool = False,
    require_company: bool = True,
) -> Reservation:
    query = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.hotel_id == hotel_id,
        Reservation.deleted_at.is_(None),
    )
    if lock:
        query = query.with_for_update()
    reservation = query.one_or_none()
    if reservation is None:
        raise CompanyNightChargeError("La reserva no pertenece a este hotel.")
    if require_company and reservation.company_id is None:
        raise CompanyNightChargeError("Los adicionales por noche solo se usan en reservas de empresas.")
    return reservation


def _company(db: Session, *, hotel_id: int, company_id: int, lock: bool = False) -> Company:
    query = db.query(Company).filter(Company.hotel_id == hotel_id, Company.id == company_id)
    if lock:
        query = query.with_for_update()
    company = query.one_or_none()
    if company is None:
        raise CompanyNightChargeError("La empresa vinculada a la reserva no está disponible.")
    return company


def _paid_and_pending_by_charge(db: Session, *, hotel_id: int, charge_ids: list[int]) -> tuple[dict[int, Decimal], set[int]]:
    if not charge_ids:
        return {}, set()
    allocations = (
        db.query(CompanyNightChargePaymentAllocation, Transaction)
        .join(
            Transaction,
            (Transaction.id == CompanyNightChargePaymentAllocation.transaction_id)
            & (Transaction.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightChargePaymentAllocation.company_night_charge_id.in_(charge_ids),
        )
        .all()
    )
    tx_ids = [tx.id for _allocation, tx in allocations if tx.transaction_type != TransactionTypeEnum.REFUND]
    refunds: dict[int, Decimal] = {}
    if tx_ids:
        for tx_id, total in (
            db.query(Transaction.refund_of_transaction_id, func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.hotel_id == hotel_id,
                Transaction.refund_of_transaction_id.in_(tx_ids),
                Transaction.transaction_type == TransactionTypeEnum.REFUND,
                Transaction.status == TransactionStatusEnum.COMPLETED,
            )
            .group_by(Transaction.refund_of_transaction_id)
            .all()
        ):
            refunds[int(tx_id)] = Decimal(str(total or 0))

    paid: dict[int, Decimal] = {}
    pending: set[int] = set()
    for allocation, transaction in allocations:
        charge_id = allocation.company_night_charge_id
        if transaction.status == TransactionStatusEnum.PENDING:
            pending.add(charge_id)
            continue
        if transaction.status != TransactionStatusEnum.COMPLETED or transaction.transaction_type == TransactionTypeEnum.REFUND:
            continue
        transaction_amount = Decimal(str(transaction.amount or 0))
        refunded = min(refunds.get(transaction.id, Decimal("0.00")), transaction_amount)
        refund_fraction = refunded / transaction_amount if transaction_amount > 0 else Decimal("0")
        net_allocation = Decimal(str(allocation.amount)) * (Decimal("1") - refund_fraction)
        paid[charge_id] = paid.get(charge_id, Decimal("0.00")) + net_allocation

    return {key: value.quantize(CENT, rounding=ROUND_HALF_UP) for key, value in paid.items()}, pending


def get_company_night_charges(
    db: Session, *, hotel_id: int, reservation_id: int
) -> CompanyNightChargesSummaryRead:
    reservation = _reservation(db, hotel_id=hotel_id, reservation_id=reservation_id)
    company = _company(db, hotel_id=hotel_id, company_id=reservation.company_id)
    rows = (
        db.query(CompanyNightCharge)
        .filter(CompanyNightCharge.hotel_id == hotel_id, CompanyNightCharge.reservation_id == reservation_id)
        .order_by(CompanyNightCharge.stay_date.asc(), CompanyNightCharge.id.asc())
        .all()
    )
    paid_by_id, pending_ids = _paid_and_pending_by_charge(
        db, hotel_id=hotel_id, charge_ids=[row.id for row in rows]
    )
    today = hotel_today(db, hotel_id)
    charges = []
    for row in rows:
        amount = Decimal(str(row.amount)).quantize(CENT)
        paid = min(paid_by_id.get(row.id, Decimal("0.00")), amount).quantize(CENT)
        remaining = max(Decimal("0.00"), amount - paid).quantize(CENT)
        charges.append(
            CompanyNightChargeRead(
                id=row.id,
                stay_date=row.stay_date,
                amount=amount,
                currency_code=row.currency_code,
                paid_amount=paid,
                remaining_due=remaining,
                payment_pending=row.id in pending_ids,
                review_only=row.stay_date < today and remaining > 0,
            )
        )
    return CompanyNightChargesSummaryRead(
        reservation_id=reservation.id,
        company_id=company.id,
        currency_code=(reservation.currency_code or "ARS").upper(),
        nightly_surcharge_amount=(
            Decimal(str(company.extra_person_nightly_surcharge)).quantize(CENT)
            if company.extra_person_nightly_surcharge is not None
            else None
        ),
        charges=charges,
    )


def add_company_night_charges(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    stay_dates: list[date],
    actor_user_id: int | None,
) -> CompanyNightChargesSummaryRead:
    reservation = _reservation(db, hotel_id=hotel_id, reservation_id=reservation_id, lock=True)
    company = _company(db, hotel_id=hotel_id, company_id=reservation.company_id, lock=True)
    amount = Decimal(str(company.extra_person_nightly_surcharge or 0)).quantize(CENT)
    if amount <= 0:
        raise CompanyNightChargeError("Gerencia debe configurar un adicional positivo por huésped y noche en la ficha de la empresa.")
    if len(stay_dates) > 90:
        raise CompanyNightChargeError("Podés seleccionar hasta 90 noches por vez.")
    for stay_date in stay_dates:
        if not (reservation.check_in_date <= stay_date < reservation.check_out_date):
            raise CompanyNightChargeError("Cada adicional debe corresponder a una noche de esta reserva.")

    existing = {
        row.stay_date: row
        for row in db.query(CompanyNightCharge)
        .filter(
            CompanyNightCharge.hotel_id == hotel_id,
            CompanyNightCharge.reservation_id == reservation_id,
            CompanyNightCharge.stay_date.in_(stay_dates),
        )
        .with_for_update()
        .all()
    }
    created_any = False
    for stay_date in stay_dates:
        if stay_date in existing:
            continue
        adjustment = BillingAdjustment(
            hotel_id=hotel_id,
            reservation_id=reservation_id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=amount,
            currency_code=(reservation.currency_code or "ARS").upper(),
            tax_amount=Decimal("0.00"),
            total_amount=amount,
            effective_at=datetime.combine(stay_date, time.min),
            notes=f"Adicional corporativo por huésped extra; noche {stay_date.isoformat()}",
            created_by_user_id=actor_user_id,
        )
        db.add(adjustment)
        db.flush()
        charge = CompanyNightCharge(
            hotel_id=hotel_id,
            reservation_id=reservation_id,
            company_id=company.id,
            billing_adjustment_id=adjustment.id,
            stay_date=stay_date,
            amount=amount,
            currency_code=(reservation.currency_code or "ARS").upper(),
            created_by_user_id=actor_user_id,
        )
        db.add(charge)
        db.flush()
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=actor_user_id,
                action="company_night_charge.created",
                resource_type="reservation",
                resource_id=str(reservation_id),
                details=(
                    f'{{"company_id":{company.id},"charge_id":{charge.id},'
                    f'"stay_date":"{stay_date.isoformat()}","amount":"{amount:.2f}"}}'
                ),
            )
        )
        created_any = True
    if created_any:
        # Re-evaluate a previously fully-paid booking when management adds a
        # new collectible amount. Keep status transitions in the finance
        # service so the same audit/history behavior is used for payments.
        from app.services.payment_service import sync_reservation_financial_status

        sync_reservation_financial_status(
            db,
            reservation,
            hotel_id=hotel_id,
            reason_code="company_night_charge_created",
        )
    db.flush()
    return get_company_night_charges(db, hotel_id=hotel_id, reservation_id=reservation_id)


def prepare_company_night_charge_payment(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    amount: Decimal,
    charge_ids: list[int],
    idempotency_key: str | None,
) -> list[tuple[CompanyNightCharge, Decimal]] | None:
    """Lock and validate selected per-night dues before creating a payment.

    None means this idempotency key already owns an equivalent allocation.
    An empty list means the reservation has no company night charges.
    """
    reservation = _reservation(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        lock=True,
        require_company=False,
    )
    if idempotency_key:
        existing_tx = db.query(Transaction).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation_id,
            Transaction.idempotency_key == idempotency_key,
        ).one_or_none()
        if existing_tx is not None:
            existing_ids = {
                row.company_night_charge_id
                for row in db.query(CompanyNightChargePaymentAllocation).filter(
                    CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
                    CompanyNightChargePaymentAllocation.transaction_id == existing_tx.id,
                ).all()
            }
            if existing_ids != set(charge_ids):
                raise CompanyNightChargeError("La clave de pago ya fue usada para otra selección de noches.")
            return None

    if reservation.company_id is None:
        if charge_ids:
            raise CompanyNightChargeError("Los adicionales por noche solo se usan en reservas de empresas.")
        return []

    rows = (
        db.query(CompanyNightCharge)
        .filter(CompanyNightCharge.hotel_id == hotel_id, CompanyNightCharge.reservation_id == reservation_id)
        .with_for_update()
        .all()
    )
    if not rows:
        if charge_ids:
            raise CompanyNightChargeError("La reserva no tiene noches adicionales para cobrar.")
        return []

    paid_by_id, pending_ids = _paid_and_pending_by_charge(db, hotel_id=hotel_id, charge_ids=[row.id for row in rows])
    amounts = {row.id: Decimal(str(row.amount)).quantize(CENT) for row in rows}
    due_by_id = {
        row.id: max(Decimal("0.00"), amounts[row.id] - paid_by_id.get(row.id, Decimal("0.00"))).quantize(CENT)
        for row in rows
    }
    outstanding_ids = {charge_id for charge_id, due in due_by_id.items() if due > 0}
    if not charge_ids:
        allocated_paid = sum(paid_by_id.values(), Decimal("0.00"))
        total_paid = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
        base_paid = max(Decimal("0.00"), total_paid - allocated_paid)
        base_due = max(Decimal("0.00"), Decimal(str(reservation.total_amount or 0)) - base_paid)
        if amount.quantize(CENT) <= base_due.quantize(CENT):
            return []
    if not outstanding_ids:
        if charge_ids:
            raise CompanyNightChargeError("No quedan noches adicionales pendientes de pago.")
        raise CompanyNightChargeError("El importe supera el saldo base de la empresa y no hay adicionales pendientes.")
    if not charge_ids:
        raise CompanyNightChargeError("Seleccioná las noches adicionales que se están pagando.")
    if len(set(charge_ids)) != len(charge_ids):
        raise CompanyNightChargeError("No repitas noches en un mismo pago.")
    selected_ids = set(charge_ids)
    if not selected_ids.issubset(outstanding_ids):
        raise CompanyNightChargeError("La selección incluye una noche ajena a la reserva o ya pagada.")
    today = hotel_today(db, hotel_id)
    selected_dates = {row.id: row.stay_date for row in rows}
    if any(selected_dates[charge_id] < today for charge_id in selected_ids):
        raise CompanyNightChargeError("Las noches vencidas quedan como revisión y no se cobran desde este flujo.")
    if selected_ids & pending_ids:
        raise CompanyNightChargeError("Ya hay un pago pendiente de confirmación para alguna noche seleccionada.")
    expected_amount = sum((due_by_id[item] for item in selected_ids), Decimal("0.00")).quantize(CENT)
    if amount.quantize(CENT) != expected_amount:
        raise CompanyNightChargeError(
            f"El importe debe coincidir con las noches seleccionadas: ${expected_amount:.2f}."
        )
    rows_by_id = {row.id: row for row in rows}
    return [(rows_by_id[item], due_by_id[item]) for item in sorted(selected_ids)]


def record_company_night_charge_payment_allocations(
    db: Session,
    *,
    hotel_id: int,
    transaction: Transaction,
    allocation_plan: list[tuple[CompanyNightCharge, Decimal]],
) -> None:
    # Persist the selected nights for failed attempts too. The summary ignores
    # failed transactions, but retaining the intent lets an idempotent retry
    # prove that it is replaying the same request rather than reallocating it.
    if transaction.status not in {
        TransactionStatusEnum.PENDING,
        TransactionStatusEnum.COMPLETED,
        TransactionStatusEnum.FAILED,
    }:
        return
    existing = db.query(CompanyNightChargePaymentAllocation).filter(
        CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
        CompanyNightChargePaymentAllocation.transaction_id == transaction.id,
    ).all()
    expected = {charge.id: amount.quantize(CENT) for charge, amount in allocation_plan}
    if existing:
        recorded = {row.company_night_charge_id: Decimal(str(row.amount)).quantize(CENT) for row in existing}
        if recorded != expected:
            raise CompanyNightChargeError("El pago ya tiene una asignación distinta de noches corporativas.")
        return
    for charge, amount in allocation_plan:
        db.add(
            CompanyNightChargePaymentAllocation(
                hotel_id=hotel_id,
                transaction_id=transaction.id,
                company_night_charge_id=charge.id,
                amount=amount.quantize(CENT),
            )
        )
    db.flush()
