"""
Lightweight authentication/context helpers.

These dependencies only provide a hotel_id so the API can stay scoped per hotel
without introducing a full auth system. If the caller sends the header
`X-Hotel-Id`, it is respected; otherwise we fall back to the first persisted
HotelConfiguration or create a default one (id=1).
"""
from dataclasses import dataclass
from typing import Optional, Set

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.hotel_config import HotelConfiguration
from app.services.security import decode_access_token


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
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
) -> AuthContext:
    """Return a minimal context with hotel scoping."""
    hotel_id = _resolve_hotel_id(db, x_hotel_id)
    user_id = x_user_id
    if authorization:
        payload = _decode_authorization_header(authorization)
        user_id = payload.get("email") or payload.get("sub") or user_id
    return AuthContext(hotel_id=hotel_id, user_id=user_id, permissions=set())


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


def _decode_authorization_header(header_value: str) -> dict:
    if not header_value.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Header Authorization inválido")
    token = header_value.split(" ", 1)[1]
    return decode_access_token(token)


def get_current_user_optional(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
) -> Optional[User]:
    if not authorization:
        return None
    payload = _decode_authorization_header(authorization)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin usuario")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido")
    return user


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
) -> User:
    user = get_current_user_optional(db=db, authorization=authorization)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
    return user
