from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.hotel_config import HotelConfiguration
from app.services.fx_service import (
    DIRECT_CURRENCY_BLUE_RATE_TYPES,
    USD_RATE_TYPES,
    get_all_rates_snapshot,
    parse_provider_updated_at,
)

logger = logging.getLogger(__name__)


class FxSnapshotError(ValueError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


async def create_hotel_fx_snapshot(db: Session, *, hotel_id: int) -> dict[str, object]:
    """Fetch one live snapshot and mark the hotel's configured ARS-to-USD quote."""
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    if config is None:
        raise FxSnapshotError(
            "No se encontró la configuración del hotel para guardar la cotización.",
            status_code=404,
        )

    selected_market = str(config.fx_ars_to_usd_rate_type or "oficial").strip().lower()
    selected_side = str(config.fx_ars_to_usd_rate_side or "venta").strip().lower()
    if selected_market not in USD_RATE_TYPES or selected_side not in {"compra", "venta"}:
        raise FxSnapshotError(
            "La configuración de mercado o lado de cotización ARS a USD no es válida.",
            status_code=422,
        )

    try:
        snapshot_data = await get_all_rates_snapshot()
    except Exception as exc:
        logger.error("Error fetching snapshot for persistence error_type=%s", type(exc).__name__)
        raise FxSnapshotError(
            "No se pudieron obtener los tipos de cambio para persistir.", status_code=502
        ) from exc

    if not snapshot_data:
        raise FxSnapshotError("DolarAPI no devolvió datos. Intente nuevamente.", status_code=502)

    selected_quote = snapshot_data.get(selected_market)
    try:
        selected_rate = Decimal(str(selected_quote.get(selected_side))) if isinstance(selected_quote, dict) else None
    except (InvalidOperation, TypeError, ValueError):
        selected_rate = None
    if selected_rate is None or not selected_rate.is_finite() or selected_rate <= 0:
        raise FxSnapshotError(
            f"DolarAPI no devolvió una cotización {selected_side} válida para el mercado {selected_market} configurado.",
            status_code=502,
        )

    fetched_at = datetime.now(timezone.utc)
    rows: list[FxRateSnapshot] = []
    for rate_type, rate_data in snapshot_data.items():
        if not isinstance(rate_data, dict):
            continue
        normalized_type = (
            rate_type
            if rate_type in USD_RATE_TYPES or rate_type in DIRECT_CURRENCY_BLUE_RATE_TYPES
            else f"{str(rate_data.get('moneda') or rate_type).strip().lower()}_oficial"
        )
        is_selected_quote = normalized_type == selected_market
        rows.append(
            FxRateSnapshot(
                hotel_id=hotel_id,
                rate_type=normalized_type,
                provider_market=str(rate_data.get("casa") or rate_type).strip().lower(),
                moneda=(rate_data.get("moneda") or "USD").upper(),
                compra=rate_data.get("compra"),
                venta=rate_data.get("venta"),
                fetched_at=fetched_at,
                provider_updated_at=parse_provider_updated_at(
                    rate_data.get("fechaActualizacion") or rate_data.get("fecha")
                ),
                selected_side=selected_side if is_selected_quote else None,
                base_currency="USD" if is_selected_quote else None,
                quote_currency="ARS" if is_selected_quote else None,
                applied_rate=selected_rate if is_selected_quote else None,
                source="dolarapi.com",
            )
        )

    try:
        db.add_all(rows)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error persisting FX snapshot error_type=%s", type(exc).__name__)
        raise FxSnapshotError("No se pudieron guardar las cotizaciones del hotel.", status_code=500) from exc

    return {
        "stored": len(rows),
        "message": (
            f"Se guardaron {len(rows)} cotizaciones y se seleccionó {selected_side} "
            f"del mercado {selected_market} para las sugerencias de tarifas."
        ),
        "selected_market": selected_market,
        "selected_side": selected_side,
        "applied_rate": float(selected_rate),
    }
