"""Delete public form data after 90 days using Supabase Postgres Cron.

Revision ID: 20260925_public_inquiry_retention
Revises: 20260828_public_inquiries
"""
import logging
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "20260925_public_inquiry_retention"
down_revision: Union[str, None] = "20260828_public_inquiries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_JOB_NAME = "hotel-chipre-public-form-retention"
_FUNCTION = "hotel_chipre_private.purge_public_form_data()"
LOGGER = logging.getLogger(__name__)
_NON_PRODUCTION_ENVS = {"development", "test", "qa", "preview"}


def _pg_cron_migration_enabled(available: bool, runtime_env: str) -> bool:
    if available:
        return True
    normalized_env = runtime_env.strip().lower()
    if normalized_env in _NON_PRODUCTION_ENVS:
        LOGGER.warning("pg_cron is unavailable; skipping public-form retention in %s", normalized_env)
        return False
    raise RuntimeError("pg_cron is required to enforce public-form retention in production")


def _secure_marketing_leads() -> None:
    """Keep early-access lead data behind the trusted application database role."""
    op.execute("ALTER TABLE public.marketing_leads ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.marketing_leads FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON SEQUENCE public.marketing_leads_id_seq FROM PUBLIC")
    op.execute(
        """
        DO $$
        DECLARE target_role text;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.marketing_leads FROM %I',
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON SEQUENCE public.marketing_leads_id_seq FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$
        """
    )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    cron_enabled = True
    # Local/preview PostgreSQL installations may not package pg_cron. These
    # environments contain synthetic data and may continue without the job;
    # the production deployment must fail closed if its retention guarantee
    # cannot be installed.
    context = op.get_context()
    if not context.as_sql:
        bind = op.get_bind()
        available = bind.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_available_extensions WHERE name = 'pg_cron')")
        ).scalar()
        # An unset environment is not proof that the target is non-production.
        # Require an explicit known non-production value before skipping the
        # retention job when pg_cron is unavailable.
        runtime_env = os.getenv("APP_ENV", "").strip().lower()
        cron_enabled = _pg_cron_migration_enabled(bool(available), runtime_env)

    # Table access hardening is independent of the optional non-production
    # scheduler and must apply even when pg_cron is unavailable.
    _secure_marketing_leads()
    if not cron_enabled:
        return

    # pg_cron runs inside the existing Supabase Postgres instance, so this
    # does not add a Render service or a paid scheduler. Fail the deployment
    # migration if the extension is unavailable instead of silently leaving
    # personal data without its approved deletion schedule.
    # Supabase's supported installation places pg_cron in pg_catalog and
    # grants the database owner access to the scheduler schema/tables.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog")
    op.execute("GRANT USAGE ON SCHEMA cron TO postgres")
    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cron TO postgres")
    op.execute("CREATE SCHEMA IF NOT EXISTS hotel_chipre_private")
    op.execute("REVOKE ALL PRIVILEGES ON SCHEMA hotel_chipre_private FROM PUBLIC")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION hotel_chipre_private.purge_public_form_data()
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

            DELETE FROM public.public_inquiries
            WHERE created_at < utc_now - INTERVAL '90 days';
            GET DIAGNOSTICS deleted_inquiries = ROW_COUNT;

            DELETE FROM public.marketing_leads
            WHERE updated_at < now_utc - INTERVAL '90 days';
            GET DIAGNOSTICS deleted_marketing_leads = ROW_COUNT;

            DELETE FROM public.rate_limit_events
            WHERE scope IN (
                'marketing_lead',
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
                        'REVOKE ALL PRIVILEGES ON SCHEMA hotel_chipre_private FROM %I',
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON FUNCTION hotel_chipre_private.purge_public_form_data() FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE existing_job record;
        BEGIN
            IF pg_catalog.to_regclass('cron.job') IS NOT NULL THEN
                FOR existing_job IN
                    SELECT jobid FROM cron.job WHERE jobname = '{_JOB_NAME}'
                LOOP
                    PERFORM cron.unschedule(existing_job.jobid);
                END LOOP;
            END IF;
        END $$
        """
    )
    op.execute(
        f"""
        SELECT cron.schedule(
            '{_JOB_NAME}',
            '0 4 * * *',
            'SELECT hotel_chipre_private.purge_public_form_data()'
        )
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        f"""
        DO $$
        DECLARE existing_job record;
        BEGIN
            IF pg_catalog.to_regclass('cron.job') IS NOT NULL THEN
                FOR existing_job IN
                    SELECT jobid FROM cron.job WHERE jobname = '{_JOB_NAME}'
                LOOP
                    PERFORM cron.unschedule(existing_job.jobid);
                END LOOP;
            END IF;
        END $$
        """
    )
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION}")
    op.execute("DROP SCHEMA IF EXISTS hotel_chipre_private")
    # Deliberately keep marketing_leads access restricted after rollback; a
    # downgrade must not silently re-expose contact data to public API roles.
