"""Align allocation enum storage with the model values.

The original allocation migration emitted SQLAlchemy enum member names
(`PENDING`, `RUNNING`, ...) while the runtime models deliberately persist the
lowercase enum values. This repair keeps fresh SQLite/preview databases and
already-migrated PostgreSQL databases on the same contract.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260724_allocation_enum_values"
down_revision: Union[str, None] = "20260724_payment_proofs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RUN_VALUES = ("pending", "running", "succeeded", "failed", "partial")
_ASSIGNMENT_VALUES = ("proposed", "applied", "locked", "rejected", "manual_review")


def _sqlite_rebuild_constraints(values: tuple[str, ...]) -> str:
    return "status IN ({})".format(", ".join(repr(value) for value in values))


def _repair_sqlite() -> None:
    op.execute("UPDATE allocation_runs SET status = lower(status)")
    op.execute("UPDATE allocation_assignments SET status = lower(status)")

    with op.batch_alter_table("allocation_runs", recreate="always") as batch:
        batch.drop_constraint("allocation_run_status_enum", type_="check")
        batch.create_check_constraint(
            "allocation_run_status_enum",
            _sqlite_rebuild_constraints(_RUN_VALUES),
        )

    with op.batch_alter_table("allocation_assignments", recreate="always") as batch:
        batch.drop_constraint("allocation_assignment_status_enum", type_="check")
        batch.create_check_constraint(
            "allocation_assignment_status_enum",
            _sqlite_rebuild_constraints(_ASSIGNMENT_VALUES),
        )


def _existing_enum_labels(bind, enum_name: str) -> set[str]:
    rows = bind.execute(
        sa.text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = :enum_name"
        ),
        {"enum_name": enum_name},
    )
    return {row[0] for row in rows}


def _rename_postgres_enum_values(
    enum_name: str,
    values: tuple[str, ...],
    *,
    restore_uppercase: bool = False,
) -> None:
    # Guarded because some production environments already have these enums
    # created directly from the current (already-lowercase) model values via
    # an old startup self-heal pass -- in that case the uppercase source
    # label this migration expects to rename from was never written, and
    # RENAME VALUE on a nonexistent label raises InvalidParameterValue.
    bind = op.get_bind()
    existing_labels = _existing_enum_labels(bind, enum_name)
    for value in values:
        current = value if restore_uppercase else value.upper()
        target = value.upper() if restore_uppercase else value
        if current in existing_labels and target not in existing_labels:
            op.execute(f'ALTER TYPE "{enum_name}" RENAME VALUE \'{current}\' TO \'{target}\'')


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _repair_sqlite()
    elif dialect == "postgresql":
        _rename_postgres_enum_values("allocation_run_status_enum", _RUN_VALUES)
        _rename_postgres_enum_values("allocation_assignment_status_enum", _ASSIGNMENT_VALUES)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("UPDATE allocation_runs SET status = upper(status)")
        op.execute("UPDATE allocation_assignments SET status = upper(status)")

        with op.batch_alter_table("allocation_runs", recreate="always") as batch:
            batch.drop_constraint("allocation_run_status_enum", type_="check")
            batch.create_check_constraint(
                "allocation_run_status_enum",
                _sqlite_rebuild_constraints(tuple(value.upper() for value in _RUN_VALUES)),
            )

        with op.batch_alter_table("allocation_assignments", recreate="always") as batch:
            batch.drop_constraint("allocation_assignment_status_enum", type_="check")
            batch.create_check_constraint(
                "allocation_assignment_status_enum",
                _sqlite_rebuild_constraints(tuple(value.upper() for value in _ASSIGNMENT_VALUES)),
            )
    elif dialect == "postgresql":
        _rename_postgres_enum_values("allocation_run_status_enum", _RUN_VALUES, restore_uppercase=True)
        _rename_postgres_enum_values(
            "allocation_assignment_status_enum", _ASSIGNMENT_VALUES, restore_uppercase=True
        )
