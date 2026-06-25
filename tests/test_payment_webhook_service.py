from datetime import date
from decimal import Decimal

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction, TransactionStatusEnum
from app.services.payment_link_service import balance_due_from_transactions
from app.services.payment_webhook_service import ingest_webhook


def _reservation(db, hotel_id: int = 1) -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name="Webhook", last_name="Guest", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Webhook Room",
        code=f"WH{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"WH-{hotel_id}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 4),
        total_amount=Decimal("300.00"),
        deposit_amount=Decimal("90.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _link(db, reservation: Reservation) -> PaymentLink:
    link = PaymentLink(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        provider="mercado_pago",
        link_code="plink-test",
        requested_amount=Decimal("100.00"),
        recipient_email="webhook@example.com",
        status="pending",
        external_reference="signed-ref",
    )
    db.add(link)
    db.flush()
    return link


def test_gateway_webhook_is_idempotent_by_provider_webhook_id(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    payload = {
        "webhook_id": "mp-hook-1",
        "payment_id": "mp-payment-1",
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }

    first = ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-1", payload=payload, payment_link_id=link.id)
    second = ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-1", payload=payload, payment_link_id=link.id)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert db.query(PaymentWebhookEvent).count() == 1
    assert db.query(Payment).count() == 1
    assert db.query(Transaction).count() == 1


def test_completed_gateway_payment_creates_one_transaction(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    payload = {
        "webhook_id": "mp-hook-2",
        "payment_id": "mp-payment-2",
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }

    ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-2", payload=payload, payment_link_id=link.id)
    ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-2-duplicate-status", payload=payload, payment_link_id=link.id)

    txs = db.query(Transaction).all()
    assert len(txs) == 1
    assert txs[0].status == TransactionStatusEnum.COMPLETED
    assert txs[0].idempotency_key == "mercado_pago:mp-payment-2:completed"
    db.refresh(link)
    assert link.collected_amount == Decimal("100.00")
    assert link.first_payment_at is not None
    assert link.last_payment_at is not None


def test_duplicate_same_webhook_is_idempotent_no_double_transaction(db):
    """Re-delivering the SAME webhook must not create a 2nd transaction nor raise.

    Exercises the §12 race fix: the event INSERT now lives inside begin_nested(),
    and the Transaction is inserted with idempotency_key already set so a duplicate
    collides on the unique index and is resolved as a replay.
    """
    reservation = _reservation(db)
    link = _link(db, reservation)
    payload = {
        "webhook_id": "mp-hook-dup",
        "payment_id": "mp-payment-dup",
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }

    first = ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-dup", payload=payload, payment_link_id=link.id)
    # Exact same webhook re-delivered (replay) -> must be idempotent, never 500.
    second = ingest_webhook(db, hotel_id=1, provider="mercado_pago", webhook_id="mp-hook-dup", payload=payload, payment_link_id=link.id)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["event_id"] == first["event_id"]
    assert db.query(PaymentWebhookEvent).count() == 1
    assert db.query(Payment).count() == 1
    txs = db.query(Transaction).all()
    assert len(txs) == 1
    assert txs[0].status == TransactionStatusEnum.COMPLETED
    assert txs[0].idempotency_key == "mercado_pago:mp-payment-dup:completed"


def test_process_payment_replays_on_duplicate_idempotency_key(db):
    """Two distinct webhooks for the same completed payment id -> one transaction.

    Simulates concurrent/duplicate delivery hitting process_payment directly with
    the same idempotency_key: the 2nd insert collides on the unique index inside the
    savepoint and process_payment returns the EXISTING transaction (replay), not a 500.
    """
    from app.schemas.transaction import PaymentRequest, PaymentGatewayResponse
    from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
    from app.services.payment_service import process_payment

    reservation = _reservation(db, hotel_id=2)
    key = "mercado_pago:dup-key:completed"

    def _request():
        return PaymentRequest(
            reservation_id=reservation.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency="ARS",
            description="dup",
        )

    gw = PaymentGatewayResponse(success=True, external_payment_id="dup-key", external_status="approved")

    tx1 = process_payment(db, _request(), hotel_id=2, gateway_response=gw, idempotency_key=key)
    db.flush()
    tx2 = process_payment(db, _request(), hotel_id=2, gateway_response=gw, idempotency_key=key)
    db.flush()

    assert tx1.id == tx2.id
    assert db.query(Transaction).filter(Transaction.idempotency_key == key).count() == 1


def test_balance_due_uses_transactions_not_payments(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    db.add(
        Payment(
            hotel_id=1,
            reservation_id=reservation.id,
            payment_link_id=link.id,
            provider="mercado_pago",
            external_payment_id="pending-only",
            amount=Decimal("250.00"),
            currency="ARS",
            status="pending",
        )
    )
    db.flush()

    assert balance_due_from_transactions(db, 1, reservation.id) == Decimal("300.00")
