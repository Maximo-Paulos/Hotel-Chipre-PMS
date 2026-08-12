"""Public API-key authentication, separate from staff JWT auth."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.rate_limiter import SimpleRateLimiter
from app.database import get_db
from app.models.hotel_api_key import APIKeyPurposeEnum
from app.models.hotel_config import HotelConfiguration
from app.services.hotel_api_key_service import HotelAPIKeyError, record_key_usage, verify_key
from app.services.tenant_context import set_tenant_hotel_context


DEFAULT_PUBLIC_API_RATE_LIMIT_PER_MINUTE = 60

public_api_limiter = SimpleRateLimiter(
    "public_hotel_api",
    limit=DEFAULT_PUBLIC_API_RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)


@dataclass(slots=True)
class PublicAPIContext:
    hotel_id: int
    api_key_id: int
    key_prefix: str
    purpose: APIKeyPurposeEnum


def get_public_api_context(
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> PublicAPIContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key requerida")

    try:
        key = verify_key(db, x_api_key)
    except HotelAPIKeyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    hotel_id = key.hotel_id
    api_key_id = key.id
    key_prefix = key.key_prefix
    purpose = key.purpose
    rate_limit = _public_api_rate_limit_for_hotel(db, hotel_id)

    subject = f"hotel:{hotel_id}:key:{api_key_id}"
    if not public_api_limiter.allow(subject, db=db, limit=rate_limit):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit excedido")

    record_key_usage(db, key)
    context = PublicAPIContext(
        hotel_id=hotel_id,
        api_key_id=api_key_id,
        key_prefix=key_prefix,
        purpose=purpose,
    )
    db.commit()
    # API-key lookup happens before the hotel is known.  The migration keeps
    # that hash-only lookup outside RLS; all subsequent public operations use
    # the resolved tenant context in this transaction.
    set_tenant_hotel_context(db, hotel_id)
    return context


def require_public_api_purpose(*expected_purposes: APIKeyPurposeEnum):
    """Authorize a public key for a specific external product surface.

    Purpose validation happens before rate limiting, commits, and
    ``last_used_at`` updates. A purpose mismatch is authorization failure
    (403), not credential failure (401).
    """

    allowed = frozenset(expected_purposes)
    if not allowed:
        raise ValueError("At least one API key purpose is required")

    def dependency(
        db: Session = Depends(get_db),
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> PublicAPIContext:
        if not x_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-API-Key requerida")
        try:
            key = verify_key(db, x_api_key)
        except HotelAPIKeyError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        if key.purpose not in allowed:
            # ``verify_key`` is read-only, so rollback guarantees a mismatch
            # cannot update usage metadata or persist incidental autoflushes.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La API key no esta autorizada para este endpoint",
            )

        hotel_id = key.hotel_id
        api_key_id = key.id
        rate_limit = _public_api_rate_limit_for_hotel(db, hotel_id)
        subject = f"hotel:{hotel_id}:key:{api_key_id}"
        if not public_api_limiter.allow(subject, db=db, limit=rate_limit):
            db.rollback()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit excedido")

        record_key_usage(db, key)
        context = PublicAPIContext(
            hotel_id=hotel_id,
            api_key_id=api_key_id,
            key_prefix=key.key_prefix,
            purpose=key.purpose,
        )
        db.commit()
        set_tenant_hotel_context(db, hotel_id)
        return context

    return dependency


require_web_engine_api_context = require_public_api_purpose(APIKeyPurposeEnum.WEB_ENGINE)
require_whatsapp_api_context = require_public_api_purpose(APIKeyPurposeEnum.WHATSAPP_BOT)


def _public_api_rate_limit_for_hotel(db: Session, hotel_id: int) -> int:
    try:
        configured = (
            db.query(HotelConfiguration.public_api_rate_limit_per_minute)
            .filter(HotelConfiguration.id == hotel_id)
            .scalar()
        )
    except SQLAlchemyError:
        db.rollback()
        return DEFAULT_PUBLIC_API_RATE_LIMIT_PER_MINUTE

    try:
        limit = int(configured)
    except (TypeError, ValueError):
        return DEFAULT_PUBLIC_API_RATE_LIMIT_PER_MINUTE
    return limit if limit > 0 else DEFAULT_PUBLIC_API_RATE_LIMIT_PER_MINUTE
