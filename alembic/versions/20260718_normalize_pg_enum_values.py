"""repair: normalize PostgreSQL enum labels used by OTA and allocation models

Revision ID: 20260718_normalize_pg_enums
Revises: 20260626_repair_reservation_unique_constraint
Create Date: 2026-07-18

The original OTA/allocation foundation migration created PostgreSQL enum labels
from the Python member names (for example ``PENDING``).  The SQLAlchemy models
persist the enum *values* instead (for example ``pending``).  PostgreSQL then
rejects legitimate model defaults and the runtime schema self-heal emits an
error on every boot.

``ALTER TYPE ... RENAME VALUE`` preserves every stored value and is safe for
existing rows.  Each rename is guarded so upgrading a database that already
has lower-case labels is a no-op.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260718_normalize_pg_enums"
down_revision: Union[str, None] = "20260626_repair_reservation_unique_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept as plain strings so this migration remains independent from future model
# refactors.  Every type below was created with upper-case labels by
# dee1bd0660f6_ota_allocation_foundation.py, while the current models persist
# the lower-case enum values.
ENUM_VALUE_RENAMES: dict[str, tuple[tuple[str, str], ...]] = {
    "ota_connection_status_enum": (
        ("PENDING", "pending"),
        ("HEALTHY", "healthy"),
        ("DEGRADED", "degraded"),
        ("ERROR", "error"),
        ("REVOKED", "revoked"),
    ),
    "llm_policy_suggestion_status_enum": (
        ("DRAFT", "draft"),
        ("REVIEWED", "reviewed"),
        ("ACCEPTED", "accepted"),
        ("REJECTED", "rejected"),
        ("SUPERSEDED", "superseded"),
    ),
    "ota_sync_job_status_enum": (
        ("PENDING", "pending"),
        ("RUNNING", "running"),
        ("SUCCEEDED", "succeeded"),
        ("FAILED", "failed"),
        ("RETRYING", "retrying"),
        ("CANCELLED", "cancelled"),
    ),
    "allocation_run_status_enum": (
        ("PENDING", "pending"),
        ("RUNNING", "running"),
        ("SUCCEEDED", "succeeded"),
        ("FAILED", "failed"),
        ("PARTIAL", "partial"),
    ),
    "allocation_assignment_status_enum": (
        ("PROPOSED", "proposed"),
        ("APPLIED", "applied"),
        ("LOCKED", "locked"),
        ("REJECTED", "rejected"),
        ("MANUAL_REVIEW", "manual_review"),
    ),
    "ota_reservation_lifecycle_enum": (
        ("NEW", "new"),
        ("CONFIRMED", "confirmed"),
        ("MODIFIED", "modified"),
        ("CANCEL_REQUESTED", "cancel_requested"),
        ("CANCELLED", "cancelled"),
        ("HOLD", "hold"),
        ("EXPIRED", "expired"),
        ("MANUAL_RESOLUTION_REQUIRED", "manual_resolution_required"),
    ),
    "room_move_type_enum": (
        ("AUTO_ASSIGNMENT", "auto_assignment"),
        ("MANUAL_MOVE", "manual_move"),
        ("UPGRADE", "upgrade"),
        ("DOWNGRADE", "downgrade"),
        ("OVERBOOKING_RESOLUTION", "overbooking_resolution"),
        ("MAINTENANCE_RELOCATION", "maintenance_relocation"),
    ),
    "reservation_adjustment_kind_enum": (
        ("UPGRADE", "upgrade"),
        ("DOWNGRADE", "downgrade"),
        ("DATE_CHANGE", "date_change"),
        ("OTA_CANCEL_AND_REBOOK", "ota_cancel_and_rebook"),
        ("MANUAL_RATE_OVERRIDE", "manual_rate_override"),
        ("REFUND", "refund"),
        ("OTHER", "other"),
    ),
    "reservation_adjustment_status_enum": (
        ("DRAFT", "draft"),
        ("PENDING", "pending"),
        ("APPLIED", "applied"),
        ("FAILED", "failed"),
        ("CANCELLED", "cancelled"),
    ),
    "billing_adjustment_type_enum": (
        ("CHARGE", "charge"),
        ("CREDIT", "credit"),
        ("REFUND", "refund"),
        ("COMMISSION", "commission"),
        ("TAX_CORRECTION", "tax_correction"),
        ("FX_CORRECTION", "fx_correction"),
    ),
}


def _rename_enum_labels(renames: dict[str, tuple[tuple[str, str], ...]]) -> None:
    """Rename present PostgreSQL labels, preserving data and idempotency."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for type_name, value_pairs in renames.items():
        for old_value, new_value in value_pairs:
            # All identifiers and labels come from the static mapping above,
            # never user input.  The catalog guard makes reruns harmless.
            bind.execute(
                sa.text(
                    "DO $$\n"
                    "BEGIN\n"
                    "    IF EXISTS (\n"
                    "        SELECT 1\n"
                    "        FROM pg_type AS t\n"
                    "        JOIN pg_enum AS e ON e.enumtypid = t.oid\n"
                    f"        WHERE t.typname = '{type_name}' AND e.enumlabel = '{old_value}'\n"
                    "    ) THEN\n"
                    f"        ALTER TYPE \"{type_name}\" RENAME VALUE '{old_value}' TO '{new_value}';\n"
                    "    END IF;\n"
                    "END $$;"
                )
            )


def upgrade() -> None:
    _rename_enum_labels(ENUM_VALUE_RENAMES)


def downgrade() -> None:
    reverse_renames = {
        type_name: tuple((new_value, old_value) for old_value, new_value in value_pairs)
        for type_name, value_pairs in ENUM_VALUE_RENAMES.items()
    }
    _rename_enum_labels(reverse_renames)
