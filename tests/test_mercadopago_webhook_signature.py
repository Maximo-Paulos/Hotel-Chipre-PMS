from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac

import pytest

from app.services.payment_link_test_service import (
    PaymentLinkTestError,
    validate_mercadopago_webhook_signature,
)


def _build_signature(secret: str, data_id: str, request_id: str, ts: int | None = None) -> str:
    timestamp = ts or int(datetime.now(timezone.utc).timestamp())
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={timestamp},v1={digest}"


def test_validate_mercadopago_webhook_signature_accepts_valid_headers():
    secret = "webhook-secret"
    request_id = "req-123"
    data_id = "payment-789"
    signature = _build_signature(secret, data_id, request_id)

    validate_mercadopago_webhook_signature(
        secret,
        data_id=data_id,
        request_id=request_id,
        signature_header=signature,
    )


def test_validate_mercadopago_webhook_signature_rejects_invalid_headers():
    with pytest.raises(PaymentLinkTestError):
        validate_mercadopago_webhook_signature(
            "webhook-secret",
            data_id="payment-789",
            request_id="req-123",
            signature_header="ts=1700000000,v1=deadbeef",
        )


def test_validate_mercadopago_webhook_signature_rejects_expired_timestamp():
    secret = "webhook-secret"
    request_id = "req-123"
    data_id = "payment-789"
    signature = _build_signature(secret, data_id, request_id, ts=int(datetime.now(timezone.utc).timestamp()) - 1000)

    with pytest.raises(PaymentLinkTestError):
        validate_mercadopago_webhook_signature(
            secret,
            data_id=data_id,
            request_id=request_id,
            signature_header=signature,
        )
