"""Staff management endpoints for hotel public API keys."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.hotel_api_key import HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead
from app.services.hotel_api_key_service import HotelAPIKeyError, issue_key, list_keys, revoke_key


router = APIRouter(prefix="/api/hotel-api-keys", tags=["Hotel API Keys"])


@router.post("", response_model=HotelAPIKeyIssued, status_code=status.HTTP_201_CREATED)
def issue_hotel_api_key(
    payload: HotelAPIKeyIssue,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission("apikey:manage")),
):
    try:
        key, secret = issue_key(
            db,
            hotel_id=context.hotel_id,
            name=payload.name,
            purpose=payload.purpose,
            created_by_user_id=context.user_id,
            expires_at=payload.expires_at,
        )
        db.commit()
        db.refresh(key)
        safe = HotelAPIKeyRead.model_validate(key).model_dump()
        return HotelAPIKeyIssued(**safe, secret=secret)
    except HotelAPIKeyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[HotelAPIKeyRead])
def list_hotel_api_keys(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission("apikey:manage")),
):
    return list_keys(db, hotel_id=context.hotel_id)


@router.post("/{key_id}/revoke", response_model=HotelAPIKeyRead)
def revoke_hotel_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission("apikey:manage")),
):
    try:
        key = revoke_key(db, hotel_id=context.hotel_id, key_id=key_id, revoked_by_user_id=context.user_id)
        db.commit()
        db.refresh(key)
        return key
    except HotelAPIKeyError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
