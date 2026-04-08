"""add integration catalog

Revision ID: 9b0becb6c658
Revises: 20260407_subscription_tables
Create Date: 2026-04-07 15:18:13.198532
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '9b0becb6c658'
down_revision: Union[str, None] = '20260407_subscription_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_catalog",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("auth_type", sa.String(length=30), nullable=False),
        sa.Column("scopes", sa.String(length=500), nullable=True),
        sa.Column("doc_url", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", name="uq_integration_provider"),
    )

    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), sa.ForeignKey("integration_catalog.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, default="pending"),
        sa.Column("auth_payload", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("hotel_id", "integration_id", name="uq_connection_hotel_integration"),
    )

    op.create_table(
        "integration_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("integration_connections.id"), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # seed catalog defaults
    catalog_rows = [
        ("booking", "Booking.com", "api_key", "content,availability", "https://developers.booking.com/connectivity"),
        ("expedia", "Expedia", "signature", "content,availability", "https://developers.expediagroup.com/"),
        ("mercadopago", "MercadoPago", "oauth_code", "payments,offline_access", "https://www.mercadopago.com.ar/developers/en"),
        ("paypal", "PayPal", "oauth_code", "payments,openid,email,offline_access", "https://developer.paypal.com/docs/api/overview/"),
        ("gmail", "Gmail", "oauth_code", "gmail.send gmail.readonly", "https://developers.google.com/gmail/api"),
        ("whatsapp", "WhatsApp Business", "bearer_token", "messages", "https://developers.facebook.com/docs/whatsapp/"),
    ]
    op.bulk_insert(
        sa.table(
            "integration_catalog",
            sa.column("provider", sa.String()),
            sa.column("display_name", sa.String()),
            sa.column("auth_type", sa.String()),
            sa.column("scopes", sa.String()),
            sa.column("doc_url", sa.String()),
            sa.column("created_at", sa.DateTime()),
        ),
        [
            {
                "provider": p,
                "display_name": n,
                "auth_type": a,
                "scopes": s,
                "doc_url": u,
                "created_at": datetime.utcnow(),
            }
            for p, n, a, s, u in catalog_rows
        ],
    )


def downgrade() -> None:
    op.drop_table("integration_events")
    op.drop_table("integration_connections")
    op.drop_table("integration_catalog")
