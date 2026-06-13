"""
FastAPI routes for hotel permission matrix management.
"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_permission
from app.services.permission_service import (
    PERMISSION_DEFINITIONS,
    PERMISSION_PERMISSION_MANAGE,
    ROLE_CODES,
    get_matrix,
    set_override,
)

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


class PermissionOverrideRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=50)
    permission_code: str = Field(..., min_length=1, max_length=100)
    allowed: bool


@router.get("/matrix")
def read_permission_matrix(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    return {"hotel_id": context.hotel_id, "matrix": get_matrix(db, context.hotel_id)}


@router.put("/override")
def update_permission_override(
    payload: PermissionOverrideRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PERMISSION_MANAGE)),
):
    if payload.role not in ROLE_CODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rol invalido")
    if payload.permission_code not in PERMISSION_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Permiso invalido")

    override = set_override(
        db,
        hotel_id=context.hotel_id,
        role=payload.role,
        code=payload.permission_code,
        allowed=payload.allowed,
        user_id=context.user_id,
    )
    db.commit()
    db.refresh(override)
    return {
        "hotel_id": override.hotel_id,
        "role": override.role,
        "permission_code": override.permission_code,
        "allowed": override.allowed,
        "updated_by_user_id": override.updated_by_user_id,
        "updated_at": override.updated_at,
    }
