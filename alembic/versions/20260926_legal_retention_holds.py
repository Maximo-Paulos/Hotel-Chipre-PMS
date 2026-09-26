"""Honor auditable legal holds in public-form retention.

Revision ID: 20260926_legal_retention_holds
Revises: 20260925_public_inquiry_retention
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa


revision: str = "20260926_legal_retention_holds"
down_revision: Union[str, None] = "20260925_public_inquiry_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_NAME = "hotel-chipre-public-form-retention"
_FUNCTION = "hotel_chipre_private.purge_public_form_data()"
_NON_PRODUCTION_ENVS = {"development", "test", "qa", "preview"}


def _cron_is_required() -> bool:
    return os.getenv("APP_ENV", "").strip().lower() not in _NON_PRODUCTION_ENVS


def _create_and_secure_retention_holds() -> None:
    op.execute(
        """
        CREATE TABLE public.privacy_retention_holds (
            id SERIAL PRIMARY KEY,
            resource_type VARCHAR(40) NOT NULL,
            record_id INTEGER NOT NULL,
            reason_code VARCHAR(40) NOT NULL,
            case_reference VARCHAR(120) NOT NULL,
            hold_until TIMESTAMPTZ NULL,
            placed_by_user_id INTEGER NULL REFERENCES public.users(id) ON DELETE SET NULL,
            placed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            released_at TIMESTAMPTZ NULL,
            released_by_user_id INTEGER NULL REFERENCES public.users(id) ON DELETE SET NULL,
            release_reason_code VARCHAR(40) NULL,
            release_reference VARCHAR(120) NULL,
            CONSTRAINT uq_privacy_retention_holds_resource_record UNIQUE (resource_type, record_id),
            CONSTRAINT ck_privacy_retention_holds_resource_type
                CHECK (resource_type IN ('marketing_lead', 'public_inquiry')),
            CONSTRAINT ck_privacy_retention_holds_record_id_positive CHECK (record_id > 0)
        )
        """
    )
    op.execute("CREATE INDEX ix_privacy_retention_holds_lookup ON public.privacy_retention_holds (resource_type, record_id, released_at)")
    op.execute("ALTER TABLE public.privacy_retention_holds ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.privacy_retention_holds FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON SEQUENCE public.privacy_retention_holds_id_seq FROM PUBLIC")
    op.execute(
        """
        DO $$
        DECLARE target_role text;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE public.privacy_retention_holds FROM %I',
                        target_role
                    );
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON SEQUENCE public.privacy_retention_holds_id_seq FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$
        """
    )


def _upgrade_sqlite() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("privacy_retention_holds"):
        op.create_table(
            "privacy_retention_holds",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("resource_type", sa.String(length=40), nullable=False),
            sa.Column("record_id", sa.Integer(), nullable=False),
            sa.Column("reason_code", sa.String(length=40), nullable=False),
            sa.Column("case_reference", sa.String(length=120), nullable=False),
            sa.Column("hold_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("placed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("released_by_user_id", sa.Integer(), nullable=True),
            sa.Column("release_reason_code", sa.String(length=40), nullable=True),
            sa.Column("release_reference", sa.String(length=120), nullable=True),
            sa.ForeignKeyConstraint(["placed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("resource_type", "record_id", name="uq_privacy_retention_holds_resource_record"),
            sa.CheckConstraint(
                "resource_type IN ('marketing_lead', 'public_inquiry')",
                name="ck_privacy_retention_holds_resource_type",
            ),
            sa.CheckConstraint("record_id > 0", name="ck_privacy_retention_holds_record_id_positive"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("privacy_retention_holds"):
        indexes = {index["name"] for index in inspector.get_indexes("privacy_retention_holds")}
        if "ix_privacy_retention_holds_lookup" not in indexes:
            op.create_index(
                "ix_privacy_retention_holds_lookup",
                "privacy_retention_holds",
                ["resource_type", "record_id", "released_at"],
            )

    if inspector.has_table("marketing_leads"):
        indexes = {index["name"] for index in inspector.get_indexes("marketing_leads")}
        if "ix_marketing_leads_updated_at" not in indexes:
            op.create_index("ix_marketing_leads_updated_at", "marketing_leads", ["updated_at"])


def _downgrade_sqlite() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("privacy_retention_holds"):
        op.drop_table("privacy_retention_holds")
    if inspector.has_table("marketing_leads"):
        indexes = {index["name"] for index in inspector.get_indexes("marketing_leads")}
        if "ix_marketing_leads_updated_at" in indexes:
            op.drop_index("ix_marketing_leads_updated_at", table_name="marketing_leads")


def _install_purge_function(*, honor_legal_holds: bool) -> None:
    lock_holds = "LOCK TABLE public.privacy_retention_holds IN SHARE MODE;" if honor_legal_holds else ""
    inquiry_hold = (
        """
        AND NOT EXISTS (
            SELECT 1 FROM public.privacy_retention_holds AS hold
            WHERE hold.resource_type = 'public_inquiry'
              AND hold.record_id = inquiry.id
              AND hold.released_at IS NULL
              AND (hold.hold_until IS NULL OR hold.hold_until > now_utc)
        )
        """
        if honor_legal_holds
        else ""
    )
    lead_hold = (
        """
        AND NOT EXISTS (
            SELECT 1 FROM public.privacy_retention_holds AS hold
            WHERE hold.resource_type = 'marketing_lead'
              AND hold.record_id = lead.id
              AND hold.released_at IS NULL
              AND (hold.hold_until IS NULL OR hold.hold_until > now_utc)
        )
        """
        if honor_legal_holds
        else ""
    )
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

            -- Hold writes lock this table before their target row. Taking the
            -- conflicting lock first serializes purge against hold placement.
            {lock_holds}

            DELETE FROM public.public_inquiries AS inquiry
            WHERE inquiry.created_at < utc_now - INTERVAL '90 days'
            {inquiry_hold};
            GET DIAGNOSTICS deleted_inquiries = ROW_COUNT;

            DELETE FROM public.marketing_leads AS lead
            WHERE lead.updated_at < now_utc - INTERVAL '90 days'
            {lead_hold};
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
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON SCHEMA hotel_chipre_private FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END $$
        """
    )


def _reschedule_purge_job(*, required: bool) -> None:
    required_sql = "TRUE" if required else "FALSE"
    op.execute(
        f"""
        DO $$
        DECLARE existing_job record;
        BEGIN
            IF pg_catalog.to_regclass('cron.job') IS NULL THEN
                IF {required_sql} THEN
                    RAISE EXCEPTION 'pg_cron is required to enforce public-form retention';
                END IF;
                RETURN;
            END IF;
            FOR existing_job IN
                SELECT jobid FROM cron.job WHERE jobname = '{_JOB_NAME}'
            LOOP
                PERFORM cron.unschedule(existing_job.jobid);
            END LOOP;
            PERFORM cron.schedule(
                '{_JOB_NAME}',
                '0 4 * * *',
                'SELECT hotel_chipre_private.purge_public_form_data()'
            );
        END $$
        """
    )


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _upgrade_sqlite()
        return
    if dialect != "postgresql":
        return

    _create_and_secure_retention_holds()
    op.execute("CREATE INDEX ix_marketing_leads_updated_at ON public.marketing_leads (updated_at)")
    op.execute("CREATE SCHEMA IF NOT EXISTS hotel_chipre_private")
    op.execute("REVOKE ALL PRIVILEGES ON SCHEMA hotel_chipre_private FROM PUBLIC")
    _install_purge_function(honor_legal_holds=True)
    _reschedule_purge_job(required=_cron_is_required())


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _downgrade_sqlite()
        return
    if dialect != "postgresql":
        return

    # Block concurrent hold placement while deciding whether rollback is safe.
    # A downgrade must never erase a currently effective legal exception.
    op.execute("LOCK TABLE public.privacy_retention_holds IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.privacy_retention_holds
                WHERE released_at IS NULL
                  AND (hold_until IS NULL OR hold_until > pg_catalog.clock_timestamp())
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade while effective privacy retention holds exist';
            END IF;
        END $$
        """
    )
    _install_purge_function(honor_legal_holds=False)
    _reschedule_purge_job(required=_cron_is_required())
    op.execute("DROP TABLE public.privacy_retention_holds")
    op.execute("DROP INDEX IF EXISTS public.ix_marketing_leads_updated_at")
