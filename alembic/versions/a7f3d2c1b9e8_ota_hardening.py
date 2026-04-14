"""ota hardening: hotel-scoped mappings and webhook credentials

Revision ID: a7f3d2c1b9e8
Revises: b7c1f0a8f9d2
Create Date: 2026-04-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = "a7f3d2c1b9e8"
down_revision: Union[str, None] = "b7c1f0a8f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "ota_webhook_credentials" not in table_names:
        op.create_table(
            "ota_webhook_credentials",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("webhook_secret_hash", sa.String(length=128), nullable=False),
            sa.Column("external_property_id", sa.String(length=120), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("hotel_id", "provider", name="uq_ota_webhook_credential_hotel_provider"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ota_webhook_credentials_hotel_id", "ota_webhook_credentials", ["hotel_id"], unique=False)

    if "ota_reservation_mappings" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("ota_reservation_mappings")}
        if "hotel_id" not in existing_columns:
            with op.batch_alter_table("ota_reservation_mappings") as batch_op:
                batch_op.add_column(sa.Column("hotel_id", sa.Integer(), nullable=True))

            op.execute(
                """
                UPDATE ota_reservation_mappings
                SET hotel_id = COALESCE(
                    (SELECT reservations.hotel_id
                     FROM reservations
                     WHERE reservations.id = ota_reservation_mappings.reservation_id),
                    (SELECT reservations.hotel_id
                     FROM reservations
                     WHERE reservations.external_id = ota_reservation_mappings.ota_reservation_id
                     LIMIT 1)
                )
                WHERE hotel_id IS NULL
                """
            )
            op.execute("DELETE FROM ota_reservation_mappings WHERE hotel_id IS NULL")

            with op.batch_alter_table("ota_reservation_mappings") as batch_op:
                batch_op.alter_column("hotel_id", existing_type=sa.Integer(), nullable=False)
                batch_op.create_foreign_key(
                    "fk_ota_reservation_mappings_hotel",
                    "hotel_configuration",
                    ["hotel_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch_op.create_unique_constraint(
                    "uq_ota_mapping_hotel_provider_reservation",
                    ["hotel_id", "ota_name", "ota_reservation_id"],
                )

            op.create_index("ix_ota_reservation_mappings_hotel_id", "ota_reservation_mappings", ["hotel_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "ota_reservation_mappings" in table_names:
        with op.batch_alter_table("ota_reservation_mappings") as batch_op:
            batch_op.drop_constraint("uq_ota_mapping_hotel_provider_reservation", type_="unique")
            batch_op.drop_constraint("fk_ota_reservation_mappings_hotel", type_="foreignkey")
        op.drop_index("ix_ota_reservation_mappings_hotel_id", table_name="ota_reservation_mappings")
        with op.batch_alter_table("ota_reservation_mappings") as batch_op:
            batch_op.drop_column("hotel_id")

    if "ota_webhook_credentials" in table_names:
        op.drop_index("ix_ota_webhook_credentials_hotel_id", table_name="ota_webhook_credentials")
        op.drop_table("ota_webhook_credentials")
