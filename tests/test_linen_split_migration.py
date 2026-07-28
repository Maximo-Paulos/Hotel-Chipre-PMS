"""Regression/data-migration guard for 20260727_linen_split.

The owner explicitly rejected a shared StockItem.kind='linen' flag in favor
of physically separate tables. This exercises the *data* migration (not just
the schema) against a real, hand-inserted 'linen' row on a database built by
`alembic upgrade` (not Base.metadata.create_all, which always reflects the
current model and would hide a broken migration): items, a location shared
with a general-supply movement (must stay in stock_locations, get an
independent copy in linen_locations) and an exclusive-to-linen location
(must move, not copy), plus the vendor/price/remito FK rewrites -- then a
full upgrade -> downgrade -> upgrade cycle to prove the data survives both
directions, per the task's required validation.
"""
import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


PRE_LINEN_SPLIT_REVISION = "513720cf2551"


def _run_alembic(cwd: str, db_path: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True, text=True, env=env, cwd=cwd,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"


def _seed_pre_split_data(engine) -> None:
    """Hand-insert a real 'linen' StockItem plus movements and a laundry
    vendor/price/remito referencing it -- the exact shape a hotel with the
    previous loop's StockItem.kind='linen' deploy would have."""
    # HotelConfiguration has dozens of NOT NULL columns with Python-side (not
    # server-side) defaults -- the ORM is the only column-agnostic way to
    # seed one; unlike linen_*, its schema is untouched by this migration.
    from app.models.hotel_config import HotelConfiguration

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        session.add(HotelConfiguration(id=1, subscription_active=True))
        session.commit()
    finally:
        session.close()

    with engine.begin() as conn:
        # 100: exclusive to linen. 101: shared with a general-supply movement.
        conn.execute(text("INSERT INTO stock_locations (id, hotel_id, name) VALUES (100, 1, 'Deposito casa')"))
        conn.execute(text("INSERT INTO stock_locations (id, hotel_id, name) VALUES (101, 1, 'Deposito compartido')"))
        conn.execute(text(
            "INSERT INTO stock_items (id, hotel_id, name, unit, active, kind) "
            "VALUES (200, 1, 'Sabanas', 'unidad', 1, 'linen')"
        ))
        conn.execute(text(
            "INSERT INTO stock_items (id, hotel_id, name, unit, active, kind) "
            "VALUES (201, 1, 'Bolsas de residuos', 'unidad', 1, 'supply')"
        ))
        conn.execute(text(
            "INSERT INTO laundry_vendors (id, hotel_id, name, stock_location_id, active, created_at) "
            "VALUES (300, 1, 'Lavadero Test', 101, 1, '2026-07-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO stock_movements (id, hotel_id, item_id, location_id, movement_type, quantity, reason, created_at) "
            "VALUES (400, 1, 200, 100, 'in', '20.00', 'opening balance', '2026-07-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO stock_movements (id, hotel_id, item_id, location_id, movement_type, quantity, reason, created_at) "
            "VALUES (401, 1, 200, 100, 'out', '5.00', 'sent to laundry', '2026-07-02T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO stock_movements (id, hotel_id, item_id, location_id, movement_type, quantity, reason, created_at) "
            "VALUES (402, 1, 200, 101, 'in', '5.00', 'received by laundry', '2026-07-02T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO stock_movements (id, hotel_id, item_id, location_id, movement_type, quantity, reason, created_at) "
            "VALUES (403, 1, 201, 101, 'in', '50.00', 'supply also stored here', '2026-07-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO laundry_vendor_prices "
            "(id, hotel_id, vendor_id, stock_item_id, unit_price, currency_code, created_at, updated_at) "
            "VALUES (500, 1, 300, 200, '150.00', 'ARS', '2026-07-01T00:00:00', '2026-07-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO laundry_remitos (id, hotel_id, vendor_id, direction, remito_number, remito_date, created_at) "
            "VALUES (600, 1, 300, 'outbound', 'R-001', '2026-07-01T00:00:00', '2026-07-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO laundry_remito_lines (id, hotel_id, remito_id, stock_item_id, quantity, unit_price_snapshot) "
            "VALUES (700, 1, 600, 200, '5.00', '150.00')"
        ))


def test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/mig.db"
        _run_alembic(cwd, db_path, "upgrade", PRE_LINEN_SPLIT_REVISION)

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            _seed_pre_split_data(engine)
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "upgrade", "20260727_linen_split")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                _assert_migrated_state(conn)
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PRE_LINEN_SPLIT_REVISION)
        _run_alembic(cwd, db_path, "upgrade", "20260727_linen_split")

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                _assert_migrated_state(conn)
        finally:
            engine.dispose()


def _assert_migrated_state(conn) -> None:
    # The linen item moved out of stock_items, same id, into linen_items.
    linen_item = conn.execute(text("SELECT name, unit FROM linen_items WHERE id = 200")).first()
    assert linen_item == ("Sabanas", "unidad")
    assert conn.execute(text("SELECT COUNT(*) FROM stock_items WHERE id = 200")).scalar() == 0

    # The general-supply item never moved, and stock_items.kind is gone.
    supply_item = conn.execute(text("SELECT name FROM stock_items WHERE id = 201")).first()
    assert supply_item == ("Bolsas de residuos",)
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(stock_items)"))}
    assert "kind" not in columns
    assert "unit_cost" in columns

    # The exclusive-to-linen location (100, "Deposito casa") moved out of
    # stock_locations entirely.
    assert conn.execute(text("SELECT COUNT(*) FROM stock_locations WHERE name = 'Deposito casa'")).scalar() == 0
    linen_only_location = conn.execute(
        text("SELECT hotel_id FROM linen_locations WHERE name = 'Deposito casa'")
    ).first()
    assert linen_only_location == (1,)

    # The shared location ("Deposito compartido") stays in stock_locations
    # (the general-supply movement still needs it) AND gets an independent
    # copy in linen_locations.
    assert conn.execute(
        text("SELECT COUNT(*) FROM stock_locations WHERE name = 'Deposito compartido'")
    ).scalar() == 1
    assert conn.execute(
        text("SELECT COUNT(*) FROM linen_locations WHERE name = 'Deposito compartido'")
    ).scalar() == 1
    # The still-live general-supply movement at the shared location is untouched.
    assert float(conn.execute(text("SELECT quantity FROM stock_movements WHERE id = 403")).scalar()) == 50.0

    # Every migrated movement for the linen item landed in linen_movements,
    # and none of it is left behind in stock_movements.
    assert conn.execute(text("SELECT COUNT(*) FROM linen_movements WHERE item_id = 200")).scalar() == 3
    assert conn.execute(text("SELECT COUNT(*) FROM stock_movements WHERE item_id = 200")).scalar() == 0

    # Vendor/price/remito line FKs were repointed at the new linen_* ids.
    vendor_location_id = conn.execute(
        text("SELECT linen_location_id FROM laundry_vendors WHERE id = 300")
    ).scalar()
    assert conn.execute(
        text("SELECT name FROM linen_locations WHERE id = :id"), {"id": vendor_location_id}
    ).scalar() == "Deposito compartido"
    item_id, unit_price = conn.execute(
        text("SELECT linen_item_id, unit_price FROM laundry_vendor_prices WHERE id = 500")
    ).first()
    assert item_id == 200
    assert float(unit_price) == 150.0
    item_id, quantity = conn.execute(
        text("SELECT linen_item_id, quantity FROM laundry_remito_lines WHERE id = 700")
    ).first()
    assert item_id == 200
    assert float(quantity) == 5.0

    # laundry_vendors/laundry_vendor_prices/laundry_remito_lines no longer
    # carry the old stock_* columns at all.
    vendor_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(laundry_vendors)"))}
    assert "stock_location_id" not in vendor_columns
    price_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(laundry_vendor_prices)"))}
    assert "stock_item_id" not in price_columns
    line_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(laundry_remito_lines)"))}
    assert "stock_item_id" not in line_columns
