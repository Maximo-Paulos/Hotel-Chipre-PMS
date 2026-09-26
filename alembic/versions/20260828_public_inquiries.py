"""store public marketing inquiries and notification state

Revision ID: 20260828_public_inquiries
Revises: 20260924_action_stepup_single_use
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_public_inquiries"
down_revision: Union[str, None] = "20260924_action_stepup_single_use"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_status = sa.Enum(
        "not_configured",
        "sent",
        "failed",
        name="public_inquiry_notification_status",
        native_enum=True,
        create_constraint=True,
    )
    op.create_table(
        "public_inquiries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("company_name", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_path", sa.String(length=200), nullable=False),
        sa.Column("privacy_consent_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notification_status", notification_status, nullable=False),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("notification_error_type", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_inquiries_created_at", "public_inquiries", ["created_at"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE public.public_inquiries ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL PRIVILEGES ON TABLE public.public_inquiries FROM PUBLIC')
        op.execute('REVOKE ALL PRIVILEGES ON SEQUENCE public.public_inquiries_id_seq FROM PUBLIC')
        op.execute(
            """
            DO $$
            DECLARE target_role text;
            BEGIN
                FOREACH target_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role) THEN
                        EXECUTE format(
                            'REVOKE ALL PRIVILEGES ON TABLE public.public_inquiries FROM %I',
                            target_role
                        );
                        EXECUTE format(
                            'REVOKE ALL PRIVILEGES ON SEQUENCE public.public_inquiries_id_seq FROM %I',
                            target_role
                        );
                    END IF;
                END LOOP;
            END $$
            """
        )


def downgrade() -> None:
    op.drop_index("ix_public_inquiries_created_at", table_name="public_inquiries")
    op.drop_table("public_inquiries")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS public_inquiry_notification_status")
