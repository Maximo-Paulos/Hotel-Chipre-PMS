"""Domain service for public marketing inquiry capture."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

import app.config as app_config
from app.adapters.rate_limiter import (
    public_inquiry_email_limiter,
    public_inquiry_global_limiter,
    public_inquiry_source_limiter,
)
from app.models.public_inquiry import PublicInquiry, PublicInquiryNotificationStatus
from app.schemas.public_inquiry import PublicInquiryCreate
from app.services import email_service

LOGGER = logging.getLogger(__name__)


class PublicInquiryRateLimitError(RuntimeError):
    """Raised when one public source exceeds its inquiry budget."""


def _digest_key(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _rate_limit_keys(request: Request, email: str, secret: str) -> tuple[str | None, str, str]:
    # Render places requests behind Cloudflare. Trust only its single-IP header;
    # never use a caller-controlled X-Forwarded-For value. A global limiter
    # still applies when the edge IP is absent or the peer is a proxy.
    source = (request.headers.get("cf-connecting-ip") or "").strip()
    if not source and request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}:
        source = request.client.host
    try:
        normalized_source = ipaddress.ip_address(source).compressed if source else None
    except ValueError:
        normalized_source = None

    source_key = (
        f"public-inquiry-source:{_digest_key(normalized_source, secret)}"
        if normalized_source
        else None
    )
    email_key = f"public-inquiry-email:{_digest_key(email.strip().lower(), secret)}"
    # A separate global budget remains in force when the trusted edge IP
    # header is absent, preventing address rotation from disabling throttling.
    global_key = f"public-inquiry-global:{_digest_key('all-sources', secret)}"
    return source_key, email_key, global_key


def _utcnow_naive() -> datetime:
    """Public inquiry timestamps use UTC in timestamp-without-time-zone columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _notification_body(inquiry: PublicInquiry) -> str:
    company = inquiry.company_name or "No informado"
    phone = inquiry.phone or "No informado"
    return (
        "Nueva consulta recibida desde Hotel Chipre PMS\n\n"
        f"Nombre: {inquiry.name}\n"
        f"Email: {inquiry.email}\n"
        f"Empresa: {company}\n"
        f"Teléfono: {phone}\n"
        f"Ruta de origen: {inquiry.source_path}\n\n"
        "Para responder, escribí un nuevo correo a la dirección indicada como Email.\n\n"
        f"Mensaje:\n{inquiry.message}\n"
    )


def _notify_inquiry(db: Session, inquiry: PublicInquiry, recipient: str) -> None:
    if not recipient:
        return

    try:
        email_service.send_platform_email(
            recipient,
            "Nueva consulta desde Hotel Chipre PMS",
            _notification_body(inquiry),
        )
    except Exception as exc:  # pragma: no cover - provider-specific failures
        inquiry.notification_status = PublicInquiryNotificationStatus.FAILED
        inquiry.notification_error_type = type(exc).__name__[:80]
        LOGGER.warning(
            "public inquiry notification failed inquiry_id=%s error_type=%s",
            inquiry.id,
            type(exc).__name__,
        )
    else:
        inquiry.notification_status = PublicInquiryNotificationStatus.SENT
        inquiry.notified_at = _utcnow_naive()
    try:
        db.commit()
    except Exception as exc:
        # The inquiry was already committed. A failure to persist delivery
        # status must not turn an accepted submission into a retry/duplicate.
        db.rollback()
        LOGGER.warning(
            "public inquiry notification status could not be persisted inquiry_id=%s error_type=%s",
            inquiry.id,
            type(exc).__name__,
        )


def create_public_inquiry(
    db: Session, payload: PublicInquiryCreate, request: Request
) -> PublicInquiry | None:
    settings = app_config.get_settings()
    rate_limit = max(1, int(getattr(settings, "PUBLIC_INQUIRY_RATE_LIMIT", 5)))
    global_rate_limit = max(1, int(getattr(settings, "PUBLIC_INQUIRY_GLOBAL_RATE_LIMIT", 100)))
    hash_secret = str(getattr(settings, "JWT_SECRET", "") or "change-me")
    source_key, email_key, global_key = _rate_limit_keys(request, payload.normalized_email, hash_secret)
    # Stop at the first exceeded bucket. Recording a rejected source against
    # the shared email/global buckets would let one noisy client exhaust the
    # budget for every legitimate visitor.
    if source_key and not public_inquiry_source_limiter.allow(source_key, db=db, limit=rate_limit):
        db.commit()
        raise PublicInquiryRateLimitError
    if not public_inquiry_email_limiter.allow(email_key, db=db, limit=rate_limit):
        db.commit()
        raise PublicInquiryRateLimitError
    if not public_inquiry_global_limiter.allow(global_key, db=db, limit=global_rate_limit):
        db.commit()
        raise PublicInquiryRateLimitError

    # Return the same public response for honeypot submissions, but persist
    # nothing. Run the limiter first so repeatedly probing the form is bounded.
    if (payload.website or "").strip():
        db.commit()
        return None

    inquiry = PublicInquiry(
        name=payload.name,
        email=payload.normalized_email,
        company_name=payload.company_name,
        phone=payload.phone,
        message=payload.message,
        source_path=payload.source_path,
        privacy_consent_at=_utcnow_naive(),
        notification_status=PublicInquiryNotificationStatus.NOT_CONFIGURED,
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    recipient = str(getattr(settings, "PUBLIC_INQUIRY_RECIPIENT_EMAIL", "") or "").strip()
    _notify_inquiry(db, inquiry, recipient)
    return inquiry
