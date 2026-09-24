"""Normalize the remaining PostgreSQL enum labels used by OTA models.

Revision ID: 20260924_pg_enum_values
Revises: 20260924_custom_hotel_roles
Create Date: 2026-09-24

The original OTA foundation stored Python enum member names in PostgreSQL,
while the current SQLAlchemy models persist each enum's lower-case value.
This forward migration renames only the five types not already repaired by
earlier mainline migrations. Existing rows are preserved in place.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_pg_enum_values"
down_revision: Union[str, None] = "20260924_custom_hotel_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
}


def _enum_labels(bind, type_name: str) -> tuple[str, set[str]]:
    rows = bind.execute(
        sa.text(
            "SELECT n.nspname, e.enumlabel "
            "FROM pg_catalog.pg_type AS t "
            "JOIN pg_catalog.pg_enum AS e ON e.enumtypid = t.oid "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = t.typnamespace "
            "WHERE n.nspname = current_schema() AND t.typname = :type_name"
        ),
        {"type_name": type_name},
    ).all()
    if not rows:
        raise RuntimeError(
            f"Enum PostgreSQL {type_name!r} no existe en el schema actual; "
            "se cancela la migración sin continuar."
        )
    schemas = {str(row[0]) for row in rows}
    if len(schemas) != 1:
        raise RuntimeError(f"Enum PostgreSQL {type_name!r} aparece en varios schemas actuales.")
    return schemas.pop(), {str(row[1]) for row in rows}


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _rename_enum_labels(renames: dict[str, tuple[tuple[str, str], ...]]) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for type_name, value_pairs in renames.items():
        schema_name, labels = _enum_labels(bind, type_name)
        qualified_type = f"{_quote_identifier(schema_name)}.{_quote_identifier(type_name)}"
        for old_value, new_value in value_pairs:
            if old_value in labels and new_value in labels:
                raise RuntimeError(
                    f"Enum {schema_name}.{type_name} contiene ambas etiquetas "
                    f"{old_value!r} y {new_value!r}; se requiere reparación manual."
                )
            if old_value in labels:
                # Identifiers and labels come only from this static mapping; no
                # user-provided SQL is interpolated here.
                bind.execute(
                    sa.text(
                        f"ALTER TYPE {qualified_type} RENAME VALUE "
                        f"'{old_value}' TO '{new_value}'"
                    )
                )
                labels.remove(old_value)
                labels.add(new_value)
            elif new_value not in labels:
                raise RuntimeError(
                    f"Enum {schema_name}.{type_name} no contiene ni "
                    f"{old_value!r} ni {new_value!r}; se cancela la migración."
                )


def upgrade() -> None:
    _rename_enum_labels(ENUM_VALUE_RENAMES)


def downgrade() -> None:
    reverse_renames = {
        type_name: tuple((new_value, old_value) for old_value, new_value in value_pairs)
        for type_name, value_pairs in ENUM_VALUE_RENAMES.items()
    }
    _rename_enum_labels(reverse_renames)
