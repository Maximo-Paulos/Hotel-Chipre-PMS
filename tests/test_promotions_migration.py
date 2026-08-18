from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker


PRE_REVISION = "20260813_guest_restrictions"
REVISION = "20260818_promotions"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _engine(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _seed_pre_migration_surcharge(engine) -> None:
    from app.models.hotel_config import HotelConfiguration
    from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum

    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        db.add(HotelConfiguration(id=8401, subscription_active=True))
        db.flush()
        db.add(
            PaymentSurcharge(
                hotel_id=8401,
                payment_method="cash",
                surcharge_type=PaymentSurchargeTypeEnum.PERCENTAGE,
                amount=7.5,
                currency_code="ARS",
            )
        )
        db.commit()


def _load_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260818_promotions.py"
    spec = importlib.util.spec_from_file_location("promotions_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "promotions.db")
        _alembic(cwd, db_path, "upgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            _seed_pre_migration_surcharge(engine)
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            table_names = inspect(engine).get_table_names()
            assert "promotions" in table_names
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT payment_method, amount FROM payment_surcharges WHERE hotel_id = 8401")
                ).mappings().one()
                assert row["payment_method"] == "cash"
                # Backfilled through the Float -> Numeric column type change.
                assert Decimal(str(row["amount"])) == Decimal("7.5")
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "downgrade", PRE_REVISION)
        engine = _engine(db_path)
        try:
            assert "promotions" not in inspect(engine).get_table_names()
            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT amount FROM payment_surcharges WHERE hotel_id = 8401")
                ).mappings().one()
                assert Decimal(str(row["amount"])) == Decimal("7.5")
        finally:
            engine.dispose()

        _alembic(cwd, db_path, "upgrade", REVISION)
        engine = _engine(db_path)
        try:
            assert "promotions" in inspect(engine).get_table_names()
        finally:
            engine.dispose()


def test_promotions_migration_owns_reversible_postgresql_rls(monkeypatch):
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration._install_rls(type("Connection", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})())
    migration._remove_rls(type("Connection", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})())

    ddl = "\n".join(statements)
    assert 'ALTER TABLE "promotions" ENABLE ROW LEVEL SECURITY' in ddl
    assert 'ALTER TABLE "promotions" FORCE ROW LEVEL SECURITY' in ddl
    assert 'CREATE POLICY "tenant_isolation_promotions"' in ddl
    assert "current_setting('app.hotel_id', true)" in ddl
    assert "WITH CHECK" in ddl
    assert 'DROP POLICY IF EXISTS "tenant_isolation_promotions"' in ddl
    assert 'ALTER TABLE "promotions" DISABLE ROW LEVEL SECURITY' in ddl
