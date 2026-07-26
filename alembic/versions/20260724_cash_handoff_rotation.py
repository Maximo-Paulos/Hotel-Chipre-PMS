"""Add zero-balance cash rotation and custody handoffs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260724_cash_handoff_rotation"
down_revision: Union[str, None] = "20260724_allocation_enum_values"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_successor_reference(dialect: str) -> None:
    # Guarded because some production environments already have this column
    # (and its unique constraint) out-of-band via an old startup self-heal
    # pass while alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    has_column = "successor_session_id" in {c["name"] for c in inspector.get_columns("cash_close_reports")}
    has_unique = "uq_cash_close_reports_successor_session" in {
        uc["name"] for uc in inspector.get_unique_constraints("cash_close_reports")
    }

    column = sa.Column(
        "successor_session_id",
        sa.Integer(),
        sa.ForeignKey(
            "cash_sessions.id",
            name="fk_cash_close_reports_successor_session",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    if dialect == "sqlite":
        if has_column and has_unique:
            return
        with op.batch_alter_table("cash_close_reports", recreate="always") as batch:
            if not has_column:
                batch.add_column(column)
            if not has_unique:
                batch.create_unique_constraint(
                    "uq_cash_close_reports_successor_session",
                    ["successor_session_id"],
                )
        return
    # `op.add_column` with a Column whose ForeignKey has an explicit `name=`
    # already emits the FK constraint inline as part of ADD COLUMN on
    # PostgreSQL. A separate `op.create_foreign_key(...)` call here was
    # redundant and failed with DuplicateObject on a real Postgres server
    # (confirmed by reproducing this migration against a from-scratch local
    # PostgreSQL 16 instance) -- SQLite's batch-recreate path never exercised
    # this, which is why it went unnoticed.
    if not has_column:
        op.add_column("cash_close_reports", column)
    if not has_unique:
        op.create_unique_constraint(
            "uq_cash_close_reports_successor_session",
            "cash_close_reports",
            ["successor_session_id"],
        )


def _drop_successor_reference(dialect: str) -> None:
    if dialect == "sqlite":
        with op.batch_alter_table("cash_close_reports", recreate="always") as batch:
            batch.drop_constraint("uq_cash_close_reports_successor_session", type_="unique")
            batch.drop_column("successor_session_id")
        return
    op.drop_constraint("uq_cash_close_reports_successor_session", "cash_close_reports", type_="unique")
    op.drop_constraint("fk_cash_close_reports_successor_session", "cash_close_reports", type_="foreignkey")
    op.drop_column("cash_close_reports", "successor_session_id")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    _add_successor_reference(dialect)

    if dialect == "postgresql":
        # create_type=False: the type is created explicitly right below with
        # checkfirst=True. Leaving the default (True) makes create_table's own
        # before_create dispatch try to create it a second time -- without a
        # checkfirst guard on that second attempt -- and fail with
        # DuplicateObject on a real PostgreSQL server (same class of bug as
        # 20260612_audit_log_and_transaction_fk.py's _audit_action_enum, which
        # already documents this exact pattern).
        custody_status = postgresql.ENUM(
            "pending",
            "confirmed",
            name="cash_custody_status_enum",
            create_type=False,
        )
        custody_status.create(op.get_bind(), checkfirst=True)
    else:
        custody_status = sa.String(length=20)

    inspector = sa.inspect(op.get_bind())
    if "cash_custody_handoffs" not in inspector.get_table_names():
        op.create_table(
            "cash_custody_handoffs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("close_report_id", sa.Integer(), nullable=False),
            sa.Column("delivered_by_user_id", sa.Integer(), nullable=True),
            sa.Column("received_by_user_id", sa.Integer(), nullable=True),
            sa.Column("delivered_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", custody_status, nullable=False, server_default="pending"),
            sa.Column("delivered_at", sa.DateTime(), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.CheckConstraint("delivered_amount >= 0", name="ck_cash_custody_delivered_nonneg"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["close_report_id"], ["cash_close_reports.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["delivered_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("close_report_id"),
        )
    if "ix_cash_custody_handoffs_hotel_status" not in ({ix["name"] for ix in inspector.get_indexes("cash_custody_handoffs")} if inspector.has_table("cash_custody_handoffs") else set()):
        op.create_index(
            "ix_cash_custody_handoffs_hotel_status",
            "cash_custody_handoffs",
            ["hotel_id", "status"],
        )

    if dialect == "postgresql":
        bind = op.get_bind()
        # ENABLE/FORCE ROW LEVEL SECURITY are idempotent (safe to re-run);
        # CREATE POLICY is not, so guard it against pg_policies.
        op.execute('ALTER TABLE "cash_custody_handoffs" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "cash_custody_handoffs" FORCE ROW LEVEL SECURITY')
        policy_exists = bind.execute(sa.text(
            "SELECT 1 FROM pg_policies WHERE tablename = 'cash_custody_handoffs' "
            "AND policyname = 'tenant_isolation_cash_custody_handoffs'"
        )).first()
        if not policy_exists:
            op.execute('''CREATE POLICY "tenant_isolation_cash_custody_handoffs" ON "cash_custody_handoffs"
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_cash_custody_handoffs" ON "cash_custody_handoffs"')
        op.execute('ALTER TABLE "cash_custody_handoffs" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "cash_custody_handoffs" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_cash_custody_handoffs_hotel_status", table_name="cash_custody_handoffs")
    op.drop_table("cash_custody_handoffs")
    _drop_successor_reference(dialect)
    if dialect == "postgresql":
        postgresql.ENUM(name="cash_custody_status_enum").drop(op.get_bind(), checkfirst=True)
