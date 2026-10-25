"""Snapshot corporate terms per reservation and audit manager review.

Revision ID: 20261025_company_reservation_terms
Revises: 20261025_guest_arrivals
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20261025_company_reservation_terms"
down_revision: str | None = "20261025_guest_arrivals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "reservation_company_terms_reviews"


def _install_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{_TABLE}" ON "{_TABLE}"')
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{_TABLE}" ON "{_TABLE}"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{_TABLE}" ON "{_TABLE}"')
    op.execute(f'ALTER TABLE "{_TABLE}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.add_column("reservations", sa.Column("company_terms_snapshot", sa.JSON(), nullable=True))
    op.add_column("reservations", sa.Column("company_terms_reviewed_config", sa.JSON(), nullable=True))
    op.add_column("reservations", sa.Column("company_terms_review_state", sa.String(length=40), nullable=True))
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "block_checkin_on_company_terms_change",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("expected_config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("previous_snapshot", sa.JSON(), nullable=True),
        sa.Column("previous_reviewed_config", sa.JSON(), nullable=True),
        sa.Column("current_company_terms", sa.JSON(), nullable=False),
        sa.Column("resulting_snapshot", sa.JSON(), nullable=True),
        sa.Column("applied_reservation_changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('keep_snapshot', 'accept_current')",
            name="ck_reservation_company_terms_review_action",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_reservation_company_terms_review_reason"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_company_terms_reviews_hotel", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_company_terms_reviews_reservation", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_reservation_company_terms_reviews_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name="fk_reservation_company_terms_reviews_actor_user_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservation_company_terms_reviews"),
        sa.UniqueConstraint(
            "hotel_id", "id", name="uq_reservation_company_terms_reviews_hotel_id_id"
        ),
        sa.UniqueConstraint(
            "hotel_id", "reservation_id", "idempotency_key",
            name="uq_reservation_company_terms_reviews_idempotency",
        ),
    )
    op.create_index(
        "ix_reservation_company_terms_reviews_hotel_reservation_created",
        _TABLE,
        ["hotel_id", "reservation_id", "created_at", "id"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_reservation_company_terms_review_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'reservation company terms reviews are append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{_TABLE}_append_only
            BEFORE UPDATE OR DELETE ON {_TABLE}
            FOR EACH ROW EXECUTE FUNCTION reject_reservation_company_terms_review_mutation()
            """
        )
    _install_tenant_rls()


def downgrade() -> None:
    _remove_tenant_rls()
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{_TABLE}_append_only ON {_TABLE}")
        op.execute("DROP FUNCTION IF EXISTS reject_reservation_company_terms_review_mutation()")
    op.drop_index(
        "ix_reservation_company_terms_reviews_hotel_reservation_created",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
    op.drop_column("hotel_configuration", "block_checkin_on_company_terms_change")
    op.drop_column("reservations", "company_terms_review_state")
    op.drop_column("reservations", "company_terms_reviewed_config")
    op.drop_column("reservations", "company_terms_snapshot")
