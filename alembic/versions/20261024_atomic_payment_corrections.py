"""Add auditable, idempotent payment corrections.

Revision ID: 20261024_atomic_payment_corrections
Revises: ebaf9d3d2baa
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261024_atomic_payment_corrections"
down_revision: Union[str, None] = "ebaf9d3d2baa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "payment:correct"
_PERMISSION_DESCRIPTION = "Correct a recorded payment"
_MANUAL_REFERENCE_INDEX = "uq_transactions_manual_reference_hotel_method"


def _manual_reference_index_exists(connection) -> bool:
    if connection.dialect.name == "sqlite":
        return connection.execute(
            sa.text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = 'transactions' AND name = :index_name"
            ),
            {"index_name": _MANUAL_REFERENCE_INDEX},
        ).first() is not None
    if connection.dialect.name == "postgresql":
        return connection.execute(
            sa.text(
                "SELECT 1 FROM pg_class index_relation "
                "JOIN pg_index index_metadata ON index_metadata.indexrelid = index_relation.oid "
                "JOIN pg_class table_relation ON table_relation.oid = index_metadata.indrelid "
                "WHERE index_relation.oid = to_regclass(:index_name) "
                "AND table_relation.oid = to_regclass('transactions')"
            ),
            {"index_name": _MANUAL_REFERENCE_INDEX},
        ).first() is not None
    return any(
        index.get("name") == _MANUAL_REFERENCE_INDEX
        for index in sa.inspect(connection).get_indexes("transactions")
    )


def _assert_manual_reference_keys_unique(connection, *, include_cancelled: bool) -> None:
    """Fail before DDL if existing rows cannot satisfy the target unique index."""
    active_only = "" if include_cancelled else " AND status <> 'cancelled'"
    duplicate = connection.execute(
        sa.text(
            "SELECT 1 FROM transactions "
            "WHERE manual_reference IS NOT NULL" + active_only + " "
            "GROUP BY hotel_id, payment_method, lower(manual_reference) "
            "HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        scope = "including cancelled transactions" if include_cancelled else "among active transactions"
        raise RuntimeError(
            "Cannot change the manual-reference unique index: duplicate hotel/payment-method/reference "
            f"values exist {scope}. Reconcile those rows before retrying the migration."
        )


def _replace_manual_reference_index(connection, *, include_cancelled: bool) -> None:
    if _manual_reference_index_exists(connection):
        op.drop_index(_MANUAL_REFERENCE_INDEX, table_name="transactions")
    predicate = "manual_reference IS NOT NULL"
    if not include_cancelled:
        predicate += " AND status <> 'cancelled'"
    op.create_index(
        _MANUAL_REFERENCE_INDEX,
        "transactions",
        ["hotel_id", "payment_method", sa.text("lower(manual_reference)")],
        unique=True,
        postgresql_where=sa.text(predicate),
        sqlite_where=sa.text(predicate),
    )


def _install_tenant_rls() -> None:
    """Keep correction history isolated even for direct SQL access."""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute('ALTER TABLE "payment_corrections" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "payment_corrections" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_payment_corrections" '
        'ON "payment_corrections"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_payment_corrections"
        ON "payment_corrections"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_payment_corrections" '
        'ON "payment_corrections"'
    )
    op.execute('ALTER TABLE "payment_corrections" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "payment_corrections" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()
    # Some supported databases arrive here without the legacy index (for
    # example after a partial/manual schema repair). Validate existing rows
    # before any DDL, then replace the index only when it exists.
    _assert_manual_reference_keys_unique(connection, include_cancelled=False)

    op.create_table(
        "payment_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("source_transaction_id", sa.Integer(), nullable=False),
        sa.Column("source_reservation_id", sa.Integer(), nullable=False),
        sa.Column("target_reservation_id", sa.Integer(), nullable=True),
        sa.Column("replacement_transaction_id", sa.Integer(), nullable=True),
        sa.Column("correction_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "correction_type IN ('reassign', 'duplicate_reversal')",
            name="ck_payment_corrections_type",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0 AND length(trim(idempotency_key)) >= 8",
            name="ck_payment_corrections_reason_and_key",
        ),
        sa.CheckConstraint(
            "(correction_type = 'reassign' AND target_reservation_id IS NOT NULL "
            "AND replacement_transaction_id IS NOT NULL) OR "
            "(correction_type = 'duplicate_reversal' AND target_reservation_id IS NULL "
            "AND replacement_transaction_id IS NULL)",
            name="ck_payment_corrections_replacement_shape",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "source_transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_corrections_source_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "source_reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_corrections_source_reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "target_reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_corrections_target_reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "replacement_transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_corrections_replacement_transaction",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_payment_corrections_hotel_id_id"),
        sa.UniqueConstraint("hotel_id", "source_transaction_id", name="uq_payment_corrections_source"),
        sa.UniqueConstraint("hotel_id", "idempotency_key", name="uq_payment_corrections_idempotency"),
    )
    op.create_index(
        "ix_payment_corrections_hotel_created",
        "payment_corrections",
        ["hotel_id", "created_at", "id"],
        unique=False,
    )
    _install_tenant_rls()

    # A corrected payment may reuse the same verified manual receipt reference.
    # Keep uniqueness across active rows while preserving the canceled source.
    _replace_manual_reference_index(connection, include_cancelled=False)

    connection.execute(
        sa.text(
            "INSERT INTO permissions "
            "(code, description, critical, step_up_required, delegable) "
            "VALUES (:code, :description, false, true, false) "
            "ON CONFLICT (code) DO UPDATE SET description = excluded.description, "
            "critical = false, step_up_required = true, delegable = false"
        ),
        {"code": _PERMISSION, "description": _PERMISSION_DESCRIPTION},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
            "VALUES ('owner', :code, true), ('co_owner', :code, true), "
            "('manager', :code, true), ('receptionist', :code, false), "
            "('housekeeping', :code, false) "
            "ON CONFLICT (role, permission_code) DO NOTHING"
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # The migration/table owner is subject to FORCE RLS too. Temporarily
        # remove FORCE so the retention guard sees correction history from all
        # hotels; an exception rolls this DDL back with the migration.
        op.execute('ALTER TABLE "payment_corrections" NO FORCE ROW LEVEL SECURITY')

    has_correction_history = connection.execute(
        sa.text("SELECT 1 FROM payment_corrections LIMIT 1")
    ).first()
    if has_correction_history:
        raise RuntimeError(
            "Cannot downgrade payment corrections while correction history exists; "
            "preserve and reconcile that ledger before removing its schema."
        )

    # The older index also constrained cancelled transactions. A new partial
    # index can permit duplicates that the downgrade cannot restore, so stop
    # before dropping any schema when such rows exist.
    _assert_manual_reference_keys_unique(connection, include_cancelled=True)

    _remove_tenant_rls()
    op.drop_index("ix_payment_corrections_hotel_created", table_name="payment_corrections")
    op.drop_table("payment_corrections")

    _replace_manual_reference_index(connection, include_cancelled=True)

    connection.execute(
        sa.text("DELETE FROM role_permission_defaults WHERE permission_code = :code"),
        {"code": _PERMISSION},
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE code = :code "
            "AND NOT EXISTS (SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM user_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM temporary_action_grants WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM action_step_up_ticket_uses WHERE permission_code = :code)"
        ),
        {"code": _PERMISSION},
    )
