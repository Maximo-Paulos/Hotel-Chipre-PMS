import json
from datetime import date
from decimal import Decimal

import pytest

from app.config import get_settings
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import (
    Notification,
    NotificationChannelEnum,
    NotificationOutbox,
    NotificationPreference,
)
from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction, TransactionStatusEnum
from app.models.user import User
from app.services import payment_service, payment_webhook_service
from app.services.payment_link_service import balance_due_from_transactions, cancel_link
from app.services.payment_webhook_service import (
    PaymentWebhookError,
    RetryablePaymentWebhookError,
    ingest_webhook,
)


@pytest.fixture(autouse=True)
def _enable_inbound_provider_events(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _reservation(db, hotel_id: int = 1) -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True, enable_mercado_pago=True))
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
        execution_mode="provider",
        payable=True,
        external_checkout_url="https://mp.test/checkout/plink-test",
        external_reference="signed-ref",
    )
    db.add(link)
    db.flush()
    return link


def _provider_result(
    link: PaymentLink,
    *,
    status: str = "approved",
    amount: str = "100.00",
    currency: str = "ARS",
    collector_id: str | None = None,
):
    """Build a canonical provider response for service tests without network IO."""

    def fetch(_db, _hotel_id, payment_id):
        response = {
            "id": payment_id,
            "external_reference": link.external_reference,
            "status": status,
            "transaction_amount": amount,
            "currency_id": currency,
        }
        if collector_id is not None:
            response["collector_id"] = collector_id
        return response

    return fetch


def _management_member(db, *, hotel_id: int, user_id: int, role: str) -> User:
    user = User(
        id=user_id,
        email=f"webhook-alert-{user_id}@example.test",
        password_hash="test-only",
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role=role, status="active"))
    db.flush()
    return user


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

    first = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-1",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )
    second = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-1",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )

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

    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-2",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )
    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-2-duplicate-status",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )

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

    first = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-dup",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )
    # Exact same webhook re-delivered (replay) -> must be idempotent, never 500.
    second = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-dup",
        payload=payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )

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
    from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
    from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
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


def test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(db):
    """A later-arriving webhook for the SAME payment reporting an earlier status
    (network reordering, not a real refund) must not undo a completed payment.
    """
    reservation = _reservation(db)
    link = _link(db, reservation)
    approved_payload = {
        "webhook_id": "mp-hook-order-1",
        "payment_id": "mp-payment-order",
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }
    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-order-1",
        payload=approved_payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )

    stale_pending_payload = {
        "webhook_id": "mp-hook-order-0-late",
        "payment_id": "mp-payment-order",
        "status": "pending",
        "amount": "100.00",
        "currency": "ARS",
    }
    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-order-0-late",
        payload=stale_pending_payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link, status="pending"),
    )

    payment = db.query(Payment).filter(Payment.external_payment_id == "mp-payment-order").one()
    assert payment.status == "completed"
    db.refresh(link)
    assert link.collected_amount == Decimal("100.00")
    assert db.query(Transaction).count() == 1


@pytest.mark.parametrize("reported_status", ["rejected", "charged_back"])
def test_verified_late_rejection_alerts_management_without_changing_completed_ledger(db, reported_status):
    reservation = _reservation(db)
    link = _link(db, reservation)
    users_by_role = {
        role: _management_member(db, hotel_id=reservation.hotel_id, user_id=user_id, role=role)
        for role, user_id in (("owner", 4101), ("co_owner", 4102), ("manager", 4103))
    }
    receptionist = _management_member(db, hotel_id=reservation.hotel_id, user_id=4104, role="receptionist")
    # Required payment discrepancies still appear in the in-app inbox if an
    # operator disabled routine notifications for this event type.
    db.add(
        NotificationPreference(
            hotel_id=reservation.hotel_id,
            user_id=users_by_role["manager"].id,
            event_type="payment.completed_status_discrepancy",
            in_app_enabled=False,
        )
    )
    db.flush()

    external_payment_id = "mp-payment-late-rejected"

    def provider_result(status: str):
        return lambda *_args, **_kwargs: {
            "id": external_payment_id,
            "external_reference": link.external_reference,
            "status": status,
            "transaction_amount": "40.00",
            "currency_id": "ARS",
        }

    approved = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-late-rejected-approved",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result("approved"),
    )
    assert approved["status"] == "ok"
    assert db.query(Transaction).count() == 1
    assert link.collected_amount == Decimal("40.00")

    # Model a reservation cancellation after a partial collection. Its open
    # provider link is closed, but an already-completed payment still needs
    # late-status reconciliation for the management alert.
    cancel_link(db, reservation.hotel_id, link.id, reason="reservation cancelled")
    reservation.status = ReservationStatusEnum.CANCELLED
    db.flush()
    transaction_before = db.query(Transaction).one()
    balance_before = balance_due_from_transactions(db, reservation.hotel_id, reservation.id)

    rejected = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-late-rejected-failed",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result(reported_status),
    )

    assert rejected["status"] == "review_required"
    assert rejected["alert_queued"] is True
    payment = db.query(Payment).one()
    assert payment.status == "completed"
    assert link.status == "cancelled"
    assert link.collected_amount == Decimal("40.00")
    assert reservation.status == ReservationStatusEnum.CANCELLED
    rejected_event = db.query(PaymentWebhookEvent).filter_by(webhook_id="mp-hook-late-rejected-failed").one()
    assert rejected_event.processed is True
    assert rejected_event.processing_error is None
    assert balance_due_from_transactions(db, reservation.hotel_id, reservation.id) == balance_before
    transactions_after = db.query(Transaction).all()
    assert len(transactions_after) == 1
    assert transactions_after[0].id == transaction_before.id
    assert transactions_after[0].amount == transaction_before.amount
    assert transactions_after[0].status == TransactionStatusEnum.COMPLETED
    assert transactions_after[0].transaction_type.value != "refund"

    outbox_rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.hotel_id == reservation.hotel_id,
            NotificationOutbox.event_type == "payment.completed_status_discrepancy",
        )
        .all()
    )
    assert {row.recipient_user_id for row in outbox_rows} == {
        users_by_role["owner"].id,
        users_by_role["co_owner"].id,
        users_by_role["manager"].id,
    }
    assert {row.channel for row in outbox_rows} == {NotificationChannelEnum.IN_APP}
    assert all(row.entity_type == "reservation" and row.entity_id == reservation.id for row in outbox_rows)
    assert all(row.severity.value == "critical" for row in outbox_rows)
    assert all(external_payment_id not in (row.title + (row.body or "") + (row.payload or "")) for row in outbox_rows)
    assert json.loads(outbox_rows[0].payload) == {
        "event_id": rejected_event.id,
        "payment_id": payment.id,
        "payment_link_id": link.id,
        "reservation_id": reservation.id,
        "status": "failed",
    }

    # The ordinary notification worker materializes durable outbox rows into
    # the inbox; replaying the same delivery or a second provider event for
    # this payment must not create another inbox item.
    from app.services.notification_service import process_pending_outbox

    process_pending_outbox(db)
    inbox_rows = (
        db.query(Notification)
        .filter(Notification.event_type == "payment.completed_status_discrepancy")
        .all()
    )
    assert len(inbox_rows) == 3
    assert receptionist.id not in {row.recipient_user_id for row in inbox_rows}
    for row in inbox_rows:
        assert row.entity_type == "reservation"
        assert row.entity_id == reservation.id
        assert external_payment_id not in (row.title + (row.body or "") + (row.payload or ""))

    duplicate_delivery = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-late-rejected-failed",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=lambda *_args, **_kwargs: pytest.fail("duplicate webhook must not call the provider"),
    )
    second_provider_event = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-late-rejected-replay",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result("failed"),
    )
    assert duplicate_delivery["duplicate"] is True
    assert second_provider_event["status"] == "review_required"
    assert db.query(NotificationOutbox).filter(
        NotificationOutbox.event_type == "payment.completed_status_discrepancy"
    ).count() == 3
    assert db.query(Notification).filter(
        Notification.event_type == "payment.completed_status_discrepancy"
    ).count() == 3
    assert db.query(Transaction).count() == 1


def test_webhook_body_rejection_does_not_override_provider_verified_approval(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    external_payment_id = "mp-payment-provider-status-wins"
    verified_approved = {
        "id": external_payment_id,
        "external_reference": link.external_reference,
        "status": "approved",
        "transaction_amount": "100.00",
        "currency_id": "ARS",
    }

    ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-provider-status-approved",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=lambda *_args, **_kwargs: verified_approved,
    )
    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-provider-status-contradiction",
        payload={
            "type": "payment",
            "data": {"id": external_payment_id},
            "status": "rejected",
            "amount": "100.00",
            "currency": "ARS",
        },
        payment_link_id=link.id,
        provider_fetcher=lambda *_args, **_kwargs: verified_approved,
    )

    assert result["status"] == "ok"
    assert db.query(Payment).one().status == "completed"
    assert db.query(Transaction).count() == 1
    assert db.query(NotificationOutbox).filter(
        NotificationOutbox.event_type == "payment.completed_status_discrepancy"
    ).count() == 0


def test_rejected_payment_cannot_be_flipped_to_completed_by_later_webhook(db):
    """A payment already recorded as rejected/failed must not silently become
    completed from a later webhook for the same external payment id."""
    reservation = _reservation(db)
    link = _link(db, reservation)
    rejected_payload = {
        "webhook_id": "mp-hook-rej-1",
        "payment_id": "mp-payment-rej",
        "status": "rejected",
        "amount": "100.00",
        "currency": "ARS",
    }
    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-rej-1",
        payload=rejected_payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link, status="rejected"),
    )

    approved_payload = {
        "webhook_id": "mp-hook-rej-2-suspicious",
        "payment_id": "mp-payment-rej",
        "status": "approved",
        "amount": "100.00",
        "currency": "ARS",
    }
    ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-rej-2-suspicious",
        payload=approved_payload,
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link),
    )

    payment = db.query(Payment).filter(Payment.external_payment_id == "mp-payment-rej").one()
    assert payment.status == "failed"
    assert db.query(Transaction).count() == 0


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


def test_minimal_mercadopago_notification_is_verified_by_provider_fetcher(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    link.gateway_response = {"pms_account_id": "collector-1"}
    fetched = {
        "id": "mp-payment-fetched",
        "external_reference": link.external_reference,
        "status": "approved",
        "transaction_amount": 100.0,
        "currency_id": "ARS",
        "collector_id": "collector-1",
    }

    result = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-minimal",
        payload={"type": "payment", "data": {"id": "mp-payment-fetched"}},
        payment_link_id=link.id,
        provider_fetcher=lambda _db, _hotel_id, _payment_id: fetched,
    )

    assert result["status"] == "ok"
    assert db.query(Payment).one().external_payment_id == "mp-payment-fetched"


def test_provider_verified_payment_must_match_selected_link_external_reference(db):
    reservation = _reservation(db)
    source_link = _link(db, reservation)

    target_guest = Guest(first_name="Target", last_name="Guest", hotel_id=reservation.hotel_id)
    db.add(target_guest)
    db.flush()
    target_reservation = Reservation(
        hotel_id=reservation.hotel_id,
        confirmation_code="WH-1-TARGET",
        guest_id=target_guest.id,
        category_id=reservation.category_id,
        check_in_date=date(2026, 8, 5),
        check_out_date=date(2026, 8, 7),
        total_amount=Decimal("300.00"),
        deposit_amount=Decimal("90.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(target_reservation)
    db.flush()
    target_link = PaymentLink(
        hotel_id=reservation.hotel_id,
        reservation_id=target_reservation.id,
        provider="mercado_pago",
        link_code="plink-cross-reference-target",
        requested_amount=Decimal("100.00"),
        recipient_email="target@example.com",
        status="pending",
        execution_mode="provider",
        payable=True,
        external_checkout_url="https://mp.test/checkout/target",
        external_reference="signed-ref-target",
    )
    db.add(target_link)
    db.flush()

    with pytest.raises(PaymentWebhookError, match="referencia del pago verificado"):
        ingest_webhook(
            db,
            hotel_id=reservation.hotel_id,
            provider="mercado_pago",
            webhook_id="mp-hook-cross-reference",
            payload={
                "type": "payment",
                "external_reference": target_link.external_reference,
                "payment_id": "mp-payment-owned-by-source-link",
                "status": "approved",
                "amount": "100.00",
                "currency": "ARS",
            },
            provider_fetcher=lambda *_args, **_kwargs: {
                "id": "mp-payment-owned-by-source-link",
                "external_reference": source_link.external_reference,
                "status": "approved",
                "transaction_amount": "100.00",
                "currency_id": "ARS",
            },
        )

    assert db.query(Payment).count() == 0
    assert db.query(Transaction).count() == 0
    assert db.query(PaymentWebhookEvent).count() == 0
    assert target_link.collected_amount == Decimal("0.00")


def test_mercadopago_resource_id_precedes_legacy_root_id(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    root_event_id = "mp-event-root-123"
    resource_payment_id = "mp-payment-resource-456"
    fetched_payment_ids = []

    def provider_fetcher(_db, _hotel_id, payment_id):
        fetched_payment_ids.append(payment_id)
        return {
            "id": payment_id,
            "external_reference": link.external_reference,
            "status": "approved",
            "transaction_amount": 100.0,
            "currency_id": "ARS",
        }

    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-notification-event-789",
        payload={
            "id": root_event_id,
            "type": "payment",
            "external_reference": link.external_reference,
            "data": {"id": resource_payment_id},
        },
        payment_link_id=link.id,
        provider_fetcher=provider_fetcher,
    )

    assert result["status"] == "ok"
    assert fetched_payment_ids == [resource_payment_id]
    payment = db.query(Payment).one()
    assert payment.external_payment_id == resource_payment_id
    event = db.query(PaymentWebhookEvent).one()
    assert event.webhook_id == "mp-notification-event-789"
    assert event.raw_payload["id"] == root_event_id
    transaction = db.query(Transaction).one()
    assert transaction.idempotency_key == f"mercado_pago:{resource_payment_id}:completed"


def test_gateway_webhook_persists_reconciliation_projection_without_provider_pii(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    link.gateway_response = {"pms_account_id": "collector-1"}
    sensitive_marker = "SYNTHETIC_PRIVATE_PROVIDER_VALUE"
    event_payload = {
        "id": "mp-payment-privacy-1",
        "type": "payment",
        "action": "payment.updated",
        "date_created": "2026-08-02T10:00:00Z",
        "api_version": "v1",
        "live_mode": True,
        "external_reference": link.external_reference,
        "data": {"id": "mp-payment-privacy-1", "private": sensitive_marker},
        "payer": {"email": sensitive_marker, "phone": sensitive_marker},
        "metadata": {"guest_name": sensitive_marker},
    }
    provider_response = {
        "id": "mp-payment-privacy-1",
        "external_reference": link.external_reference,
        "status": "approved",
        "status_detail": "accredited",
        "transaction_amount": 100.0,
        "currency_id": "ARS",
        "date_created": "2026-08-02T09:59:00Z",
        "date_approved": "2026-08-02T10:00:00Z",
        "date_last_updated": "2026-08-02T10:01:00Z",
        "collector_id": "collector-1",
        "transaction_amount_refunded": 0.0,
        "payer": {"email": sensitive_marker, "phone": sensitive_marker},
        "card": {"last_four_digits": "4242", "cardholder": {"name": sensitive_marker}},
        "additional_info": {"items": [{"title": sensitive_marker}]},
        "point_of_interaction": {"transaction_data": {"ticket": sensitive_marker}},
        "metadata": {"guest_name": sensitive_marker, "booking_note": sensitive_marker},
    }

    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-event-privacy-1",
        payload=event_payload,
        payment_link_id=link.id,
        provider_fetcher=lambda _db, _hotel_id, _payment_id: provider_response,
    )

    assert result["status"] == "ok"
    payment = db.query(Payment).one()
    expected_payment_response = {
        "id": "mp-payment-privacy-1",
        "external_reference": link.external_reference,
        "status": "approved",
        "status_detail": "accredited",
        "transaction_amount": 100.0,
        "currency_id": "ARS",
        "date_created": "2026-08-02T09:59:00Z",
        "date_approved": "2026-08-02T10:00:00Z",
        "date_last_updated": "2026-08-02T10:01:00Z",
        "collector_id": "collector-1",
        "transaction_amount_refunded": 0.0,
    }
    assert payment.external_payment_id == "mp-payment-privacy-1"
    assert payment.status == "completed"
    assert payment.amount == Decimal("100.00")
    assert payment.gateway_response == expected_payment_response

    event = db.query(PaymentWebhookEvent).one()
    assert event.processed is True
    assert event.event_type == "payment"
    assert event.raw_payload == {
        "id": "mp-payment-privacy-1",
        "type": "payment",
        "action": "payment.updated",
        "api_version": "v1",
        "live_mode": True,
        "external_reference": link.external_reference,
        "data": {"id": "mp-payment-privacy-1"},
    }

    transaction = db.query(Transaction).one()
    assert transaction.status == TransactionStatusEnum.COMPLETED
    assert transaction.amount == Decimal("100.00")
    assert transaction.idempotency_key == "mercado_pago:mp-payment-privacy-1:completed"
    assert json.loads(transaction.gateway_response) == expected_payment_response

    persisted_json = json.dumps(
        [payment.gateway_response, event.raw_payload, transaction.gateway_response],
        sort_keys=True,
    )
    assert sensitive_marker not in persisted_json
    assert '"payer"' not in persisted_json
    assert '"card"' not in persisted_json
    assert '"metadata"' not in persisted_json
    assert '"additional_info"' not in persisted_json
    assert '"point_of_interaction"' not in persisted_json


def test_gateway_webhook_persists_fixed_processing_error_without_exception_details(db, monkeypatch):
    reservation = _reservation(db)
    link = _link(db, reservation)
    webhook_id = "mp-hook-processing-error"
    sensitive_marker = "SYNTHETIC_INTERNAL_PRIVATE_MARKER"

    def fail_transaction_processing(*_args, **_kwargs):
        raise RuntimeError(f"provider response contained {sensitive_marker}")

    monkeypatch.setattr(
        payment_webhook_service,
        "_ensure_completed_transaction",
        fail_transaction_processing,
    )

    with pytest.raises(RuntimeError, match=sensitive_marker):
        ingest_webhook(
            db,
            hotel_id=reservation.hotel_id,
            provider="mercado_pago",
            webhook_id=webhook_id,
            payload={
                "payment_id": "mp-payment-processing-error",
                "status": "approved",
                "amount": "100.00",
                "currency": "ARS",
            },
            payment_link_id=link.id,
            provider_fetcher=_provider_result(link),
        )

    # A caller may handle the failure and commit the event for retry/audit.
    db.commit()
    event = db.query(PaymentWebhookEvent).filter_by(webhook_id=webhook_id).one()
    assert event.processed is False
    assert event.processing_error == "payment_webhook_processing_failed"
    assert sensitive_marker not in event.processing_error


@pytest.mark.parametrize(
    ("amount", "expected_link_status"),
    [("40.00", "cancelled"), ("100.00", "completed")],
)
def test_verified_late_success_is_recorded_without_reopening_cancelled_link(
    db, amount: str, expected_link_status: str
):
    reservation = _reservation(db)
    link = _link(db, reservation)
    cancel_link(db, 1, link.id, reason="reservation cancelled")
    fetched = {
        "id": "mp-payment-after-cancel",
        "external_reference": link.external_reference,
        "status": "approved",
        "transaction_amount": amount,
        "currency_id": "ARS",
    }

    result = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id=f"mp-hook-after-cancel-{amount}",
        payload={"type": "payment", "data": {"id": "mp-payment-after-cancel"}},
        payment_link_id=link.id,
        provider_fetcher=lambda _db, _hotel_id, _payment_id: fetched,
    )

    assert result["status"] == "ok"
    payment = db.query(Payment).one()
    assert payment.status == "completed"
    assert db.query(Transaction).one().status == TransactionStatusEnum.COMPLETED
    db.refresh(link)
    assert link.collected_amount == Decimal(amount)
    assert link.status == expected_link_status
    assert link.payable is False
    assert link.cancelled_at is not None


def test_verified_late_success_on_cancelled_reservation_is_recorded_for_manual_review(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    cancel_link(db, 1, link.id, reason="reservation cancelled")
    reservation.status = ReservationStatusEnum.CANCELLED
    db.flush()

    fetched = {
        "id": "mp-payment-after-reservation-cancel",
        "external_reference": link.external_reference,
        "status": "approved",
        "transaction_amount": 40.0,
        "currency_id": "ARS",
    }
    result = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-after-reservation-cancel",
        payload={"type": "payment", "data": {"id": "mp-payment-after-reservation-cancel"}},
        payment_link_id=link.id,
        provider_fetcher=lambda _db, _hotel_id, _payment_id: fetched,
    )

    assert result["status"] == "ok"
    assert db.query(Transaction).one().status == TransactionStatusEnum.COMPLETED
    db.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.amount_paid == Decimal("40.00")
    assert reservation.requires_manual_review is True
    assert reservation.settlement_status == "review_cancellation"
    db.refresh(link)
    assert link.status == "cancelled"
    assert link.payable is False


def test_cancel_during_provider_verification_is_seen_before_payment_settlement(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    fetched = {
        "id": "mp-payment-cancel-race",
        "external_reference": link.external_reference,
        "status": "approved",
        "transaction_amount": 40.0,
        "currency_id": "ARS",
    }

    def verify_then_cancel(session, hotel_id, _payment_id):
        # Model the cancellation committing while the webhook waits on its
        # external provider verification call. The write path must refresh
        # reservation and link state after that boundary.
        reservation.status = ReservationStatusEnum.CANCELLED
        cancel_link(session, hotel_id, link.id, reason="reservation cancelled")
        session.flush()
        return fetched

    result = ingest_webhook(
        db,
        hotel_id=1,
        provider="mercado_pago",
        webhook_id="mp-hook-cancel-race",
        payload={"type": "payment", "data": {"id": "mp-payment-cancel-race"}},
        payment_link_id=link.id,
        provider_fetcher=verify_then_cancel,
    )

    assert result["status"] == "ok"
    payment = db.query(Payment).one()
    assert payment.status == "completed"
    assert db.query(Transaction).one().status == TransactionStatusEnum.COMPLETED
    db.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.amount_paid == Decimal("40.00")
    assert reservation.requires_manual_review is True
    db.refresh(link)
    assert link.status == "cancelled"
    assert link.payable is False


def test_mp_fields_untrusted_when_outbound_connections_are_disabled(db, monkeypatch):
    reservation = _reservation(db)
    link = _link(db, reservation)
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    with pytest.raises(
        RetryablePaymentWebhookError,
        match="conexiones salientes estan deshabilitadas",
    ):
        ingest_webhook(
            db,
            hotel_id=reservation.hotel_id,
            provider="mercado_pago",
            webhook_id="mp-hook-outbound-disabled",
            payload={
                "payment_id": "mp-unverified-outbound-disabled",
                "status": "approved",
                "amount": "100.00",
                "currency": "ARS",
            },
            payment_link_id=link.id,
        )

    assert db.query(Payment).count() == 0
    assert db.query(Transaction).count() == 0
    assert db.query(PaymentWebhookEvent).count() == 0
    assert link.collected_amount == Decimal("0.00")


def test_cancelled_payment_link_rejects_unverified_success_event(db, monkeypatch):
    reservation = _reservation(db)
    link = _link(db, reservation)
    cancel_link(db, 1, link.id, reason="reservation cancelled")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    with pytest.raises(
        RetryablePaymentWebhookError,
        match="conexiones salientes estan deshabilitadas",
    ):
        ingest_webhook(
            db,
            hotel_id=1,
            provider="mercado_pago",
            webhook_id="mp-hook-unverified-after-cancel",
            payload={
                "payment_id": "mp-unverified-after-cancel",
                "status": "approved",
                "amount": "100.00",
                "currency": "ARS",
            },
            payment_link_id=link.id,
        )

    assert db.query(Payment).count() == 0
    assert db.query(PaymentWebhookEvent).count() == 0


def test_mercadopago_notification_rejects_different_collector_account(db):
    reservation = _reservation(db)
    link = _link(db, reservation)
    link.gateway_response = {"pms_account_id": "collector-1"}

    with pytest.raises(PaymentWebhookError, match="cuenta de Mercado Pago distinta"):
        ingest_webhook(
            db,
            hotel_id=1,
            provider="mercado_pago",
            webhook_id="mp-hook-wrong-account",
            payload={
                "payment_id": "mp-payment-wrong-account",
                "status": "approved",
                "amount": 100.0,
                "currency": "ARS",
                "collector_id": "collector-2",
            },
            payment_link_id=link.id,
            provider_fetcher=_provider_result(link, collector_id="collector-2"),
        )


def test_legacy_mp_link_without_snapshot_credits_exact_provider_amount_without_current_surcharge_or_fx(
    db,
    monkeypatch,
):
    reservation = _reservation(db)
    reservation.currency_code = "USD"
    link = _link(db, reservation)
    link.currency = "USD"
    db.add(
        PaymentSurcharge(
            hotel_id=reservation.hotel_id,
            payment_method="mercado_pago",
            surcharge_type=PaymentSurchargeTypeEnum.FIXED,
            amount=Decimal("1000.00"),
            currency_code="ARS",
            is_active=True,
        )
    )
    db.flush()

    conversion_calls = []

    def current_fx_quote(*_args, **_kwargs):
        conversion_calls.append(True)
        return Decimal("0.02"), {"source_quote": {"market": "blue", "side": "venta"}}

    monkeypatch.setattr(payment_service, "_payment_conversion_rate", current_fx_quote)
    external_payment_id = "mp-legacy-no-snapshot-exact"
    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-no-snapshot-exact",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=_provider_result(link, amount="100.00", currency="USD"),
    )

    assert result["status"] == "ok"
    payment = db.query(Payment).one()
    assert payment.amount == Decimal("100.00")
    assert payment.currency == "USD"
    assert payment.gateway_response["transaction_amount"] == "100.00"
    transaction = db.query(Transaction).one()
    assert transaction.amount == Decimal("100.00")
    assert transaction.tender_amount == Decimal("100.00")
    assert transaction.tender_currency == "USD"
    assert transaction.fee_amount == Decimal("0.00")
    assert transaction.gross_amount == Decimal("100.00")
    assert json.loads(transaction.gateway_response)["transaction_amount"] == "100.00"
    assert conversion_calls == []


def test_legacy_mp_link_without_fx_snapshot_persists_payment_for_manual_review_without_ledger_conversion(
    db,
    monkeypatch,
):
    reservation = _reservation(db)
    link = _link(db, reservation)
    link.currency = "USD"
    link.requested_amount = Decimal("80.00")
    manager = _management_member(db, hotel_id=reservation.hotel_id, user_id=4201, role="manager")
    db.flush()

    def current_fx_quote(*_args, **_kwargs):
        pytest.fail("legacy payment reconciliation must not query the current FX quote")

    monkeypatch.setattr(payment_service, "_payment_conversion_rate", current_fx_quote)
    external_payment_id = "mp-legacy-cross-currency-review"
    provider_calls = []

    def provider_result(*args, **kwargs):
        provider_calls.append(True)
        return _provider_result(link, amount="80.00", currency="USD")(*args, **kwargs)

    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-cross-currency-review",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result,
    )

    assert result["status"] == "review_required"
    assert result["reason"] == "legacy_link_missing_payment_fx_snapshot_review_required"
    assert result["alert_queued"] is True
    assert provider_calls == [True]
    payment = db.query(Payment).one()
    assert payment.amount == Decimal("80.00")
    assert payment.currency == "USD"
    assert payment.gateway_response["transaction_amount"] == "80.00"
    assert db.query(Transaction).count() == 0
    db.refresh(link)
    assert link.collected_amount == Decimal("80.00")
    assert link.status == "completed"
    assert link.payable is False
    event = db.query(PaymentWebhookEvent).one()
    assert event.processed is True
    assert event.processing_error == result["reason"]
    outbox = db.query(NotificationOutbox).filter_by(
        hotel_id=reservation.hotel_id,
        event_type="payment.provider_reconciliation_review_required",
    ).one()
    assert outbox.recipient_user_id == manager.id
    assert outbox.channel == NotificationChannelEnum.IN_APP
    assert outbox.entity_type == "reservation"
    assert outbox.entity_id == reservation.id
    assert external_payment_id not in outbox.title + (outbox.body or "") + (outbox.payload or "")

    replay_with_new_event_id = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-cross-currency-review-replay",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result,
    )
    assert replay_with_new_event_id["status"] == "review_required"
    assert replay_with_new_event_id["duplicate"] is False
    assert provider_calls == [True, True]
    assert db.query(Payment).count() == 1
    assert db.query(PaymentWebhookEvent).count() == 2
    assert db.query(NotificationOutbox).filter_by(
        event_type="payment.provider_reconciliation_review_required"
    ).count() == 1

    duplicate = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-cross-currency-review",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=lambda *_args, **_kwargs: pytest.fail("duplicate webhook must not call the provider"),
    )
    assert duplicate["status"] == "review_required"
    assert duplicate["duplicate"] is True
    assert db.query(Payment).count() == 1
    assert db.query(PaymentWebhookEvent).count() == 2
    assert db.query(NotificationOutbox).filter_by(
        event_type="payment.provider_reconciliation_review_required"
    ).count() == 1
    assert db.query(Transaction).count() == 0


def test_legacy_mp_capture_above_link_and_reservation_balance_is_saved_for_review_without_allocation(db):
    reservation = _reservation(db)
    reservation.total_amount = Decimal("100.00")
    link = _link(db, reservation)
    link.requested_amount = Decimal("100.00")
    manager = _management_member(db, hotel_id=reservation.hotel_id, user_id=4202, role="manager")
    db.flush()

    external_payment_id = "mp-legacy-overpayment-review"
    provider_calls = []

    def provider_result(*args, **kwargs):
        provider_calls.append(True)
        return _provider_result(link, amount="103.00", currency="ARS")(*args, **kwargs)

    result = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-overpayment-review",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=provider_result,
    )

    assert result["status"] == "review_required"
    assert result["reason"] == "legacy_link_amount_exceeds_link_balance_review_required"
    assert result["alert_queued"] is True
    assert provider_calls == [True]
    payment = db.query(Payment).one()
    assert payment.status == "completed"
    assert payment.amount == Decimal("103.00")
    assert payment.currency == "ARS"
    assert payment.gateway_response["transaction_amount"] == "103.00"
    assert db.query(Transaction).count() == 0
    db.refresh(link)
    assert link.collected_amount == Decimal("103.00")
    assert link.status == "completed"
    assert link.payable is False
    event = db.query(PaymentWebhookEvent).one()
    assert event.processed is True
    assert event.processing_error == result["reason"]
    outbox = db.query(NotificationOutbox).filter_by(
        hotel_id=reservation.hotel_id,
        event_type="payment.provider_reconciliation_review_required",
    ).one()
    assert outbox.recipient_user_id == manager.id

    duplicate = ingest_webhook(
        db,
        hotel_id=reservation.hotel_id,
        provider="mercado_pago",
        webhook_id="mp-hook-legacy-overpayment-review",
        payload={"type": "payment", "data": {"id": external_payment_id}},
        payment_link_id=link.id,
        provider_fetcher=lambda *_args, **_kwargs: pytest.fail("duplicate webhook must not call the provider"),
    )
    assert duplicate["status"] == "review_required"
    assert duplicate["duplicate"] is True
    assert db.query(Payment).count() == 1
    assert db.query(PaymentWebhookEvent).count() == 1
    assert db.query(NotificationOutbox).filter_by(
        event_type="payment.provider_reconciliation_review_required"
    ).count() == 1
    assert db.query(Transaction).count() == 0
