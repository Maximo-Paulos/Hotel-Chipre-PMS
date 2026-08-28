"""Domain service for public marketing inquiry capture."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

import app.config as app_config
from app.adapters.rate_limiter import public_inquiry_email_limiter, public_inquiry_source_limiter
from app.models.public_inquiry import PublicInquiry, PublicInquiryNotificationStatus
from app.schemas.public_inquiry import PublicInquiryCreate
from app.services import email_service

LOGGER = logging.getLogger(__name__)


class PublicInquiryRateLimitError(RuntimeError):
    """Raised when one public source exceeds its inquiry budget."""


def _digest_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rate_limit_keys(request: Request, email: str) -> tuple[str, str]:
    source = request.client.host if request.client else "unknown"
    return f"public-inquiry-source:{_digest_key(source)}", f"public-inquiry-email:{_digest_key(email)}"


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
        inquiry.notified_at = datetime.now(timezone.utc)
    db.commit()


def create_public_inquiry(db: Session, payload: PublicInquiryCreate, request: Request) -> PublicInquiry:
    settings = app_config.get_settings()
    if (payload.website or "").strip():
        raise ValueError("Solicitud inválida")

    rate_limit = max(1, int(getattr(settings, "PUBLIC_INQUIRY_RATE_LIMIT", 5)))
    source_key, email_key = _rate_limit_keys(request, payload.normalized_email)
    source_allowed = public_inquiry_source_limiter.allow(source_key, db=db, limit=rate_limit)
    email_allowed = public_inquiry_email_limiter.allow(email_key, db=db, limit=rate_limit)
    if not source_allowed or not email_allowed:
        db.commit()
        raise PublicInquiryRateLimitError

    inquiry = PublicInquiry(
        name=payload.name,
        email=payload.normalized_email,
        company_name=payload.company_name,
        phone=payload.phone,
        message=payload.message,
        source_path=payload.source_path,
        privacy_consent_at=datetime.now(timezone.utc),
        notification_status=PublicInquiryNotificationStatus.NOT_CONFIGURED,
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    recipient = str(getattr(settings, "PUBLIC_INQUIRY_RECIPIENT_EMAIL", "") or "").strip()
    _notify_inquiry(db, inquiry, recipient)
    return inquiry
