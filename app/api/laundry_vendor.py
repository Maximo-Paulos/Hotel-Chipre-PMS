"""
FastAPI routes for outsourced laundry vendors, pricing and remitos.

Separate router from app/api/laundry.py (legacy LaundryBatch/LaundryItem
lifecycle, kept as read-only history -- see memory checkpoint
20260725-235929) to avoid mixing the two models in one file.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.services.laundry_vendor_service import (
    LaundryVendorError,
    create_remito,
    create_vendor,
    get_vendor,
    list_remitos,
    list_vendor_prices,
    list_vendors,
    mark_vendor_settlement_paid,
    set_vendor_price,
    update_vendor,
    vendor_balance,
    vendor_settlements,
    vendor_spend,
)
from app.services.permission_service import (
    PERMISSION_LAUNDRY_MANAGE_VENDORS,
    PERMISSION_LAUNDRY_OPERATE_REMITOS,
)
from app.services.stock_service import StockError

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
    stock_location_id: int
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool
    created_at: datetime


class VendorPriceUpsert(BaseModel):
    stock_item_id: int
    unit_price: Decimal
    currency_code: Optional[str] = None


class VendorPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    stock_item_id: int
    unit_price: Decimal
    currency_code: str
    updated_at: datetime


class RemitoLineIn(BaseModel):
    stock_item_id: int
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
    stock_item_id: int
    quantity: Decimal
    unit_price_snapshot: Optional[Decimal] = None


class RemitoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    vendor_id: int
    direction: str
    remito_number: str
    remito_date: datetime
    notes: Optional[str] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    lines: list[RemitoLineRead] = Field(default_factory=list)


class RemitoCreateResponse(BaseModel):
    remito: RemitoRead
    warnings: list[str] = Field(default_factory=list)


class VendorBalanceLine(BaseModel):
    stock_item_id: int
    stock_item_name: str
    quantity: Decimal


class VendorSpendLine(BaseModel):
    stock_item_id: int
    stock_item_name: str
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
    return list_vendors(db, hotel_id=context.hotel_id)


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
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
):
    try:
        price = set_vendor_price(db, hotel_id=context.hotel_id, vendor_id=vendor_id, **data.model_dump())
    except (LaundryVendorError, StockError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(price)
    return price


@router.get("/vendors/{vendor_id}/prices", response_model=list[VendorPriceRead])
def list_laundry_vendor_prices(
    vendor_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
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
    except (LaundryVendorError, StockError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(remito)
    warnings = [
        f"No hay precio configurado para el item {line.stock_item_id}"
        for line in remito.lines
        if line.unit_price_snapshot is None
    ]
    return {"remito": remito, "warnings": warnings}


@router.get("/remitos", response_model=list[RemitoRead])
def list_laundry_remitos(
    vendor_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_OPERATE_REMITOS)),
):
    return list_remitos(
        db, hotel_id=context.hotel_id, vendor_id=vendor_id, date_from=date_from, date_to=date_to
    )


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
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_LAUNDRY_MANAGE_VENDORS)),
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
