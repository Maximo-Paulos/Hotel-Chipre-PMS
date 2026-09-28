"""
Payment Service — Financial Engine.
Implements the booking cart flow:
  - Deposit payment (e.g. 30%) → status: deposit_paid
  - Full payment → status: fully_paid
  - Balance payment at check-in
  
Coordinates with payment gateway adapters (MercadoPago, PayPal) and cash.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.operations import BillingAdjustment, ReservationStatusHistory
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.transaction import (
    Transaction, PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
)
from app.models.hotel_config import HotelConfiguration
from app.schemas.transaction import PaymentRequest, PaymentGatewayResponse
from app.services.reservation_service import transition_reservation_status
from app.services.financial_ledger import (
    completed_paid_amount,
    operational_balance_due,
    paid_amount_with_legacy_fallback,
    reconciled_paid_amounts_by_reservation,
)


class PaymentError(Exception):
    """Custom exception for payment logic errors."""
    pass


class PaymentNotFoundError(PaymentError):
    """A payment target is absent from the caller's tenant scope."""


DEFAULT_DEPOSIT_PERCENTAGE = 30.0
MANUAL_REFERENCE_METHODS = frozenset(
    {PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.DEBIT_CARD, PaymentMethodEnum.BANK_TRANSFER}
)


def _same_idempotent_payment(existing: Transaction, request: PaymentRequest, currency: str) -> bool:
    return (
        Decimal(str(existing.amount)) == Decimal(str(request.amount))
        and existing.payment_method == request.payment_method
        and existing.transaction_type == request.transaction_type
        and existing.currency == currency
        and existing.manual_reference == request.manual_reference
        and existing.refund_of_transaction_id == request.refund_of_transaction_id
        and existing.refund_reason == request.refund_reason
    )


def get_hotel_config(db: Session, hotel_id: int) -> HotelConfiguration:
    """
    Get or create the per-hotel configuration.
    No global/singleton fallback â€” requires explicit hotel_id.
    """
    if hotel_id is None:
        raise PaymentError("hotel_id is required for finance operations")

    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    if not config:
        config = HotelConfiguration(id=hotel_id)
        db.add(config)
        db.flush()

    # Defensive defaults (transitional only, not hardcoded product behavior)
    if config.deposit_percentage is None:
        config.deposit_percentage = DEFAULT_DEPOSIT_PERCENTAGE
    if config.enable_cash is None:
        config.enable_cash = True
    if config.enable_mercado_pago is None:
        config.enable_mercado_pago = True
    if config.enable_paypal is None:
        config.enable_paypal = True
    if config.enable_credit_card is None:
        config.enable_credit_card = True
    if config.enable_debit_card is None:
        config.enable_debit_card = True
    if config.enable_bank_transfer is None:
        config.enable_bank_transfer = False

    return config


def validate_payment_method_enabled(db: Session, method: PaymentMethodEnum, hotel_id: int) -> None:
    """Check that the requested payment method is enabled in hotel config."""
    config = get_hotel_config(db, hotel_id)
    if not config.is_payment_method_enabled(method.value):
        raise PaymentError(f"Payment method '{method.value}' is currently disabled")


def _resolve_reservation_hotel(
    reservation: Reservation,
    hotel_id: Optional[int],
    existing_tx_hotel_id: Optional[int] = None,
) -> int:
    """
    Resolve hotel scope using caller input or existing transactions.
    """
    reservation_hotel_id = getattr(reservation, "hotel_id", None)

    if reservation_hotel_id is not None and hotel_id is not None and reservation_hotel_id != hotel_id:
        raise PaymentError(
            f"Reservation {reservation.id} does not belong to hotel {hotel_id} (belongs to {reservation_hotel_id})"
        )

    if reservation_hotel_id is not None and existing_tx_hotel_id is not None and reservation_hotel_id != existing_tx_hotel_id:
        raise PaymentError(
            f"Reservation {reservation.id} already has payments for hotel {existing_tx_hotel_id}"
        )

    if existing_tx_hotel_id is not None and hotel_id is not None and hotel_id != existing_tx_hotel_id:
        raise PaymentError(f"Reservation {reservation.id} already has payments for hotel {existing_tx_hotel_id}")

    resolved = reservation_hotel_id or hotel_id or existing_tx_hotel_id

    if resolved is None:
        raise PaymentError("hotel_id is required for finance operations")

    return resolved


def _resolve_payment_currency(reservation: Reservation, requested_currency: Optional[str]) -> str:
    """
    Keep every payment in the reservation's ledger currency. We do not have a
    validated FX conversion flow here, so accepting a different currency would
    make balance checks and paid totals compare unlike amounts.
    """
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    candidate = (requested_currency or reservation_currency).strip().upper()
    if (
        len(reservation_currency) != 3
        or not reservation_currency.isascii()
        or not reservation_currency.isalpha()
        or len(candidate) != 3
        or not candidate.isascii()
        or not candidate.isalpha()
    ):
        raise PaymentError("La moneda de la reserva o del pago no es válida")
    if candidate != reservation_currency:
        raise PaymentError(
            f"La moneda del pago ({candidate}) debe coincidir con la reserva ({reservation_currency})"
        )
    return candidate


def _payment_method_value(method) -> str:
    return method.value if hasattr(method, "value") else str(method)


def calculate_payment_surcharge(
    db: Session,
    *,
    hotel_id: int,
    payment_method,
    base_amount,
) -> dict:
    base = Decimal(str(base_amount or 0)).quantize(Decimal("0.01"))
    surcharge_record = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.hotel_id == hotel_id,
            PaymentSurcharge.payment_method == _payment_method_value(payment_method),
            PaymentSurcharge.is_active.is_(True),
        )
        .first()
    )

    surcharge_type = None
    surcharge_value = None
    surcharge_amount = Decimal("0.00")
    if surcharge_record:
        surcharge_type = (
            surcharge_record.surcharge_type.value
            if hasattr(surcharge_record.surcharge_type, "value")
            else str(surcharge_record.surcharge_type)
        )
        surcharge_value = surcharge_record.amount
        if surcharge_record.surcharge_type == PaymentSurchargeTypeEnum.FIXED:
            surcharge_amount = Decimal(str(surcharge_record.amount)).quantize(Decimal("0.01"))
        else:
            surcharge_amount = (base * Decimal(str(surcharge_record.amount)) / Decimal("100")).quantize(Decimal("0.01"))

    # A discount-shaped adjustment (negative amount) must never push the
    # final amount below 0 -- clamp rather than invent negative money owed.
    final_amount = max(Decimal("0.00"), (base + surcharge_amount)).quantize(Decimal("0.01"))
    return {
        "base_amount": base,
        "surcharge_type": surcharge_type,
        "surcharge_value": surcharge_value,
        "surcharge_amount": surcharge_amount,
        "final_amount": final_amount,
    }


def calculate_base_amount_before_surcharge(
    db: Session,
    *,
    hotel_id: int,
    payment_method,
    final_amount,
) -> Decimal:
    final = Decimal(str(final_amount or 0)).quantize(Decimal("0.01"))
    surcharge_record = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.hotel_id == hotel_id,
            PaymentSurcharge.payment_method == _payment_method_value(payment_method),
            PaymentSurcharge.is_active.is_(True),
        )
        .first()
    )
    if not surcharge_record:
        return final
    if surcharge_record.surcharge_type == PaymentSurchargeTypeEnum.FIXED:
        return max(Decimal("0.00"), final - Decimal(str(surcharge_record.amount))).quantize(Decimal("0.01"))
    divisor = Decimal("1") + (Decimal(str(surcharge_record.amount)) / Decimal("100"))
    if divisor <= 0:
        return final
    return (final / divisor).quantize(Decimal("0.01"))


def process_payment(
    db: Session,
    request: PaymentRequest,
    hotel_id: Optional[int] = None,
    gateway_response: Optional[PaymentGatewayResponse] = None,
    idempotency_key: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    manual_confirmation: bool = False,
    apply_surcharge: bool = True,
    allow_verified_cancelled_settlement: bool = False,
) -> Transaction:
    """
    Process a payment for a reservation.
    
    This is the core financial engine:
    1. Validate reservation exists and is in a payable state
    2. Validate payment method is enabled
    3. Validate amount does not exceed balance due
    4. Create Transaction record
    5. If gateway involved (MP/PayPal), record external IDs
    6. Update reservation.amount_paid
    7. Transition reservation status based on financial state

    For cash payments, the transaction is completed immediately.
    For gateway payments, the caller provides the gateway_response.

    ``apply_surcharge`` (default True) adds any active PaymentSurcharge on top
    of ``request.amount`` and records it as gross_amount/fee_amount. This is
    correct when the caller represents a live collection point (cash handed
    over now, or a gateway/link amount that already asked the guest for the
    grossed-up figure before it arrived). It is WRONG when ``request.amount``
    is itself a historical fact -- e.g. a bank-transfer proof, where the guest
    already sent an exact, already-capped-at-balance amount and there is no
    additional money to invent on top. Callers reconciling such a fact must
    pass ``apply_surcharge=False`` so fee_amount/gross_amount are not
    fabricated for money nobody actually collected.
    """
    # 1. Validate reservation
    reservation_query = db.query(Reservation).filter(Reservation.id == request.reservation_id)
    if hotel_id is not None:
        reservation_query = reservation_query.filter(Reservation.hotel_id == hotel_id)
    reservation = (
        reservation_query
        .enable_eagerloads(False)
        .with_for_update()
        .first()
    )

    if not reservation:
        raise PaymentNotFoundError("Reservation not found")

    existing_tx_query = db.query(Transaction.hotel_id).filter(Transaction.reservation_id == request.reservation_id)
    if hotel_id is not None:
        existing_tx_query = existing_tx_query.filter(Transaction.hotel_id == hotel_id)
    existing_tx = existing_tx_query.first()
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError("Reservation does not belong to selected hotel")

    is_refund = request.transaction_type == TransactionTypeEnum.REFUND
    transaction_currency = _resolve_payment_currency(reservation, request.currency)
    if idempotency_key is not None:
        existing_by_key = (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.reservation_id == request.reservation_id,
                Transaction.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing_by_key is not None:
            if not _same_idempotent_payment(existing_by_key, request, transaction_currency):
                raise PaymentError("Idempotency key was already used for a different payment request")
            return existing_by_key

    if request.manual_reference and (is_refund or request.payment_method not in MANUAL_REFERENCE_METHODS):
        raise PaymentError("Manual references are only valid for in-person card, debit, or bank-transfer payments")
    if not is_refund and (request.refund_of_transaction_id is not None or request.refund_reason is not None):
        raise PaymentError("Refund source and reason are only valid for refund transactions")
    refund_source = None
    if is_refund:
        if request.payment_method != PaymentMethodEnum.CASH:
            raise PaymentError("Manual reservation refunds must be returned through cash")
        if request.refund_of_transaction_id is None or not request.refund_reason:
            raise PaymentError("A refund must identify the original payment and include a reason")
        refund_source = (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.reservation_id == request.reservation_id,
                Transaction.id == request.refund_of_transaction_id,
                Transaction.status == TransactionStatusEnum.COMPLETED,
                Transaction.transaction_type != TransactionTypeEnum.REFUND,
            )
            .with_for_update()
            .first()
        )
        if refund_source is None:
            raise PaymentError("The original payment was not found as a completed payment for this reservation")
        if refund_source.currency != transaction_currency:
            raise PaymentError("A refund must use the original payment currency")
        already_refunded = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.refund_of_transaction_id == refund_source.id,
                Transaction.transaction_type == TransactionTypeEnum.REFUND,
                Transaction.status == TransactionStatusEnum.COMPLETED,
            )
            .scalar()
        )
        refundable_remaining = Decimal(str(refund_source.amount)) - Decimal(str(already_refunded or 0))
        # These values are stored as two-decimal NUMERIC amounts, so there is
        # no floating-point rounding to absorb here. A one-cent tolerance would
        # permit a refund larger than the original payment.
        if Decimal(str(request.amount)) > refundable_remaining:
            raise PaymentError(
                f"Refund amount ${request.amount:.2f} exceeds the remaining refundable amount "
                f"${max(refundable_remaining, Decimal('0.00')):.2f} for the original payment"
            )
    if manual_confirmation and request.manual_reference:
        duplicate_reference = (
            db.query(Transaction.id)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.payment_method == request.payment_method,
                func.lower(Transaction.manual_reference) == request.manual_reference.strip().lower(),
            )
            .first()
        )
        if duplicate_reference is not None:
            raise PaymentError("This manual payment reference is already recorded for the reservation")

    verified_late_settlement = (
        allow_verified_cancelled_settlement
        and reservation.status == ReservationStatusEnum.CANCELLED
        and gateway_response is not None
        and gateway_response.success
        and bool(gateway_response.external_payment_id)
    )
    if not is_refund and reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
    ) and not verified_late_settlement:
        raise PaymentError(
            f"Cannot process payment for reservation in status '{reservation.status.value}'"
        )

    # 2. Validate payment method
    validate_payment_method_enabled(db, request.payment_method, resolved_hotel_id)
    if apply_surcharge and not is_refund:
        surcharge_info = calculate_payment_surcharge(
            db,
            hotel_id=resolved_hotel_id,
            payment_method=request.payment_method,
            base_amount=request.amount,
        )
        surcharge_amount = surcharge_info["surcharge_amount"]
    else:
        surcharge_amount = Decimal("0.00")
    gross_amount = (Decimal(str(request.amount)) + surcharge_amount).quantize(Decimal("0.01"))

    # 3. Validate against the confirmed transaction ledger; amount_paid is only
    #    a materialized compatibility cache and must not authorize overpayment.
    _TOLERANCE = Decimal("0.01")
    ledger_paid = paid_amount_with_legacy_fallback(db, resolved_hotel_id, reservation)
    if is_refund:
        if Decimal(str(request.amount)) > ledger_paid:
            raise PaymentError(
                f"Refund amount ${request.amount:.2f} exceeds paid amount ${ledger_paid:.2f}"
            )
    else:
        balance = operational_balance_due(
            db,
            hotel_id=resolved_hotel_id,
            reservation=reservation,
            paid_amount=ledger_paid,
        )
        if Decimal(str(request.amount)) > Decimal(str(balance)) + _TOLERANCE:
            raise PaymentError(
                f"Payment amount ${request.amount:.2f} exceeds balance due ${balance:.2f}"
            )

    if request.payment_method == PaymentMethodEnum.CASH:
        from app.services import cash_register_service

        try:
            cash_register_service.require_open_session_for_currency(
                db,
                hotel_id=resolved_hotel_id,
                currency_code=transaction_currency,
            )
        except cash_register_service.CashRegisterError as exc:
            raise PaymentError(str(exc)) from exc

    # 4. Create transaction
    tx_status = TransactionStatusEnum.PENDING
    external_payment_id = None
    external_status = None
    raw_response = None
    processed_at = None

    # Cash and an explicitly approved manual proof are completed immediately.
    # Bank transfers submitted without proof intentionally remain pending.
    if request.payment_method == PaymentMethodEnum.CASH or manual_confirmation:
        tx_status = TransactionStatusEnum.COMPLETED
        processed_at = datetime.now(timezone.utc)

    # For gateway payments, use the provided response
    if gateway_response:
        if gateway_response.success:
            tx_status = TransactionStatusEnum.COMPLETED
            processed_at = datetime.now(timezone.utc)
        else:
            tx_status = TransactionStatusEnum.FAILED

        external_payment_id = gateway_response.external_payment_id
        external_status = gateway_response.external_status
        raw_response = gateway_response.gateway_response

    # idempotency_key is set AT CONSTRUCTION (before the INSERT) so a concurrent
    # duplicate delivery collides on the partial unique index
    # (hotel_id, reservation_id, idempotency_key) during the flush itself, rather
    # than leaving a race window where the key is assigned after the row is visible.
    transaction = Transaction(
        hotel_id=resolved_hotel_id,
        reservation_id=request.reservation_id,
        amount=request.amount,
        gross_amount=gross_amount,
        fee_amount=surcharge_amount,
        currency=transaction_currency,
        transaction_type=request.transaction_type,
        payment_method=request.payment_method,
        status=tx_status,
        external_payment_id=external_payment_id,
        external_status=external_status,
        manual_reference=request.manual_reference,
        refund_of_transaction_id=request.refund_of_transaction_id,
        refund_reason=request.refund_reason,
        gateway_response=raw_response,
        description=request.description,
        processed_at=processed_at,
        idempotency_key=idempotency_key,
        created_by_user_id=actor_user_id,
    )
    if idempotency_key is not None:
        # Savepoint: if a concurrent delivery already inserted this key, the unique
        # index raises IntegrityError here; roll back ONLY this insert and replay the
        # existing transaction (idempotent), never poisoning the outer transaction.
        try:
            with db.begin_nested():
                db.add(transaction)
                db.flush()
        except IntegrityError:
            existing = (
                db.query(Transaction)
                .filter(
                    Transaction.hotel_id == resolved_hotel_id,
                    Transaction.reservation_id == request.reservation_id,
                    Transaction.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                if _same_idempotent_payment(existing, request, transaction_currency):
                    return existing
                raise PaymentError("Idempotency key was already used for a different payment request")
            if manual_confirmation and request.manual_reference:
                duplicate_reference = (
                    db.query(Transaction.id)
                    .filter(
                        Transaction.hotel_id == resolved_hotel_id,
                        Transaction.payment_method == request.payment_method,
                        func.lower(Transaction.manual_reference) == request.manual_reference.strip().lower(),
                    )
                    .first()
                )
                if duplicate_reference is not None:
                    raise PaymentError("This manual payment reference is already recorded for the reservation")
            raise
    else:
        db.add(transaction)
        db.flush()

    # 5. If completed, update reservation financial state
    if tx_status == TransactionStatusEnum.COMPLETED:
        _update_reservation_financials(
            db,
            reservation,
            request.amount,
            request.transaction_type,
            resolved_hotel_id,
        )
        if verified_late_settlement:
            reservation.requires_manual_review = True
            reservation.settlement_status = "review_cancellation"
        # 6. Physical cash must land in an explicitly opened caja so the
        #    arqueo reconciles. The cash-register service rejects the payment
        #    if there is no open session.
        if request.payment_method == PaymentMethodEnum.CASH:
            from app.services import cash_register_service

            try:
                cash_register_service.record_cash_payment_movement(
                    db,
                    transaction=transaction,
                    recorded_by_user_id=actor_user_id,
                )
            except cash_register_service.CashRegisterError as exc:
                # Every process_payment caller (direct payment route, webhook
                # processing, reservation extension, transfer-proof approval)
                # already catches PaymentError with a clean 4xx response.
                # Without this translation a cash charge with no open caja
                # crashed as an unhandled 500 instead of blocking clearly.
                raise PaymentError(str(exc)) from exc

    return transaction


def get_payment_link_with_surcharge(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    payment_method: str,
    amount: Optional[float] = None,
) -> dict:
    """
    Calculate surcharge for a payment link and return a guest-facing breakdown.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise PaymentError(f"Reservation {reservation_id} not found")
    if reservation.hotel_id and reservation.hotel_id != hotel_id:
        raise PaymentError(f"Reservation {reservation_id} does not belong to hotel {hotel_id}")

    if amount is None:
        amount = operational_balance_due(db, hotel_id=hotel_id, reservation=reservation)
    base_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if base_amount <= 0:
        raise PaymentError("Payment amount must be greater than zero")

    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=payment_method,
        base_amount=base_amount,
    )
    final_amount = surcharge_info["final_amount"]
    payment_url = f"/api/pay/{payment_method}/{reservation_id}?amount={final_amount}"
    shareable_link = f"/pay/{reservation.confirmation_code}/{payment_method}"

    return {
        "base_amount": float(surcharge_info["base_amount"]),
        "surcharge_type": surcharge_info["surcharge_type"],
        "surcharge_value": surcharge_info["surcharge_value"],
        "surcharge_amount": float(surcharge_info["surcharge_amount"]),
        "final_amount": float(final_amount),
        "payment_url": payment_url,
        "shareable_link": shareable_link,
    }


def _update_reservation_financials(
    db: Session,
    reservation: Reservation,
    amount: float,
    tx_type: TransactionTypeEnum,
    hotel_id: int,
) -> None:
    """
    Refresh the materialized amount_paid cache from confirmed OTA credits and
    the in-house completed ledger, then transition status from that total.

    State machine:
    - If deposit paid (amount >= deposit_amount) and status is PENDING → deposit_paid
    - If fully paid (balance_due == 0) → fully_paid
    """
    reservation.amount_paid = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    _sync_reservation_financial_status(db, reservation, hotel_id=hotel_id, reason_code=tx_type.value)
    db.flush()


def _sync_reservation_financial_status(
    db: Session,
    reservation: Reservation,
    *,
    hotel_id: int,
    reason_code: str,
) -> None:
    if reservation.status in (
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.PRE_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
    ):
        return

    _TOL = Decimal("0.01")
    d_paid = Decimal(str(reservation.amount_paid or 0))
    d_total = Decimal(str(reservation.total_amount or 0))
    d_deposit = Decimal(str(reservation.deposit_amount or 0))
    if d_paid >= d_total - _TOL:
        target_status = ReservationStatusEnum.FULLY_PAID
    elif d_paid >= d_deposit - _TOL and d_paid > 0:
        target_status = ReservationStatusEnum.DEPOSIT_PAID
    else:
        target_status = ReservationStatusEnum.PENDING

    if reservation.status == target_status:
        return

    if reservation.can_transition_to(target_status):
        transition_reservation_status(db, reservation, target_status, hotel_id, reason_code=reason_code)
        return

    previous_status = reservation.status
    reservation.status = target_status
    db.add(
        ReservationStatusHistory(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            from_status=previous_status.value if previous_status else None,
            to_status=target_status.value,
            reason_code=reason_code,
            notes="Financial reconciliation adjusted reservation status outside the forward-only state machine",
        )
    )


def get_reservation_financial_summary(db: Session, hotel_id: Optional[int], reservation_id: int) -> dict:
    """
    Get a full financial summary for a reservation.
    Returns total, paid, balance, deposit required, and all transactions.
    """
    reservation_query = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_query = reservation_query.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_query.first()
    if not reservation:
        raise PaymentNotFoundError("Reservation not found")

    existing_tx_query = db.query(Transaction.hotel_id).filter(Transaction.reservation_id == reservation_id)
    if hotel_id is not None:
        existing_tx_query = existing_tx_query.filter(Transaction.hotel_id == hotel_id)
    existing_tx = existing_tx_query.first()
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError(f"Reservation {reservation_id} does not belong to hotel {resolved_hotel_id}")

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.reservation_id == reservation_id,
            Transaction.hotel_id == resolved_hotel_id,
        )
        .order_by(Transaction.created_at)
        .all()
    )

    completed_transactions = [
        t for t in transactions if t.status == TransactionStatusEnum.COMPLETED
    ]
    billing_adjustments = (
        db.query(BillingAdjustment)
        .filter(
            BillingAdjustment.reservation_id == reservation_id,
            BillingAdjustment.hotel_id == resolved_hotel_id,
        )
        .order_by(BillingAdjustment.effective_at, BillingAdjustment.id)
        .all()
    )
    billing_adjustment_total = Decimal(str(round(sum(adj.total_amount for adj in billing_adjustments), 2)))
    completed_payment_total = Decimal(str(round(
        sum(_signed_transaction_amount(t.transaction_type, t.amount) for t in completed_transactions),
        2,
    )))
    d_total = Decimal(str(reservation.total_amount or 0))
    materialized_paid = Decimal(str(reservation.amount_paid or 0))
    d_paid = paid_amount_with_legacy_fallback(db, resolved_hotel_id, reservation)
    operational_total = d_total + billing_adjustment_total
    operational_balance_due = max(Decimal("0"), operational_total - d_paid)
    evidenced_paid = reconciled_paid_amounts_by_reservation(
        db,
        resolved_hotel_id,
        [reservation.id],
    ).get(reservation.id, Decimal("0.00"))
    reconciliation_gap = materialized_paid - evidenced_paid

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "currency_code": reservation.currency_code or "ARS",
        "total_amount": reservation.total_amount,
        "deposit_required": reservation.deposit_amount,
        "amount_paid": d_paid,
        "balance_due": max(Decimal("0"), d_total - d_paid),
        "operational_total_amount": operational_total,
        "operational_balance_due": operational_balance_due,
        "billing_adjustment_total": billing_adjustment_total,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "has_financial_reconciliation_gap": abs(reconciliation_gap) > 0.01,
        "financial_reconciliation_gap": reconciliation_gap,
        "recommended_next_action": _recommended_financial_action(
            reservation=reservation,
            operational_balance_due=operational_balance_due,
        ),
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "gross_amount": t.gross_amount if t.gross_amount is not None else t.amount,
                "fee_amount": t.fee_amount or 0,
                "currency": t.currency,
                "method": t.payment_method.value,
                "type": t.transaction_type.value,
                "status": t.status.value,
                "manual_reference": t.manual_reference,
                "refund_of_transaction_id": t.refund_of_transaction_id,
                "created_at": str(t.created_at),
            }
            for t in transactions
        ],
        "billing_adjustments": [
            {
                "id": adj.id,
                "type": adj.adjustment_type.value if hasattr(adj.adjustment_type, "value") else str(adj.adjustment_type),
                "amount": adj.amount,
                "tax_amount": adj.tax_amount,
                "total_amount": adj.total_amount,
                "currency_code": adj.currency_code,
                "notes": adj.notes,
            }
            for adj in billing_adjustments
        ],
        "completed_payments": completed_payment_total,
    }


def _signed_transaction_amount(transaction_type: TransactionTypeEnum, amount) -> Decimal:
    d = Decimal(str(amount))
    return -d if transaction_type == TransactionTypeEnum.REFUND else d


def _recommended_financial_action(*, reservation: Reservation, operational_balance_due: float) -> str | None:
    if reservation.requires_manual_review:
        return "manual_review_required"
    if reservation.status == ReservationStatusEnum.CANCELLED and reservation.source != ReservationSourceEnum.DIRECT:
        return "review_cancellation_settlement"
    if reservation.settlement_status in {"manual_resolution_required", "pending_hotel_action"}:
        return "resolve_external_channel"
    if operational_balance_due > 0.01 and reservation.payment_collection_model == "hotel_collect":
        return "collect_from_guest"
    if reservation.payment_collection_model == "ota_prepaid" and reservation.settlement_status in {"pending", "unknown"}:
        return "await_channel_settlement"
    return None
