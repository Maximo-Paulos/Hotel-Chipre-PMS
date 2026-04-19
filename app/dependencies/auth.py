"""
Strict authentication/context helpers.

Every operational request must resolve to a real authenticated user plus an
active hotel membership. We never fall back to hotel 1 or fabricate a hotel
context from headers alone.
"""
from dataclasses import dataclass
from typing import Optional, Set

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.services.hotel_service import get_memberships_for_user
from app.services.security import decode_access_token


@dataclass
class AuthContext:
    """Minimal request context used by routers that expect a hotel scope."""

    hotel_id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    is_verified: bool = False
    permissions: Optional[Set[str]] = None


def _parse_header_hotel_id(header_value: Optional[str]) -> Optional[int]:
    if header_value is None or not str(header_value).strip():
        return None
    try:
        parsed = int(header_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Hotel-Id invalido") from exc
    if parsed <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Hotel-Id invalido")
    return parsed


def _parse_token_hotel_id(payload: dict | None) -> Optional[int]:
    if not payload:
        return None
    raw = payload.get("hotel_id")
    if raw in (None, ""):
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _decode_authorization_header(header_value: str) -> dict:
    if not header_value.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Header Authorization invalido")
    token = header_value.split(" ", 1)[1]
    return decode_access_token(token)


def _authenticate_user(db: Session, authorization: Optional[str]) -> tuple[User, dict]:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacion requerida")

    payload = _decode_authorization_header(authorization)
    raw_user_id = payload.get("sub")
    try:
        user_id = int(raw_user_id) if raw_user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin usuario valido")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no valido")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifica tu email para usar el sistema")
    return user, payload


def _resolve_membership(
    memberships: list[HotelMembership],
    requested_hotel_id: Optional[int],
    token_hotel_id: Optional[int],
) -> HotelMembership:
    membership_by_hotel = {membership.hotel_id: membership for membership in memberships if membership.status == "active"}
    if not membership_by_hotel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene hoteles activos asignados",
        )

    selected_hotel_id = requested_hotel_id or token_hotel_id
    if selected_hotel_id is not None:
        membership = membership_by_hotel.get(selected_hotel_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenes acceso al hotel solicitado",
            )
        return membership

    if len(membership_by_hotel) == 1:
        return next(iter(membership_by_hotel.values()))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Debes seleccionar un hotel valido para esta sesion",
    )


def get_auth_context(
    db: Session = Depends(get_db),
    x_hotel_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> AuthContext:
    """Return an authenticated context scoped to an active hotel membership."""

    user, payload = _authenticate_user(db, authorization)
    memberships = get_memberships_for_user(db, user.id)
    membership = _resolve_membership(
        memberships,
        requested_hotel_id=_parse_header_hotel_id(x_hotel_id),
        token_hotel_id=_parse_token_hotel_id(payload),
    )

    return AuthContext(
        hotel_id=membership.hotel_id,
        user_id=user.id,
        user_email=user.email,
        user_role=membership.role,
        is_verified=user.is_verified,
        permissions=set(),
    )


def require_permission(permission: str):
    """
    Dependency factory that enforces a permission via hotel membership roles.
    """

    permission_roles = {
        "config:manage": {"owner", "co_owner"},
    }

    def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        perms = context.permissions or set()
        perms.add(permission)
        context.permissions = perms
        if not context.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifica tu email para usar el sistema")
        allowed_roles = permission_roles.get(permission)
        if allowed_roles and context.user_role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")
        return context

    return dependency


def require_roles(*roles: str):
    """
    Dependency to enforce that the current user has one of the allowed roles in the current hotel.
    """

    allowed = set(roles)

    def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not context.is_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifica tu email para usar el sistema")
        if context.user_role in allowed:
            return context
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")

    return dependency


def require_platform_admin():
    def dependency(
        db: Session = Depends(get_db),
        x_hotel_id: Optional[str] = Header(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> AuthContext:
        user, payload = _authenticate_user(db, authorization)
        if user.role != "platform_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")

        hotel_id = _parse_header_hotel_id(x_hotel_id) or _parse_token_hotel_id(payload) or 0
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user.id,
            user_email=user.email,
            user_role=user.role,
            is_verified=user.is_verified,
            permissions={"platform:admin"},
        )

    return dependency


def get_current_user_optional(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
) -> Optional[User]:
    if not authorization:
        return None
    user, _ = _authenticate_user(db, authorization)
    return user


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, convert_underscores=False),
) -> User:
    user = get_current_user_optional(db=db, authorization=authorization)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacion requerida")
    return user
