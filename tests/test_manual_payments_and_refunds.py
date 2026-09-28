"""Regression coverage for in-person payments and financial step-up controls."""

from datetime import datetime, timezone
import importlib

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.reservation import ReservationSourceEnum, ReservationStatusEnum
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.cash_register_service import open_session
from app.services.permission_service import (
    PERMISSION_PAYMENT_REFUND,
    PERMISSION_RESERVATION_CANCEL_PAID,
)
from tests.test_payment_links_api import _reservation, client_with_db


def _manual_payment(
    client,
    reservation_id: int,
    *,
    method: str = "credit_card",
    key: str = "manual-card-payment-001",
    reference: str | None = None,
):
    payload = {
        "reservation_id": reservation_id,
        "amount": 30,
        "payment_method": method,
        "transaction_type": "partial_payment",
    }
    if reference is not None:
        payload["manual_reference"] = reference
    return client.post(
        "/api/payments/",
        json=payload,
        headers={"Idempotency-Key": key},
    )


def _step_up_header(ctx, permission_code: str, path: str) -> dict[str, str]:
    ticket = create_action_step_up_ticket(
        user_id=1,
        hotel_id=ctx["hotel_id"],
        token_version=0,
        permission_code=permission_code,
        method="POST",
        path=path,
    )
    return {"X-Action-Step-Up-Ticket": ticket}


@pytest.mark.parametrize("method", ["credit_card", "debit_card", "bank_transfer"])
def test_manual_in_person_payment_requires_reference_and_records_actor(client_with_db, method):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, f"MANUAL-{method.upper()}-1")
    db.get(HotelConfiguration, 1).enable_bank_transfer = True
    db.flush()

    missing_reference = _manual_payment(client, reservation.id, method=method, key=f"manual-{method}-payment-001")
    assert missing_reference.status_code == 400
    assert "reference" in missing_reference.json()["detail"].lower()
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0

    recorded = _manual_payment(
        client,
        reservation.id,
        method=method,
        key=f"manual-{method}-payment-001",
        reference="POS-482901",
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["status"] == "completed"
    assert recorded.json()["manual_reference"] == "POS-482901"

    transaction = db.query(Transaction).filter_by(reservation_id=reservation.id).one()
    assert transaction.payment_method.value == method
    assert transaction.status == TransactionStatusEnum.COMPLETED
    assert transaction.manual_reference == "POS-482901"
    assert transaction.created_by_user_id == 1

    duplicate_reference = _manual_payment(
        client,
        reservation.id,
        method=method,
        key=f"duplicate-{method}-payment-002",
        reference="pos-482901",
    )
    assert duplicate_reference.status_code == 400
    assert "already recorded" in duplicate_reference.json()["detail"].lower()
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1


def test_completed_manual_payment_retry_reuses_transaction_before_balance_validation(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "MANUAL-IDEMPOTENT-FULL-1")
    payload = {
        "reservation_id": reservation.id,
        "amount": float(reservation.total_amount),
        "payment_method": "credit_card",
        "transaction_type": "full_payment",
        "manual_reference": "POS-IDEMPOTENT-9001",
    }
    headers = {"Idempotency-Key": "manual-full-payment-once-001"}

    first = client.post("/api/payments/", json=payload, headers=headers)
    retry = client.post("/api/payments/", json=payload, headers=headers)
    changed_payload = client.post(
        "/api/payments/",
        json={**payload, "amount": float(reservation.total_amount) - 1},
        headers=headers,
    )

    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert changed_payload.status_code == 400
    assert "idempotency key" in changed_payload.json()["detail"].lower()
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1


def test_refund_requires_manager_permission_and_one_use_step_up(client_with_db):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, "MANUAL-REFUND-1")
    paid = _manual_payment(client, reservation.id, reference="POS-482902")
    assert paid.status_code == 201, paid.text

    refund_path = "/api/payments/"
    refund_payload = {
        "reservation_id": reservation.id,
        "amount": 30,
        "payment_method": "cash",
        "transaction_type": "refund",
        "refund_of_transaction_id": paid.json()["id"],
        "refund_reason": "Guest cancellation approved by manager",
    }
    headers = {"Idempotency-Key": "manager-refund-operation-001"}

    receptionist_refund = client.post(refund_path, json=refund_payload, headers=headers)
    assert receptionist_refund.status_code == 403

    open_session(db, hotel_id=1, opened_by_user_id=1, opening_balance=0)
    db.flush()
    ctx["role"] = "manager"

    missing_step_up = client.post(refund_path, json=refund_payload, headers=headers)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["permission_code"] == PERMISSION_PAYMENT_REFUND

    action_headers = {
        **headers,
        **_step_up_header(ctx, PERMISSION_PAYMENT_REFUND, refund_path),
    }
    approved = client.post(refund_path, json=refund_payload, headers=action_headers)
    assert approved.status_code == 201, approved.text
    assert approved.json()["transaction_type"] == "refund"
    assert approved.json()["status"] == "completed"
    assert approved.json()["refund_of_transaction_id"] == paid.json()["id"]
    assert approved.json()["refund_reason"] == refund_payload["refund_reason"]

    summary = client.get(f"/api/payments/summary/{reservation.id}")
    assert summary.status_code == 200, summary.text
    refund_summary = next(tx for tx in summary.json()["transactions"] if tx["type"] == "refund")
    assert refund_summary["refund_of_transaction_id"] == paid.json()["id"]
    assert "refund_reason" not in refund_summary

    replayed = client.post(refund_path, json=refund_payload, headers=action_headers)
    assert replayed.status_code == 428
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 2

    retry_headers = {
        **headers,
        **_step_up_header(ctx, PERMISSION_PAYMENT_REFUND, refund_path),
    }
    idempotent_retry = client.post(refund_path, json=refund_payload, headers=retry_headers)
    assert idempotent_retry.status_code == 201, idempotent_retry.text
    assert idempotent_retry.json()["id"] == approved.json()["id"]
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 2


def test_refund_cannot_exceed_original_payment_by_one_cent(client_with_db):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, "MANUAL-REFUND-CENT-CAP")
    paid = _manual_payment(
        client,
        reservation.id,
        key="manual-refund-cent-source",
        reference="POS-REFUND-CENT-SOURCE",
    )
    assert paid.status_code == 201, paid.text

    open_session(db, hotel_id=1, opened_by_user_id=1, opening_balance=100)
    db.flush()
    ctx["role"] = "manager"
    path = "/api/payments/"
    refund_payload = {
        "reservation_id": reservation.id,
        "amount": "30.01",
        "payment_method": "cash",
        "transaction_type": "refund",
        "refund_of_transaction_id": paid.json()["id"],
        "refund_reason": "Refund amount exceeds original payment",
    }

    response = client.post(
        path,
        json=refund_payload,
        headers={
            "Idempotency-Key": "manual-refund-cent-overrun",
            **_step_up_header(ctx, PERMISSION_PAYMENT_REFUND, path),
        },
    )

    assert response.status_code == 400, response.text
    assert "remaining refundable amount" in response.json()["detail"].lower()
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1
    db.refresh(reservation)
    assert reservation.amount_paid == 30


def test_cancelling_paid_reservation_requires_manager_step_up_without_auto_refund(client_with_db):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, "PAID-CANCEL-1")
    db.add(
        Transaction(
            hotel_id=1,
            reservation_id=reservation.id,
            amount=30,
            currency="ARS",
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            payment_method=PaymentMethodEnum.CREDIT_CARD,
            status=TransactionStatusEnum.COMPLETED,
            processed_at=datetime.now(timezone.utc),
            created_by_user_id=1,
        )
    )
    db.commit()

    path = f"/api/reservations/{reservation.id}/cancel"
    receptionist_cancel = client.post(path)
    assert receptionist_cancel.status_code == 403
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1

    ctx["role"] = "manager"
    missing_step_up = client.post(path)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["permission_code"] == PERMISSION_RESERVATION_CANCEL_PAID

    cancelled = client.post(
        path,
        headers=_step_up_header(ctx, PERMISSION_RESERVATION_CANCEL_PAID, path),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    # Cancellation records the decision but never silently issues a refund.
    transactions = db.query(Transaction).filter_by(reservation_id=reservation.id).all()
    assert len(transactions) == 1
    assert transactions[0].transaction_type == TransactionTypeEnum.PARTIAL_PAYMENT


@pytest.mark.parametrize(
    "cancel_path",
    ["/api/reservations/{id}/cancel", "/api/bookings/{id}/cancel"],
)
def test_both_cancel_routes_protect_legacy_paid_reservations(client_with_db, cancel_path):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, f"LEGACY-PAID-CANCEL-{cancel_path.split('/')[2]}")
    reservation.status = ReservationStatusEnum.DEPOSIT_PAID
    reservation.amount_paid = 30
    db.commit()

    path = cancel_path.format(id=reservation.id)
    receptionist_attempt = client.post(path)
    assert receptionist_attempt.status_code == 403
    db.refresh(reservation)
    assert reservation.status.value == "deposit_paid"
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0

    ctx["role"] = "manager"
    missing_step_up = client.post(path)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["permission_code"] == PERMISSION_RESERVATION_CANCEL_PAID

    approved = client.post(
        path,
        headers=_step_up_header(ctx, PERMISSION_RESERVATION_CANCEL_PAID, path),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "cancelled"
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0


@pytest.mark.parametrize(
    "cancel_path",
    ["/api/reservations/{id}/cancel", "/api/bookings/{id}/cancel"],
)
def test_paid_cancel_rechecks_reservation_after_step_up_commit(client_with_db, monkeypatch, cancel_path):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, f"CANCEL-LOCK-RECHECK-{cancel_path.split('/')[2]}")
    reservation.status = ReservationStatusEnum.DEPOSIT_PAID
    reservation.amount_paid = 30
    db.commit()

    module_name = "app.api.reservations" if "/reservations/" in cancel_path else "app.api.bookings"
    route_module = importlib.import_module(module_name)

    def simulate_concurrent_checkin(_request, session, _context, _permission):
        current = session.get(type(reservation), reservation.id)
        current.status = ReservationStatusEnum.CHECKED_IN
        session.commit()  # models the step-up ticket's commit releasing the first row lock

    monkeypatch.setattr(route_module, "authorize_permission", simulate_concurrent_checkin)
    ctx["role"] = "manager"
    response = client.post(cancel_path.format(id=reservation.id))

    assert response.status_code == 409, response.text
    db.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.CHECKED_IN


def test_paid_booking_cannot_be_soft_deleted(client_with_db):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, "PAID-BOOKING-NO-SOFT-DELETE")
    reservation.status = ReservationStatusEnum.DEPOSIT_PAID
    reservation.amount_paid = 30
    db.commit()
    ctx["role"] = "manager"

    response = client.delete(f"/api/bookings/{reservation.id}")

    assert response.status_code == 409
    assert "cancellation workflow" in response.json()["detail"]
    db.refresh(reservation)
    assert reservation.deleted_at is None


def test_paid_ota_reservation_cannot_be_rebooked_without_payment_transfer(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "PAID-OTA-NO-REBOOK")
    reservation.source = ReservationSourceEnum.OTHER_OTA
    reservation.source_provider_code = "booking"
    reservation.external_id = "BKG-PAID-TRANSFER-MISSING"
    reservation.status = ReservationStatusEnum.DEPOSIT_PAID
    reservation.amount_paid = 30
    db.commit()

    response = client.post(
        f"/api/reservations/{reservation.id}/rebook-direct",
        json={"target_category_id": reservation.category_id},
    )

    assert response.status_code == 409, response.text
    assert "does not transfer or reconcile payments" in response.json()["detail"]
    db.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.DEPOSIT_PAID
