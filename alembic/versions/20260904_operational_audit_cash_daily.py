"""Operational audit fields, daily cash indexes, and audit read permission."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_operational_audit_cash_daily"
down_revision: Union[str, None] = "tech0140_job_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUDIT_PERMISSION = "operations:audit:view"


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns)


def _drop_index_if_present(name: str, table: str) -> None:
    if name in _indexes(table):
        op.drop_index(name, table_name=table)


def _seed_audit_permission(connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description) "
            "SELECT :code, :description WHERE NOT EXISTS "
            "(SELECT 1 FROM permissions WHERE code = :code)"
        ),
        {"code": AUDIT_PERMISSION, "description": "Read the integral operations audit"},
    )
    for role in ("owner", "co_owner", "manager", "receptionist", "housekeeping"):
        connection.execute(
            sa.text(
                "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
                "SELECT :role, :code, :allowed WHERE NOT EXISTS ("
                "SELECT 1 FROM role_permission_defaults WHERE role = :role AND permission_code = :code)"
            ),
            {"role": role, "code": AUDIT_PERMISSION, "allowed": role in {"owner", "co_owner"}},
        )

    # This is an intentional default expansion from the approved cash
    # dashboard contract. Hotel-level overrides remain untouched.
    connection.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = TRUE "
            "WHERE role = 'manager' AND permission_code = 'cash:view'"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns("room_move_events")
    for name, column in (
        ("origin_room_disposition", sa.String(length=20)),
        ("origin_room_disposition_note", sa.Text()),
        ("origin_room_status_before", sa.String(length=30)),
        ("origin_room_status_after", sa.String(length=30)),
    ):
        if name not in columns:
            op.add_column("room_move_events", sa.Column(name, column, nullable=True))

    _create_index_if_missing(
        "ix_room_move_events_hotel_occurred_at",
        "room_move_events",
        ["hotel_id", "occurred_at", "id"],
    )
    _create_index_if_missing(
        "ix_room_move_events_hotel_rooms",
        "room_move_events",
        ["hotel_id", "from_room_id", "to_room_id"],
    )
    _create_index_if_missing(
        "ix_transactions_hotel_processed_status_method",
        "transactions",
        ["hotel_id", "processed_at", "status", "payment_method"],
    )
    _create_index_if_missing(
        "ix_cash_movements_hotel_recorded_type_actor",
        "cash_movements",
        ["hotel_id", "recorded_at", "movement_type", "recorded_by_user_id"],
    )
    _create_index_if_missing(
        "ix_audit_logs_hotel_created_actor",
        "audit_logs",
        ["hotel_id", "created_at", "actor_user_id"],
    )
    _create_index_if_missing(
        "ix_reservation_status_history_hotel_changed_actor",
        "reservation_status_history",
        ["hotel_id", "changed_at", "changed_by_user_id"],
    )
    _seed_audit_permission(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _drop_index_if_present("ix_reservation_status_history_hotel_changed_actor", "reservation_status_history")
    _drop_index_if_present("ix_audit_logs_hotel_created_actor", "audit_logs")
    _drop_index_if_present("ix_cash_movements_hotel_recorded_type_actor", "cash_movements")
    _drop_index_if_present("ix_transactions_hotel_processed_status_method", "transactions")
    _drop_index_if_present("ix_room_move_events_hotel_rooms", "room_move_events")
    _drop_index_if_present("ix_room_move_events_hotel_occurred_at", "room_move_events")
    for name in (
        "origin_room_status_after",
        "origin_room_status_before",
        "origin_room_disposition_note",
        "origin_room_disposition",
    ):
        if name in _columns("room_move_events"):
            op.drop_column("room_move_events", name)

    bind.execute(
        sa.text(
            "DELETE FROM role_permission_defaults WHERE permission_code = :code"
        ),
        {"code": AUDIT_PERMISSION},
    )
    bind.execute(
        sa.text(
            "DELETE FROM permissions WHERE code = :code AND NOT EXISTS ("
            "SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM user_permission_overrides WHERE permission_code = :code)"
        ),
        {"code": AUDIT_PERMISSION},
    )
    bind.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = FALSE "
            "WHERE role = 'manager' AND permission_code = 'cash:view'"
        )
    )
