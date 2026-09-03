"""Add durable job dedupe and worker heartbeat metadata."""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "tech0140_job_runtime"
down_revision: Union[str, None] = "tech0140_stored_objects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rls(table: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'''CREATE POLICY "tenant_isolation_{table}" ON "{table}"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "job_dispatch_records" not in inspector.get_table_names():
        op.create_table(
            "job_dispatch_records",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("task_name", sa.String(160), nullable=False),
            sa.Column("deduplication_key", sa.String(255), nullable=False),
            sa.Column("correlation_id", sa.String(128), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hotel_id", "task_name", "deduplication_key", name="uq_job_dispatch_hotel_task_dedupe"),
            sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_job_dispatch_status"),
        )
        op.create_index("ix_job_dispatch_hotel_status", "job_dispatch_records", ["hotel_id", "status"])
        _rls("job_dispatch_records")
    if "service_heartbeats" not in inspector.get_table_names():
        op.create_table(
            "service_heartbeats",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("environment", sa.String(32), nullable=False),
            sa.Column("service_name", sa.String(80), nullable=False),
            sa.Column("instance_id", sa.String(160), nullable=False),
            sa.Column("queue_name", sa.String(80), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("environment", "service_name", "instance_id", name="uq_service_heartbeat_identity"),
        )
        op.create_index("ix_service_heartbeats_last_seen", "service_heartbeats", ["environment", "last_seen_at"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("job_dispatch_records",):
            op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"')
            op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_service_heartbeats_last_seen", table_name="service_heartbeats")
    op.drop_table("service_heartbeats")
    op.drop_index("ix_job_dispatch_hotel_status", table_name="job_dispatch_records")
    op.drop_table("job_dispatch_records")
