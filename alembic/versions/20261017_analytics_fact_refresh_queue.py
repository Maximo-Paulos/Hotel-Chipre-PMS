"""Add a tenant-isolated SQL queue for reservation fact refreshes."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261017_analytics_fact_refresh_queue"
down_revision: Union[str, None] = "3aaf546faec7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "analytics_fact_refresh_jobs"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_error_type", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("date_to >= date_from", name="ck_analytics_fact_refresh_jobs_date_window"),
        sa.CheckConstraint("attempts >= 0", name="ck_analytics_fact_refresh_jobs_attempts_nonnegative"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id",
            "reservation_id",
            name="uq_analytics_fact_refresh_jobs_hotel_reservation",
        ),
    )
    op.create_index(
        "ix_analytics_fact_refresh_jobs_hotel_available",
        TABLE,
        ["hotel_id", "available_at", "id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        quoted = f'"{TABLE}"'
        policy = f'"tenant_isolation_{TABLE}"'
        op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
        op.execute(
            f"CREATE POLICY {policy} ON {quoted} "
            "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer) "
            "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        quoted = f'"{TABLE}"'
        policy = f'"tenant_isolation_{TABLE}"'
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
        op.execute(f"ALTER TABLE {quoted} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_analytics_fact_refresh_jobs_hotel_available", table_name=TABLE)
    op.drop_table(TABLE)
