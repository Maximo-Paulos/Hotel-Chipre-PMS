"""Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.

Revision ID: 20260911_whatsapp_crm
Revises: 20260910_marketing_pricing_and_leads
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260911_whatsapp_crm"
down_revision: Union[str, None] = "20260910_marketing_pricing_and_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


_RLS_TABLES = (
    "whatsapp_channels",
    "whatsapp_contacts",
    "whatsapp_conversations",
    "whatsapp_messages",
    "whatsapp_conversation_notes",
    "whatsapp_conversation_events",
    "whatsapp_outbound_outbox",
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
    inspector = sa.inspect(bind)
    if "integration_connections" in inspector.get_table_names():
        unique_pairs = {tuple(item.get("column_names") or ()) for item in inspector.get_unique_constraints("integration_connections")}
        unique_pairs.update(tuple(item.get("column_names") or ()) for item in inspector.get_indexes("integration_connections") if item.get("unique"))
        if ("hotel_id", "id") not in unique_pairs:
            with op.batch_alter_table("integration_connections") as batch_op:
                batch_op.create_unique_constraint("uq_integration_connections_hotel_id", ["hotel_id", "id"])
    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_channels" not in tables:
        op.create_table(
            "whatsapp_channels",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("integration_connection_id", sa.Integer(), nullable=True),
            sa.Column("waba_id", sa.String(120), nullable=True),
            sa.Column("phone_number_id", sa.String(120), nullable=True),
            sa.Column("display_phone_number", sa.String(40), nullable=True),
            sa.Column("display_name", sa.String(160), nullable=True),
            sa.Column("status", _enum("whatsapp_channel_status_enum", "not_enabled", "ready", "in_meta", "waiting_verification", "waiting_payment_method", "connecting_webhooks", "test_pending", "active", "attention", "paused", "disconnected"), nullable=False, server_default="not_enabled"),
            sa.Column("onboarding_step", sa.String(60), nullable=True),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("last_error", sa.String(300), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "integration_connection_id"], ["integration_connections.hotel_id", "integration_connections.id"], name="fk_whatsapp_channels_hotel_integration", ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", name="uq_whatsapp_channels_hotel"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_whatsapp_channels_hotel_id"),
            sa.UniqueConstraint("hotel_id", "phone_number_id", name="uq_whatsapp_channels_hotel_phone"),
        )
        op.create_index("ix_whatsapp_channels_hotel_status", "whatsapp_channels", ["hotel_id", "status"])

    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_provider_routes" not in tables:
        op.create_table(
            "whatsapp_provider_routes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("phone_number_id", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("phone_number_id", name="uq_whatsapp_provider_routes_phone"),
        )
        op.create_index("ix_whatsapp_provider_routes_hotel", "whatsapp_provider_routes", ["hotel_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_contacts" not in tables:
        op.create_table(
            "whatsapp_contacts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("normalized_phone", sa.String(40), nullable=False),
            sa.Column("display_name", sa.String(160), nullable=True),
            sa.Column("guest_id", sa.Integer(), nullable=True),
            sa.Column("association_confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("association_confirmed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"], name="fk_whatsapp_contacts_hotel_guest", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["association_confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", "channel_id", "normalized_phone", name="uq_whatsapp_contacts_phone"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_whatsapp_contacts_hotel_id"),
        )
        op.create_index("ix_whatsapp_contacts_hotel_guest", "whatsapp_contacts", ["hotel_id", "guest_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_conversations" not in tables:
        op.create_table(
            "whatsapp_conversations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("status", _enum("whatsapp_conversation_status_enum", "new", "open", "assigned", "pending", "closed"), nullable=False, server_default="new"),
            sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
            sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
            sa.Column("department", sa.String(60), nullable=True),
            sa.Column("shift_key", sa.String(80), nullable=True),
            sa.Column("human_active", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("service_window_expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_inbound_at", sa.DateTime(), nullable=True),
            sa.Column("last_message_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "contact_id"], ["whatsapp_contacts.hotel_id", "whatsapp_contacts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_whatsapp_conversations_hotel_id"),
            sa.UniqueConstraint("hotel_id", "channel_id", "contact_id", name="uq_whatsapp_conversations_contact"),
        )
        op.create_index("ix_whatsapp_conversations_inbox", "whatsapp_conversations", ["hotel_id", "status", "assigned_to_user_id", "last_message_at"])
        op.create_index("ix_whatsapp_conversations_shift", "whatsapp_conversations", ["hotel_id", "shift_key", "status"])

    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_messages" not in tables:
        op.create_table(
            "whatsapp_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("provider_message_id", sa.String(180), nullable=True),
            sa.Column("direction", _enum("whatsapp_message_direction_enum", "inbound", "outbound", "internal", "system"), nullable=False),
            sa.Column("status", _enum("whatsapp_message_status_enum", "received", "queued", "sent", "delivered", "read", "failed"), nullable=False, server_default="received"),
            sa.Column("message_type", sa.String(40), nullable=False, server_default="text"),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("media_object_key", sa.String(300), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("occurred_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "conversation_id"], ["whatsapp_conversations.hotel_id", "whatsapp_conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("hotel_id", "provider_message_id", name="uq_whatsapp_messages_provider_id"),
            sa.UniqueConstraint("hotel_id", "id", name="uq_whatsapp_messages_hotel_id"),
        )
        op.create_index("ix_whatsapp_messages_conversation_created", "whatsapp_messages", ["hotel_id", "conversation_id", "created_at"])

    for table_name, index_name in (("whatsapp_conversation_notes", "ix_whatsapp_notes_conversation"), ("whatsapp_conversation_events", "ix_whatsapp_events_conversation")):
        tables = set(sa.inspect(bind).get_table_names())
        if table_name in tables:
            continue
        is_note = table_name.endswith("notes")
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id" if is_note else "actor_user_id", sa.Integer(), nullable=True),
            sa.Column("body" if is_note else "event_type", sa.Text() if is_note else sa.String(80), nullable=False),
            *([] if is_note else [sa.Column("payload_json", sa.Text(), nullable=True)]),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "conversation_id"], ["whatsapp_conversations.hotel_id", "whatsapp_conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_user_id" if is_note else "actor_user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index(index_name, table_name, ["hotel_id", "conversation_id", "created_at"])
    tables = set(sa.inspect(bind).get_table_names())
    if "whatsapp_outbound_outbox" not in tables:
        op.create_table(
            "whatsapp_outbound_outbox",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("last_error", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id", "message_id"], ["whatsapp_messages.hotel_id", "whatsapp_messages.id"], name="fk_whatsapp_outbox_hotel_message", ondelete="CASCADE"),
            sa.UniqueConstraint("hotel_id", "message_id", name="uq_whatsapp_outbox_message"),
        )
        op.create_index("ix_whatsapp_outbox_pending", "whatsapp_outbound_outbox", ["hotel_id", "status", "next_attempt_at"])
    _install_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _remove_rls(bind)
    try:
        op.drop_index("ix_whatsapp_outbox_pending", table_name="whatsapp_outbound_outbox")
    except Exception:
        pass
    if "whatsapp_outbound_outbox" in sa.inspect(bind).get_table_names():
        op.drop_table("whatsapp_outbound_outbox")
    for table_name, index_name in (("whatsapp_conversation_events", "ix_whatsapp_events_conversation"), ("whatsapp_conversation_notes", "ix_whatsapp_notes_conversation"), ("whatsapp_messages", "ix_whatsapp_messages_conversation_created"), ("whatsapp_conversations", "ix_whatsapp_conversations_shift"), ("whatsapp_conversations", "ix_whatsapp_conversations_inbox"), ("whatsapp_contacts", "ix_whatsapp_contacts_hotel_guest"), ("whatsapp_channels", "ix_whatsapp_channels_hotel_status")):
        if table_name in {"whatsapp_conversations", "whatsapp_channels", "whatsapp_contacts", "whatsapp_messages"}:
            try:
                op.drop_index(index_name, table_name=table_name)
            except Exception:
                pass
    op.drop_index("ix_whatsapp_provider_routes_hotel", table_name="whatsapp_provider_routes")
    op.drop_table("whatsapp_provider_routes")
    for table_name in ("whatsapp_conversation_events", "whatsapp_conversation_notes", "whatsapp_messages", "whatsapp_conversations", "whatsapp_contacts", "whatsapp_channels"):
        op.drop_table(table_name)
    inspector = sa.inspect(bind)
    if "integration_connections" in inspector.get_table_names() and any(
        item.get("name") == "uq_integration_connections_hotel_id"
        for item in inspector.get_unique_constraints("integration_connections")
    ):
        with op.batch_alter_table("integration_connections") as batch_op:
            batch_op.drop_constraint("uq_integration_connections_hotel_id", type_="unique")
