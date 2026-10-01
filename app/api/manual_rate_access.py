"""Payload-conditional authorization for manual reservation rates."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import AuthContext
from app.services.permission_service import (
    PERMISSION_RESERVATION_MANUAL_RATE,
    PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
    audit_permission_denied,
    resolve,
)


def authorize_manual_rate_scope(db: Session, context: AuthContext) -> str:
    """Return the strongest manual-rate capability the actor currently has."""
    if resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_RESERVATION_MANUAL_RATE,
        user_id=context.user_id,
    ):
        return "unbounded"
    if resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
        user_id=context.user_id,
    ):
        return "bounded"

    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=PERMISSION_RESERVATION_MANUAL_RATE_LIMITED,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenes permisos para fijar una tarifa manual en la reserva.",
    )
