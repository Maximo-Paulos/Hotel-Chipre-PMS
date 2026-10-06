"""Company-only nightly extras and payment allocations."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_night_charge import (
    CompanyNightCharge,
    CompanyNightChargeAmountAdjustment,
    CompanyNightChargePaymentAllocation,
    CompanyNightlySurchargeRate,
)
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.company_night_charge import (
    CompanyNightChargeAmountAdjustmentRead,
    CompanyNightChargeRead,
    CompanyNightChargesSummaryRead,
)
from app.services.timezones import hotel_today
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.services.row_locks import lock_query


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
        query = lock_query(query, Reservation)
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


def _rate_for_date(
    db: Session,
    *,
    hotel_id: int,
    company_id: int,
    stay_date: date,
) -> CompanyNightlySurchargeRate | None:
    return (
        db.query(CompanyNightlySurchargeRate)
        .filter(
            CompanyNightlySurchargeRate.hotel_id == hotel_id,
            CompanyNightlySurchargeRate.company_id == company_id,
            CompanyNightlySurchargeRate.effective_from <= stay_date,
        )
        .order_by(
            CompanyNightlySurchargeRate.effective_from.desc(),
            CompanyNightlySurchargeRate.id.desc(),
        )
        .first()
    )


def list_company_nightly_surcharge_rates(
    db: Session,
    *,
    hotel_id: int,
    company_id: int,
) -> list[CompanyNightlySurchargeRate]:
    _company(db, hotel_id=hotel_id, company_id=company_id)
    return (
        db.query(CompanyNightlySurchargeRate)
        .filter(
            CompanyNightlySurchargeRate.hotel_id == hotel_id,
            CompanyNightlySurchargeRate.company_id == company_id,
        )
        .order_by(
            CompanyNightlySurchargeRate.effective_from.desc(),
            CompanyNightlySurchargeRate.id.desc(),
        )
        .all()
    )


def create_company_nightly_surcharge_rate(
    db: Session,
    *,
    hotel_id: int,
    company_id: int,
    effective_from: date,
    amount: Decimal,
    actor_user_id: int | None,
) -> CompanyNightlySurchargeRate:
    company = _company(db, hotel_id=hotel_id, company_id=company_id, lock=True)
    effective_today = hotel_today(db, hotel_id)
    if effective_from < effective_today:
        raise CompanyNightChargeError("La nueva tarifa debe regir desde hoy o una fecha futura.")
    normalized_amount = Decimal(str(amount)).quantize(CENT, rounding=ROUND_HALF_UP)
    if normalized_amount < 0:
        raise CompanyNightChargeError("La tarifa no puede ser negativa.")
    existing = (
        db.query(CompanyNightlySurchargeRate)
        .filter(
            CompanyNightlySurchargeRate.hotel_id == hotel_id,
            CompanyNightlySurchargeRate.company_id == company_id,
            CompanyNightlySurchargeRate.effective_from == effective_from,
        )
        .order_by(CompanyNightlySurchargeRate.id.desc())
        .with_for_update()
        .first()
    )
    if existing is not None and Decimal(str(existing.amount)).quantize(CENT) == normalized_amount:
        return existing
    rate = CompanyNightlySurchargeRate(
        hotel_id=hotel_id,
        company_id=company_id,
        effective_from=effective_from,
        amount=normalized_amount,
        created_by_user_id=actor_user_id,
    )
    db.add(rate)
    db.flush()
    if effective_from <= effective_today:
        # Retain the legacy summary field as a current-rate projection for
        # older clients. The history table remains the pricing authority.
        company.extra_person_nightly_surcharge = normalized_amount
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action="company_nightly_rate.created",
            resource_type="company",
            resource_id=str(company_id),
            details=json.dumps(
                {
                    "rate_id": rate.id,
                    "effective_from": effective_from.isoformat(),
                    "amount": f"{normalized_amount:.2f}",
                },
                separators=(",", ":"),
            ),
        )
    )
    db.flush()
    return rate


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
        refund_rows = (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == hotel_id,
                Transaction.refund_of_transaction_id.in_(tx_ids),
                Transaction.transaction_type == TransactionTypeEnum.REFUND,
                Transaction.status == TransactionStatusEnum.COMPLETED,
            )
            .all()
        )
        refund_ids = [row.id for row in refund_rows]
        explicitly_allocated_refund_ids = {
            transaction_id
            for (transaction_id,) in db.query(CompanyNightChargePaymentAllocation.transaction_id)
            .filter(
                CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
                CompanyNightChargePaymentAllocation.transaction_id.in_(refund_ids),
            )
            .distinct()
            .all()
        } if refund_ids else set()
        for refund in refund_rows:
            if refund.id not in explicitly_allocated_refund_ids:
                source_id = int(refund.refund_of_transaction_id)
                refunds[source_id] = refunds.get(source_id, Decimal("0.00")) + Decimal(str(refund.amount or 0))

    paid: dict[int, Decimal] = {}
    pending: set[int] = set()
    for allocation, transaction in allocations:
        charge_id = allocation.company_night_charge_id
        if transaction.status == TransactionStatusEnum.PENDING:
            pending.add(charge_id)
            continue
        if transaction.status != TransactionStatusEnum.COMPLETED:
            continue
        allocated_amount = Decimal(str(allocation.amount or 0))
        if transaction.transaction_type == TransactionTypeEnum.REFUND:
            paid[charge_id] = paid.get(charge_id, Decimal("0.00")) - allocated_amount
            continue
        transaction_amount = Decimal(str(transaction.amount or 0))
        refunded = min(refunds.get(transaction.id, Decimal("0.00")), transaction_amount)
        refund_fraction = refunded / transaction_amount if transaction_amount > 0 else Decimal("0")
        net_allocation = allocated_amount * (Decimal("1") - refund_fraction)
        paid[charge_id] = paid.get(charge_id, Decimal("0.00")) + net_allocation

    return {key: value.quantize(CENT, rounding=ROUND_HALF_UP) for key, value in paid.items()}, pending


def prepare_company_night_charge_refund(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    source_transaction: Transaction,
    amount: Decimal,
    refund_allocations: list[object],
) -> list[dict[str, object]] | None:
    """Validate explicit refund amounts against the source payment's night allocations.

    Returns ``None`` for an ordinary payment with no company-night allocations.
    Amounts are applied amounts in reservation currency; tender conversion is
    performed by the payment service using the original transaction snapshot.
    """
    source_rows = (
        db.query(CompanyNightChargePaymentAllocation, CompanyNightCharge)
        .join(
            CompanyNightCharge,
            (CompanyNightCharge.id == CompanyNightChargePaymentAllocation.company_night_charge_id)
            & (CompanyNightCharge.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightChargePaymentAllocation.transaction_id == source_transaction.id,
            CompanyNightCharge.hotel_id == hotel_id,
            CompanyNightCharge.reservation_id == reservation_id,
        )
        .with_for_update()
        .all()
    )
    if not source_rows:
        if refund_allocations:
            raise CompanyNightChargeError("El pago original no contiene adicionales por noche para devolver.")
        return None

    source_by_charge = {
        int(allocation.company_night_charge_id): Decimal(str(allocation.amount or 0)).quantize(CENT)
        for allocation, _charge in source_rows
    }
    source_amount = Decimal(str(source_transaction.amount or 0)).quantize(CENT)
    if sum(source_by_charge.values(), Decimal("0.00")).quantize(CENT) != source_amount:
        raise CompanyNightChargeError("El pago original no tiene una asignación completa y válida por noche.")
    if not refund_allocations:
        raise CompanyNightChargeError("Seleccioná la noche empresarial a la que corresponde la devolución.")

    requested: dict[int, Decimal] = {}
    for item in refund_allocations:
        charge_id = int(getattr(item, "charge_id", item.get("charge_id") if isinstance(item, dict) else 0))
        raw_amount = getattr(item, "amount", item.get("amount") if isinstance(item, dict) else None)
        requested[charge_id] = Decimal(str(raw_amount)).quantize(CENT)
    requested_total = sum(requested.values(), Decimal("0.00")).quantize(CENT)
    if abs(requested_total - amount.quantize(CENT)) > CENT:
        raise CompanyNightChargeError(
            "La suma asignada a las noches debe coincidir con el importe aplicado de la devolución."
        )
    if any(charge_id not in source_by_charge for charge_id in requested):
        raise CompanyNightChargeError("La noche seleccionada no pertenece al pago original.")

    completed_refunds = (
        db.query(Transaction)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation_id,
            Transaction.refund_of_transaction_id == source_transaction.id,
            Transaction.transaction_type == TransactionTypeEnum.REFUND,
            Transaction.status == TransactionStatusEnum.COMPLETED,
        )
        .with_for_update()
        .all()
    )
    refund_ids = [row.id for row in completed_refunds]
    prior_refund_allocations = (
        db.query(CompanyNightChargePaymentAllocation)
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightChargePaymentAllocation.transaction_id.in_(refund_ids),
        )
        .all()
        if refund_ids
        else []
    )
    explicitly_allocated_refund_ids = {row.transaction_id for row in prior_refund_allocations}
    refunded_by_charge: dict[int, Decimal] = {}
    for allocation in prior_refund_allocations:
        refunded_by_charge[allocation.company_night_charge_id] = (
            refunded_by_charge.get(allocation.company_night_charge_id, Decimal("0.00"))
            + Decimal(str(allocation.amount or 0))
        )
    legacy_refund_amount = sum(
        (
            Decimal(str(row.amount or 0))
            for row in completed_refunds
            if row.id not in explicitly_allocated_refund_ids
        ),
        Decimal("0.00"),
    ).quantize(CENT)
    legacy_ratio = min(Decimal("1"), legacy_refund_amount / source_amount) if source_amount > 0 else Decimal("0")

    for charge_id, requested_amount in requested.items():
        original_amount = source_by_charge[charge_id]
        legacy_refund_for_charge = (original_amount * legacy_ratio).quantize(CENT, rounding=ROUND_HALF_UP)
        remaining = max(
            Decimal("0.00"),
            original_amount - refunded_by_charge.get(charge_id, Decimal("0.00")) - legacy_refund_for_charge,
        ).quantize(CENT)
        if requested_amount > remaining:
            raise CompanyNightChargeError(
                f"La devolución para la noche {charge_id} supera el saldo disponible de {remaining:.2f}."
            )

    return [
        {"charge_id": charge_id, "amount": requested_amount}
        for charge_id, requested_amount in sorted(requested.items())
    ]


def record_company_night_charge_refund_allocations(
    db: Session,
    *,
    hotel_id: int,
    transaction: Transaction,
    allocation_plan: list[dict[str, object]],
) -> None:
    for item in allocation_plan:
        db.add(
            CompanyNightChargePaymentAllocation(
                hotel_id=hotel_id,
                transaction_id=transaction.id,
                company_night_charge_id=int(item["charge_id"]),
                amount=Decimal(str(item["amount"])).quantize(CENT),
            )
        )
    db.flush()


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
    adjustment_rows = (
        db.query(CompanyNightChargeAmountAdjustment)
        .filter(
            CompanyNightChargeAmountAdjustment.hotel_id == hotel_id,
            CompanyNightChargeAmountAdjustment.company_night_charge_id.in_([row.id for row in rows]),
        )
        .order_by(
            CompanyNightChargeAmountAdjustment.company_night_charge_id.asc(),
            CompanyNightChargeAmountAdjustment.created_at.asc(),
            CompanyNightChargeAmountAdjustment.id.asc(),
        )
        .all()
        if rows
        else []
    )
    adjustments_by_charge: dict[int, list[CompanyNightChargeAmountAdjustmentRead]] = {}
    for adjustment in adjustment_rows:
        adjustments_by_charge.setdefault(adjustment.company_night_charge_id, []).append(
            CompanyNightChargeAmountAdjustmentRead(
                id=adjustment.id,
                previous_amount=Decimal(str(adjustment.previous_amount)).quantize(CENT),
                new_amount=Decimal(str(adjustment.new_amount)).quantize(CENT),
                delta_amount=Decimal(str(adjustment.delta_amount)).quantize(CENT),
                reason=adjustment.reason,
                created_by_user_id=adjustment.created_by_user_id,
                created_at=adjustment.created_at,
            )
        )
    paid_by_id, pending_ids = _paid_and_pending_by_charge(
        db, hotel_id=hotel_id, charge_ids=[row.id for row in rows]
    )
    today = hotel_today(db, hotel_id)
    current_rate = _rate_for_date(db, hotel_id=hotel_id, company_id=company.id, stay_date=today)
    charges = []
    for row in rows:
        amount = Decimal(str(row.amount)).quantize(CENT)
        paid = paid_by_id.get(row.id, Decimal("0.00")).quantize(CENT)
        remaining = max(Decimal("0.00"), amount - paid).quantize(CENT)
        unit_amount = (
            Decimal(str(row.unit_amount)).quantize(CENT)
            if row.unit_amount is not None and Decimal(str(row.unit_amount)) > 0
            else (amount / Decimal(max(1, int(row.quantity or 1)))).quantize(CENT, rounding=ROUND_HALF_UP)
        )
        charges.append(
            CompanyNightChargeRead(
                id=row.id,
                stay_date=row.stay_date,
                amount=amount,
                unit_amount=unit_amount,
                quantity=int(row.quantity or 1),
                rate_effective_from=row.rate_effective_from,
                currency_code=row.currency_code,
                paid_amount=paid,
                remaining_due=remaining,
                payment_pending=row.id in pending_ids,
                review_only=row.stay_date < today and remaining > 0,
                adjustments=adjustments_by_charge.get(row.id, []),
            )
        )
    return CompanyNightChargesSummaryRead(
        reservation_id=reservation.id,
        company_id=company.id,
        currency_code=(reservation.currency_code or "ARS").upper(),
        nightly_surcharge_amount=(
            Decimal(str(current_rate.amount)).quantize(CENT)
            if current_rate is not None
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
    extra_person_count: int = 1,
) -> CompanyNightChargesSummaryRead:
    reservation = _reservation(db, hotel_id=hotel_id, reservation_id=reservation_id, lock=True)
    company = _company(db, hotel_id=hotel_id, company_id=reservation.company_id, lock=True)
    if reservation.status in {
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.NO_SHOW,
    }:
        raise CompanyNightChargeError("No se pueden crear adicionales para una reserva cerrada o cancelada.")
    if len(stay_dates) > 90:
        raise CompanyNightChargeError("Podés seleccionar hasta 90 noches por vez.")
    if extra_person_count <= 0 or extra_person_count > 99:
        raise CompanyNightChargeError("La cantidad de huéspedes extra debe estar entre 1 y 99.")
    contracted_guest_count = max(
        1,
        int(reservation.num_adults or 0) + int(reservation.num_children or 0),
    )
    linked_additional_guest_ids = {
        guest.id for guest in (reservation.additional_guests or ()) if guest.id is not None
    }
    actual_guest_count = max(contracted_guest_count, 1 + len(linked_additional_guest_ids))
    billable_extra_people = max(0, actual_guest_count - contracted_guest_count)
    if extra_person_count > billable_extra_people:
        raise CompanyNightChargeError(
            "La cantidad cobrada supera las personas registradas por encima de la ocupación contratada."
        )
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
        rate = _rate_for_date(
            db,
            hotel_id=hotel_id,
            company_id=company.id,
            stay_date=stay_date,
        )
        if rate is None:
            raise CompanyNightChargeError(
                f"No hay una tarifa por persona extra vigente para la noche {stay_date.isoformat()}."
            )
        unit_amount = Decimal(str(rate.amount)).quantize(CENT)
        if unit_amount <= 0:
            raise CompanyNightChargeError(
                f"La tarifa vigente no genera un adicional para la noche {stay_date.isoformat()}."
            )
        amount = (unit_amount * Decimal(extra_person_count)).quantize(CENT, rounding=ROUND_HALF_UP)
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
            unit_amount=unit_amount,
            quantity=extra_person_count,
            rate_id=rate.id,
            rate_effective_from=rate.effective_from,
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


def correct_company_night_charge_amounts(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    items: list[dict[str, object]],
    actor_user_id: int | None,
) -> CompanyNightChargesSummaryRead:
    """Correct explicitly selected night totals while retaining payment rows.

    The current charge and linked billing adjustment are updated so existing
    read/report paths see the corrected value. An append-only record captures
    previous/new/delta and reason; allocations and transactions are untouched.
    """
    reservation = _reservation(db, hotel_id=hotel_id, reservation_id=reservation_id, lock=True)
    normalized: dict[int, tuple[Decimal, str]] = {}
    for item in items:
        charge_id = int(item["charge_id"])
        amount = Decimal(str(item["new_amount"])).quantize(CENT, rounding=ROUND_HALF_UP)
        reason = str(item["reason"]).strip()
        if amount <= 0:
            raise CompanyNightChargeError("El importe corregido debe ser positivo.")
        if not reason:
            raise CompanyNightChargeError("Indicá el motivo de cada corrección.")
        normalized[charge_id] = (amount, reason)
    if not normalized:
        raise CompanyNightChargeError("Seleccioná al menos una noche para corregir.")
    if len(normalized) > 90:
        raise CompanyNightChargeError("Podés corregir hasta 90 noches por vez.")

    charges = (
        db.query(CompanyNightCharge)
        .filter(
            CompanyNightCharge.hotel_id == hotel_id,
            CompanyNightCharge.reservation_id == reservation_id,
            CompanyNightCharge.id.in_(normalized),
        )
        .with_for_update()
        .all()
    )
    if len(charges) != len(normalized):
        raise CompanyNightChargeError("La selección incluye un cargo que no pertenece a esta reserva.")
    changed_any = False
    adjustments: list[CompanyNightChargeAmountAdjustment] = []
    for charge in sorted(charges, key=lambda row: (row.stay_date, row.id)):
        new_amount, reason = normalized[charge.id]
        previous_amount = Decimal(str(charge.amount)).quantize(CENT)
        delta_amount = (new_amount - previous_amount).quantize(CENT)
        if delta_amount == 0:
            continue
        billing_adjustment = (
            lock_query(db.query(BillingAdjustment), BillingAdjustment)
            .filter(
                BillingAdjustment.hotel_id == hotel_id,
                BillingAdjustment.id == charge.billing_adjustment_id,
                BillingAdjustment.reservation_id == reservation_id,
            )
            .one_or_none()
        )
        if billing_adjustment is None:
            raise CompanyNightChargeError("No se encontró el ajuste contable asociado al adicional.")
        record = CompanyNightChargeAmountAdjustment(
            hotel_id=hotel_id,
            company_night_charge_id=charge.id,
            previous_amount=previous_amount,
            new_amount=new_amount,
            delta_amount=delta_amount,
            reason=reason,
            created_by_user_id=actor_user_id,
        )
        db.add(record)
        charge.amount = new_amount
        billing_adjustment.amount = new_amount
        billing_adjustment.total_amount = new_amount
        db.flush()
        adjustments.append(record)
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=actor_user_id,
                action="company_night_charge.amount_corrected",
                resource_type="reservation",
                resource_id=str(reservation_id),
                details=json.dumps(
                    {
                        "company_id": charge.company_id,
                        "charge_id": charge.id,
                        "stay_date": charge.stay_date.isoformat(),
                        "previous_amount": f"{previous_amount:.2f}",
                        "new_amount": f"{new_amount:.2f}",
                        "delta_amount": f"{delta_amount:.2f}",
                        "reason": reason,
                    },
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            )
        )
        changed_any = True
    if not changed_any:
        raise CompanyNightChargeError("Los importes seleccionados ya coinciden con los valores actuales.")

    from app.services.payment_service import sync_reservation_financial_status

    sync_reservation_financial_status(
        db,
        reservation,
        hotel_id=hotel_id,
        reason_code="company_night_charge_amount_corrected",
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
