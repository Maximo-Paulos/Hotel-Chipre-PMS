"""
FastAPI routes for stock and inventory operations.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.services.stock_service import (
    StockError,
    create_location,
    create_stock_item,
    current_stock,
    delete_location,
    delete_stock_item,
    get_location,
    get_stock_item,
    list_locations,
    list_stock_items,
    low_stock_items,
    register_movement,
    update_location,
    update_stock_item,
)

router = APIRouter(prefix="/api/stock", tags=["Stock"])


class StockItemCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool = True


class StockItemUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    min_quantity: Optional[Decimal] = None
    active: Optional[bool] = None


class StockItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str
    sku: Optional[str] = None
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool


class StockLocationCreate(BaseModel):
    name: str


class StockLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str


class StockMovementCreate(BaseModel):
    item_id: int
    location_id: Optional[int] = None
    movement_type: str
    quantity: Decimal
    reason: Optional[str] = None
    reservation_id: Optional[int] = None


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    item_id: int
    location_id: Optional[int] = None
    movement_type: str
    quantity: Decimal
    reason: Optional[str] = None
    reservation_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime


@router.post("/items", response_model=StockItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    data: StockItemCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    item = create_stock_item(db, hotel_id=context.hotel_id, **data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@router.get("/items", response_model=list[StockItemRead])
def list_items(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_stock_items(db, hotel_id=context.hotel_id)


@router.get("/items/low-stock", response_model=list[StockItemRead])
def list_low_stock_items(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return low_stock_items(db, hotel_id=context.hotel_id)


@router.get("/items/{item_id}", response_model=StockItemRead)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        return get_stock_item(db, hotel_id=context.hotel_id, item_id=item_id)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/items/{item_id}", response_model=StockItemRead)
def update_item(
    item_id: int,
    data: StockItemUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        item = update_stock_item(db, hotel_id=context.hotel_id, item_id=item_id, **data.model_dump(exclude_unset=True))
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        delete_stock_item(
            db,
            hotel_id=context.hotel_id,
            item_id=item_id,
            deleted_by_user_id=context.user_id,
        )
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return None


@router.post("/locations", response_model=StockLocationRead, status_code=status.HTTP_201_CREATED)
def create_stock_location(
    data: StockLocationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    location = create_location(db, hotel_id=context.hotel_id, name=data.name)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[StockLocationRead])
def list_stock_locations(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_locations(db, hotel_id=context.hotel_id)


@router.get("/locations/{location_id}", response_model=StockLocationRead)
def get_stock_location(
    location_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        return get_location(db, hotel_id=context.hotel_id, location_id=location_id)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/locations/{location_id}", response_model=StockLocationRead)
def update_stock_location(
    location_id: int,
    data: StockLocationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        location = update_location(db, hotel_id=context.hotel_id, location_id=location_id, name=data.name)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    db.refresh(location)
    return location


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock_location(
    location_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        delete_location(
            db,
            hotel_id=context.hotel_id,
            location_id=location_id,
            deleted_by_user_id=context.user_id,
        )
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return None


@router.post("/movements", response_model=StockMovementRead, status_code=status.HTTP_201_CREATED)
def create_movement(
    data: StockMovementCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        movement = register_movement(
            db,
            hotel_id=context.hotel_id,
            created_by_user_id=context.user_id,
            **data.model_dump(),
        )
    except StockError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/items/{item_id}/current")
def get_current_stock(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    try:
        quantity = current_stock(db, hotel_id=context.hotel_id, item_id=item_id)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"item_id": item_id, "quantity": quantity}
