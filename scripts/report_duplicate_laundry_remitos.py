#!/usr/bin/env python3
"""Read-only report of duplicate laundry remito numbers before migration.

Set MIGRATION_PREFLIGHT_DATABASE_URL explicitly to the intended local or
approved database. This script never loads .env or chooses a default database.
"""

from __future__ import annotations

import csv
import os
import sys
from sqlalchemy import create_engine

from app.services.laundry_remito_preflight import duplicate_laundry_remitos


def main() -> int:
    database_url = os.environ.get("MIGRATION_PREFLIGHT_DATABASE_URL", "").strip()
    if not database_url:
        print(
            "Definí MIGRATION_PREFLIGHT_DATABASE_URL explícitamente; no se leyó .env ni se eligió una base por defecto.",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            rows = duplicate_laundry_remitos(connection)
    finally:
        engine.dispose()

    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=("hotel_id", "vendor_id", "direction", "remito_number", "duplicate_count", "row_ids"),
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "row_ids": ",".join(str(value) for value in row["row_ids"])})
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
