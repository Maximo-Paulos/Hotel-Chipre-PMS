"""Repair a legacy cash-handoff schema before starting the API.

The managed database can contain application tables created after an outdated
Alembic version marker. Running a normal upgrade there replays already-present
tables and fails. This narrow, PostgreSQL-only repair creates the missing
cash-handoff reference, custody table, and their integrity constraints,
idempotently and without rewriting business data.

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
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_type
        WHERE typname = 'cash_custody_status_enum'
      ) THEN
        CREATE TYPE cash_custody_status_enum AS ENUM ('pending', 'confirmed');
      END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_custody_handoffs (
      id SERIAL PRIMARY KEY,
      hotel_id INTEGER NOT NULL REFERENCES hotel_configuration (id) ON DELETE CASCADE,
      close_report_id INTEGER NOT NULL UNIQUE,
      delivered_by_user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
      received_by_user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
      delivered_amount NUMERIC(12, 2) NOT NULL,
      status cash_custody_status_enum NOT NULL DEFAULT 'pending',
      delivered_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
      received_at TIMESTAMP WITHOUT TIME ZONE,
      notes TEXT,
      CONSTRAINT ck_cash_custody_delivered_nonneg CHECK (delivered_amount >= 0),
      CONSTRAINT fk_cash_custody_handoffs_hotel_close_report
        FOREIGN KEY (hotel_id, close_report_id)
        REFERENCES cash_close_reports (hotel_id, id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cash_custody_handoffs_hotel_status
      ON cash_custody_handoffs (hotel_id, status)
    """,
    "ALTER TABLE cash_custody_handoffs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE cash_custody_handoffs FORCE ROW LEVEL SECURITY",
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = current_schema()
          AND tablename = 'cash_custody_handoffs'
          AND policyname = 'tenant_isolation_cash_custody_handoffs'
      ) THEN
        CREATE POLICY tenant_isolation_cash_custody_handoffs ON cash_custody_handoffs
          USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
          WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer);
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
