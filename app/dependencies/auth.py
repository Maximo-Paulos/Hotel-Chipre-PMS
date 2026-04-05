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
from app.services.hotel_service import (
    get_or_create_hotel_for_owner,
    get_memberships_for_user,
)
from app.models.hotel_membership import HotelMembership
from fastapi import Request


@dataclass
class AuthContext:
    """Minimal request context used by routers that expect a hotel scope."""
    hotel_id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    permissions: Optional[Set[str]] = None


def _resolve_hotel_id(db: Session, header_value: Optional[str], user_email: Optional[str], user_id: Optional[int]) -> int:
    """Resolve hotel id validating membership."""
    memberships = []
    if user_id:
        memberships = get_memberships_for_user(db, user_id)
    hotel_ids = [m.hotel_id for m in memberships]

    # If header is provided, honor it only if user has membership
    if header_value:
        try:
            hid = int(header_value)
            if hid in hotel_ids:
                return hid
        except ValueError:
            pass

    # If token has email but no membership yet, create default hotel for owner
    if user_email and not memberships:
        hotel = get_or_create_hotel_for_owner(db, user_email)
        return hotel.id

    if hotel_ids:
        return hotel_ids[0]

    existing = db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).first()
    if existing:
        return existing[0]

    config = HotelConfiguration(id=1, owner_email=user_email)
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
    payload = None
    user_id_int: Optional[int] = None
    user_email = None
    if authorization:
        payload = _decode_authorization_header(authorization)
        user_email = payload.get("email")
        try:
            user_id_int = int(payload.get("sub")) if payload and payload.get("sub") else None
        except Exception:
            user_id_int = None

    hotel_id = _resolve_hotel_id(db, x_hotel_id, user_email, user_id_int)
    # Enforce subscription state globally: no operaciones si está inactiva.
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá para usar el sistema.",
        )
    return AuthContext(hotel_id=hotel_id, user_id=user_id_int, user_email=user_email, permissions=set())


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


def require_roles(*roles: str):
    """
    Dependency to enforce that the current user has one of the allowed roles in the current hotel.
    """
    def dependency(
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> AuthContext:
        # Fetch membership
        membership = (
            db.query(HotelMembership)
            .filter(
                HotelMembership.hotel_id == context.hotel_id,
                HotelMembership.user_id == context.user_id if context.user_id else None,
            )
            .first()
        )
        if not membership or membership.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permisos para esta acción")
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
