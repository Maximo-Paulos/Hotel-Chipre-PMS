"""Add the per-hotel application interface language.

The existing ``languages`` column describes languages spoken by the hotel
team. ``interface_language`` is a separate, deliberately small setting for
the frontend locale and defaults to Spanish for existing and new hotels.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260901_interface_language"
down_revision = "20260901_domain_event_outbox"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    return any(
        column["name"] == "interface_language"
        for column in sa.inspect(op.get_bind()).get_columns("hotel_configuration")
    )


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            "hotel_configuration",
            sa.Column(
                "interface_language",
                sa.String(length=2),
                nullable=False,
                server_default=sa.text("'es'"),
            ),
        )


def downgrade() -> None:
    if not _has_column():
        return

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration", recreate="auto") as batch_op:
            batch_op.drop_column("interface_language")
    else:
        op.drop_column("hotel_configuration", "interface_language")
