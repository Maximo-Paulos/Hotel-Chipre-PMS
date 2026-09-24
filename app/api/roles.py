"""Tenant-scoped custom role catalog and lifecycle endpoints."""

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission, require_roles_and_permission
from app.services.permission_service import (
    HotelRoleInUse,
    HotelRoleNameConflict,
    HotelRoleNotFound,
    HotelRoleVersionConflict,
    PERMISSION_PERMISSION_MANAGE,
    PERMISSION_SETTINGS_USERS_VIEW,
    archive_custom_role,
    create_custom_role,
    list_hotel_roles,
    publish_permission_invalidation,
    update_custom_role_name,
)


router = APIRouter(prefix="/api/roles", tags=["Roles"])
_MANAGE_ROLES = require_permission(PERMISSION_PERMISSION_MANAGE)
_READ_ROLES = require_roles_and_permission(PERMISSION_SETTINGS_USERS_VIEW, "owner", "co_owner")
CustomRoleBase = Literal["manager", "receptionist", "housekeeping"]


class RoleCatalogItem(BaseModel):
    code: str
    name: str
    kind: Literal["builtin", "custom"]
    base_role: str | None
    is_active: bool
    assigned_count: int
    pending_invitation_count: int
    permission_count: int
    version: int


class RoleListResponse(BaseModel):
    roles: list[RoleCatalogItem]


class RoleResponse(BaseModel):
    role: RoleCatalogItem


class CreateCustomRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_role: CustomRoleBase


class RenameCustomRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    expected_version: int = Field(ge=1)


class ArchiveCustomRoleRequest(BaseModel):
    expected_version: int = Field(ge=1)


def _role_item(row: dict[str, object]) -> RoleCatalogItem:
    return RoleCatalogItem.model_validate(row)


def _rollback_and_raise(db: Session, exc: Exception, *, code: int, message: str) -> None:
    db.rollback()
    raise HTTPException(status_code=code, detail=message) from exc


@router.get("", response_model=RoleListResponse)
def read_roles(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_READ_ROLES),
) -> RoleListResponse:
    return RoleListResponse(roles=[_role_item(row) for row in list_hotel_roles(db, context.hotel_id)])


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: CreateCustomRoleRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_ROLES),
) -> RoleResponse:
    try:
        row = create_custom_role(
            db,
            context.hotel_id,
            name=payload.name,
            base_role=payload.base_role,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(row)
    except HotelRoleNameConflict as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_409_CONFLICT, message=str(exc))
    except ValueError as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=str(exc))
    except IntegrityError as exc:
        _rollback_and_raise(
            db,
            exc,
            code=status.HTTP_409_CONFLICT,
            message="No se pudo crear el rol por un conflicto de datos",
        )
    publish_permission_invalidation(context.hotel_id)
    created_code = row.code
    role_data = next(item for item in list_hotel_roles(db, context.hotel_id) if item["code"] == created_code)
    return RoleResponse(role=_role_item(role_data))


@router.patch("/{role_code}", response_model=RoleResponse)
def rename_role(
    role_code: str,
    payload: RenameCustomRoleRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_ROLES),
) -> RoleResponse:
    try:
        row = update_custom_role_name(
            db,
            context.hotel_id,
            role_code,
            name=payload.name,
            expected_version=payload.expected_version,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(row)
    except HotelRoleNotFound as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_404_NOT_FOUND, message="Rol no encontrado")
    except (HotelRoleNameConflict, HotelRoleVersionConflict, StaleDataError) as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_409_CONFLICT, message=str(exc))
    except ValueError as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=str(exc))
    except IntegrityError as exc:
        _rollback_and_raise(
            db,
            exc,
            code=status.HTTP_409_CONFLICT,
            message="No se pudo actualizar el rol por un conflicto de datos",
        )
    publish_permission_invalidation(context.hotel_id)
    role_data = next(row for row in list_hotel_roles(db, context.hotel_id) if row["code"] == role_code)
    return RoleResponse(role=_role_item(role_data))


@router.delete("/{role_code}", response_model=RoleResponse)
def delete_role(
    role_code: str,
    payload: ArchiveCustomRoleRequest | None = Body(default=None),
    expected_version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_ROLES),
) -> RoleResponse:
    if payload is None and expected_version is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expected_version es obligatorio",
        )
    if payload is not None and expected_version is not None and payload.expected_version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expected_version debe coincidir en el body y la query",
        )
    if payload is not None:
        version = payload.expected_version
    else:
        assert expected_version is not None
        version = expected_version
    try:
        row = archive_custom_role(
            db,
            context.hotel_id,
            role_code,
            expected_version=version,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(row)
    except HotelRoleNotFound as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_404_NOT_FOUND, message="Rol no encontrado")
    except (HotelRoleInUse, HotelRoleVersionConflict, StaleDataError) as exc:
        _rollback_and_raise(db, exc, code=status.HTTP_409_CONFLICT, message=str(exc))
    except IntegrityError as exc:
        _rollback_and_raise(
            db,
            exc,
            code=status.HTTP_409_CONFLICT,
            message="No se pudo archivar el rol por un conflicto de datos",
        )
    if row.is_active is False:
        publish_permission_invalidation(context.hotel_id)
    role_data = next(row_data for row_data in list_hotel_roles(db, context.hotel_id) if row_data["code"] == role_code)
    return RoleResponse(role=_role_item(role_data))
