"""SQLite upgrade coverage for company nightly rate cutover and rollback guard."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from types import SimpleNamespace

from sqlalchemy import create_engine, text


PREVIOUS_REVISION = "20261014_payment_fx_currency"
RATE_REVISION = "20261015_company_nightly_rate_history"


def _run_alembic(cwd: str, db_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result


def _seed_legacy_company(db_path: str) -> int:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            hotel_columns = connection.execute(text("PRAGMA table_info(hotel_configuration)")).all()
            values: dict[str, object] = {}
            for row in hotel_columns:
                name, sql_type, not_null, default = row[1], (row[2] or "").upper(), bool(row[3]), row[4]
                if not not_null or default is not None:
                    continue
                if name == "id":
                    values[name] = 1
                elif name == "hotel_name":
                    values[name] = "Migration QA"
                elif name == "hotel_timezone":
                    values[name] = "America/Argentina/Buenos_Aires"
                elif name == "default_currency":
                    values[name] = "ARS"
                elif name == "languages":
                    values[name] = '["es"]'
                elif name == "jurisdiction_code":
                    values[name] = "AR"
                elif name == "interface_language":
                    values[name] = "es"
                elif "BOOL" in sql_type:
                    values[name] = 0
                elif "INT" in sql_type:
                    values[name] = 0
                elif any(kind in sql_type for kind in ("FLOAT", "NUMERIC", "REAL", "DECIMAL")):
                    values[name] = 0
                elif "DATE" in sql_type or "TIME" in sql_type:
                    values[name] = "2026-10-01 00:00:00"
                elif "JSON" in sql_type:
                    values[name] = "[]"
                else:
                    values[name] = "QA"
            columns = ", ".join(f'"{name}"' for name in values)
            placeholders = ", ".join(f":{name}" for name in values)
            connection.execute(text(f"INSERT INTO hotel_configuration ({columns}) VALUES ({placeholders})"), values)
            result = connection.execute(
                text(
                    "INSERT INTO companies (hotel_id, legal_name, display_name, extra_person_nightly_surcharge) "
                    "VALUES (1, 'QA Empresa', 'QA Empresa', 75.00)"
                )
            )
            return int(result.lastrowid)
    finally:
        engine.dispose()


def test_postgres_downgrade_requires_unfiltered_rls_visibility(monkeypatch):
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "alembic",
        "versions",
        f"{RATE_REVISION}.py",
    )
    spec = spec_from_file_location("company_nightly_rate_history_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    executed: list[str] = []
    bind = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        execute=lambda statement: executed.append(str(statement)),
    )
    migration._disable_silent_rls_filtering(bind)

    assert executed == ["SET LOCAL row_security = off"]


def test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/company-nightly-rates.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        company_id = _seed_legacy_company(db_path)

        _run_alembic(cwd, db_path, "upgrade", RATE_REVISION)
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                current_date = connection.execute(text("SELECT CURRENT_DATE")).scalar_one()
                rate = connection.execute(
                    text(
                        "SELECT effective_from, amount, is_migration_seed "
                        "FROM company_nightly_surcharge_rates WHERE hotel_id = 1 AND company_id = :company_id"
                    ),
                    {"company_id": company_id},
                ).one()
                assert rate.effective_from == current_date
                assert float(rate.amount) == 75.0
                assert rate.is_migration_seed in (1, True)
                assert connection.execute(
                    text(
                        "SELECT COUNT(*) FROM company_nightly_surcharge_rates "
                        "WHERE hotel_id = 1 AND company_id = :company_id AND effective_from < CURRENT_DATE"
                    ),
                    {"company_id": company_id},
                ).scalar_one() == 0
                columns = {row[1] for row in connection.execute(text("PRAGMA table_info(company_night_charges)"))}
                assert {"unit_amount", "quantity", "rate_id", "rate_effective_from"}.issubset(columns)
        finally:
            engine.dispose()

        _run_alembic(cwd, db_path, "downgrade", PREVIOUS_REVISION)
        _run_alembic(cwd, db_path, "upgrade", RATE_REVISION)


def test_company_nightly_rate_downgrade_refuses_to_discard_user_history():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/company-nightly-rates-guard.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        company_id = _seed_legacy_company(db_path)
        _run_alembic(cwd, db_path, "upgrade", RATE_REVISION)

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO company_nightly_surcharge_rates "
                        "(hotel_id, company_id, effective_from, amount, is_migration_seed, created_by_user_id) "
                        "VALUES (1, :company_id, DATE(CURRENT_DATE, '+1 day'), 110.00, 0, NULL)"
                    ),
                    {"company_id": company_id},
                )
        finally:
            engine.dispose()

        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_REVISION],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
        assert result.returncode != 0
        assert "Refusing to downgrade company nightly pricing" in result.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert connection.execute(
                    text(
                        "SELECT COUNT(*) FROM company_nightly_surcharge_rates "
                        "WHERE hotel_id = 1 AND company_id = :company_id"
                    ),
                    {"company_id": company_id},
                ).scalar_one() == 2
        finally:
            engine.dispose()


def test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/company-nightly-rate-charge-guard.db"
        _run_alembic(cwd, db_path, "upgrade", PREVIOUS_REVISION)
        company_id = _seed_legacy_company(db_path)
        _run_alembic(cwd, db_path, "upgrade", RATE_REVISION)

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                rate_id = connection.execute(
                    text(
                        "SELECT id FROM company_nightly_surcharge_rates "
                        "WHERE hotel_id = 1 AND company_id = :company_id"
                    ),
                    {"company_id": company_id},
                ).scalar_one()
                connection.execute(
                    text(
                        "INSERT INTO company_night_charges "
                        "(hotel_id, reservation_id, company_id, billing_adjustment_id, stay_date, amount, "
                        "currency_code, created_at, unit_amount, quantity, rate_id, rate_effective_from) "
                        "VALUES (1, 999, :company_id, 999, CURRENT_DATE, 150.00, 'ARS', CURRENT_TIMESTAMP, "
                        "75.00, 2, :rate_id, CURRENT_DATE)"
                    ),
                    {"company_id": company_id, "rate_id": rate_id},
                )
        finally:
            engine.dispose()

        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_REVISION],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
        assert result.returncode != 0
        assert "per-person charge snapshots" in result.stderr
