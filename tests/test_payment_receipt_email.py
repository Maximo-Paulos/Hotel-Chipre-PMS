"""Receipt PDF and email API tests use mocked provider/local transports only."""

import base64
import json
import stat
from email import policy
from email.parser import BytesParser

import pytest

from app.models.guest import Guest
from app.models.payment_receipt_email_delivery import PaymentReceiptEmailDelivery
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.services.permission_service import PERMISSION_CASH_OPERATE, set_override
from app.services.action_step_up_service import create_action_step_up_ticket
from tests.test_payment_links_api import _reservation, client_with_db


@pytest.fixture
def local_simulation_email(monkeypatch, tmp_path):
    from app.config import get_settings

    outbox = tmp_path / "private-outbox" / "payment-receipts.jsonl"
    for name, value in {
        "APP_ENV": "development",
        "EXTERNAL_EFFECTS_ENABLED": "false",
        "LOCAL_SIMULATION_CLOCK_ENABLED": "true",
        "LOCAL_SIMULATION_CLOCK_HOTEL_ID": "1",
        "DATABASE_URL": "sqlite:///:memory:",
        "DEV_EMAIL_OUTBOX_PATH": str(outbox),
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield outbox
    get_settings.cache_clear()


def _completed_payment(client, reservation_id: int, reference: str = "POS-RECEIPT-MAIL-1"):
    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": reservation_id,
            "amount": 30,
            "payment_method": "credit_card",
            "transaction_type": "partial_payment",
            "manual_reference": reference,
        },
        headers={"Idempotency-Key": "receipt-email-payment-001"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _mock_receipt_email(monkeypatch):
    from app.services import payment_receipt_email_service as email_service

    calls = []
    monkeypatch.setattr(email_service, "ensure_hotel_gmail_ready", lambda *_args: None)

    def fake_send(db, hotel_id, *, to, subject, body, attachments=()):
        calls.append(
            {
                "hotel_id": hotel_id,
                "to": to,
                "subject": subject,
                "body": body,
                "attachments": tuple(attachments),
            }
        )
        return type("SendResult", (), {"provider_message_id": "gmail-message-fixture"})()

    monkeypatch.setattr(email_service, "send_hotel_email", fake_send)
    return calls


def _receipt_headers(transaction_id: int, idempotency_key: str, *, hotel_id: int = 1) -> dict[str, str]:
    path = f"/api/payments/transactions/{transaction_id}/receipt/email"
    return {
        "Idempotency-Key": idempotency_key,
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=1,
            hotel_id=hotel_id,
            token_version=0,
            permission_code="payment:receipt_email",
            method="POST",
            path=path,
        ),
    }


def test_receipt_email_sends_persisted_receipt_once_and_records_auditable_outcome(
    client_with_db, monkeypatch
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-1")
    guest = db.get(Guest, reservation.guest_id)
    guest.email = "guest@example.com"
    paid = _completed_payment(client, reservation.id)
    transaction = db.get(Transaction, paid["id"])
    transaction.gross_amount = 31.50
    transaction.fee_amount = 1.50
    db.flush()

    calls = _mock_receipt_email(monkeypatch)
    payload = {"recipient_email": "accounts@company.com"}
    path = f"/api/payments/transactions/{transaction.id}/receipt/email"
    first = client.post(
        path,
        json=payload,
        headers=_receipt_headers(transaction.id, "receipt-email-once-0001"),
    )
    replay = client.post(
        path,
        json=payload,
        headers=_receipt_headers(transaction.id, "receipt-email-once-0001"),
    )
    changed_recipient = client.post(
        path,
        json={"recipient_email": "other@example.com"},
        headers=_receipt_headers(transaction.id, "receipt-email-once-0001"),
    )

    assert first.status_code == 200, first.text
    assert first.json() == {
        "transaction_id": transaction.id,
        "status": "sent",
        "delivery_mode": "provider",
        "replayed": False,
    }
    assert replay.status_code == 200, replay.text
    assert replay.json() == {
        "transaction_id": transaction.id,
        "status": "sent",
        "delivery_mode": "provider",
        "replayed": True,
    }
    assert changed_recipient.status_code == 409
    assert len(calls) == 1
    assert calls[0]["hotel_id"] == 1
    assert calls[0]["to"] == "accounts@company.com"
    assert "RECEIPT-EMAIL-1" in calls[0]["subject"]
    assert "Importe: 31.50 ARS" in calls[0]["body"]
    assert "POS-RECEIPT-MAIL-1" not in calls[0]["body"]

    delivery = db.query(PaymentReceiptEmailDelivery).one()
    assert delivery.hotel_id == 1
    assert delivery.transaction_id == transaction.id
    assert delivery.actor_user_id == 1
    assert delivery.status == "sent"
    assert delivery.provider_message_id == "gmail-message-fixture"
    assert delivery.completed_at is not None
    assert len(delivery.idempotency_key_hash) == 64
    assert len(delivery.recipient_fingerprint) == 64
    assert "guest@example.com" not in repr(delivery.__dict__)


def test_receipt_pdf_download_has_safe_headers_and_email_reuses_exact_pdf_bytes(
    client_with_db, monkeypatch
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-PDF-EMAIL-1")
    paid = _completed_payment(client, reservation.id, reference="POS-RECEIPT-PDF-1")
    transaction_id = paid["id"]
    transaction = db.get(Transaction, transaction_id)
    transaction.tender_amount = 20
    transaction.tender_currency = "USD"
    transaction.amount = 30700
    transaction.currency = "ARS"
    transaction.gross_amount = 20
    transaction.fx_rate_snapshot = 0.000651
    db.flush()

    downloaded = client.get(f"/api/payments/transactions/{transaction_id}/receipt.pdf")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.headers["content-disposition"] == (
        f'attachment; filename="comprobante-pago-{transaction_id}.pdf"'
    )
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert downloaded.content.startswith(b"%PDF-")
    assert b"Referencia manual:" in downloaded.content
    assert b"POS-RECEIPT-PDF-1" in downloaded.content
    assert b"Importe aplicado:" in downloaded.content
    assert b"30700.00 ARS" in downloaded.content
    assert b"Cotizaci" in downloaded.content
    assert b"1 ARS = 0.000651 USD" in downloaded.content

    calls = _mock_receipt_email(monkeypatch)
    sent = client.post(
        f"/api/payments/transactions/{transaction_id}/receipt/email",
        json={"recipient_email": "accounting@company.com"},
        headers=_receipt_headers(transaction_id, "receipt-pdf-exact-bytes-001"),
    )
    assert sent.status_code == 200, sent.text
    attachment, = calls[0]["attachments"]
    assert attachment.filename == f"comprobante-pago-{transaction_id}.pdf"
    assert attachment.content_type == "application/pdf"
    assert attachment.content == downloaded.content


def test_receipt_pdf_is_hidden_across_tenants_and_denied_without_cash_permission(client_with_db):
    client, db, ctx = client_with_db
    reservation_b = _reservation(db, 2, "RECEIPT-PDF-TENANT-B")
    ctx["hotel_id"] = 2
    paid = _completed_payment(client, reservation_b.id, reference="POS-RECEIPT-PDF-TENANT-B")
    ctx["hotel_id"] = 1

    hidden = client.get(f"/api/payments/transactions/{paid['id']}/receipt.pdf")
    assert hidden.status_code == 404
    assert "RECEIPT-PDF-TENANT-B" not in hidden.text

    reservation_a = _reservation(db, 1, "RECEIPT-PDF-PERMISSION")
    paid_a = _completed_payment(client, reservation_a.id, reference="POS-RECEIPT-PDF-PERMISSION")
    set_override(db, 1, "receptionist", PERMISSION_CASH_OPERATE, False, user_id=1)
    db.commit()
    denied = client.get(f"/api/payments/transactions/{paid_a['id']}/receipt.pdf")
    assert denied.status_code == 403


def test_local_simulation_captures_test_email_and_pdf_without_provider_calls(
    client_with_db, monkeypatch, local_simulation_email
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-LOCAL-CAPTURE")
    paid = _completed_payment(client, reservation.id, reference="POS-RECEIPT-LOCAL-CAPTURE")
    transaction_id = paid["id"]
    download = client.get(f"/api/payments/transactions/{transaction_id}/receipt.pdf")
    assert download.status_code == 200

    from app.services import payment_receipt_email_service as email_service

    def forbidden_provider_call(*_args, **_kwargs):
        raise AssertionError("local simulation must not access Gmail")

    monkeypatch.setattr(email_service, "ensure_hotel_gmail_ready", forbidden_provider_call)
    monkeypatch.setattr(email_service, "send_hotel_email", forbidden_provider_call)
    path = f"/api/payments/transactions/{transaction_id}/receipt/email"
    payload = {"recipient_email": "accounts@company.test"}
    first = client.post(
        path,
        json=payload,
        headers=_receipt_headers(transaction_id, "receipt-local-capture-0001"),
    )
    replay = client.post(
        path,
        json=payload,
        headers=_receipt_headers(transaction_id, "receipt-local-capture-0001"),
    )

    assert first.status_code == 200, first.text
    assert first.json() == {
        "transaction_id": transaction_id,
        "status": "captured",
        "delivery_mode": "local_simulation",
        "replayed": False,
    }
    assert replay.status_code == 200, replay.text
    assert replay.json() == {
        "transaction_id": transaction_id,
        "status": "captured",
        "delivery_mode": "local_simulation",
        "replayed": True,
    }

    outbox_rows = [json.loads(line) for line in local_simulation_email.read_text().splitlines()]
    assert len(outbox_rows) == 1
    assert outbox_rows[0]["channel"] == "payment_receipt_local_simulation"
    assert stat.S_IMODE(local_simulation_email.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(local_simulation_email.stat().st_mode) == 0o600
    mime = base64.b64decode(outbox_rows[0]["mime_base64"])
    message = BytesParser(policy=policy.default).parsebytes(mime)
    assert message["To"] == "accounts@company.test"
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == "application/pdf"
    assert attachments[0].get_filename() == f"comprobante-pago-{transaction_id}.pdf"
    assert attachments[0].get_payload(decode=True) == download.content

    delivery = db.query(PaymentReceiptEmailDelivery).one()
    assert delivery.actor_user_id == 1
    assert delivery.status == "sent"
    assert delivery.provider_message_id.startswith("local-simulation:")
    assert "accounts@company.test" not in repr(delivery.__dict__)


def test_local_simulation_rejects_non_test_recipient_and_never_falls_back_to_gmail(
    client_with_db, monkeypatch, local_simulation_email
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-LOCAL-REJECT-REAL-MAIL")
    paid = _completed_payment(client, reservation.id, reference="POS-RECEIPT-LOCAL-REJECT")
    from app.services import payment_receipt_email_service as email_service

    monkeypatch.setattr(
        email_service,
        "ensure_hotel_gmail_ready",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Gmail must not be checked")),
    )
    monkeypatch.setattr(
        email_service,
        "send_hotel_email",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Gmail must not be called")),
    )
    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "someone@example.com"},
        headers=_receipt_headers(paid["id"], "receipt-local-reject-0001"),
    )
    assert response.status_code == 400
    assert db.query(PaymentReceiptEmailDelivery).count() == 0
    assert not local_simulation_email.exists()


def test_local_simulation_hotel_mismatch_fails_closed_without_provider_fallback(
    client_with_db, monkeypatch, local_simulation_email
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-LOCAL-HOTEL-MISMATCH")
    paid = _completed_payment(client, reservation.id, reference="POS-RECEIPT-LOCAL-HOTEL-MISMATCH")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_HOTEL_ID", "2")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.services import payment_receipt_email_service as email_service

    def forbidden_provider_call(*_args, **_kwargs):
        raise AssertionError("misconfigured local simulation must not access Gmail")

    monkeypatch.setattr(email_service, "ensure_hotel_gmail_ready", forbidden_provider_call)
    monkeypatch.setattr(email_service, "send_hotel_email", forbidden_provider_call)
    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "accounts@company.test"},
        headers=_receipt_headers(paid["id"], "receipt-local-hotel-mismatch-01"),
    )

    assert response.status_code == 503
    assert db.query(PaymentReceiptEmailDelivery).count() == 0
    assert not local_simulation_email.exists()


def test_receipt_email_accepts_a_refunded_receipt_transaction(client_with_db, monkeypatch):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-REFUND")
    db.get(Guest, reservation.guest_id).email = "refund@example.com"
    original = _completed_payment(client, reservation.id, reference="POS-REFUND-ORIGINAL")
    refund = Transaction(
        hotel_id=1,
        reservation_id=reservation.id,
        amount=-10,
        currency="ARS",
        tender_amount=-10,
        tender_currency="ARS",
        transaction_type=TransactionTypeEnum.REFUND,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.REFUNDED,
        refund_of_transaction_id=original["id"],
    )
    db.add(refund)
    db.flush()
    db.commit()

    calls = _mock_receipt_email(monkeypatch)
    response = client.post(
        f"/api/payments/transactions/{refund.id}/receipt/email",
        json={"recipient_email": "refund@example.com"},
        headers=_receipt_headers(refund.id, "receipt-email-refund-0001"),
    )

    assert response.status_code == 200, response.text
    assert "Comprobante de devolución" in calls[0]["subject"]
    assert "Importe devuelto: 10.00 ARS" in calls[0]["body"]
    assert "Movimiento original" in calls[0]["body"]


def test_receipt_email_denied_permission_does_not_call_gmail(client_with_db, monkeypatch):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-DENIED")
    db.get(Guest, reservation.guest_id).email = "guest@example.com"
    paid = _completed_payment(client, reservation.id)
    calls = _mock_receipt_email(monkeypatch)
    set_override(db, 1, "receptionist", PERMISSION_CASH_OPERATE, False, user_id=1)
    db.commit()

    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "guest@example.com"},
        headers={"Idempotency-Key": "receipt-email-denied-01"},
    )

    assert response.status_code == 403
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


def test_receipt_email_requires_action_bound_mfa_before_provider_call(client_with_db, monkeypatch):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-STEP-UP")
    db.get(Guest, reservation.guest_id).email = "guest@example.com"
    paid = _completed_payment(client, reservation.id)
    calls = _mock_receipt_email(monkeypatch)

    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "guest@example.com"},
        headers={"Idempotency-Key": "receipt-email-step-up-0001"},
    )

    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "STEP_UP_REQUIRED"
    assert response.json()["detail"]["permission_code"] == "payment:receipt_email"
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


@pytest.mark.parametrize(
    ("request_email", "expected_status"),
    [("not-an-email", 422), ("guest@example.test", 400)],
)
def test_receipt_email_rejects_invalid_or_reserved_test_recipient_outside_local_simulation(
    client_with_db, monkeypatch, request_email, expected_status
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, f"RCPMAIL-{expected_status}-INVALID")
    paid = _completed_payment(client, reservation.id, reference=f"POS-EMAIL-RECIPIENT-{expected_status}")
    calls = _mock_receipt_email(monkeypatch)

    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": request_email},
        headers=_receipt_headers(paid["id"], "receipt-email-invalid-0001"),
    )

    assert response.status_code == expected_status, response.text
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


def test_receipt_email_hides_other_tenant_transactions(client_with_db, monkeypatch):
    client, db, ctx = client_with_db
    reservation_b = _reservation(db, 2, "RECEIPT-EMAIL-TENANT-B")
    db.get(Guest, reservation_b.guest_id).email = "guest-b@example.com"
    ctx["hotel_id"] = 2
    paid = _completed_payment(client, reservation_b.id, reference="POS-EMAIL-TENANT-B")
    ctx["hotel_id"] = 1
    calls = _mock_receipt_email(monkeypatch)

    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "guest-b@example.com"},
        headers=_receipt_headers(paid["id"], "receipt-email-tenant-0001", hotel_id=1),
    )

    assert response.status_code == 404, response.text
    assert "RECEIPT-EMAIL-TENANT-B" not in response.text
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


def test_receipt_email_rejects_pending_transactions_without_send(client_with_db, monkeypatch):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-PENDING")
    db.get(Guest, reservation.guest_id).email = "guest@example.com"
    pending = Transaction(
        hotel_id=1,
        reservation_id=reservation.id,
        amount=5,
        currency="ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.PENDING,
    )
    db.add(pending)
    db.flush()
    calls = _mock_receipt_email(monkeypatch)

    response = client.post(
        f"/api/payments/transactions/{pending.id}/receipt/email",
        json={"recipient_email": "guest@example.com"},
        headers=_receipt_headers(pending.id, "receipt-email-pending-001"),
    )

    assert response.status_code == 404
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


def test_receipt_email_without_ready_hotel_gmail_does_not_create_attempt_or_send(
    client_with_db, monkeypatch
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-GMAIL-OFF")
    db.get(Guest, reservation.guest_id).email = "guest@example.com"
    paid = _completed_payment(client, reservation.id)
    calls = _mock_receipt_email(monkeypatch)
    from app.services import payment_receipt_email_service as email_service

    monkeypatch.setattr(
        email_service,
        "ensure_hotel_gmail_ready",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("provider secret detail")),
    )

    response = client.post(
        f"/api/payments/transactions/{paid['id']}/receipt/email",
        json={"recipient_email": "guest@example.com"},
        headers=_receipt_headers(paid["id"], "receipt-email-no-gmail-001"),
    )

    assert response.status_code == 503
    assert "provider secret detail" not in response.text
    assert calls == []
    assert db.query(PaymentReceiptEmailDelivery).count() == 0


def test_receipt_email_fails_closed_after_ambiguous_send_and_blocks_retry(
    client_with_db, monkeypatch
):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "RECEIPT-EMAIL-AMBIGUOUS")
    db.get(Guest, reservation.guest_id).email = "guest@example.com"
    paid = _completed_payment(client, reservation.id)
    calls = _mock_receipt_email(monkeypatch)

    def timeout_after_provider_acceptance(*_args, **_kwargs):
        calls.append({"attempted": True})
        raise TimeoutError("transport detail must not reach the client")

    from app.services import payment_receipt_email_service as email_service

    monkeypatch.setattr(email_service, "send_hotel_email", timeout_after_provider_acceptance)
    path = f"/api/payments/transactions/{paid['id']}/receipt/email"
    payload = {"recipient_email": "guest@example.com"}
    first = client.post(path, json=payload, headers=_receipt_headers(paid["id"], "receipt-email-timeout-001"))
    retry_same_key = client.post(path, json=payload, headers=_receipt_headers(paid["id"], "receipt-email-timeout-001"))
    retry_new_key = client.post(path, json=payload, headers=_receipt_headers(paid["id"], "receipt-email-timeout-002"))

    assert first.status_code == 503
    assert "transport detail" not in first.text
    assert retry_same_key.status_code == 409
    assert retry_new_key.status_code == 409
    assert len(calls) == 1
    delivery = db.query(PaymentReceiptEmailDelivery).one()
    assert delivery.status == "unknown"
    assert delivery.completed_at is not None
