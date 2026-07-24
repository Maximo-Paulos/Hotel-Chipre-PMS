"""ClickHouse derived analytics warehouse boundary.

PostgreSQL facts remain authoritative. This module only projects PII-free,
tenant-scoped analytical rows and exposes an explicit reconciliation result.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import urljoin

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

RESERVATION_FACT_TABLE = "fact_reservation_daily"
DIM_HOTEL_TABLE = "dim_hotel"
DIM_DATE_TABLE = "dim_date"
DIM_ROOM_TABLE = "dim_room"
DIM_ROOM_CATEGORY_TABLE = "dim_room_category"
PAYMENT_FACT_TABLE = "fact_payment"
CASH_MOVEMENT_FACT_TABLE = "fact_cash_movement"
STOCK_MOVEMENT_FACT_TABLE = "fact_stock_movement"
SOURCE_OF_TRUTH = "postgresql"

_FACT_TABLES = {
    "payment": (PAYMENT_FACT_TABLE, "transaction_date", "amount"),
    "cash_movement": (CASH_MOVEMENT_FACT_TABLE, "movement_date", "amount"),
    "stock_movement": (STOCK_MOVEMENT_FACT_TABLE, "movement_date", "quantity"),
}


class AnalyticsWarehouseUnavailable(RuntimeError):
    """Raised when a required ClickHouse warehouse cannot be used."""


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    hotel_id: int
    date_from: date
    date_to: date
    source_count: int
    warehouse_count: int

    @property
    def difference(self) -> int:
        return self.source_count - self.warehouse_count

    @property
    def ok(self) -> bool:
        return self.difference == 0


@dataclass(frozen=True, slots=True)
class WarehouseSyncResult:
    hotel_id: int
    date_from: date
    date_to: date
    rows: int
    source: str = SOURCE_OF_TRUTH


@dataclass(frozen=True, slots=True)
class FactReconciliationResult:
    """Count and amount comparison for a derived fact window.

    The result is intentionally explicit: dashboards may only publish a
    warehouse-backed number when both dimensions reconcile with PostgreSQL.
    """

    fact_name: str
    hotel_id: int
    date_from: date
    date_to: date
    source_count: int
    warehouse_count: int
    source_amount: Decimal = Decimal("0")
    warehouse_amount: Decimal = Decimal("0")

    @property
    def count_difference(self) -> int:
        return self.source_count - self.warehouse_count

    @property
    def amount_difference(self) -> Decimal:
        return self.source_amount - self.warehouse_amount

    @property
    def ok(self) -> bool:
        return self.count_difference == 0 and self.amount_difference == Decimal("0")


def _settings():
    return get_settings()


def _required() -> bool:
    return bool(_settings().CLICKHOUSE_REQUIRED)


def _validate_hotel_id(hotel_id: int) -> None:
    if not isinstance(hotel_id, int) or hotel_id <= 0:
        raise ValueError("hotel_id must be a positive integer")


def _date_value(source: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]
    raise ValueError(f"one of {keys!r} is required")


def _enum_value(value: Any, *, default: str = "unknown") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _positive_id(value: Any, field: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _unavailable(message: str, exc: Exception | None = None):
    if _required():
        raise AnalyticsWarehouseUnavailable(message) from exc
    logger.warning("analytics_warehouse.degraded", extra={"error": message})


@dataclass(slots=True)
class ClickHouseHTTPClient:
    base_url: str
    database: str
    user: str
    password: str
    timeout_seconds: float = 5.0

    def execute(self, query: str, params: Mapping[str, Any] | None = None) -> list[list[Any]]:
        response = httpx.post(
            urljoin(self.base_url.rstrip("/") + "/", ""),
            params={"database": self.database, "query": query, **dict(params or {})},
            auth=(self.user, self.password) if self.user else None,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.text.strip()
        if not body:
            return []
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
            return parsed["data"]
        if isinstance(parsed, list):
            return parsed
        return []

    def insert_json_each_row(self, table: str, rows: list[dict[str, Any]], *, version: str) -> None:
        if not rows:
            return
        payload = "".join(
            json.dumps({**row, "version": version}, ensure_ascii=True, allow_nan=False, default=str) + "\n"
            for row in rows
        )
        query = f"INSERT INTO {table} FORMAT JSONEachRow"
        response = httpx.post(
            urljoin(self.base_url.rstrip("/") + "/", ""),
            params={"database": self.database, "query": query},
            content=payload.encode("utf-8"),
            headers={"content-type": "application/x-ndjson"},
            auth=(self.user, self.password) if self.user else None,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()


def get_clickhouse_client() -> ClickHouseHTTPClient | None:
    settings = _settings()
    if not settings.CLICKHOUSE_ENABLED:
        return None
    if not settings.CLICKHOUSE_URL.strip():
        _unavailable("ClickHouse warehouse is not configured")
        return None
    return ClickHouseHTTPClient(
        base_url=settings.CLICKHOUSE_URL.strip(),
        database=settings.CLICKHOUSE_DATABASE.strip() or "default",
        user=settings.CLICKHOUSE_USER.strip(),
        password=settings.CLICKHOUSE_PASSWORD,
        timeout_seconds=max(1.0, float(settings.CLICKHOUSE_TIMEOUT_SECONDS)),
    )


def ensure_schema(client: ClickHouseHTTPClient) -> None:
    """Create only derived, PII-free tables; never create OLTP source tables."""

    statements = (
        f"""
        CREATE TABLE IF NOT EXISTS {DIM_HOTEL_TABLE} (
            hotel_id UInt64,
            hotel_name String,
            hotel_timezone String,
            currency String,
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        ORDER BY hotel_id
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {DIM_DATE_TABLE} (
            calendar_date Date,
            year UInt16,
            month UInt8,
            day UInt8,
            iso_week UInt8,
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        ORDER BY calendar_date
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {DIM_ROOM_CATEGORY_TABLE} (
            hotel_id UInt64,
            category_id UInt64,
            category_code String,
            category_name String,
            base_price_ars Nullable(Decimal(18, 2)),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY hotel_id
        ORDER BY (hotel_id, category_id)
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {DIM_ROOM_TABLE} (
            hotel_id UInt64,
            room_id UInt64,
            room_number String,
            category_id UInt64,
            status LowCardinality(String),
            is_active UInt8,
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY hotel_id
        ORDER BY (hotel_id, room_id)
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {RESERVATION_FACT_TABLE} (
            hotel_id UInt64,
            reservation_id UInt64,
            stay_date Date,
            room_id Nullable(UInt64),
            category_id UInt64,
            revenue_gross_ars Nullable(Decimal(18, 2)),
            status LowCardinality(String),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY (hotel_id, toYYYYMM(stay_date))
        ORDER BY (hotel_id, stay_date, reservation_id, category_id)
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {PAYMENT_FACT_TABLE} (
            hotel_id UInt64,
            transaction_id UInt64,
            reservation_id UInt64,
            transaction_date Date,
            amount Decimal(18, 2),
            currency LowCardinality(String),
            payment_method LowCardinality(String),
            transaction_type LowCardinality(String),
            status LowCardinality(String),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY (hotel_id, toYYYYMM(transaction_date))
        ORDER BY (hotel_id, transaction_date, transaction_id)
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {CASH_MOVEMENT_FACT_TABLE} (
            hotel_id UInt64,
            cash_movement_id UInt64,
            session_id UInt64,
            movement_date Date,
            amount Decimal(18, 2),
            currency LowCardinality(String),
            movement_type LowCardinality(String),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY (hotel_id, toYYYYMM(movement_date))
        ORDER BY (hotel_id, movement_date, cash_movement_id)
        """.strip(),
        f"""
        CREATE TABLE IF NOT EXISTS {STOCK_MOVEMENT_FACT_TABLE} (
            hotel_id UInt64,
            stock_movement_id UInt64,
            item_id UInt64,
            location_id Nullable(UInt64),
            reservation_id Nullable(UInt64),
            movement_date Date,
            quantity Decimal(18, 2),
            movement_type LowCardinality(String),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY (hotel_id, toYYYYMM(movement_date))
        ORDER BY (hotel_id, movement_date, stock_movement_id)
        """.strip(),
        """
        CREATE TABLE IF NOT EXISTS payment_daily_read_model (
            hotel_id UInt64,
            transaction_date Date,
            payment_method LowCardinality(String),
            transaction_id UInt64,
            amount Decimal(18, 2),
            version DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(version)
        PARTITION BY (hotel_id, toYYYYMM(transaction_date))
        ORDER BY (hotel_id, transaction_date, payment_method, transaction_id)
        """.strip(),
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hotel_daily_payment_totals
        TO payment_daily_read_model
        AS SELECT hotel_id, transaction_date, payment_method, transaction_id, amount, version
        FROM fact_payment
        """.strip(),
    )
    for statement in statements:
        client.execute(statement)


def build_hotel_dimension_row(source: Mapping[str, Any]) -> dict[str, Any]:
    hotel_id = _positive_id(source["hotel_id"], "hotel_id")
    return {
        "hotel_id": hotel_id,
        "hotel_name": str(source.get("hotel_name") or ""),
        "hotel_timezone": str(source.get("hotel_timezone") or "UTC"),
        "currency": str(source.get("currency") or "ARS"),
    }


def build_date_dimension_rows(date_from: date, date_to: date) -> list[dict[str, Any]]:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    rows: list[dict[str, Any]] = []
    current = date_from
    while current <= date_to:
        rows.append(
            {
                "calendar_date": current.isoformat(),
                "year": current.year,
                "month": current.month,
                "day": current.day,
                "iso_week": current.isocalendar().week,
            }
        )
        current = date.fromordinal(current.toordinal() + 1)
    return rows


def build_room_category_dimension_row(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": _positive_id(source["hotel_id"], "hotel_id"),
        "category_id": _positive_id(source["category_id"], "category_id"),
        "category_code": str(source.get("category_code") or ""),
        "category_name": str(source.get("category_name") or ""),
        "base_price_ars": source.get("base_price_ars"),
    }


def build_room_dimension_row(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": _positive_id(source["hotel_id"], "hotel_id"),
        "room_id": _positive_id(source["room_id"], "room_id"),
        "room_number": str(source.get("room_number") or ""),
        "category_id": _positive_id(source["category_id"], "category_id"),
        "status": _enum_value(source.get("status")),
        "is_active": 1 if bool(source.get("is_active", True)) else 0,
    }


def build_payment_fact_row(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": _positive_id(source["hotel_id"], "hotel_id"),
        "transaction_id": _positive_id(source["transaction_id"], "transaction_id"),
        "reservation_id": _positive_id(source["reservation_id"], "reservation_id"),
        "transaction_date": _date_value(source, "transaction_date", "created_at"),
        "amount": source["amount"],
        "currency": str(source.get("currency") or "ARS"),
        "payment_method": _enum_value(source.get("payment_method")),
        "transaction_type": _enum_value(source.get("transaction_type")),
        "status": _enum_value(source.get("status")),
    }


def canonical_payment_amount(source: Mapping[str, Any]) -> Decimal:
    """Return the signed amount allowed into confirmed financial facts."""
    status = _enum_value(source.get("status"))
    if status != "completed":
        raise ValueError("only completed transactions may enter financial facts")
    amount = Decimal(str(source["amount"]))
    if _enum_value(source.get("transaction_type")) == "refund":
        return -amount
    return amount


def build_cash_movement_fact_row(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": _positive_id(source["hotel_id"], "hotel_id"),
        "cash_movement_id": _positive_id(source["cash_movement_id"], "cash_movement_id"),
        "session_id": _positive_id(source["session_id"], "session_id"),
        "movement_date": _date_value(source, "movement_date", "recorded_at"),
        "amount": source["amount"],
        "currency": str(source.get("currency") or "ARS"),
        "movement_type": _enum_value(source.get("movement_type")),
    }


def build_stock_movement_fact_row(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": _positive_id(source["hotel_id"], "hotel_id"),
        "stock_movement_id": _positive_id(source["stock_movement_id"], "stock_movement_id"),
        "item_id": _positive_id(source["item_id"], "item_id"),
        "location_id": int(source["location_id"]) if source.get("location_id") is not None else None,
        "reservation_id": int(source["reservation_id"]) if source.get("reservation_id") is not None else None,
        "movement_date": _date_value(source, "movement_date", "created_at"),
        "quantity": source["quantity"],
        "movement_type": _enum_value(source.get("movement_type")),
    }


def project_operational_fact_rows(
    client: ClickHouseHTTPClient,
    *,
    fact_name: str,
    hotel_id: int,
    date_from: date,
    date_to: date,
    rows: list[Mapping[str, Any]],
) -> WarehouseSyncResult:
    _validate_hotel_id(hotel_id)
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    table_details = _FACT_TABLES.get(fact_name)
    if table_details is None:
        raise ValueError(f"unsupported operational fact: {fact_name}")
    table = table_details[0]
    builders = {
        "payment": build_payment_fact_row,
        "cash_movement": build_cash_movement_fact_row,
        "stock_movement": build_stock_movement_fact_row,
    }
    projected = [builders[fact_name](row) for row in rows]
    if any(row["hotel_id"] != hotel_id for row in projected):
        raise ValueError("warehouse batch contains a different hotel")
    version = datetime.now(timezone.utc).isoformat()
    client.insert_json_each_row(table, projected, version=version)
    return WarehouseSyncResult(
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        rows=len(projected),
    )


def reconcile_derived_fact(
    client: ClickHouseHTTPClient,
    *,
    fact_name: str,
    hotel_id: int,
    date_from: date,
    date_to: date,
    source_count: int,
    source_amount: Decimal = Decimal("0"),
) -> FactReconciliationResult:
    _validate_hotel_id(hotel_id)
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    table_details = _FACT_TABLES.get(fact_name)
    if table_details is None:
        raise ValueError(f"unsupported operational fact: {fact_name}")
    table, date_column, amount_column = table_details
    query = (
        f"SELECT count(), coalesce(sum({amount_column}), 0) FROM {table} FINAL "
        f"WHERE hotel_id = {hotel_id} "
        f"AND {date_column} >= toDate('{date_from.isoformat()}') "
        f"AND {date_column} <= toDate('{date_to.isoformat()}') FORMAT JSONCompact"
    )
    rows = client.execute(query)
    warehouse_count = int(rows[0][0]) if rows and rows[0] else 0
    warehouse_amount = Decimal(str(rows[0][1])) if rows and rows[0] and len(rows[0]) > 1 else Decimal("0")
    return FactReconciliationResult(
        fact_name=fact_name,
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        source_count=source_count,
        warehouse_count=warehouse_count,
        source_amount=Decimal(str(source_amount)),
        warehouse_amount=warehouse_amount,
    )

def build_reservation_fact_row(source: Mapping[str, Any]) -> dict[str, Any]:
    """Project an allow-listed fact shape and deliberately drop guest PII."""

    hotel_id = int(source["hotel_id"])
    reservation_id = int(source["reservation_id"])
    category_id = int(source["category_id"])
    _validate_hotel_id(hotel_id)
    if reservation_id <= 0 or category_id <= 0:
        raise ValueError("fact identifiers must be positive")
    stay_date = source["stay_date"]
    if isinstance(stay_date, date):
        stay_date_value = stay_date.isoformat()
    else:
        stay_date_value = str(stay_date)
    return {
        "hotel_id": hotel_id,
        "reservation_id": reservation_id,
        "stay_date": stay_date_value,
        "room_id": int(source["room_id"]) if source.get("room_id") is not None else None,
        "category_id": category_id,
        "revenue_gross_ars": source.get("revenue_gross_ars"),
        "status": str(source.get("status") or "unknown"),
    }


def reconcile_reservation_fact_counts(
    client: ClickHouseHTTPClient,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    source_count: int,
) -> ReconciliationResult:
    _validate_hotel_id(hotel_id)
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    if source_count < 0:
        raise ValueError("source_count cannot be negative")
    query = (
        f"SELECT count() FROM {RESERVATION_FACT_TABLE} FINAL "
        f"WHERE hotel_id = {hotel_id} "
        f"AND stay_date >= toDate('{date_from.isoformat()}') "
        f"AND stay_date <= toDate('{date_to.isoformat()}') FORMAT JSONCompact"
    )
    rows = client.execute(query)
    warehouse_count = int(rows[0][0]) if rows and rows[0] else 0
    return ReconciliationResult(
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        source_count=source_count,
        warehouse_count=warehouse_count,
    )


def project_reservation_fact_rows(
    client: ClickHouseHTTPClient,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    rows: list[Mapping[str, Any]],
) -> WarehouseSyncResult:
    _validate_hotel_id(hotel_id)
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    projected = [build_reservation_fact_row(row) for row in rows]
    if any(row["hotel_id"] != hotel_id for row in projected):
        raise ValueError("warehouse batch contains a different hotel")
    version = datetime.now(timezone.utc).isoformat()
    client.insert_json_each_row(RESERVATION_FACT_TABLE, projected, version=version)
    return WarehouseSyncResult(hotel_id=hotel_id, date_from=date_from, date_to=date_to, rows=len(projected))
