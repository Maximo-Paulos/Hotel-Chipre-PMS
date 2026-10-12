"""Notify active PostgreSQL listeners when durable domain events commit.

Revision ID: 20261009_domain_event_notify
Revises: 20261005_outbox_recovery_cursor
Create Date: 2026-10-09
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261009_domain_event_notify"
down_revision: Union[str, None] = "20261005_outbox_recovery_cursor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.notify_domain_event_outbox_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
            PERFORM pg_catalog.pg_notify(
                'hotel_pms_domain_events',
                json_build_object(
                    'id', NEW.id,
                    'event_id', NEW.event_id::text,
                    'hotel_id', NEW.hotel_id,
                    'domain', NEW.domain,
                    'event_type', NEW.event_type,
                    'schema_version', NEW.schema_version,
                    'stream_cursor', COALESCE(NEW.stream_cursor, NEW.id),
                    'revision', NEW.revision,
                    'occurred_at', NEW.occurred_at,
                    'origin_key', NEW.origin_key
                )::text
            );
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_domain_event_outbox_notify
        ON public.domain_event_outbox
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_domain_event_outbox_notify
        AFTER INSERT ON public.domain_event_outbox
        FOR EACH ROW
        EXECUTE FUNCTION public.notify_domain_event_outbox_insert()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_domain_event_outbox_notify
        ON public.domain_event_outbox
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.notify_domain_event_outbox_insert()")
