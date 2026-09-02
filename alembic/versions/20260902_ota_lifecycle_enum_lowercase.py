"""Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.

`OTAReservationLink.provider_state` is declared with
`values_callable=lambda enum_cls: [e.value for e in enum_cls]`, so SQLAlchemy
sends/expects lowercase labels ("new", "manual_resolution_required", ...).
The migration that originally created the native Postgres enum type
(dee1bd0660f6_ota_allocation_foundation) instead used the Python enum
members' uppercase *names* as the literal values, so the live type only
recognizes 'NEW', 'MANUAL_RESOLUTION_REQUIRED', etc. Every query that filters
on this column by Python enum value (e.g. the operational pending-actions
dashboard widget) sends the lowercase form and Postgres rejects it outright
with psycopg2.errors.InvalidTextRepresentation -- the root cause of the
persistent 500 on GET /api/reservations/actions/pending.

Postgres: `ALTER TYPE ... RENAME VALUE` relabels in place, so existing rows
keep pointing at the same enum value (just spelled lowercase) with no
backfill needed.

SQLite has no native enum type -- `sa.Enum` renders as VARCHAR + a CHECK
constraint frozen with whatever literals the migration used at the time
(uppercase here, same drift as Postgres). Recreate the column with the
CHECK constraint the current model actually expects, and lowercase any
existing data first so the recreate's CHECK doesn't reject it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_ota_lifecycle_enum_lowercase"
down_revision: Union[str, None] = "20260901_payment_proof_object_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUM_NAME = "ota_reservation_lifecycle_enum"
_LABELS = [
    "NEW",
    "CONFIRMED",
    "MODIFIED",
    "CANCEL_REQUESTED",
    "CANCELLED",
    "HOLD",
    "EXPIRED",
    "MANUAL_RESOLUTION_REQUIRED",
]


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "sqlite":
        op.execute("UPDATE ota_reservation_links SET provider_state = lower(provider_state)")
        with op.batch_alter_table("ota_reservation_links", recreate="always") as batch:
            batch.drop_constraint(_ENUM_NAME, type_="check")
            batch.create_check_constraint(
                _ENUM_NAME,
                sa.column("provider_state").in_([label.lower() for label in _LABELS]),
            )
        return

    for label in _LABELS:
        op.execute(f"ALTER TYPE {_ENUM_NAME} RENAME VALUE '{label}' TO '{label.lower()}'")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "sqlite":
        op.execute("UPDATE ota_reservation_links SET provider_state = upper(provider_state)")
        with op.batch_alter_table("ota_reservation_links", recreate="always") as batch:
            batch.drop_constraint(_ENUM_NAME, type_="check")
            batch.create_check_constraint(_ENUM_NAME, sa.column("provider_state").in_(_LABELS))
        return

    for label in _LABELS:
        op.execute(f"ALTER TYPE {_ENUM_NAME} RENAME VALUE '{label.lower()}' TO '{label}'")
