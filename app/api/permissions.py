"""Thin FastAPI transport for the tenant-scoped permission service."""
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.database import get_db
from app.dependencies.auth import (
    AuthContext,
    get_auth_context,
    require_permission_administrator,
    require_roles,
)
from app.models.hotel_membership import HotelMembership
from app.schemas.permission import (
    RolePermissionOverrideRequest,
    TemporaryActionGrantApproveRequest,
    TemporaryActionGrantConsumeRequest,
    TemporaryActionGrantRequest,
    UserPermissionOverrideRequest,
    VisibilityWindowRead,
    VisibilityWindowUpdate,
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
    list_visibility_windows,
    publish_permission_invalidation,
    PermissionVersionConflict,
    restore_role_override,
    restore_role_defaults,
    restore_user_override,
    restore_user_defaults,
    set_role_override,
    set_user_override,
    set_visibility_window,
)
from app.services.temporary_action_grant_service import (
    TemporaryGrantActor,
    TemporaryGrantAuthorizationError,
    TemporaryGrantError,
    TemporaryGrantMfaError,
    TemporaryGrantNotFoundError,
    TemporaryGrantStateError,
    approve_grant,
    consume_grant,
    deny_grant,
    list_pending_grants_for_hotel,
    request_grant,
)

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


def _temporary_grant_actor(context: AuthContext) -> TemporaryGrantActor:
    if context.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacion requerida")
    return TemporaryGrantActor(user_id=context.user_id, hotel_id=context.hotel_id)


def _temporary_grant_response(grant) -> dict:
    return {
        "id": grant.id,
        "hotel_id": grant.hotel_id,
        "requester_user_id": grant.requester_user_id,
        "approver_user_id": grant.approver_user_id,
        "permission_code": grant.permission_code,
        "resource_type": grant.resource_type,
        "resource_id": grant.resource_id,
        "reason": grant.reason,
        "status": grant.status.value if hasattr(grant.status, "value") else grant.status,
        "created_at": grant.created_at,
        "approved_at": grant.approved_at,
        "used_at": grant.used_at,
        "expires_at": grant.expires_at,
    }


def _raise_temporary_grant_http_error(exc: TemporaryGrantError) -> None:
    if isinstance(exc, TemporaryGrantNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant no encontrado") from exc
    if isinstance(exc, TemporaryGrantStateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, TemporaryGrantMfaError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, TemporaryGrantAuthorizationError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


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


def _assert_manageable_membership(actor_role: str | None, membership: HotelMembership, *, action: str) -> None:
    """Keep permission exceptions aligned with the staff-management boundary."""
    managed_roles = {
        "owner": {"co_owner", "manager", "receptionist", "housekeeping"},
        "co_owner": {"manager", "receptionist", "housekeeping"},
    }
    if membership.role not in managed_roles.get(actor_role or "", set()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tenes permisos para {action} este usuario",
        )


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
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    return {"hotel_id": context.hotel_id, "permissions": get_permission_catalog(db)}


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
            expected_version=payload.expected_version,
        )
        db.commit()
    except PermissionVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El permiso fue modificado por otra solicitud") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.refresh(override)
    publish_permission_invalidation(context.hotel_id)
    return {
        "hotel_id": override.hotel_id,
        "role": override.role,
        "permission_code": override.permission_code,
        "allowed": bool(override.allowed),
        "version": override.version,
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


def _visibility_window_response(row, role: str | None = None) -> dict:
    return {
        "role": row.role if row is not None else role,
        "past_hours": row.past_hours if row is not None else None,
        "future_hours": row.future_hours if row is not None else None,
        "updated_by_user_id": row.updated_by_user_id if row is not None else None,
        "updated_at": row.updated_at if row is not None else None,
    }


@router.get("/visibility-windows")
def read_visibility_windows(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    configured = {row.role: row for row in list_visibility_windows(db, context.hotel_id)}
    return {
        "hotel_id": context.hotel_id,
        "windows": [
            _visibility_window_response(configured.get(role), role)
            for role in ROLE_CODES
        ],
    }


@router.put("/visibility-windows", response_model=VisibilityWindowRead)
def update_visibility_window(
    payload: VisibilityWindowUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission_administrator),
):
    try:
        row = set_visibility_window(
            db,
            context.hotel_id,
            payload.role,
            payload.past_hours,
            payload.future_hours,
            context.user_id,
        )
        db.commit()
        db.refresh(row)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _visibility_window_response(row)


@router.delete("/overrides/role/{role}/{permission_code}")
@router.delete("/role-overrides/{role}/{permission_code}")
def restore_role_permission_override(
    role: str,
    permission_code: str,
    expected_version: int = Query(
        ..., ge=1, description="Version actual del override que se va a restaurar"
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _validate_role(role)
    code = _validate_code(permission_code)
    try:
        restored = restore_role_override(
            db,
            context.hotel_id,
            role,
            code,
            actor_user_id=context.user_id,
            expected_version=expected_version,
        )
        db.commit()
    except PermissionVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El permiso fue modificado por otra solicitud",
        ) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    publish_permission_invalidation(context.hotel_id)
    return restored


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
            expected_version=payload.expected_version,
        )
        db.commit()
    except PermissionVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El permiso fue modificado por otra solicitud") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.refresh(override)
    publish_permission_invalidation(context.hotel_id)
    return {
        "hotel_id": override.hotel_id,
        "user_id": override.user_id,
        "role": membership.role,
        "permission_code": override.permission_code,
        "allowed": bool(override.allowed),
        "version": override.version,
        "source": "user_override",
        "locked": False,
        "updated_by_user_id": override.updated_by_user_id,
        "updated_at": override.updated_at,
    }


@router.delete("/overrides/user/{user_id}/{permission_code}")
@router.delete("/user-overrides/{user_id}/{permission_code}")
def restore_user_permission_override(
    user_id: int,
    permission_code: str,
    expected_version: int = Query(
        ..., ge=1, description="Version actual del override que se va a restaurar"
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    if user_id == context.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No puedes modificar tus propios permisos",
        )
    membership = _target_membership_or_404(db, context.hotel_id, user_id)
    _assert_manageable_membership(context.user_role, membership, action="restaurar permisos de")
    code = _validate_code(permission_code)
    try:
        restored = restore_user_override(
            db,
            context.hotel_id,
            user_id,
            actor_user_id=context.user_id,
            code=code,
            expected_version=expected_version,
        )
        db.commit()
    except PermissionVersionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El permiso fue modificado por otra solicitud",
        ) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    publish_permission_invalidation(context.hotel_id)
    return restored


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


@router.post("/temporary-grants/request", status_code=status.HTTP_201_CREATED)
def create_temporary_action_grant(
    payload: TemporaryActionGrantRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    """Ask for one exceptional permission without changing the requester's role."""
    try:
        grant = request_grant(
            db,
            context.hotel_id,
            _temporary_grant_actor(context),
            payload.permission_code,
            payload.resource_type,
            payload.resource_id,
            payload.reason,
        )
        db.commit()
        db.refresh(grant)
        return _temporary_grant_response(grant)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except TemporaryGrantError as exc:
        db.rollback()
        _raise_temporary_grant_http_error(exc)


@router.get("/temporary-grants/pending")
def read_pending_temporary_action_grants(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    grants = list_pending_grants_for_hotel(db, context.hotel_id)
    return {
        "hotel_id": context.hotel_id,
        "grants": [_temporary_grant_response(grant) for grant in grants],
    }


@router.post("/temporary-grants/{grant_id}/approve")
def approve_temporary_action_grant(
    payload: TemporaryActionGrantApproveRequest,
    grant_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        grant, token = approve_grant(
            db,
            grant_id,
            _temporary_grant_actor(context),
            payload.totp_code,
        )
        db.commit()
        db.refresh(grant)
        return {"grant": _temporary_grant_response(grant), "token": token}
    except TemporaryGrantError as exc:
        db.rollback()
        _raise_temporary_grant_http_error(exc)


@router.post("/temporary-grants/{grant_id}/deny")
def deny_temporary_action_grant(
    grant_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        grant = deny_grant(db, grant_id, _temporary_grant_actor(context))
        db.commit()
        db.refresh(grant)
        return _temporary_grant_response(grant)
    except TemporaryGrantError as exc:
        db.rollback()
        _raise_temporary_grant_http_error(exc)


@router.post("/temporary-grants/consume")
def consume_temporary_action_grant(
    payload: TemporaryActionGrantConsumeRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        consumed = consume_grant(db, payload.token, _temporary_grant_actor(context))
        db.commit()
    except TemporaryGrantError as exc:
        db.rollback()
        _raise_temporary_grant_http_error(exc)
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grant invalido, expirado o ya consumido",
        )
    return {"consumed": True}
