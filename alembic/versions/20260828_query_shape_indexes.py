"""Add query-shape indexes and remove redundant model drift.

The ORM is the primary performance issue, but these tenant-leading indexes
support the predicates used by the reshaped hot paths. Existing indexes are
inspected by name and column order so this remains safe for installations that
created part of the schema out of band.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_query_shape_indexes"
down_revision: Union[str, None] = "20260828_retire_category_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_map(table_name: str) -> dict[str, dict]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return {}
    return {
        index["name"]: index
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def _ensure_index(table_name: str, name: str, columns: Sequence[str]) -> None:
    indexes = _index_map(table_name)
    existing = indexes.get(name)
    wanted = list(columns)
    if existing is not None:
        if existing.get("column_names") == wanted:
            return
        op.drop_index(name, table_name=table_name)
    op.create_index(name, table_name, wanted, unique=False)


def _drop_index_if_present(table_name: str, name: str) -> None:
    if name in _index_map(table_name):
        op.drop_index(name, table_name=table_name)


def upgrade() -> None:
    _ensure_index(
        "rooms",
        "ix_room_hotel_category",
        ("hotel_id", "category_id"),
    )
    _ensure_index(
        "reservations",
        "ix_reservation_hotel_deleted_at",
        ("hotel_id", "deleted_at"),
    )

    # The old index name is retained for compatibility with existing queries,
    # but its tenant key must lead to avoid spanning hotels.
    _ensure_index(
        "hotel_audit_events",
        "ix_hotel_audit_events_entity",
        ("hotel_id", "entity_type", "entity_id"),
    )

    # Keep the column-level/model-generated indexes and remove only the
    # duplicate declarations requested by the model contract.
    _drop_index_if_present("guests", "ix_guest_hotel_id")
    _drop_index_if_present("daily_rates", "ix_daily_rate_hotel_cat_date")
    _drop_index_if_present("reservations", "ix_reservations_hotel_id")


def downgrade() -> None:
    _drop_index_if_present("rooms", "ix_room_hotel_category")
    _drop_index_if_present("reservations", "ix_reservation_hotel_deleted_at")

    # Restore the previous cross-tenant audit index shape on downgrade.
    _drop_index_if_present("hotel_audit_events", "ix_hotel_audit_events_entity")
    _ensure_index(
        "hotel_audit_events",
        "ix_hotel_audit_events_entity",
        ("entity_type", "entity_id"),
    )
    _ensure_index("guests", "ix_guest_hotel_id", ("hotel_id",))
    _ensure_index(
        "daily_rates",
        "ix_daily_rate_hotel_cat_date",
        ("hotel_id", "category_id", "date"),
    )
    _ensure_index("reservations", "ix_reservations_hotel_id", ("hotel_id",))
