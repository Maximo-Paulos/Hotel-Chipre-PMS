"""
FastAPI routes for laundry operations.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.services.permission_service import PERMISSION_LAUNDRY_MOVE, PERMISSION_LAUNDRY_READ
from app.services.laundry_service import (
    LaundryError,
    add_item,
    create_batch,
    get_batch,
    list_batches,
    transition_status,
)

router = APIRouter(prefix="/api/laundry", tags=["Laundry"])


class LaundryItemCreate(BaseModel):
    item_type: str
    quantity: int
    room_id: Optional[int] = None


class LaundryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    batch_id: int
    item_type: str
    quantity: int
    room_id: Optional[int] = None


class LaundryBatchCreate(BaseModel):
    notes: Optional[str] = None


class LaundryBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    batch_code: str
    status: str
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    items: list[LaundryItemRead] = Field(default_factory=list)


class LaundryStatusUpdate(BaseModel):
    status: str


@router.post("/batches", response_model=LaundryBatchRead, status_code=status.HTTP_201_CREATED)
def create_laundry_batch(
    data: LaundryBatchCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MOVE)),
):
    batch = create_batch(
        db,
        hotel_id=context.hotel_id,
        notes=data.notes,
        created_by_user_id=context.user_id,
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches", response_model=list[LaundryBatchRead])
def list_laundry_batches(
    status_filter: Optional[str] = None,
    batch_code: Optional[str] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_READ)),
):
    return list_batches(
        db,
        hotel_id=context.hotel_id,
        filters={"status": status_filter, "batch_code": batch_code},
    )


@router.get("/batches/{batch_id}", response_model=LaundryBatchRead)
def get_laundry_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_READ)),
):
    try:
        return get_batch(db, hotel_id=context.hotel_id, batch_id=batch_id)
    except LaundryError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/batches/{batch_id}/items", response_model=LaundryItemRead, status_code=status.HTTP_201_CREATED)
def add_laundry_item(
    batch_id: int,
    data: LaundryItemCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MOVE)),
):
    try:
        item = add_item(db, hotel_id=context.hotel_id, batch_id=batch_id, **data.model_dump())
    except LaundryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(item)
    return item


@router.patch("/batches/{batch_id}/status", response_model=LaundryBatchRead)
def update_laundry_status(
    batch_id: int,
    data: LaundryStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MOVE)),
):
    try:
        batch = transition_status(db, hotel_id=context.hotel_id, batch_id=batch_id, new_status=data.status)
    except LaundryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(batch)
    return batch
