"""Repair a legacy cash-handoff schema before starting the API.

The managed database can contain application tables created after an outdated
Alembic version marker. Running a normal upgrade there replays already-present
tables and fails. This narrow, PostgreSQL-only repair creates just the missing
cash-handoff reference and its integrity constraints, idempotently and without
rewriting business data.

Usage: ``python -m app.scripts.repair_cash_handoff_schema``.
"""

from __future__ import annotations

from app.database import get_engine


class CashHandoffSchemaRepairError(RuntimeError):
    """Raised when the safe repair cannot run against the configured database."""


_REPAIR_STATEMENTS = (
    "ALTER TABLE cash_close_reports ADD COLUMN IF NOT EXISTS successor_session_id INTEGER",
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_cash_sessions_hotel_id_id'
          AND conrelid = 'cash_sessions'::regclass
      ) THEN
        ALTER TABLE cash_sessions
          ADD CONSTRAINT uq_cash_sessions_hotel_id_id UNIQUE (hotel_id, id);
      END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_cash_close_reports_hotel_id_id'
          AND conrelid = 'cash_close_reports'::regclass
      ) THEN
        ALTER TABLE cash_close_reports
          ADD CONSTRAINT uq_cash_close_reports_hotel_id_id UNIQUE (hotel_id, id);
      END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_cash_close_reports_successor_session'
          AND conrelid = 'cash_close_reports'::regclass
      ) THEN
        ALTER TABLE cash_close_reports
          ADD CONSTRAINT uq_cash_close_reports_successor_session UNIQUE (successor_session_id);
      END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_cash_close_reports_successor_session'
          AND conrelid = 'cash_close_reports'::regclass
      ) THEN
        ALTER TABLE cash_close_reports
          ADD CONSTRAINT fk_cash_close_reports_successor_session
          FOREIGN KEY (successor_session_id) REFERENCES cash_sessions (id) ON DELETE SET NULL;
      END IF;
    END $$
    """,
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_cash_close_reports_hotel_successor_session'
          AND conrelid = 'cash_close_reports'::regclass
      ) THEN
        ALTER TABLE cash_close_reports
          ADD CONSTRAINT fk_cash_close_reports_hotel_successor_session
          FOREIGN KEY (hotel_id, successor_session_id)
          REFERENCES cash_sessions (hotel_id, id);
      END IF;
    END $$
    """,
)


def repair_cash_handoff_schema(engine=None) -> None:
    """Apply the additive cash-handoff repair in one PostgreSQL transaction."""

    target_engine = engine or get_engine()
    if getattr(getattr(target_engine, "dialect", None), "name", None) != "postgresql":
        raise CashHandoffSchemaRepairError("Cash handoff repair requires PostgreSQL")

    with target_engine.begin() as connection:
        for statement in _REPAIR_STATEMENTS:
            connection.exec_driver_sql(statement)


def main() -> None:
    repair_cash_handoff_schema()
    print("Cash handoff schema repair complete")


if __name__ == "__main__":
    main()
