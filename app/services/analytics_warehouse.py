"""ClickHouse derived analytics warehouse boundary.

PostgreSQL facts remain authoritative. This module only projects PII-free,
tenant-scoped analytical rows and exposes an explicit reconciliation result.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import urljoin

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

RESERVATION_FACT_TABLE = "fact_reservation_daily"
SOURCE_OF_TRUTH = "postgresql"


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


def _settings():
    return get_settings()


def _required() -> bool:
    return bool(_settings().CLICKHOUSE_REQUIRED)


def _validate_hotel_id(hotel_id: int) -> None:
    if not isinstance(hotel_id, int) or hotel_id <= 0:
        raise ValueError("hotel_id must be a positive integer")


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
    if not settings.CLICKHOUSE_ENABLED or not settings.CLICKHOUSE_URL.strip():
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

    client.execute(
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
        """.strip()
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
