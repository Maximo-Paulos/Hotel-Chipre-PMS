"""Thin FastAPI transport for the tenant-scoped permission service."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import (
    AuthContext,
    get_auth_context,
    require_permission_administrator,
)
from app.models.hotel_membership import HotelMembership
from app.schemas.permission import (
    RolePermissionOverrideRequest,
    UserPermissionOverrideRequest,
)
from app.services.permission_service import (
    PERMISSION_DEFINITIONS,
    ROLE_CODES,
    canonical_permission_code,
    get_effective_permission_details,
    get_effective_permissions,
    get_matrix,
    get_permission_catalog,
    get_role_profiles,
    publish_permission_invalidation,
    restore_role_defaults,
    restore_user_defaults,
    set_role_override,
    set_user_override,
)

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


def _validate_role(role: str) -> None:
    if role not in ROLE_CODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rol invalido")


def _validate_code(code: str) -> str:
    if code not in PERMISSION_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Permiso invalido")
    return canonical_permission_code(code)


def _target_membership_or_404(db: Session, hotel_id: int, user_id: int) -> HotelMembership:
    membership = db.query(HotelMembership).filter_by(
        hotel_id=hotel_id,
        user_id=user_id,
        status="active",
    ).one_or_none()
    if membership is None:
        # Deliberately identical for an unknown user and another hotel's user.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return membership


@router.get("/effective")
def read_effective_permissions(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    details = get_effective_permission_details(
        db,
        context.hotel_id,
        context.user_role,
        user_id=context.user_id,
    )
    return {
        "hotel_id": context.hotel_id,
        "user_id": context.user_id,
        "role": context.user_role,
        "permissions": get_effective_permissions(
            db,
            context.hotel_id,
            context.user_role,
            user_id=context.user_id,
        ),
        "details": details,
    }


@router.get("/catalog")
def read_permission_catalog(
    context: AuthContext = Depends(require_permission_administrator),
):
    return {"hotel_id": context.hotel_id, "permissions": get_permission_catalog()}


@router.get("/matrix")
def read_permission_matrix(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    return {"hotel_id": context.hotel_id, "matrix": get_matrix(db, context.hotel_id)}


@router.get("/role-overrides")
def read_role_permission_profiles(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    return {
        "hotel_id": context.hotel_id,
        "matrix": get_role_profiles(db, context.hotel_id),
    }


def _update_role_override(
    payload: RolePermissionOverrideRequest,
    db: Session,
    context: AuthContext,
):
    _validate_role(payload.role)
    code = _validate_code(payload.permission_code)
    try:
        override = set_role_override(
            db,
            context.hotel_id,
            payload.role,
            code,
            payload.allowed,
            actor_user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    db.refresh(override)
    publish_permission_invalidation(context.hotel_id)
    return {
        "hotel_id": override.hotel_id,
        "role": override.role,
        "permission_code": override.permission_code,
        "allowed": bool(override.allowed),
        "source": "role_override",
        "locked": False,
        "updated_by_user_id": override.updated_by_user_id,
        "updated_at": override.updated_at,
    }


@router.put("/override")
@router.put("/role-overrides")
def update_permission_override(
    payload: RolePermissionOverrideRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    return _update_role_override(payload, db, context)


@router.delete("/role-overrides/{role}")
def restore_role_permission_defaults(
    role: str,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    _validate_role(role)
    restored = restore_role_defaults(db, context.hotel_id, role, context.user_id)
    db.commit()
    publish_permission_invalidation(context.hotel_id)
    return {"hotel_id": context.hotel_id, "role": role, "restored": restored}


@router.get("/user-overrides/{user_id}")
def read_user_overrides(
    user_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    membership = _target_membership_or_404(db, context.hotel_id, user_id)
    return {
        "hotel_id": context.hotel_id,
        "user_id": user_id,
        "role": membership.role,
        "details": get_effective_permission_details(
            db,
            context.hotel_id,
            membership.role,
            user_id=user_id,
        ),
    }


@router.put("/user-overrides/{user_id}")
def update_user_override(
    user_id: int,
    payload: UserPermissionOverrideRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    if user_id == context.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No puedes modificar tus propios permisos",
        )
    membership = _target_membership_or_404(db, context.hotel_id, user_id)
    code = _validate_code(payload.permission_code)
    try:
        override = set_user_override(
            db,
            context.hotel_id,
            user_id,
            membership.role,
            code,
            payload.allowed,
            actor_user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    db.refresh(override)
    publish_permission_invalidation(context.hotel_id)
    return {
        "hotel_id": override.hotel_id,
        "user_id": override.user_id,
        "role": membership.role,
        "permission_code": override.permission_code,
        "allowed": bool(override.allowed),
        "source": "user_override",
        "locked": False,
        "updated_by_user_id": override.updated_by_user_id,
        "updated_at": override.updated_at,
    }


@router.delete("/user-overrides/{user_id}")
def restore_user_permission_defaults(
    user_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    if user_id == context.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No puedes modificar tus propios permisos",
        )
    _target_membership_or_404(db, context.hotel_id, user_id)
    restored = restore_user_defaults(db, context.hotel_id, user_id, context.user_id)
    db.commit()
    publish_permission_invalidation(context.hotel_id)
    return {"hotel_id": context.hotel_id, "user_id": user_id, "restored": restored}


@router.get("/effective/preview")
def preview_effective_permissions(
    user_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    membership = _target_membership_or_404(db, context.hotel_id, user_id)
    details = get_effective_permission_details(
        db,
        context.hotel_id,
        membership.role,
        user_id=user_id,
    )
    return {
        "hotel_id": context.hotel_id,
        "user_id": user_id,
        "role": membership.role,
        "permissions": get_effective_permissions(
            db,
            context.hotel_id,
            membership.role,
            user_id=user_id,
        ),
        "details": details,
    }
