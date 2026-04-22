from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.master_admin.models import MasterStripeSettings
from app.services.integration_service import decrypt_payload, encrypt_payload

DEFAULT_TOLERANCE_SECONDS = 300
SYSTEM_STRIPE_CONFIG_KEY = "system"


def _get_settings_row(db: Session, *, create: bool = False) -> MasterStripeSettings | None:
    row = db.query(MasterStripeSettings).filter(MasterStripeSettings.config_key == SYSTEM_STRIPE_CONFIG_KEY).first()
    if row or not create:
        return row
    row = MasterStripeSettings(config_key=SYSTEM_STRIPE_CONFIG_KEY)
    db.add(row)
    db.flush()
    return row


def _stripe_secret(payload: dict[str, object]) -> str:
    return str(payload.get("stripe_secret_key") or "").strip()


def _webhook_secret(payload: dict[str, object]) -> str:
    return str(payload.get("webhook_secret") or "").strip()


def _validate_stripe_secret(secret_key: str) -> dict[str, object]:
    response = requests.get(
        "https://api.stripe.com/v1/account",
        headers={"Authorization": f"Bearer {secret_key}"},
        timeout=20,
    )
    if not response.ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe rechazo las credenciales configuradas")
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe devolvio una respuesta invalida")
    return payload


def get_stripe_status(db: Session) -> dict[str, object]:
    row = _get_settings_row(db)
    if not row:
        return {
            "configured": False,
            "enabled": False,
            "account_id": None,
            "account_name": None,
            "webhook_secret_configured": False,
            "last_checked_at": None,
            "last_error": None,
        }
    payload = decrypt_payload(row.auth_payload)
    return {
        "configured": bool(row.enabled and payload and _stripe_secret(payload)),
        "enabled": row.enabled,
        "account_id": row.account_id,
        "account_name": row.account_name,
        "webhook_secret_configured": row.webhook_secret_configured,
        "last_checked_at": row.last_checked_at,
        "last_error": row.last_error,
    }


def save_stripe_settings(db: Session, payload: dict[str, object]) -> dict[str, object]:
    secret_key = _stripe_secret(payload)
    if not secret_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta el secret key de Stripe")
    account = _validate_stripe_secret(secret_key)
    row = _get_settings_row(db, create=True)
    clean_payload = {
        "stripe_secret_key": secret_key,
        "webhook_secret": _webhook_secret(payload),
    }
    row.enabled = bool(payload.get("enabled", True))
    row.auth_payload = encrypt_payload(clean_payload)
    row.account_id = str(account.get("id") or "").strip() or None
    row.account_name = str(account.get("display_name") or account.get("email") or "").strip() or None
    row.webhook_secret_configured = bool(clean_payload["webhook_secret"])
    row.last_checked_at = datetime.now(timezone.utc)
    row.last_error = None
    db.flush()
    return get_stripe_status(db)


def clear_stripe_settings(db: Session) -> dict[str, object]:
    row = _get_settings_row(db, create=True)
    row.enabled = False
    row.auth_payload = None
    row.account_id = None
    row.account_name = None
    row.webhook_secret_configured = False
    row.last_checked_at = datetime.now(timezone.utc)
    row.last_error = None
    db.flush()
    return get_stripe_status(db)


def stripe_secret_configured(db: Session) -> bool:
    return bool(get_stripe_status(db).get("configured"))


def _webhook_secret_from_db(db: Session) -> str:
    row = _get_settings_row(db)
    if not row or not row.auth_payload:
        return ""
    payload = decrypt_payload(row.auth_payload)
    return _webhook_secret(payload)


def verify_stripe_signature(
    db: Session,
    payload: bytes,
    signature_header: str | None,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> None:
    secret = _webhook_secret_from_db(db)
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook secret no configurado en el panel master")
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
