"""Prevent hotel deletion from cascading into audit_logs.

Replaces the audit_logs.hotel_id foreign key's destructive CASCADE action with
RESTRICT so deleting a hotel cannot silently destroy its audit evidence.

Revision ID: 7b14658560e1
Revises: 20260818_notifications
Create Date: 2026-08-20 11:37:52.092491
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7b14658560e1'
down_revision: Union[str, None] = '20260818_notifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FK_NAME = "fk_audit_logs_hotel_id_hotel_configuration"
_SQLITE_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _hotel_fk(inspector: sa.Inspector) -> dict | None:
    for foreign_key in inspector.get_foreign_keys("audit_logs"):
        if (
            foreign_key.get("constrained_columns") == ["hotel_id"]
            and foreign_key.get("referred_table") == "hotel_configuration"
            and foreign_key.get("referred_columns") == ["id"]
        ):
            return foreign_key
    return None


def _replace_postgresql_fk(ondelete: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_key = _hotel_fk(inspector)

    if foreign_key is None:
        op.create_foreign_key(
            _FK_NAME,
            "audit_logs",
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
            ondelete=ondelete,
        )
        return

    current_ondelete = (foreign_key.get("options") or {}).get("ondelete")
    if current_ondelete and current_ondelete.upper() == ondelete:
        return

    constraint_name = foreign_key.get("name")
    if not constraint_name:
        raise RuntimeError(
            "audit_logs.hotel_id FK has no name on PostgreSQL; cannot replace it safely"
        )

    op.drop_constraint(constraint_name, "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "audit_logs",
        "hotel_configuration",
        ["hotel_id"],
        ["id"],
        ondelete=ondelete,
    )


def _replace_sqlite_fk(ondelete: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_key = _hotel_fk(inspector)

    with op.batch_alter_table(
        "audit_logs",
        recreate="always",
        naming_convention=_SQLITE_NAMING_CONVENTION,
    ) as batch_op:
        if foreign_key is not None:
            # SQLite reflects the historical inline FK without a name. The
            # naming convention gives that constraint a stable name inside
            # batch mode so it can be replaced safely.
            batch_op.drop_constraint(foreign_key.get("name") or _FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
            ondelete=ondelete,
        )


def _replace_fk(ondelete: str) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("audit_logs"):
        return
    if bind.dialect.name == "sqlite":
        _replace_sqlite_fk(ondelete)
    else:
        _replace_postgresql_fk(ondelete)


def upgrade() -> None:
    _replace_fk("RESTRICT")


def downgrade() -> None:
    _replace_fk("CASCADE")
