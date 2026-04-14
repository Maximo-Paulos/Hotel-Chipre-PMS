"""launch security hardening

Revision ID: 20260408_launch_security_hardening
Revises: 20260408_security_tokens, a7f3d2c1b9e8
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408_launch_security_hardening"
down_revision: Union[str, Sequence[str], None] = ("20260408_security_tokens", "a7f3d2c1b9e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk_names(inspector, table_name: str) -> set[str]:
    return {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "rate_limit_events" not in table_names:
        op.create_table(
            "rate_limit_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("scope", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_rate_limit_events_scope", "rate_limit_events", ["scope"], unique=False)
        op.create_index("ix_rate_limit_events_subject_key", "rate_limit_events", ["subject_key"], unique=False)
        op.create_index("ix_rate_limit_events_created_at", "rate_limit_events", ["created_at"], unique=False)
        op.create_index(
            "ix_rate_limit_scope_subject_created",
            "rate_limit_events",
            ["scope", "subject_key", "created_at"],
            unique=False,
        )

    if "integration_connections" in table_names:
        fk_names = _fk_names(inspector, "integration_connections")
        if "fk_integration_connections_hotel" not in fk_names:
            with op.batch_alter_table("integration_connections") as batch_op:
                batch_op.create_foreign_key(
                    "fk_integration_connections_hotel",
                    "hotel_configuration",
                    ["hotel_id"],
                    ["id"],
                    ondelete="CASCADE",
                )

    if "payment_link_tests" in table_names:
        fk_names = _fk_names(inspector, "payment_link_tests")
        if "fk_payment_link_tests_hotel" not in fk_names:
            with op.batch_alter_table("payment_link_tests") as batch_op:
                batch_op.create_foreign_key(
                    "fk_payment_link_tests_hotel",
                    "hotel_configuration",
                    ["hotel_id"],
                    ["id"],
                    ondelete="CASCADE",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "payment_link_tests" in table_names and "fk_payment_link_tests_hotel" in _fk_names(inspector, "payment_link_tests"):
        with op.batch_alter_table("payment_link_tests") as batch_op:
            batch_op.drop_constraint("fk_payment_link_tests_hotel", type_="foreignkey")

    if "integration_connections" in table_names and "fk_integration_connections_hotel" in _fk_names(inspector, "integration_connections"):
        with op.batch_alter_table("integration_connections") as batch_op:
            batch_op.drop_constraint("fk_integration_connections_hotel", type_="foreignkey")

    if "rate_limit_events" in table_names:
        op.drop_index("ix_rate_limit_scope_subject_created", table_name="rate_limit_events")
        op.drop_index("ix_rate_limit_events_created_at", table_name="rate_limit_events")
        op.drop_index("ix_rate_limit_events_subject_key", table_name="rate_limit_events")
        op.drop_index("ix_rate_limit_events_scope", table_name="rate_limit_events")
        op.drop_table("rate_limit_events")
