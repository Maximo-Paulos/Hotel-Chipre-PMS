"""
Lightweight authentication/context helpers.

These dependencies only provide a hotel_id so the API can stay scoped per hotel
without introducing a full auth system. If the caller sends the header
`X-Hotel-Id`, it is respected; otherwise we fall back to the first persisted
HotelConfiguration or create a default one (id=1).
"""
from dataclasses import dataclass
from typing import Optional, Set

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hotel_config import HotelConfiguration


@dataclass
class AuthContext:
    """Minimal request context used by routers that expect a hotel scope."""
    hotel_id: int
    user_id: Optional[str] = None
    permissions: Optional[Set[str]] = None


def _resolve_hotel_id(db: Session, header_value: Optional[str]) -> int:
    """Resolve the current hotel id, persisting a default if needed."""
    if header_value:
        try:
            return int(header_value)
        except ValueError:
            pass  # Ignore malformed header and fall back to persisted id

    existing = db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).first()
    if existing:
        return existing[0]

    # Persist a default row so future requests reuse the same id.
    config = HotelConfiguration(id=1)
    db.add(config)
    db.flush()
    return config.id


def get_auth_context(
    db: Session = Depends(get_db),
    x_hotel_id: Optional[str] = Header(default=None, convert_underscores=False),
    x_user_id: Optional[str] = Header(default=None, convert_underscores=False),
) -> AuthContext:
    """Return a minimal context with hotel scoping."""
    hotel_id = _resolve_hotel_id(db, x_hotel_id)
    return AuthContext(hotel_id=hotel_id, user_id=x_user_id, permissions=set())


def require_permission(permission: str):
    """
    Dependency factory that attaches the required permission label to the context.
    Real permission checks are out of scope; this keeps the signature stable.
    """
    def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        perms = context.permissions or set()
        perms.add(permission)
        context.permissions = perms
        return context

    return dependency
