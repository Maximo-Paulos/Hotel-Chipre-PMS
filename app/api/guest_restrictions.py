"""
FastAPI routes for GuestRestriction (formal lodging-prohibition entity).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_any_permission, require_permission
from app.models.guest import Guest
from app.models.guest_restriction import GuestRestriction
from app.schemas.guest_restriction import (
    GuestRestrictionCreate,
    GuestRestrictionRead,
    GuestRestrictionResolveRequest,
)
from app.services.guest_restriction_service import (
    GuestRestrictionConflictError,
    GuestRestrictionNotFoundError,
    create_guest_restriction,
    get_active_guest_restrictions,
    resolve_guest_restriction,
)
from app.services.permission_service import (
    PERMISSION_GUEST_PROHIBITION_MANAGE,
    PERMISSION_GUEST_PROHIBITION_READ,
)

router = APIRouter(prefix="/api/guests", tags=["Guest Restrictions"])


def _get_tenant_guest(db: Session, hotel_id: int, guest_id: int) -> Guest:
    """Tenant-scoped lookup. Cross-hotel access must 404, never 403 --
    existence of a guest in another hotel is not disclosed."""
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.hotel_id == hotel_id).one_or_none()
    if guest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guest not found")
    return guest


@router.post(
    "/{guest_id}/restrictions",
    response_model=GuestRestrictionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_restriction(
    guest_id: int,
    data: GuestRestrictionCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_PROHIBITION_MANAGE)),
):
    _get_tenant_guest(db, context.hotel_id, guest_id)
    restriction = create_guest_restriction(
        db,
        hotel_id=context.hotel_id,
        guest_id=guest_id,
        reason=data.reason,
        detail=data.detail,
        valid_until=data.valid_until,
        created_by_user_id=context.user_id,
    )
    db.commit()
    db.refresh(restriction)
    return restriction


@router.get("/{guest_id}/restrictions", response_model=list[GuestRestrictionRead])
def list_restrictions(
    guest_id: int,
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_GUEST_PROHIBITION_READ, PERMISSION_GUEST_PROHIBITION_MANAGE)
    ),
):
    _get_tenant_guest(db, context.hotel_id, guest_id)
    if active_only:
        return get_active_guest_restrictions(db, hotel_id=context.hotel_id, guest_id=guest_id)
    return (
        db.query(GuestRestriction)
        .filter(GuestRestriction.hotel_id == context.hotel_id, GuestRestriction.guest_id == guest_id)
        .order_by(GuestRestriction.id)
        .all()
    )


@router.post("/{guest_id}/restrictions/{restriction_id}/resolve", response_model=GuestRestrictionRead)
def resolve_restriction(
    guest_id: int,
    restriction_id: int,
    data: GuestRestrictionResolveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_PROHIBITION_MANAGE)),
):
    _get_tenant_guest(db, context.hotel_id, guest_id)
    try:
        restriction = resolve_guest_restriction(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            restriction_id=restriction_id,
            resolved_by_user_id=context.user_id,
            resolution_note=data.resolution_note,
        )
    except GuestRestrictionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GuestRestrictionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(restriction)
    return restriction
