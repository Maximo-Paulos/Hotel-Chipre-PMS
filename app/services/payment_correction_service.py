"""Atomic, manager-approved correction of manually recorded payments."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.cash_register import (
    CashMovement,
    CashSession,
    CashSessionStatusEnum,
)
from app.models.company_night_charge import CompanyNightChargePaymentAllocation
from app.models.payment_correction import PaymentCorrection
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.services import audit_log_service
from app.services.financial_ledger import (
    operational_balance_due,
    paid_amount_with_legacy_fallback,
)
from app.services.payment_service import (
    PaymentNotFoundError,
    _update_reservation_financials,
)
from app.services.reservation_service import reservation_has_deferred_company_billing


class PaymentCorrectionError(ValueError):
    """The requested correction conflicts with the existing payment ledger."""


class PaymentCorrectionNotFound(PaymentNotFoundError):
    """The payment or target reservation is outside the current hotel."""


class PaymentCorrectionConflict(PaymentCorrectionError):
    """The correction was already applied or the idempotency key was reused."""


@dataclass(frozen=True)
class PaymentCorrectionOutcome:
    correction: PaymentCorrection
    replayed: bool


_CORRECTABLE_METHODS = frozenset(
    {
        PaymentMethodEnum.CASH,
        PaymentMethodEnum.CREDIT_CARD,
        PaymentMethodEnum.DEBIT_CARD,
        PaymentMethodEnum.BANK_TRANSFER,
    }
)
_TERMINAL_RESERVATION_STATES = frozenset(
    {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT}
)


def _request_matches(
    correction: PaymentCorrection,
    *,
    source_transaction_id: int,
    correction_type: str,
    target_reservation_id: int | None,
    reason: str,
) -> bool:
    return (
        correction.source_transaction_id == source_transaction_id
        and correction.correction_type == correction_type
        and correction.target_reservation_id == target_reservation_id
        and correction.reason == reason
    )


def _find_idempotent_replay(
    db: Session,
    *,
    hotel_id: int,
    idempotency_key: str,
    source_transaction_id: int,
    correction_type: str,
    target_reservation_id: int | None,
    reason: str,
) -> PaymentCorrectionOutcome | None:
    correction = (
        db.query(PaymentCorrection)
        .filter(
            PaymentCorrection.hotel_id == hotel_id,
            PaymentCorrection.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if correction is None:
        return None
    if not _request_matches(
        correction,
        source_transaction_id=source_transaction_id,
        correction_type=correction_type,
        target_reservation_id=target_reservation_id,
        reason=reason,
    ):
        raise PaymentCorrectionConflict(
            "La clave de idempotencia ya se usó para otra corrección."
        )
    return PaymentCorrectionOutcome(correction=correction, replayed=True)


def correct_payment(
    db: Session,
    *,
    hotel_id: int,
    source_transaction_id: int,
    correction_type: str,
    target_reservation_id: int | None,
    reason: str,
    idempotency_key: str,
    actor_user_id: int,
) -> PaymentCorrectionOutcome:
    """Reverse a wrong/duplicate entry and optionally reassign it atomically.

    This is an internal ledger correction. It never invokes a payment provider
    and never records a refund or a second physical cash movement.
    """
    reason = " ".join((reason or "").split())
    idempotency_key = (idempotency_key or "").strip()
    if correction_type not in {"reassign", "duplicate_reversal"}:
        raise PaymentCorrectionError("El tipo de corrección no es válido.")
    if not reason or len(reason) > 240:
        raise PaymentCorrectionError("Ingresá un motivo de hasta 240 caracteres.")
    if len(idempotency_key) < 8 or len(idempotency_key) > 100:
        raise PaymentCorrectionError("La clave de idempotencia debe tener entre 8 y 100 caracteres.")
    if (correction_type == "reassign") != (target_reservation_id is not None):
        raise PaymentCorrectionError("La corrección no coincide con la reserva de destino.")

    replay = _find_idempotent_replay(
        db,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        source_transaction_id=source_transaction_id,
        correction_type=correction_type,
        target_reservation_id=target_reservation_id,
        reason=reason,
    )
    if replay is not None:
        return replay

    source_snapshot = (
        db.query(Transaction.id, Transaction.reservation_id)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.id == source_transaction_id,
        )
        .one_or_none()
    )
    if source_snapshot is None:
        raise PaymentCorrectionNotFound("No se encontró el pago para corregir.")

    reservation_ids = {int(source_snapshot.reservation_id)}
    if target_reservation_id is not None:
        reservation_ids.add(int(target_reservation_id))
    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.id.in_(reservation_ids),
        )
        .order_by(Reservation.id.asc())
        .with_for_update(of=Reservation)
        .all()
    )
    reservations_by_id = {reservation.id: reservation for reservation in reservations}
    source_reservation = reservations_by_id.get(int(source_snapshot.reservation_id))
    if source_reservation is None:
        raise PaymentCorrectionNotFound("No se encontró la reserva del pago.")
    target_reservation = (
        reservations_by_id.get(int(target_reservation_id))
        if target_reservation_id is not None
        else None
    )
    if target_reservation_id is not None and target_reservation is None:
        raise PaymentCorrectionNotFound("No se encontró la reserva de destino en este hotel.")
    if target_reservation is source_reservation:
        raise PaymentCorrectionError("La reserva de destino debe ser distinta de la reserva original.")

    # Recheck idempotency after the reservation locks: a competing request with
    # the same key may have completed while this request was waiting.
    replay = _find_idempotent_replay(
        db,
        hotel_id=hotel_id,
        idempotency_key=idempotency_key,
        source_transaction_id=source_transaction_id,
        correction_type=correction_type,
        target_reservation_id=target_reservation_id,
        reason=reason,
    )
    if replay is not None:
        return replay

    try:
        with db.begin_nested():
            source = (
                db.query(Transaction)
                .filter(
                    Transaction.hotel_id == hotel_id,
                    Transaction.id == source_transaction_id,
                )
                .with_for_update()
                .populate_existing()
                .one_or_none()
            )
            if source is None:
                raise PaymentCorrectionNotFound("No se encontró el pago para corregir.")
            if source.reservation_id != source_reservation.id:
                raise PaymentCorrectionConflict("El pago cambió de reserva durante la corrección.")

            already_corrected = (
                db.query(PaymentCorrection.id)
                .filter(
                    PaymentCorrection.hotel_id == hotel_id,
                    PaymentCorrection.source_transaction_id == source.id,
                )
                .first()
            )
            if already_corrected is not None:
                raise PaymentCorrectionConflict("Este pago ya tiene una corrección registrada.")
            if source.status != TransactionStatusEnum.COMPLETED:
                raise PaymentCorrectionError("Solo se pueden corregir cobros completados.")
            if source.transaction_type == TransactionTypeEnum.REFUND or source.refund_of_transaction_id:
                raise PaymentCorrectionError("Una devolución no se puede corregir desde este flujo.")
            if source.payment_method not in _CORRECTABLE_METHODS or source.external_payment_id or source.provider_code:
                raise PaymentCorrectionError(
                    "Este medio de pago requiere conciliación específica y no admite corrección manual."
                )
            if source.group_payment_batch_id is not None:
                raise PaymentCorrectionError(
                    "Los pagos grupales deben corregirse desde una conciliación de grupo."
                )
            has_night_allocations = (
                db.query(CompanyNightChargePaymentAllocation.id)
                .filter(
                    CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
                    CompanyNightChargePaymentAllocation.transaction_id == source.id,
                )
                .first()
            )
            if has_night_allocations is not None:
                raise PaymentCorrectionError(
                    "Este pago incluye adicionales de empresa y requiere corregir sus asignaciones junto con el pago."
                )
            prior_refund = (
                db.query(Transaction.id)
                .filter(
                    Transaction.hotel_id == hotel_id,
                    Transaction.refund_of_transaction_id == source.id,
                    Transaction.transaction_type == TransactionTypeEnum.REFUND,
                    Transaction.status == TransactionStatusEnum.COMPLETED,
                )
                .first()
            )
            if prior_refund is not None:
                raise PaymentCorrectionError(
                    "Este pago ya tiene una devolución; primero debe conciliarse ese movimiento."
                )

            movement = None
            if source.payment_method == PaymentMethodEnum.CASH:
                must_find_movement = (
                    correction_type == "duplicate_reversal" or not source.collected_before
                )
                if must_find_movement:
                    movement_ref = (
                        db.query(CashMovement)
                        .filter(
                            CashMovement.hotel_id == hotel_id,
                            CashMovement.transaction_id == source.id,
                        )
                        .with_entities(CashMovement.id, CashMovement.session_id)
                        .one_or_none()
                    )
                    if movement_ref is None:
                        if correction_type == "duplicate_reversal":
                            raise PaymentCorrectionConflict(
                                "No se encontró un movimiento asociado a una caja abierta. "
                                "Este cobro requiere conciliación autorizada antes de anularse."
                            )
                        if not source.collected_before:
                            raise PaymentCorrectionError(
                                "No se encontró el ingreso físico de caja asociado al pago."
                            )
                    else:
                        # Cash close locks the session before calculating its
                        # expected balance. Take the same lock before changing
                        # the movement so close and correction see one ledger
                        # state. Duplicate reversals are allowed only while
                        # that session is still open; reassignments preserve
                        # the physical income and can update the attribution
                        # after close.
                        cash_session = (
                            db.query(CashSession)
                            .filter(
                                CashSession.hotel_id == hotel_id,
                                CashSession.id == movement_ref.session_id,
                            )
                            .with_for_update(of=CashSession)
                            .populate_existing()
                            .one_or_none()
                        )
                        if cash_session is None:
                            raise PaymentCorrectionError(
                                "No se encontró la sesión de caja del pago asociado."
                            )
                        if (
                            correction_type == "duplicate_reversal"
                            and cash_session.status != CashSessionStatusEnum.OPEN
                        ):
                            raise PaymentCorrectionConflict(
                                "El movimiento duplicado solo se puede anular mientras la caja está abierta. "
                                "La sesión ya cerró o está pendiente de aprobación; solicitá una conciliación autorizada."
                            )
                        movement = (
                            db.query(CashMovement)
                            .filter(
                                CashMovement.hotel_id == hotel_id,
                                CashMovement.id == movement_ref.id,
                                CashMovement.transaction_id == source.id,
                            )
                            .with_for_update(of=CashMovement)
                            .populate_existing()
                            .one_or_none()
                        )
                        if movement is None or movement.session_id != cash_session.id:
                            raise PaymentCorrectionConflict(
                                "El movimiento de caja cambió durante la corrección. Volvé a intentar."
                            )
                        if movement.voided_at is not None:
                            raise PaymentCorrectionConflict(
                                "El movimiento de caja ya fue anulado; revisá la conciliación antes de continuar."
                            )

            if target_reservation is not None:
                if target_reservation.status in _TERMINAL_RESERVATION_STATES:
                    raise PaymentCorrectionError(
                        "No se puede imputar un pago a una reserva cancelada o con checkout finalizado."
                    )
                if (target_reservation.currency_code or "ARS").strip().upper() != (
                    source.currency or "ARS"
                ).strip().upper():
                    raise PaymentCorrectionError(
                        "La reserva de destino debe usar la misma moneda del asiento original."
                    )
                if reservation_has_deferred_company_billing(
                    db, hotel_id=hotel_id, reservation=target_reservation
                ):
                    raise PaymentCorrectionError(
                        "La reserva de destino usa facturación diferida; no se puede imputar este cobro general."
                    )
                current_paid = paid_amount_with_legacy_fallback(
                    db, hotel_id, target_reservation
                )
                balance = operational_balance_due(
                    db,
                    hotel_id=hotel_id,
                    reservation=target_reservation,
                    paid_amount=current_paid,
                )
                amount = Decimal(str(source.amount or 0)).quantize(Decimal("0.01"))
                if amount <= 0 or amount > balance:
                    raise PaymentCorrectionError(
                        f"El pago ({amount:.2f} {source.currency}) supera el saldo disponible "
                        f"de la reserva de destino ({Decimal(str(balance)):.2f})."
                    )

            source_before = {
                "status": source.status.value,
                "reservation_id": source.reservation_id,
                "amount": source.amount,
                "currency": source.currency,
                "payment_method": source.payment_method.value,
                "manual_reference": source.manual_reference,
            }
            source.status = TransactionStatusEnum.CANCELLED
            source.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.flush()

            replacement = None
            if target_reservation is not None:
                replacement = Transaction(
                    hotel_id=hotel_id,
                    reservation_id=target_reservation.id,
                    amount=source.amount,
                    currency=source.currency,
                    tender_amount=source.tender_amount,
                    tender_currency=source.tender_currency,
                    cash_received_amount=source.cash_received_amount,
                    cash_change_amount=source.cash_change_amount,
                    cash_tip_amount=source.cash_tip_amount,
                    rounding_credit_amount=source.rounding_credit_amount,
                    credit_refund_amount=Decimal("0.00"),
                    refund_component=source.refund_component,
                    gross_amount=source.gross_amount,
                    tax_amount=source.tax_amount,
                    fee_amount=source.fee_amount,
                    net_amount=source.net_amount,
                    fx_rate_snapshot=source.fx_rate_snapshot,
                    fx_quote_details=dict(source.fx_quote_details or {}) or None,
                    transaction_type=source.transaction_type,
                    payment_method=source.payment_method,
                    status=TransactionStatusEnum.COMPLETED,
                    manual_reference=source.manual_reference,
                    collected_before=source.collected_before,
                    collected_on=source.collected_on,
                    prior_receipt_note=source.prior_receipt_note,
                    description=f"Reimputación del pago #{source.id}",
                    pricing_snapshot=source.pricing_snapshot,
                    created_by_user_id=actor_user_id,
                    processed_at=source.processed_at,
                )
                db.add(replacement)
                db.flush()

                if movement is not None:
                    movement_before = {
                        "reservation_id": movement.reservation_id,
                        "transaction_id": movement.transaction_id,
                        "description": movement.description,
                    }
                    movement.reservation_id = target_reservation.id
                    movement.transaction_id = replacement.id
                    movement.description = (
                        f"Cobro corregido para reserva #{target_reservation.id} "
                        f"(tx #{replacement.id}; origen tx #{source.id})"
                    )[:300]
                    movement_after = {
                        "reservation_id": movement.reservation_id,
                        "transaction_id": movement.transaction_id,
                        "description": movement.description,
                    }
                    audit_log_service.create_audit_log(
                        db,
                        hotel_id=hotel_id,
                        table_name="cash_movements",
                        record_id=movement.id,
                        action=AuditActionEnum.UPDATE,
                        actor_user_id=actor_user_id,
                        payload_before=movement_before,
                        payload_after=movement_after,
                    )

            correction = PaymentCorrection(
                hotel_id=hotel_id,
                source_transaction_id=source.id,
                source_reservation_id=source_reservation.id,
                target_reservation_id=target_reservation.id if target_reservation else None,
                replacement_transaction_id=replacement.id if replacement else None,
                correction_type=correction_type,
                reason=reason,
                idempotency_key=idempotency_key,
                actor_user_id=actor_user_id,
            )
            db.add(correction)
            db.flush()

            if correction_type == "duplicate_reversal" and movement is not None:
                movement_before = {
                    "voided_at": movement.voided_at,
                    "voided_by_payment_correction_id": movement.voided_by_payment_correction_id,
                    "transaction_id": movement.transaction_id,
                }
                movement.voided_at = datetime.now(timezone.utc).replace(tzinfo=None)
                movement.voided_by_payment_correction_id = correction.id
                db.flush()
                audit_log_service.create_audit_log(
                    db,
                    hotel_id=hotel_id,
                    table_name="cash_movements",
                    record_id=movement.id,
                    action=AuditActionEnum.UPDATE,
                    actor_user_id=actor_user_id,
                    payload_before=movement_before,
                    payload_after={
                        "voided_at": movement.voided_at,
                        "voided_by_payment_correction_id": correction.id,
                        "transaction_id": movement.transaction_id,
                        "reason": reason,
                    },
                )

            audit_log_service.create_audit_log(
                db,
                hotel_id=hotel_id,
                table_name="transactions",
                record_id=source.id,
                action=AuditActionEnum.STATUS_CHANGE,
                actor_user_id=actor_user_id,
                payload_before=source_before,
                payload_after={
                    **source_before,
                    "status": source.status.value,
                    "correction_id": correction.id,
                    "reason": reason,
                },
            )
            if replacement is not None:
                audit_log_service.create_audit_log(
                    db,
                    hotel_id=hotel_id,
                    table_name="transactions",
                    record_id=replacement.id,
                    action=AuditActionEnum.CREATE,
                    actor_user_id=actor_user_id,
                    payload_after={
                        "reservation_id": replacement.reservation_id,
                        "amount": replacement.amount,
                        "currency": replacement.currency,
                        "payment_method": replacement.payment_method.value,
                        "status": replacement.status.value,
                        "correction_id": correction.id,
                        "source_transaction_id": source.id,
                    },
                )
            audit_log_service.create_audit_log(
                db,
                hotel_id=hotel_id,
                table_name="payment_corrections",
                record_id=correction.id,
                action=AuditActionEnum.CREATE,
                actor_user_id=actor_user_id,
                payload_after={
                    "source_transaction_id": source.id,
                    "source_reservation_id": source_reservation.id,
                    "target_reservation_id": correction.target_reservation_id,
                    "replacement_transaction_id": correction.replacement_transaction_id,
                    "cash_movement_id": movement.id if movement is not None else None,
                    "correction_type": correction_type,
                    "reason": reason,
                    "actor_user_id": actor_user_id,
                },
            )

            _update_reservation_financials(
                db,
                source_reservation,
                source.amount,
                source.transaction_type,
                hotel_id,
            )
            if replacement is not None and target_reservation is not None:
                _update_reservation_financials(
                    db,
                    target_reservation,
                    replacement.amount,
                    replacement.transaction_type,
                    hotel_id,
                )

            return PaymentCorrectionOutcome(correction=correction, replayed=False)
    except IntegrityError as exc:
        # The unique hotel/key constraint arbitrates retries whose requests
        # race before either row becomes visible. The savepoint rolls the
        # complete financial correction back before inspecting the winner.
        replay = _find_idempotent_replay(
            db,
            hotel_id=hotel_id,
            idempotency_key=idempotency_key,
            source_transaction_id=source_transaction_id,
            correction_type=correction_type,
            target_reservation_id=target_reservation_id,
            reason=reason,
        )
        if replay is not None:
            return replay
        corrected_source = (
            db.query(PaymentCorrection.id)
            .filter(
                PaymentCorrection.hotel_id == hotel_id,
                PaymentCorrection.source_transaction_id == source_transaction_id,
            )
            .first()
        )
        if corrected_source is not None:
            raise PaymentCorrectionConflict("Este pago ya tiene una corrección registrada.") from exc
        raise
