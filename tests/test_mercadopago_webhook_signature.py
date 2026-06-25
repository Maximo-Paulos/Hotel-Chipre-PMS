from __future__ import annotations

import hashlib
import hmac

from app.services.payment_webhook_service import validate_mercadopago_webhook_signature


def _build_signature(secret: str, data_id: str, request_id: str, ts: str = "1700000000") -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature():
    secret = "webhook-secret"
    request_id = "req-123"
    data_id = "payment-789"
    signature = _build_signature(secret, data_id, request_id)

    assert validate_mercadopago_webhook_signature(
        secret,
        data_id=data_id,
        request_id=request_id,
        signature_header=signature,
    ) is True


def test_validate_mercadopago_webhook_signature_rejects_wrong_signature():
    assert validate_mercadopago_webhook_signature(
        "webhook-secret",
        data_id="payment-789",
        request_id="req-123",
        signature_header="ts=1700000000,v1=deadbeef",
    ) is False


def test_validate_mercadopago_webhook_signature_rejects_tampered_data_id():
    secret = "webhook-secret"
    request_id = "req-123"
    data_id = "payment-789"
    signature = _build_signature(secret, data_id, request_id)

    assert validate_mercadopago_webhook_signature(
        secret,
        data_id="payment-tampered",
        request_id=request_id,
        signature_header=signature,
    ) is False
