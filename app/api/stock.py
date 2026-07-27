"""
FastAPI routes for stock and inventory operations.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_any_permission, require_permission
from app.services.permission_service import (
    PERMISSION_LAUNDRY_OPERATE_REMITOS,
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_OPERATE,
    audit_permission_denied,
    resolve,
)
from app.services.stock_service import (
    StockError,
    consumption_report,
    create_location,
    create_stock_item,
    current_stock,
    delete_location,
    delete_stock_item,
    get_location,
    get_stock_item,
    list_stock_movements,
    list_locations,
    list_stock_items,
    low_stock_items,
    register_movement,
    update_location,
    update_stock_item,
)

router = APIRouter(prefix="/api/stock", tags=["Stock"])


def _ensure_adjustment_permission(db: Session, context: AuthContext) -> None:
    if resolve(db, context.hotel_id, context.user_role, PERMISSION_STOCK_ADJUST):
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=PERMISSION_STOCK_ADJUST,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para ajustar stock")


StockItemKind = Literal["supply", "linen"]


class StockItemCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool = True
    # StockPage never sends this (always "supply", the default) -- only
    # LaundryPage's own item-creation form sends "linen". See list_items(kind=).
    kind: StockItemKind = "supply"


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
    kind: StockItemKind


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


class StockConsumptionItem(BaseModel):
    stock_item_id: int
    stock_item_name: str
    unit: str
    current_quantity: Decimal
    previous_quantity: Decimal
    variation_pct: Optional[Decimal] = None


class StockConsumptionReportRead(BaseModel):
    hotel_id: int
    group_by: str
    date_from: date
    date_to: date
    previous_date_from: date
    previous_date_to: date
    items: list[StockConsumptionItem]


@router.post("/items", response_model=StockItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    data: StockItemCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    try:
        item = create_stock_item(db, hotel_id=context.hotel_id, **data.model_dump())
    except StockError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(item)
    return item


@router.get("/items", response_model=list[StockItemRead])
def list_items(
    # StockPage asks for kind=supply, LaundryPage asks for kind=linen; omit
    # to get the old undifferentiated hotel-wide list (back-compat).
    kind: Optional[StockItemKind] = None,
    db: Session = Depends(get_db),
    # D2 (laundry vendors): a remito line picks a StockItem the same way it
    # picks a StockLocation above -- same require_any_permission reasoning.
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_STOCK_OPERATE, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    return list_stock_items(db, hotel_id=context.hotel_id, kind=kind)


@router.get("/items/low-stock", response_model=list[StockItemRead])
def list_low_stock_items(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    return low_stock_items(db, hotel_id=context.hotel_id)


@router.get("/items/{item_id}", response_model=StockItemRead)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    location = create_location(db, hotel_id=context.hotel_id, name=data.name)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[StockLocationRead])
def list_stock_locations(
    db: Session = Depends(get_db),
    # D2 (laundry vendors): housekeeping holds laundry:operate_remitos but not
    # stock:operate, and still needs this list to pick a house StockLocation
    # when filing a remito -- see frontend/src/views/protected/LaundryPage.tsx.
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_STOCK_OPERATE, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    return list_locations(db, hotel_id=context.hotel_id)


@router.get("/locations/{location_id}", response_model=StockLocationRead)
def get_stock_location(
    location_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    try:
        if data.movement_type in ("adjustment", "adjustment_out"):
            _ensure_adjustment_permission(db, context)
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


@router.get("/movements", response_model=list[StockMovementRead])
def list_movements(
    item_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    return list_stock_movements(db, hotel_id=context.hotel_id, item_id=item_id, limit=limit)


@router.get("/consumption-report", response_model=StockConsumptionReportRead)
def get_stock_consumption_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    group_by: str = Query(default="week"),
    db: Session = Depends(get_db),
    # D5 (Via D): same permission as every other stock read in this router
    # (list_items, list_movements, ...) -- there is no separate "read stock"
    # permission today, and this report is derived from the same movements
    # anyone with stock:operate can already list one by one.
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    try:
        return consumption_report(
            db, hotel_id=context.hotel_id, date_from=date_from, date_to=date_to, group_by=group_by
        )
    except StockError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/items/{item_id}/current")
def get_current_stock(
    item_id: int,
    # Optional narrowing to one StockLocation -- e.g. D2 (laundry vendors)
    # uses this to show "clean linen at the hotel" vs the hotel-wide total,
    # which never changes for a transfer (see current_stock() docstring).
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_OPERATE)),
):
    try:
        quantity = current_stock(db, hotel_id=context.hotel_id, item_id=item_id, location_id=location_id)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"item_id": item_id, "quantity": quantity}
