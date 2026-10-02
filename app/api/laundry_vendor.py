"""
FastAPI routes for outsourced laundry vendors, pricing, remitos and the
linen (ropa blanca) item/location catalog that backs them.

Separate router from app/api/laundry.py (legacy LaundryBatch/LaundryItem
lifecycle, kept as read-only history -- see memory checkpoint
20260725-235929) to avoid mixing the two models in one file. Also separate
from app/api/stock.py: linen items/locations/movements are their own tables
(app/models/linen.py), not StockItem/StockLocation/StockMovement -- the
owner explicitly rejected a shared table split by a ``kind`` flag.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_all_permissions, require_any_permission, require_permission
from app.services.laundry_vendor_service import (
    LaundryVendorError,
    DuplicateLaundryRemitoError,
    create_remito,
    create_vendor,
    list_remitos,
    list_vendor_prices,
    list_vendors,
    mark_vendor_settlement_paid,
    remito_creator_labels,
    set_vendor_price,
    update_vendor,
    vendor_balance,
    vendor_settlements,
    vendor_spend,
    is_duplicate_remito_integrity_error,
)
from app.services.linen_service import (
    LinenError,
    create_linen_item,
    create_location as create_linen_location,
    current_stock as current_linen_stock,
    delete_linen_item,
    linen_summary,
    list_linen_items,
    list_locations as list_linen_locations,
    LinenIdempotencyConflict,
    register_movement as register_linen_movement,
    register_opening_counts,
    set_location_minimum,
    transfer_linen_stock,
)
from app.services.permission_service import (
    PERMISSION_LAUNDRY_MANAGE_VENDORS,
    PERMISSION_LAUNDRY_OPERATE_REMITOS,
    PERMISSION_LAUNDRY_PRICE_MANAGE,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
)

router = APIRouter(prefix="/api/laundry", tags=["Laundry Vendors"])


class VendorCreate(BaseModel):
    name: str
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool = True


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    active: Optional[bool] = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str
    linen_location_id: int
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool
    created_at: datetime


class VendorPriceUpsert(BaseModel):
    linen_item_id: int
    unit_price: Decimal
    effective_from: date = Field(default_factory=date.today)
    currency_code: Optional[str] = None


class VendorPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    linen_item_id: int
    unit_price: Decimal
    effective_from: date
    currency_code: str
    updated_at: datetime


class RemitoLineIn(BaseModel):
    linen_item_id: int
    quantity: Decimal


class RemitoCreate(BaseModel):
    vendor_id: int
    direction: str
    remito_number: str
    remito_date: datetime
    house_location_id: int
    lines: list[RemitoLineIn]
    notes: Optional[str] = None


class RemitoLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    linen_item_id: int
    quantity: Decimal
    unit_price_snapshot: Optional[Decimal] = None


class RemitoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    vendor_id: int
    direction: str
    house_location_id: Optional[int] = None
    remito_number: str
    remito_date: datetime
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    lines: list[RemitoLineRead] = Field(default_factory=list)


class RemitoCreateResponse(BaseModel):
    remito: RemitoRead
    warnings: list[str] = Field(default_factory=list)


def _remito_reads(db: Session, *, hotel_id: int, remitos: list) -> list[RemitoRead]:
    labels = remito_creator_labels(db, hotel_id=hotel_id, remitos=remitos)
    results: list[RemitoRead] = []
    for remito in remitos:
        result = RemitoRead.model_validate(remito)
        label = labels.get(remito.created_by_user_id) if remito.created_by_user_id is not None else None
        if label is None and remito.created_by_user_id is not None:
            label = "Usuario del hotel"
        results.append(result.model_copy(update={"created_by_name": label}))
    return results


def _remito_read(db: Session, *, hotel_id: int, remito) -> RemitoRead:
    return _remito_reads(db, hotel_id=hotel_id, remitos=[remito])[0]


def _housekeeping_remito(remito: RemitoRead) -> RemitoRead:
    """Remove vendor billing snapshots and free text from an HK response."""

    safe = remito
    return safe.model_copy(
        update={
            "notes": None,
            "created_by_user_id": None,
            "lines": [
                line.model_copy(update={"unit_price_snapshot": None})
                for line in safe.lines
            ],
        }
    )


class VendorBalanceLine(BaseModel):
    linen_item_id: int
    linen_item_name: str
    quantity: Decimal


class VendorSpendLine(BaseModel):
    linen_item_id: int
    linen_item_name: str
    quantity: Decimal
    subtotal: Decimal


class VendorSpendRead(BaseModel):
    total: Decimal
    by_item: list[VendorSpendLine]


class SettlementQuarterRead(BaseModel):
    period_start: date
    period_end: date
    total_amount: Decimal
    by_item: list[VendorSpendLine]
    paid: bool
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None


class SettlementMarkPaid(BaseModel):
    paid: bool
    notes: Optional[str] = None


class LinenItemCreate(BaseModel):
    name: str
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool = True


class LinenItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str
    unit: str
    min_quantity: Optional[Decimal] = None
    active: bool


class LinenLocationCreate(BaseModel):
    name: str


class LinenLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str


class LinenMovementCreate(BaseModel):
    linen_item_id: int
    location_id: Optional[int] = None
    movement_type: str
    quantity: Decimal
    reason: Optional[str] = None


class LinenMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    item_id: int
    location_id: Optional[int] = None
    movement_type: str
    quantity: Decimal
    reason: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    transfer_reference: Optional[str] = None


class LinenTransferCreate(BaseModel):
    linen_item_id: int = Field(gt=0)
    source_location_id: int = Field(gt=0)
    destination_location_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class LinenTransferRead(BaseModel):
    transfer_reference: str
    outbound: LinenMovementRead
    inbound: LinenMovementRead


class LinenOpeningCountLineIn(BaseModel):
    linen_item_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)


class LinenOpeningCountBatchIn(BaseModel):
    counts: list[LinenOpeningCountLineIn] = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=500)


@router.get("/items", response_model=list[LinenItemRead])
def list_laundry_linen_items(
    db: Session = Depends(get_db),
    # Both the vendor/price admin panel and the day-to-day remito form need
    # this list -- see require_any_permission's docstring for the same
    # reasoning previously applied to GET /api/stock/items.
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    return list_linen_items(db, hotel_id=context.hotel_id)


@router.post("/items", response_model=LinenItemRead, status_code=status.HTTP_201_CREATED)
def create_laundry_linen_item(
    data: LinenItemCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        item = create_linen_item(db, hotel_id=context.hotel_id, **data.model_dump())
    except LinenError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_laundry_linen_item(
    item_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        delete_linen_item(db, hotel_id=context.hotel_id, item_id=item_id, deleted_by_user_id=context.user_id)
    except LinenError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return None


@router.get("/items/{item_id}/current")
def get_current_laundry_linen_stock(
    item_id: int,
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    try:
        quantity = current_linen_stock(db, hotel_id=context.hotel_id, item_id=item_id, location_id=location_id)
    except LinenError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"item_id": item_id, "quantity": quantity}


class LinenLocationBalanceRead(BaseModel):
    location_id: int
    current_quantity: Decimal
    has_movements: bool


class LinenSummaryEntry(BaseModel):
    item: LinenItemRead
    current_quantity: Decimal
    min_quantity: Optional[Decimal] = None
    location_balances: list[LinenLocationBalanceRead] = Field(default_factory=list)


class LinenParLevelUpsert(BaseModel):
    min_quantity: Decimal = Field(ge=0)


class LinenParLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    item_id: int
    location_id: int
    min_quantity: Decimal


@router.get("/items/summary", response_model=list[LinenSummaryEntry])
def get_laundry_linen_summary(
    location_id: Optional[int] = None,
    db: Session = Depends(get_db),
    # Every active linen item's balance in one request -- avoids the N+1
    # per-item /items/{id}/current pattern (see LaundryPage.tsx's
    # houseStockQueries), same shape as GET /api/stock/summary.
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    return linen_summary(db, hotel_id=context.hotel_id, location_id=location_id)


@router.put("/items/{item_id}/locations/{location_id}/minimum", response_model=LinenParLevelRead)
def set_laundry_linen_location_minimum(
    item_id: int,
    location_id: int,
    data: LinenParLevelUpsert,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        par_level = set_location_minimum(
            db,
            hotel_id=context.hotel_id,
            item_id=item_id,
            location_id=location_id,
            min_quantity=data.min_quantity,
            actor_user_id=context.user_id,
        )
    except LinenError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 400, detail=str(exc))
    db.commit()
    db.refresh(par_level)
    return par_level


@router.get("/locations", response_model=list[LinenLocationRead])
def list_laundry_linen_locations(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS, PERMISSION_LAUNDRY_OPERATE_REMITOS)
    ),
):
    return list_linen_locations(db, hotel_id=context.hotel_id)


@router.post("/locations", response_model=LinenLocationRead, status_code=status.HTTP_201_CREATED)
def create_laundry_linen_location(
    data: LinenLocationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        location = create_linen_location(db, hotel_id=context.hotel_id, name=data.name)
    except LinenError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(location)
    return location


@router.post("/movements", response_model=LinenMovementRead, status_code=status.HTTP_201_CREATED)
def create_laundry_linen_movement(
    data: LinenMovementCreate,
    db: Session = Depends(get_db),
    # Loading an opening balance (or correcting one) is an inventory-admin
    # action, same trust level as creating the item/vendor itself -- not
    # exposed to housekeeping's day-to-day operate_remitos permission.
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        movement = register_linen_movement(
            db,
            hotel_id=context.hotel_id,
            item_id=data.linen_item_id,
            location_id=data.location_id,
            movement_type=data.movement_type,
            quantity=data.quantity,
            reason=data.reason,
            created_by_user_id=context.user_id,
        )
    except LinenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(movement)
    return movement


@router.post("/opening-counts", response_model=list[LinenMovementRead], status_code=status.HTTP_201_CREATED)
def create_laundry_linen_opening_counts(
    data: LinenOpeningCountBatchIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        movements = register_opening_counts(
            db,
            hotel_id=context.hotel_id,
            counts=[line.model_dump() for line in data.counts],
            reason=data.reason,
            created_by_user_id=context.user_id,
        )
    except LinenError as exc:
        status_code = 409 if "prior movements" in str(exc).lower() or "only available" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
    db.commit()
    for movement in movements:
        db.refresh(movement)
    return movements


@router.post("/transfers", response_model=LinenTransferRead, status_code=status.HTTP_201_CREATED)
def create_laundry_linen_transfer(
    data: LinenTransferCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        reference, outbound, inbound = transfer_linen_stock(
            db,
            hotel_id=context.hotel_id,
            item_id=data.linen_item_id,
            source_location_id=data.source_location_id,
            destination_location_id=data.destination_location_id,
            quantity=data.quantity,
            reason=data.reason,
            created_by_user_id=context.user_id,
            idempotency_key=idempotency_key,
        )
    except LinenIdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LinenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    db.refresh(outbound)
    db.refresh(inbound)
    return {"transfer_reference": reference, "outbound": outbound, "inbound": inbound}


@router.post("/vendors", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_laundry_vendor(
    data: VendorCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    vendor = create_vendor(db, hotel_id=context.hotel_id, **data.model_dump())
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/vendors", response_model=list[VendorRead])
def list_laundry_vendors(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
):
    vendors = list_vendors(db, hotel_id=context.hotel_id)
    if context.operational_role != "housekeeping":
        return vendors
    # Housekeeping needs the vendor id/name/location to create a remito, not
    # the vendor contact directory. Materialize schemas so ORM attributes are
    # never serialized before the redaction is applied.
    return [
        VendorRead.model_validate(vendor).model_copy(
            update={"contact_phone": None, "contact_email": None}
        )
        for vendor in vendors
    ]


@router.patch("/vendors/{vendor_id}", response_model=VendorRead)
def update_laundry_vendor(
    vendor_id: int,
    data: VendorUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        vendor = update_vendor(
            db, hotel_id=context.hotel_id, vendor_id=vendor_id, **data.model_dump(exclude_unset=True)
        )
    except LaundryVendorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    db.refresh(vendor)
    return vendor


@router.post("/vendors/{vendor_id}/prices", response_model=VendorPriceRead, status_code=status.HTTP_201_CREATED)
def upsert_laundry_vendor_price(
    vendor_id: int,
    data: VendorPriceUpsert,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_LAUNDRY_MANAGE_VENDORS, PERMISSION_LAUNDRY_PRICE_MANAGE)
    ),
):
    try:
        price = set_vendor_price(
            db,
            hotel_id=context.hotel_id,
            vendor_id=vendor_id,
            actor_user_id=context.user_id,
            **data.model_dump(),
        )
    except DuplicateLaundryRemitoError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (LaundryVendorError, LinenError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if is_duplicate_remito_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un remito con ese número, lavadero y sentido. Revisá si es salida o entrada.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo confirmar el remito en este momento.",
        ) from exc
    db.refresh(price)
    return price


@router.get("/vendors/{vendor_id}/prices", response_model=list[VendorPriceRead])
def list_laundry_vendor_prices(
    vendor_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        return list_vendor_prices(db, hotel_id=context.hotel_id, vendor_id=vendor_id)
    except LaundryVendorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/remitos", response_model=RemitoCreateResponse, status_code=status.HTTP_201_CREATED)
def create_laundry_remito(
    data: RemitoCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
):
    try:
        remito = create_remito(
            db,
            hotel_id=context.hotel_id,
            vendor_id=data.vendor_id,
            direction=data.direction,
            remito_number=data.remito_number,
            remito_date=data.remito_date,
            house_location_id=data.house_location_id,
            lines=[line.model_dump() for line in data.lines],
            notes=data.notes,
            actor_user_id=context.user_id,
        )
    except DuplicateLaundryRemitoError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (LaundryVendorError, LinenError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if is_duplicate_remito_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un remito con ese número, lavadero y sentido. Revisá si es salida o entrada.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo confirmar el remito en este momento.",
        ) from exc
    db.refresh(remito)
    warnings = [
        f"No hay precio configurado para el item {line.linen_item_id}"
        for line in remito.lines
        if line.unit_price_snapshot is None
    ]
    remito_read = _remito_read(db, hotel_id=context.hotel_id, remito=remito)
    safe_remito = _housekeeping_remito(remito_read) if context.operational_role == "housekeeping" else remito_read
    return {"remito": safe_remito, "warnings": warnings}


@router.get("/remitos", response_model=list[RemitoRead])
def list_laundry_remitos(
    vendor_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
):
    remitos = list_remitos(
        db, hotel_id=context.hotel_id, vendor_id=vendor_id, date_from=date_from, date_to=date_to
    )
    remito_reads = _remito_reads(db, hotel_id=context.hotel_id, remitos=remitos)
    if context.operational_role == "housekeeping":
        return [_housekeeping_remito(remito) for remito in remito_reads]
    return remito_reads


@router.get("/vendors/{vendor_id}/balance", response_model=list[VendorBalanceLine])
def get_laundry_vendor_balance(
    vendor_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
):
    try:
        return vendor_balance(db, hotel_id=context.hotel_id, vendor_id=vendor_id)
    except LaundryVendorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/vendors/{vendor_id}/spend", response_model=VendorSpendRead)
def get_laundry_vendor_spend(
    vendor_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    # Financial visibility, not vendor operations -- owner/co-owner only by
    # default (same gate as app/api/reports.py), distinct from
    # laundry:manage_vendors which a manager already holds by default and
    # which still covers creating vendors/setting prices/remitos below.
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    try:
        return vendor_spend(db, hotel_id=context.hotel_id, vendor_id=vendor_id, date_from=date_from, date_to=date_to)
    except LaundryVendorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/vendors/{vendor_id}/settlements", response_model=list[SettlementQuarterRead])
def get_laundry_vendor_settlements(
    vendor_id: int,
    year: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    try:
        return vendor_settlements(db, hotel_id=context.hotel_id, vendor_id=vendor_id, year=year)
    except LaundryVendorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/vendors/{vendor_id}/settlements/{period_start}/mark-paid", response_model=SettlementQuarterRead)
def mark_laundry_vendor_settlement_paid(
    vendor_id: int,
    period_start: date,
    data: SettlementMarkPaid,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    try:
        mark_vendor_settlement_paid(
            db,
            hotel_id=context.hotel_id,
            vendor_id=vendor_id,
            period_start=period_start,
            paid=data.paid,
            notes=data.notes,
            actor_user_id=context.user_id,
        )
        db.commit()
        # Re-read through the same live-total path used for the list endpoint
        # so the response always mirrors what GET .../settlements returns.
        quarters = vendor_settlements(db, hotel_id=context.hotel_id, vendor_id=vendor_id, year=period_start.year)
    except LaundryVendorError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return next(q for q in quarters if q["period_start"] == period_start)
