"""
FastAPI routes for stock and inventory operations.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.datetime_types import UTCDateTime
from app.services.permission_service import (
    PERMISSION_STOCK_ADJUST,
    PERMISSION_STOCK_ADMIN,
    PERMISSION_STOCK_COUNT_CONFIRM,
    PERMISSION_STOCK_MOVE,
    PERMISSION_STOCK_READ,
    audit_permission_denied,
    resolve,
)
from app.services.stock_service import (
    StockCountRecountRequired,
    StockError,
    StockIdempotencyConflict,
    cancel_stock_count_session,
    confirm_stock_count_session,
    consumption_report,
    create_location,
    create_stock_count_session,
    create_stock_item,
    current_stock,
    delete_location,
    delete_stock_item,
    get_location,
    get_stock_count_session,
    get_stock_item,
    list_locations,
    list_stock_count_sessions,
    list_stock_items,
    list_stock_movements,
    low_stock_items,
    record_stock_count,
    register_movement,
    register_opening_count,
    stock_summary,
    transfer_stock,
    update_location,
    update_stock_item,
)

router = APIRouter(prefix="/api/stock", tags=["Stock"])


def _ensure_adjustment_permission(db: Session, context: AuthContext) -> None:
    if resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_STOCK_ADJUST,
        user_id=context.user_id,
    ):
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=PERMISSION_STOCK_ADJUST,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para ajustar stock")


class StockItemCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool = True
    # ARS, same as the rest of Stock -- see app/models/stock.py StockItem.unit_cost.
    unit_cost: Optional[Decimal] = None


class StockItemUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    unit: Optional[str] = None
    min_quantity: Optional[Decimal] = None
    active: Optional[bool] = None
    unit_cost: Optional[Decimal] = None


class StockItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str
    sku: Optional[str] = None
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool
    unit_cost: Optional[Decimal] = None


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
    created_at: UTCDateTime
    idempotency_key: Optional[str] = None
    transfer_reference: Optional[str] = None


class StockTransferCreate(BaseModel):
    item_id: int = Field(gt=0)
    source_location_id: int = Field(gt=0)
    destination_location_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class StockTransferRead(BaseModel):
    transfer_reference: str
    outbound: StockMovementRead
    inbound: StockMovementRead


class StockOpeningCountCreate(BaseModel):
    item_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class StockCountSessionCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("A reason is required")
        return normalized


class StockCountRecordCreate(BaseModel):
    item_id: int = Field(gt=0)
    location_id: int | None = Field(default=None, gt=0)
    counted_quantity: Decimal = Field(ge=0, le=Decimal("9999999999.99"))

    @field_validator("counted_quantity")
    @classmethod
    def supported_count_precision(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Counted quantity must be finite")
        if value % Decimal("0.01") != 0:
            raise ValueError("Counted quantity supports at most two decimal places")
        return value


class StockCountConfirmation(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("A confirmation reason is required")
        return normalized


class StockCountSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    status: str
    reason: str
    created_by_user_id: int | None
    created_at: UTCDateTime
    counter_user_id: int | None
    confirmed_by_user_id: int | None
    confirmation_reason: str | None
    confirmed_at: UTCDateTime | None
    self_approved: bool
    cancelled_by_user_id: int | None
    cancellation_reason: str | None
    cancelled_at: UTCDateTime | None


class StockCountLineRead(BaseModel):
    id: int
    item_id: int
    item_name: str
    location_id: int | None
    location_name: str | None
    system_quantity_at_count: Decimal
    counted_quantity: Decimal
    movement_version: int
    current_movement_version: int
    recount_required: bool
    counted_by_user_id: int | None
    counted_at: UTCDateTime
    applied_adjustment: Decimal | None
    adjusted_at: UTCDateTime | None


class StockCountSessionDetailRead(StockCountSessionRead):
    counts: list[StockCountLineRead]


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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
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
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    return list_stock_items(db, hotel_id=context.hotel_id)


class StockLocationBalanceRead(BaseModel):
    location_id: int
    location_name: str
    current_quantity: Decimal
    has_movements: bool


class StockSummaryEntry(BaseModel):
    item: StockItemRead
    current_quantity: Decimal
    location_balances: list[StockLocationBalanceRead] = Field(default_factory=list)


@router.get("/summary", response_model=list[StockSummaryEntry])
def get_stock_summary(
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    """Every item's current balance in one request -- avoids the N+1
    per-item /items/{id}/current pattern for grids that need every balance
    at once (see StockPage.tsx).
    """
    return stock_summary(db, hotel_id=context.hotel_id, location_id=location_id)


@router.get("/items/low-stock", response_model=list[StockItemRead])
def list_low_stock_items(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    return low_stock_items(db, hotel_id=context.hotel_id)


@router.get("/items/{item_id}", response_model=StockItemRead)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
):
    location = create_location(db, hotel_id=context.hotel_id, name=data.name)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[StockLocationRead])
def list_stock_locations(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    return list_locations(db, hotel_id=context.hotel_id)


@router.get("/locations/{location_id}", response_model=StockLocationRead)
def get_stock_location(
    location_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADMIN)),
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
    # Same convention as POST /api/payment-links: a client-generated key on a
    # retried request (e.g. a flaky connection resends the same POST) so the
    # retry returns the first attempt's movement instead of double-counting
    # stock, rather than being part of the JSON body.
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_MOVE)),
):
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not 8 <= len(idempotency_key) <= 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Idempotency-Key must contain between 8 and 100 non-whitespace characters",
            )
    try:
        if data.movement_type in ("adjustment", "adjustment_out"):
            _ensure_adjustment_permission(db, context)
        movement = register_movement(
            db,
            hotel_id=context.hotel_id,
            created_by_user_id=context.user_id,
            idempotency_key=idempotency_key,
            **data.model_dump(),
        )
    except StockIdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StockError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(movement)
    return movement


@router.post("/transfers", response_model=StockTransferRead, status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    data: StockTransferCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_MOVE)),
):
    try:
        reference, outbound, inbound = transfer_stock(
            db,
            hotel_id=context.hotel_id,
            item_id=data.item_id,
            source_location_id=data.source_location_id,
            destination_location_id=data.destination_location_id,
            quantity=data.quantity,
            reason=data.reason,
            created_by_user_id=context.user_id,
            idempotency_key=idempotency_key,
        )
    except StockIdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    db.refresh(outbound)
    db.refresh(inbound)
    return {"transfer_reference": reference, "outbound": outbound, "inbound": inbound}


@router.post("/opening-counts", response_model=StockMovementRead, status_code=status.HTTP_201_CREATED)
def create_opening_stock_count(
    data: StockOpeningCountCreate,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_ADJUST)),
):
    try:
        movement = register_opening_count(
            db,
            hotel_id=context.hotel_id,
            item_id=data.item_id,
            location_id=data.location_id,
            quantity=data.quantity,
            reason=data.reason,
            created_by_user_id=context.user_id,
            idempotency_key=idempotency_key,
        )
    except StockIdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StockError as exc:
        # An opening count is valid only while this item/location has no
        # movement history; stale forms are conflicts and must be refreshed.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    db.refresh(movement)
    return movement


def _stock_count_line_read(line, *, session_status: str) -> StockCountLineRead:
    item = line.item
    location = line.location
    current_version = item.movement_version or 0
    return StockCountLineRead(
        id=line.id,
        item_id=line.item_id,
        item_name=item.name,
        location_id=line.location_id,
        location_name=location.name if location is not None else None,
        system_quantity_at_count=line.system_quantity_at_count,
        counted_quantity=line.counted_quantity,
        movement_version=line.movement_version,
        current_movement_version=current_version,
        recount_required=session_status == "open"
        and current_version != line.movement_version,
        counted_by_user_id=line.counted_by_user_id,
        counted_at=line.counted_at,
        applied_adjustment=line.applied_adjustment,
        adjusted_at=line.adjusted_at,
    )


def _stock_count_session_detail(session) -> StockCountSessionDetailRead:
    return StockCountSessionDetailRead(
        **StockCountSessionRead.model_validate(session).model_dump(),
        counts=[
            _stock_count_line_read(line, session_status=session.status)
            for line in session.counts
        ],
    )


@router.post(
    "/count-sessions",
    response_model=StockCountSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def start_stock_count_session(
    data: StockCountSessionCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_MOVE)),
):
    try:
        session = create_stock_count_session(
            db,
            hotel_id=context.hotel_id,
            created_by_user_id=context.user_id,
            reason=data.reason,
        )
    except StockError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(session)
    return session


@router.get("/count-sessions", response_model=list[StockCountSessionRead])
def get_stock_count_sessions(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    return list_stock_count_sessions(
        db, hotel_id=context.hotel_id, limit=limit, offset=offset
    )


@router.get("/count-sessions/{session_id}", response_model=StockCountSessionDetailRead)
def get_stock_count_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    try:
        session = get_stock_count_session(
            db, hotel_id=context.hotel_id, session_id=session_id
        )
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _stock_count_session_detail(session)


@router.post(
    "/count-sessions/{session_id}/counts",
    response_model=StockCountLineRead,
    status_code=status.HTTP_201_CREATED,
)
def record_stock_count_line(
    session_id: int,
    data: StockCountRecordCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_MOVE)),
):
    try:
        line = record_stock_count(
            db,
            hotel_id=context.hotel_id,
            session_id=session_id,
            item_id=data.item_id,
            location_id=data.location_id,
            counted_quantity=data.counted_quantity,
            counted_by_user_id=context.user_id,
        )
    except StockError as exc:
        message = str(exc)
        code = (
            404
            if message
            in {
                "Stock count session not found",
                "Stock item not found",
                "Stock location not found",
            }
            else 409
        )
        raise HTTPException(status_code=code, detail=message)
    db.commit()
    db.refresh(line)
    return _stock_count_line_read(line, session_status="open")


@router.post(
    "/count-sessions/{session_id}/confirm",
    response_model=StockCountSessionDetailRead,
)
def confirm_stock_count(
    session_id: int,
    data: StockCountConfirmation,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_COUNT_CONFIRM)),
):
    try:
        session = confirm_stock_count_session(
            db,
            hotel_id=context.hotel_id,
            session_id=session_id,
            confirmed_by_user_id=context.user_id,
            reason=data.reason,
        )
    except StockCountRecountRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "recount_required": exc.items,
            },
        )
    except StockError as exc:
        message = str(exc)
        code = 404 if message == "Stock count session not found" else 409
        raise HTTPException(status_code=code, detail=message)
    db.commit()
    return _stock_count_session_detail(
        get_stock_count_session(db, hotel_id=context.hotel_id, session_id=session_id)
    )


@router.post(
    "/count-sessions/{session_id}/cancel",
    response_model=StockCountSessionRead,
)
def cancel_stock_count(
    session_id: int,
    data: StockCountConfirmation,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_COUNT_CONFIRM)),
):
    try:
        session = cancel_stock_count_session(
            db,
            hotel_id=context.hotel_id,
            session_id=session_id,
            cancelled_by_user_id=context.user_id,
            reason=data.reason,
        )
    except StockError as exc:
        message = str(exc)
        code = 404 if message == "Stock count session not found" else 409
        raise HTTPException(status_code=code, detail=message)
    db.commit()
    db.refresh(session)
    return session


@router.get("/movements", response_model=list[StockMovementRead])
def list_movements(
    item_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    return list_stock_movements(db, hotel_id=context.hotel_id, item_id=item_id, limit=limit)


@router.get("/consumption-report", response_model=StockConsumptionReportRead)
def get_stock_consumption_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    group_by: str = Query(default="week"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_STOCK_READ)),
):
    try:
        quantity = current_stock(db, hotel_id=context.hotel_id, item_id=item_id, location_id=location_id)
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"item_id": item_id, "quantity": quantity}
