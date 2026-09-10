"""add tenant-scoped operational tasks and shift handoffs

Revision ID: 20260910_operational_tasks_handoff
Revises: 63f2a956b2b2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_operational_tasks_handoff"
down_revision: Union[str, None] = "63f2a956b2b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


_RLS_TABLES = (
    "operational_tasks",
    "operational_task_events",
    "shift_handoffs",
    "shift_handoff_tasks",
)


def _install_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table_name in _RLS_TABLES:
        op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(
            f'''CREATE POLICY "tenant_isolation_{table_name}"
               ON "{table_name}"
               USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
               WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def _remove_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table_name in reversed(_RLS_TABLES):
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "operational_tasks" not in tables:
        op.create_table(
            "operational_tasks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=True),
            sa.Column("reservation_id", sa.Integer(), nullable=True),
            sa.Column("room_block_id", sa.Integer(), nullable=True),
            sa.Column("task_type", _enum("operational_task_type_enum", "general", "reception", "housekeeping", "maintenance"), nullable=False),
            sa.Column("status", _enum("operational_task_status_enum", "pending", "in_progress", "pending_review", "resolved"), nullable=False),
            sa.Column("priority", _enum("operational_task_priority_enum", "low", "medium", "high", "critical"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_operational_tasks_hotel_id_id"),
        )
        op.create_index("ix_operational_tasks_hotel_status_due", "operational_tasks", ["hotel_id", "status", "due_at"])
        op.create_index("ix_operational_tasks_hotel_room", "operational_tasks", ["hotel_id", "room_id"])
        op.create_index("ix_operational_tasks_hotel_reservation", "operational_tasks", ["hotel_id", "reservation_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "operational_task_events" not in tables:
        op.create_table(
            "operational_task_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("from_status", sa.String(length=40), nullable=True),
            sa.Column("to_status", sa.String(length=40), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id", "task_id"], ["operational_tasks.hotel_id", "operational_tasks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_operational_task_events_hotel_task_created", "operational_task_events", ["hotel_id", "task_id", "created_at"])

    tables = set(sa.inspect(bind).get_table_names())
    if "shift_handoffs" not in tables:
        op.create_table(
            "shift_handoffs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("delivered_by_user_id", sa.Integer(), nullable=True),
            sa.Column("received_by_user_id", sa.Integer(), nullable=True),
            sa.Column("cash_close_report_id", sa.Integer(), nullable=True),
            sa.Column("status", _enum("shift_handoff_status_enum", "pending_acknowledgement", "acknowledged"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["delivered_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["hotel_id", "cash_close_report_id"], ["cash_close_reports.hotel_id", "cash_close_reports.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_shift_handoffs_hotel_id_id"),
        )
        op.create_index("ix_shift_handoffs_hotel_delivered", "shift_handoffs", ["hotel_id", "delivered_at"])

    tables = set(sa.inspect(bind).get_table_names())
    if "shift_handoff_tasks" not in tables:
        op.create_table(
            "shift_handoff_tasks",
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("handoff_id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), primary_key=True),
            sa.ForeignKeyConstraint(["hotel_id", "handoff_id"], ["shift_handoffs.hotel_id", "shift_handoffs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "task_id"], ["operational_tasks.hotel_id", "operational_tasks.id"], ondelete="CASCADE"),
        )
    _install_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _remove_rls(bind)
    tables = set(sa.inspect(bind).get_table_names())
    if "shift_handoff_tasks" in tables:
        op.drop_table("shift_handoff_tasks")
    if "shift_handoffs" in tables:
        op.drop_index("ix_shift_handoffs_hotel_delivered", table_name="shift_handoffs")
        op.drop_table("shift_handoffs")
    if "operational_task_events" in tables:
        op.drop_index("ix_operational_task_events_hotel_task_created", table_name="operational_task_events")
        op.drop_table("operational_task_events")
    if "operational_tasks" in tables:
        op.drop_index("ix_operational_tasks_hotel_reservation", table_name="operational_tasks")
        op.drop_index("ix_operational_tasks_hotel_room", table_name="operational_tasks")
        op.drop_index("ix_operational_tasks_hotel_status_due", table_name="operational_tasks")
        op.drop_table("operational_tasks")
