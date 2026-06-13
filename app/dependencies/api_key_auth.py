"""Public API-key authentication, separate from staff JWT auth."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.rate_limiter import SimpleRateLimiter
from app.database import get_db
from app.services.hotel_api_key_service import HotelAPIKeyError, verify_key


public_api_limiter = SimpleRateLimiter("public_hotel_api", limit=60, window_seconds=60)


@dataclass(slots=True)
class PublicAPIContext:
    hotel_id: int
    api_key_id: int
    key_prefix: str


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

    subject = f"hotel:{key.hotel_id}:key:{key.id}"
    if not public_api_limiter.allow(subject, db=db):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit excedido")

    context = PublicAPIContext(hotel_id=key.hotel_id, api_key_id=key.id, key_prefix=key.key_prefix)
    db.commit()
    return context
