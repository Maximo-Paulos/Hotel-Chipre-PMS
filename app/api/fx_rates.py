from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission, require_roles
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.services.fx_service import RATE_TYPES, fetch_all_rates, fetch_rate, get_all_rates_snapshot
from app.services.permission_service import PERMISSION_REPORTS_FINANCIAL_VIEW


router = APIRouter(prefix="/fx", tags=["FX Rates"])
logger = logging.getLogger(__name__)


class FxRateItem(BaseModel):
    type: str
    nombre: Optional[str] = None
    moneda: Optional[str] = None
    compra: Optional[float] = None
    venta: Optional[float] = None
    fechaActualizacion: Optional[str] = None


class FxRateUsdOficial(BaseModel):
    compra: Optional[float] = None
    venta: Optional[float] = None
    fecha: Optional[str] = None


class FxSnapshotRead(BaseModel):
    id: int
    hotel_id: Optional[int] = None
    rate_type: str
    moneda: str
    compra: Optional[float] = None
    venta: Optional[float] = None
    fetched_at: datetime
    source: str

    model_config = {"from_attributes": True}


class FxSnapshotCreateResponse(BaseModel):
    stored: int
    message: str


@router.get("/rates", response_model=list[FxRateItem], summary="All current FX rates")
async def get_all_rates(
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    try:
        rates = await fetch_all_rates()
    except Exception as exc:
        logger.error("Error fetching all FX rates error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron obtener los tipos de cambio. Intente nuevamente.",
        ) from exc

    items: list[FxRateItem] = []
    for key, data in rates.items():
        if not isinstance(data, dict):
            continue
        items.append(
            FxRateItem(
                type=key,
                nombre=data.get("nombre"),
                moneda=data.get("moneda"),
                compra=data.get("compra"),
                venta=data.get("venta"),
                fechaActualizacion=data.get("fechaActualizacion"),
            )
        )
    return items


@router.get("/rates/usd/oficial", response_model=FxRateUsdOficial, summary="Official USD rate shortcut")
async def get_usd_oficial_rate(
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    data = await fetch_rate("oficial")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener el tipo de cambio oficial.",
        )
    return FxRateUsdOficial(
        compra=data.get("compra"),
        venta=data.get("venta"),
        fecha=data.get("fechaActualizacion"),
    )


@router.get("/rates/{rate_type}", response_model=FxRateItem, summary="Single USD rate type")
async def get_single_rate(
    rate_type: str,
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    if rate_type not in RATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de cambio '{rate_type}' no válido. Opciones: {', '.join(RATE_TYPES)}",
        )
    data = await fetch_rate(rate_type)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo obtener el tipo de cambio '{rate_type}'.",
        )
    return FxRateItem(
        type=rate_type,
        nombre=data.get("nombre"),
        moneda=data.get("moneda"),
        compra=data.get("compra"),
        venta=data.get("venta"),
        fechaActualizacion=data.get("fechaActualizacion"),
    )


@router.post(
    "/snapshot",
    response_model=FxSnapshotCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist current FX rates to DB",
)
async def create_fx_snapshot(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    try:
        snapshot_data = await get_all_rates_snapshot()
    except Exception as exc:
        logger.error("Error fetching snapshot for persistence error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron obtener los tipos de cambio para persistir.",
        ) from exc

    if not snapshot_data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="DolarAPI no devolvio datos. Intente nuevamente.",
        )

    fetched_at = datetime.now(timezone.utc)
    rows: list[FxRateSnapshot] = []
    for rate_type, rate_data in snapshot_data.items():
        if not isinstance(rate_data, dict):
            continue
        rows.append(
            FxRateSnapshot(
                hotel_id=context.hotel_id,
                rate_type=rate_type,
                moneda=(rate_data.get("moneda") or "USD").upper(),
                compra=rate_data.get("compra"),
                venta=rate_data.get("venta"),
                fetched_at=fetched_at,
                source="dolarapi.com",
            )
        )

    db.add_all(rows)
    db.commit()
    return FxSnapshotCreateResponse(
        stored=len(rows),
        message=f"Se persistieron {len(rows)} tipos de cambio correctamente.",
    )


@router.get("/snapshots", response_model=list[FxSnapshotRead], summary="Historical FX snapshots")
def list_fx_snapshots(
    from_date: Optional[str] = Query(None, alias="from", description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="YYYY-MM-DD"),
    rate_type: Optional[str] = Query(None, description="Filter by rate type, e.g. oficial"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    query = db.query(FxRateSnapshot).filter(
        or_(FxRateSnapshot.hotel_id == context.hotel_id, FxRateSnapshot.hotel_id.is_(None))
    )

    if from_date:
        try:
            dt_from = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(FxRateSnapshot.fetched_at >= dt_from)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato de fecha 'from' invalido. Use YYYY-MM-DD.",
            ) from exc

    if to_date:
        try:
            dt_to = datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.filter(FxRateSnapshot.fetched_at <= dt_to)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato de fecha 'to' invalido. Use YYYY-MM-DD.",
            ) from exc

    if rate_type:
        query = query.filter(FxRateSnapshot.rate_type == rate_type)

    snapshots = query.order_by(FxRateSnapshot.fetched_at.desc()).limit(limit).all()
    return [FxSnapshotRead.model_validate(snapshot) for snapshot in snapshots]
