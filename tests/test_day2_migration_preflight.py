from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.services.laundry_remito_preflight import duplicate_laundry_remitos, format_duplicate_report


def _create_remitos(connection) -> None:
    connection.execute(
        text(
            "CREATE TABLE laundry_remitos ("
            "id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, vendor_id INTEGER NOT NULL, "
            "direction TEXT NOT NULL, remito_number TEXT NOT NULL)"
        )
    )


def _load_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "d2a7e93f4c2b_day2_feedback_schema.py"
    spec = importlib.util.spec_from_file_location("day2_feedback_schema_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_remito_preflight_reports_ids_and_trimmed_duplicates():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_remitos(connection)
        connection.execute(
            text(
                "INSERT INTO laundry_remitos (id, hotel_id, vendor_id, direction, remito_number) "
                "VALUES (:id, :hotel_id, :vendor_id, :direction, :number)"
            ),
            [
                {"id": 11, "hotel_id": 1, "vendor_id": 7, "direction": "outbound", "number": "REM-22"},
                {"id": 12, "hotel_id": 1, "vendor_id": 7, "direction": "outbound", "number": "\tREM-22\n"},
            ],
        )

        report = duplicate_laundry_remitos(connection)

    assert report == [
        {
            "hotel_id": 1,
            "vendor_id": 7,
            "direction": "outbound",
            "remito_number": "REM-22",
            "duplicate_count": 2,
            "row_ids": [11, 12],
        }
    ]
    assert "11,12" in format_duplicate_report(report)
    engine.dispose()


def test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_remitos(connection)
        connection.execute(
            text(
                "INSERT INTO laundry_remitos (id, hotel_id, vendor_id, direction, remito_number) "
                "VALUES (41, 1, 7, 'inbound', '  REM-44\t')"
            )
        )

        report = duplicate_laundry_remitos(connection)

    assert report[0]["remito_number"] == "REM-44"
    assert report[0]["duplicate_count"] == 1
    assert report[0]["row_ids"] == [41]
    assert "espacios externos" in format_duplicate_report(report)
    engine.dispose()


def test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved():
    engine = create_engine("sqlite:///:memory:")
    migration = _load_migration()
    with engine.begin() as connection:
        _create_remitos(connection)
        connection.execute(
            text(
                "INSERT INTO laundry_remitos VALUES "
                "(21, 2, 8, 'inbound', 'A-1'), (22, 2, 8, 'inbound', 'A-1')"
            )
        )

        with pytest.raises(RuntimeError, match="21,22"):
            migration._assert_no_duplicate_remitos(connection)
    engine.dispose()


def test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint():
    engine = create_engine("sqlite:///:memory:")
    migration = _load_migration()
    with engine.begin() as connection:
        _create_remitos(connection)
        connection.execute(
            text(
                "INSERT INTO laundry_remitos (id, hotel_id, vendor_id, direction, remito_number) "
                "VALUES (:id, 1, 7, 'outbound', :number)"
            ),
            [{"id": 51, "number": "REM-55"}, {"id": 52, "number": "\tREM-55\n"}],
        )

        with pytest.raises(RuntimeError, match="51,52"):
            migration._assert_no_duplicate_remitos(connection)
    engine.dispose()


def test_remito_preflight_is_empty_when_no_duplicate_exists():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_remitos(connection)
        connection.execute(
            text(
                "INSERT INTO laundry_remitos VALUES "
                "(31, 1, 7, 'outbound', 'A-1'), "
                "(32, 1, 7, 'inbound', 'A-1'), "
                "(33, 2, 7, 'outbound', 'A-1')"
            )
        )
        assert duplicate_laundry_remitos(connection) == []
    engine.dispose()


def test_day2_downgrade_refuses_to_discard_persisted_operational_data():
    engine = create_engine("sqlite:///:memory:")
    migration = _load_migration()
    with engine.begin() as connection:
        for table_name in (
            "reservation_group_payment_batches",
            "reservation_group_payment_allocations",
            "cash_expenses",
            "rate_change_drafts",
            "operational_task_attachments",
            "transactions",
            "user_sessions",
            "hotel_configuration",
        ):
            connection.execute(text(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY)"))

        for table_name, columns in (
            ("transactions", ", group_payment_batch_id INTEGER"),
            ("user_sessions", ", previous_session_token_hash TEXT, previous_token_rotated_at TEXT"),
            (
                "hotel_configuration",
                ", fiscal_legal_name TEXT, fiscal_tax_id TEXT, fiscal_vat_condition TEXT, "
                "fiscal_address TEXT, fiscal_point_of_sale INTEGER",
            ),
        ):
            connection.execute(text(f"DROP TABLE {table_name}"))
            connection.execute(text(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY{columns})"))

        migration._guard_day2_downgrade_data(connection)
        connection.execute(text("INSERT INTO cash_expenses (id) VALUES (1)"))
        with pytest.raises(RuntimeError, match="cash_expenses"):
            migration._guard_day2_downgrade_data(connection)
    engine.dispose()
