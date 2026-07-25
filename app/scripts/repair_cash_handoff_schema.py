"""Repair a legacy cash-handoff schema before starting the API.

The managed database can contain application tables created after an outdated
Alembic version marker. Running a normal upgrade there replays already-present
tables and fails. This narrow, PostgreSQL-only repair creates the missing
cash-handoff reference, custody table, and their integrity constraints,
idempotently and without rewriting business data.

Usage: ``python -m app.scripts.repair_cash_handoff_schema``.
"""

from __future__ import annotations

from sqlalchemy import inspect

from app.database import Base, get_engine


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
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_transactions_hotel_id_id'
          AND conrelid = 'transactions'::regclass
      ) THEN
        ALTER TABLE transactions
          ADD CONSTRAINT uq_transactions_hotel_id_id UNIQUE (hotel_id, id);
      END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS payment_proofs (
      id SERIAL PRIMARY KEY,
      hotel_id INTEGER NOT NULL REFERENCES hotel_configuration (id) ON DELETE CASCADE,
      reservation_id INTEGER NOT NULL,
      transaction_id INTEGER,
      amount NUMERIC(12, 2) NOT NULL,
      currency VARCHAR(3) NOT NULL,
      payment_method VARCHAR(30) NOT NULL,
      status VARCHAR(20) NOT NULL,
      storage_key VARCHAR(255) NOT NULL,
      original_filename VARCHAR(255),
      content_type VARCHAR(80) NOT NULL,
      file_size_bytes INTEGER NOT NULL,
      sha256_hex VARCHAR(64) NOT NULL,
      submitted_by_user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
      reviewed_by_user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
      rejection_reason TEXT,
      created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
      reviewed_at TIMESTAMP WITHOUT TIME ZONE,
      CONSTRAINT ck_payment_proofs_amount_positive CHECK (amount > 0),
      CONSTRAINT ck_payment_proofs_file_size_positive CHECK (file_size_bytes > 0),
      CONSTRAINT ck_payment_proofs_bank_transfer_only CHECK (payment_method = 'bank_transfer'),
      CONSTRAINT uq_payment_proofs_transaction_id UNIQUE (transaction_id),
      CONSTRAINT uq_payment_proofs_storage_key UNIQUE (storage_key),
      CONSTRAINT uq_payment_proofs_hotel_sha256 UNIQUE (hotel_id, sha256_hex),
      CONSTRAINT uq_payment_proofs_hotel_id_id UNIQUE (hotel_id, id),
      CONSTRAINT fk_payment_proofs_hotel_reservation
        FOREIGN KEY (hotel_id, reservation_id)
        REFERENCES reservations (hotel_id, id) ON DELETE CASCADE,
      CONSTRAINT fk_payment_proofs_hotel_transaction
        FOREIGN KEY (hotel_id, transaction_id)
        REFERENCES transactions (hotel_id, id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_payment_proofs_hotel_id ON payment_proofs (hotel_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_proofs_reservation_id ON payment_proofs (reservation_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_proofs_status ON payment_proofs (status)",
    """
    CREATE INDEX IF NOT EXISTS ix_payment_proofs_hotel_reservation_status
      ON payment_proofs (hotel_id, reservation_id, status)
    """,
    "ALTER TABLE payment_proofs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE payment_proofs FORCE ROW LEVEL SECURITY",
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = current_schema()
          AND tablename = 'payment_proofs'
          AND policyname = 'tenant_isolation_payment_proofs'
      ) THEN
        CREATE POLICY tenant_isolation_payment_proofs ON payment_proofs
          USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
          WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer);
      END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS payment_proof_blobs (
      id SERIAL PRIMARY KEY,
      hotel_id INTEGER NOT NULL REFERENCES hotel_configuration (id) ON DELETE CASCADE,
      proof_id INTEGER NOT NULL UNIQUE,
      content BYTEA NOT NULL,
      content_type VARCHAR(80) NOT NULL,
      sha256_hex VARCHAR(64) NOT NULL,
      created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
      CONSTRAINT ck_payment_proof_blobs_content_nonempty CHECK (length(content) > 0),
      CONSTRAINT ck_payment_proof_blobs_sha256_length CHECK (length(sha256_hex) = 64),
      CONSTRAINT uq_payment_proof_blobs_hotel_id_id UNIQUE (hotel_id, id),
      CONSTRAINT fk_payment_proof_blobs_hotel_proof
        FOREIGN KEY (hotel_id, proof_id)
        REFERENCES payment_proofs (hotel_id, id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_payment_proof_blobs_hotel_id ON payment_proof_blobs (hotel_id)",
    "CREATE INDEX IF NOT EXISTS ix_payment_proof_blobs_proof_id ON payment_proof_blobs (proof_id)",
    """
    CREATE INDEX IF NOT EXISTS ix_payment_proof_blobs_hotel_proof
      ON payment_proof_blobs (hotel_id, proof_id)
    """,
    "ALTER TABLE payment_proof_blobs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE payment_proof_blobs FORCE ROW LEVEL SECURITY",
    """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = current_schema()
          AND tablename = 'payment_proof_blobs'
          AND policyname = 'tenant_isolation_payment_proof_blobs'
      ) THEN
        CREATE POLICY tenant_isolation_payment_proof_blobs ON payment_proof_blobs
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


def missing_model_tables(engine, *, metadata=None, inspect_factory=None) -> list[str]:
    """Return model tables absent from a PostgreSQL database without changing it."""

    if getattr(getattr(engine, "dialect", None), "name", None) != "postgresql":
        raise CashHandoffSchemaRepairError("Schema drift report requires PostgreSQL")

    if metadata is None:
        import app.models  # noqa: F401

        metadata = Base.metadata
    inspector = (inspect_factory or inspect)(engine)
    existing_tables = set(inspector.get_table_names())
    return sorted(table.name for table in metadata.sorted_tables if table.name not in existing_tables)


def main() -> None:
    engine = get_engine()
    repair_cash_handoff_schema(engine)
    print("Cash handoff schema repair complete")
    missing_tables = missing_model_tables(engine)
    if missing_tables:
        print("Schema drift missing model tables: " + ", ".join(missing_tables))
    else:
        print("Schema drift missing model tables: none")


if __name__ == "__main__":
    main()
