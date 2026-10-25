"""Add the keyset pagination index for WhatsApp message history.

Revision ID: 20261025_wa_msg_cursor_idx
Revises: 20261025_allocation_reservation_trigger_index
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20261025_wa_msg_cursor_idx"
down_revision: str | None = "20261025_allocation_reservation_trigger_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEX_NAME = "ix_whatsapp_messages_hotel_conversation_id"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # WhatsApp history can grow while the index is being built. Concurrent
        # creation keeps normal inserts and webhook writes available.
        with op.get_context().autocommit_block():
            op.create_index(
                _INDEX_NAME,
                "whatsapp_messages",
                ["hotel_id", "conversation_id", "id"],
                unique=False,
                postgresql_concurrently=True,
            )
        return

    op.create_index(
        _INDEX_NAME,
        "whatsapp_messages",
        ["hotel_id", "conversation_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(
                _INDEX_NAME,
                table_name="whatsapp_messages",
                postgresql_concurrently=True,
            )
        return

    op.drop_index(_INDEX_NAME, table_name="whatsapp_messages")
