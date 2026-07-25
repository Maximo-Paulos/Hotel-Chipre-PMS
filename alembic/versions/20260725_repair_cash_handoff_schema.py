"""Repair cash handoff columns that were absent from an already-stamped schema.

Some existing PostgreSQL environments recorded the cash-handoff revision while
``cash_close_reports.successor_session_id`` was still absent. This repair is
idempotent and only adds the nullable reference plus its integrity constraints
when inspection proves they are missing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260725_repair_cash_handoff_schema"
down_revision: Union[str, None] = "20260724_billing_adjustment_enum_values"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_unique(inspector, table_name: str, columns: tuple[str, ...]) -> bool:
    wanted = list(columns)
    return any(item.get("column_names") == wanted for item in inspector.get_unique_constraints(table_name)) or any(
        item.get("unique") and item.get("column_names") == wanted
        for item in inspector.get_indexes(table_name)
    )


def _has_fk(inspector, table_name: str, columns: tuple[str, ...], referred_columns: tuple[str, ...]) -> bool:
    return any(
        item.get("constrained_columns") == list(columns)
        and item.get("referred_table") == "cash_sessions"
        and item.get("referred_columns") == list(referred_columns)
        for item in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    if "successor_session_id" not in {column["name"] for column in inspector.get_columns("cash_close_reports")}:
        op.add_column("cash_close_reports", sa.Column("successor_session_id", sa.Integer(), nullable=True))

    # The original cash-handoff migration owns these constraints. Reapply only
    # the missing pieces so a partially applied historical revision becomes a
    # valid schema without rewriting or deleting data.
    if not _has_unique(inspector, "cash_close_reports", ("successor_session_id",)):
        op.create_unique_constraint(
            "uq_cash_close_reports_successor_session",
            "cash_close_reports",
            ["successor_session_id"],
        )
    if not _has_fk(inspector, "cash_close_reports", ("successor_session_id",), ("id",)):
        op.create_foreign_key(
            "fk_cash_close_reports_successor_session",
            "cash_close_reports",
            "cash_sessions",
            ["successor_session_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_unique(inspector, "cash_sessions", ("hotel_id", "id")):
        op.create_unique_constraint("uq_cash_sessions_hotel_id_id", "cash_sessions", ["hotel_id", "id"])
    if not _has_unique(inspector, "cash_close_reports", ("hotel_id", "id")):
        op.create_unique_constraint("uq_cash_close_reports_hotel_id_id", "cash_close_reports", ["hotel_id", "id"])
    if not _has_fk(inspector, "cash_close_reports", ("hotel_id", "successor_session_id"), ("hotel_id", "id")):
        op.create_foreign_key(
            "fk_cash_close_reports_hotel_successor_session",
            "cash_close_reports",
            "cash_sessions",
            ["hotel_id", "successor_session_id"],
            ["hotel_id", "id"],
        )


def downgrade() -> None:
    # Deliberately no-op: this is a repair for historical, partially applied
    # schemas. Dropping the reference could erase successor links created after
    # repair and cannot be distinguished safely from the original migration.
    return
