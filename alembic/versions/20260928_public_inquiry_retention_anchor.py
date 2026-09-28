"""Backfill the public inquiry retention clock and update the purge function.

Revision ID: 20260928_public_inquiry_retention_anchor
Revises: 20260928_public_inquiry_updated_at
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260928_public_inquiry_retention_anchor"
down_revision: Union[str, None] = "20260928_public_inquiry_updated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCTION = "hotel_chipre_private.purge_public_form_data()"


def _install_purge_function(inquiry_anchor: str) -> None:
    if inquiry_anchor not in {"created_at", "updated_at"}:
        raise ValueError("Unsupported public inquiry retention anchor")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION}
        RETURNS void
        LANGUAGE plpgsql
        SET search_path = pg_catalog
        AS $function$
        DECLARE
            deleted_inquiries bigint;
            deleted_marketing_leads bigint;
            deleted_rate_limit_events bigint;
            now_utc timestamptz;
            utc_now timestamp without time zone;
        BEGIN
            now_utc := pg_catalog.clock_timestamp();
            utc_now := pg_catalog.timezone('UTC', now_utc);

            -- Use the same lock order as hold placement so a legal hold and
            -- the scheduled purge serialize instead of racing one another.
            LOCK TABLE public.privacy_retention_holds IN SHARE MODE;

            DELETE FROM public.public_inquiries AS inquiry
            WHERE inquiry.{inquiry_anchor} < utc_now - INTERVAL '90 days'
              AND NOT EXISTS (
                  SELECT 1 FROM public.privacy_retention_holds AS hold
                  WHERE hold.resource_type = 'public_inquiry'
                    AND hold.record_id = inquiry.id
                    AND hold.released_at IS NULL
                    AND (hold.hold_until IS NULL OR hold.hold_until > now_utc)
              );
            GET DIAGNOSTICS deleted_inquiries = ROW_COUNT;

            DELETE FROM public.marketing_leads AS lead
            WHERE lead.updated_at < now_utc - INTERVAL '90 days'
              AND NOT EXISTS (
                  SELECT 1 FROM public.privacy_retention_holds AS hold
                  WHERE hold.resource_type = 'marketing_lead'
                    AND hold.record_id = lead.id
                    AND hold.released_at IS NULL
                    AND (hold.hold_until IS NULL OR hold.hold_until > now_utc)
              );
            GET DIAGNOSTICS deleted_marketing_leads = ROW_COUNT;

            DELETE FROM public.rate_limit_events
            WHERE scope IN (
                'marketing_lead',
                'marketing_lead_global',
                'public_inquiry_source',
                'public_inquiry_email',
                'public_inquiry_global'
            )
              AND created_at < utc_now - INTERVAL '15 minutes';
            GET DIAGNOSTICS deleted_rate_limit_events = ROW_COUNT;

            RAISE LOG
                'public form retention completed deleted_inquiries=% deleted_marketing_leads=% deleted_rate_limit_events=%',
                deleted_inquiries,
                deleted_marketing_leads,
                deleted_rate_limit_events;
        END;
        $function$
        """
    )
    op.execute(f"REVOKE ALL PRIVILEGES ON FUNCTION {_FUNCTION} FROM PUBLIC")
    op.execute(
        """
        DO $$
        DECLARE target_role text;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON FUNCTION hotel_chipre_private.purge_public_form_data() FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        return

    table = "public.public_inquiries" if dialect == "postgresql" else "public_inquiries"
    op.execute(
        sa.text(
            f"UPDATE {table} SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
    )

    if dialect == "sqlite":
        with op.batch_alter_table("public_inquiries") as batch_op:
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=False),
                nullable=False,
            )
    else:
        op.alter_column(
            "public_inquiries",
            "updated_at",
            schema="public",
            existing_type=sa.DateTime(timezone=False),
            nullable=False,
        )
        _install_purge_function("updated_at")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # Keep historical hold records auditable. The next schema downgrade
        # removes this table, so fail closed until the operator explicitly
        # exports/resolves every record instead of silently discarding it.
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM public.privacy_retention_holds) THEN
                    RAISE EXCEPTION
                        'Cannot downgrade privacy retention while legal hold audit records exist';
                END IF;
            END $$
            """
        )
        # Restore the prior clock while retaining legal-hold exclusions.
        # The following schema downgrade removes updated_at only afterward.
        _install_purge_function("created_at")
