from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone

from fastapi import HTTPException, status


DEFAULT_TOLERANCE_SECONDS = 300


def _webhook_secret() -> str:
    return (os.getenv("MASTER_STRIPE_WEBHOOK_SECRET") or os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()


def stripe_secret_configured() -> bool:
    return bool(_webhook_secret())


def verify_stripe_signature(payload: bytes, signature_header: str | None, tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS) -> None:
    secret = _webhook_secret()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook secret no configurado")
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta la firma de Stripe")

    timestamp = None
    expected_signatures: list[str] = []
    for part in signature_header.split(","):
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de Stripe invalida") from exc
        elif key == "v1" and value:
            expected_signatures.append(value)

    if timestamp is None or not expected_signatures:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de Stripe invalida")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if abs(now_ts - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de Stripe expirada")

    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    computed = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(computed, candidate) for candidate in expected_signatures):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma de Stripe invalida")

