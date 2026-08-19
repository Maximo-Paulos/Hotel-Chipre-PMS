"""add notification backend: notifications, push_subscriptions,
notification_preferences, notification_outbox, daily_report_schedules

Revision ID: 20260818_notifications
Revises: 20260818_stock_movement_idem
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260818_notifications"
down_revision: Union[str, None] = "20260818_stock_movement_idem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEVERITY_ENUM = sa.Enum("info", "warning", "critical", name="notification_severity_enum")
OUTBOX_SEVERITY_ENUM = sa.Enum("info", "warning", "critical", name="notification_outbox_severity_enum")
CHANNEL_ENUM = sa.Enum("in_app", "push", "email", name="notification_channel_enum")
OUTBOX_STATUS_ENUM = sa.Enum("pending", "sent", "failed", "expired", name="notification_outbox_status_enum")

_TABLES = (
    "daily_report_schedules",
    "notification_outbox",
    "notification_preferences",
    "push_subscriptions",
    "notifications",
)


def _install_rls(connection, table_name: str) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{table_name}"
           ON "{table_name}"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection, table_name: str) -> None:
    """Remove the PostgreSQL tenant policy before dropping its table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
    op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", SEVERITY_ENUM, nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("outbox_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_notifications_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"],
            name="fk_notifications_recipient_user_id_users", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("outbox_id", name="uq_notifications_outbox_id"),
    )
    op.create_index(
        "ix_notifications_hotel_recipient_created", "notifications",
        ["hotel_id", "recipient_user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_hotel_recipient_unread", "notifications",
        ["hotel_id", "recipient_user_id", "is_read"],
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_push_subscriptions_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_push_subscriptions_user_id_users", ondelete="CASCADE",
        ),
        # SQLite/PG both cap on the string/text length actually indexed;
        # endpoint is a browser push URL (well under any dialect's
        # index-entry limit). Declared inline in create_table -- SQLite has
        # no ALTER TABLE ADD CONSTRAINT outside batch mode.
        sa.UniqueConstraint(
            "hotel_id", "user_id", "endpoint", name="uq_push_subscriptions_hotel_user_endpoint",
        ),
    )
    op.create_index("ix_push_subscriptions_hotel_user", "push_subscriptions", ["hotel_id", "user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_notification_preferences_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_notification_preferences_user_id_users", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "hotel_id", "user_id", "event_type", name="uq_notification_preferences_hotel_user_event",
        ),
        sa.CheckConstraint(
            "quiet_hours_start IS NULL OR (quiet_hours_start >= 0 AND quiet_hours_start <= 23)",
            name="ck_notification_preferences_quiet_start_range",
        ),
        sa.CheckConstraint(
            "quiet_hours_end IS NULL OR (quiet_hours_end >= 0 AND quiet_hours_end <= 23)",
            name="ck_notification_preferences_quiet_end_range",
        ),
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        sa.Column("channel", CHANNEL_ENUM, nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("severity", OUTBOX_SEVERITY_ENUM, nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", OUTBOX_STATUS_ENUM, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_notification_outbox_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"],
            name="fk_notification_outbox_recipient_user_id_users", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "hotel_id", "dedupe_key", "channel", "recipient_user_id", name="uq_notification_outbox_dedupe",
        ),
        # Bind target for the composite (hotel_id, outbox_id) FK on
        # notifications below -- a plain PK(id) does not satisfy a composite
        # FK target on PostgreSQL without an explicit (hotel_id, id) unique
        # constraint (harmless/trivial since id is already unique alone).
        sa.UniqueConstraint("hotel_id", "id", name="uq_notification_outbox_hotel_id_id"),
    )
    op.create_index(
        "ix_notification_outbox_pending", "notification_outbox", ["hotel_id", "status", "next_retry_at"],
    )

    # Now that notification_outbox exists, wire notifications.outbox_id -> it.
    # Composite, not scalar: a Notification must never reference another
    # hotel's NotificationOutbox row (see app/models/notification.py).
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.create_foreign_key(
            "fk_notifications_hotel_outbox",
            "notification_outbox", ["hotel_id", "outbox_id"], ["hotel_id", "id"], ondelete="SET NULL",
        )

    op.create_table(
        "daily_report_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("recipient_user_ids", sa.Text(), nullable=True),
        sa.Column("recipient_roles", sa.Text(), nullable=True),
        sa.Column("channels", sa.Text(), nullable=False, server_default='["in_app"]'),
        sa.Column("sections", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_sent_date_local", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_daily_report_schedules_hotel_id_hotel_configuration", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("hotel_id", name="uq_daily_report_schedules_hotel_id"),
        sa.CheckConstraint("hour >= 0 AND hour <= 23", name="ck_daily_report_schedules_hour_range"),
    )

    for table_name in _TABLES:
        _install_rls(connection, table_name)


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in reversed(_TABLES):
        _remove_rls(connection, table_name)

    op.drop_table("daily_report_schedules")

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("fk_notifications_hotel_outbox", type_="foreignkey")

    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("notification_preferences")
    op.drop_index("ix_push_subscriptions_hotel_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_index("ix_notifications_hotel_recipient_unread", table_name="notifications")
    op.drop_index("ix_notifications_hotel_recipient_created", table_name="notifications")
    op.drop_table("notifications")

    if connection.dialect.name == "postgresql":
        OUTBOX_STATUS_ENUM.drop(connection, checkfirst=True)
        CHANNEL_ENUM.drop(connection, checkfirst=True)
        OUTBOX_SEVERITY_ENUM.drop(connection, checkfirst=True)
        SEVERITY_ENUM.drop(connection, checkfirst=True)
