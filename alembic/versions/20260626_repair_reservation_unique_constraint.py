"""repair: ensure uq_reservation_hotel_id_id exists before payment_links FK

Revision ID: 20260626_repair_reservation_unique_constraint
Revises: 20260625_public_api_rate_limit_config
Branch Labels: None
Depends On: None

The phase-6 payment-tables migration adds this constraint but on some deploys
the alembic_version row was written while the constraint was never applied
(partial rollback or prior error). This migration is idempotent: it adds the
constraint via CREATE UNIQUE INDEX IF NOT EXISTS so it is safe to run even
when the constraint already exists.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260626_repair_reservation_unique_constraint"
down_revision: Union[str, None] = "20260625_public_api_rate_limit_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Idempotent: no-op if constraint/index already exists
        bind.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_reservation_hotel_id_id "
            "ON reservations (hotel_id, id)"
        ))
    else:
        # SQLite path: skip if constraint already present
        inspector = sa.inspect(bind)
        existing = {
            uc["name"]
            for uc in inspector.get_unique_constraints("reservations")
        }
        if "uq_reservation_hotel_id_id" not in existing:
            with op.batch_alter_table("reservations", recreate="always") as batch_op:
                batch_op.create_unique_constraint(
                    "uq_reservation_hotel_id_id", ["hotel_id", "id"]
                )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS uq_reservation_hotel_id_id"
        ))
    else:
        with op.batch_alter_table("reservations", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_reservation_hotel_id_id", type_="unique")
