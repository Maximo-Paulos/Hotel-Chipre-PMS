"""Align room-movement enum storage with the runtime enum values.

The original allocation foundation migration created ``room_move_type_enum``
from SQLAlchemy enum member names (``MANUAL_MOVE``), while the model and
service persist enum values (``manual_move``).  This made manual room moves
fail on a freshly migrated SQLite or PostgreSQL database.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "20260724_room_move_enum_values"
down_revision: Union[str, None] = "20260724_extended_tenant_composite_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VALUES = (
    "auto_assignment",
    "manual_move",
    "upgrade",
    "downgrade",
    "overbooking_resolution",
    "maintenance_relocation",
)


def _constraint(values: tuple[str, ...]) -> str:
    return "move_type IN ({})".format(", ".join(repr(value) for value in values))


def _repair_sqlite(*, restore_uppercase: bool = False) -> None:
    target_values = tuple(value.upper() for value in _VALUES) if restore_uppercase else _VALUES
    op.execute("UPDATE room_move_events SET move_type = lower(move_type)")
    if restore_uppercase:
        op.execute("UPDATE room_move_events SET move_type = upper(move_type)")

    with op.batch_alter_table("room_move_events", recreate="always") as batch:
        batch.drop_constraint("room_move_type_enum", type_="check")
        batch.create_check_constraint("room_move_type_enum", _constraint(target_values))


def _rename_postgres_values(*, restore_uppercase: bool = False) -> None:
    connection = op.get_bind()
    current = {
        row[0]
        for row in connection.execute(
            text(
                "SELECT e.enumlabel "
                "FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'room_move_type_enum'"
            )
        )
    }
    for value in _VALUES:
        source = value if restore_uppercase else value.upper()
        target = value.upper() if restore_uppercase else value
        if source in current and target not in current:
            op.execute(f'ALTER TYPE "room_move_type_enum" RENAME VALUE \'{source}\' TO \'{target}\'')
            current.remove(source)
            current.add(target)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _repair_sqlite()
    elif dialect == "postgresql":
        _rename_postgres_values()


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _repair_sqlite(restore_uppercase=True)
    elif dialect == "postgresql":
        _rename_postgres_values(restore_uppercase=True)
