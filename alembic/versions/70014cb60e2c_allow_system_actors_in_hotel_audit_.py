"""Allow system actors in hotel audit events.

Revision ID: 70014cb60e2c
Revises: 20260820_user_sessions
Create Date: 2026-08-20 15:13:21.118115
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '70014cb60e2c'
down_revision: Union[str, None] = '20260820_user_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FK_NAME = "fk_hotel_audit_events_user_id_users"
_SQLITE_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _user_fk(inspector: sa.Inspector) -> dict | None:
    for foreign_key in inspector.get_foreign_keys("hotel_audit_events"):
        if (
            foreign_key.get("constrained_columns") == ["user_id"]
            and foreign_key.get("referred_table") == "users"
            and foreign_key.get("referred_columns") == ["id"]
        ):
            return foreign_key
    return None


def _replace_postgresql_fk(ondelete: str | None) -> None:
    bind = op.get_bind()
    foreign_key = _user_fk(sa.inspect(bind))

    if foreign_key is None:
        op.create_foreign_key(
            _FK_NAME,
            "hotel_audit_events",
            "users",
            ["user_id"],
            ["id"],
            ondelete=ondelete,
        )
        return

    current_ondelete = (foreign_key.get("options") or {}).get("ondelete")
    if (current_ondelete or "").upper() == (ondelete or "").upper():
        return

    constraint_name = foreign_key.get("name")
    if not constraint_name:
        raise RuntimeError(
            "hotel_audit_events.user_id FK has no name on PostgreSQL; "
            "cannot replace it safely"
        )

    op.drop_constraint(constraint_name, "hotel_audit_events", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "hotel_audit_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete=ondelete,
    )


def _replace_sqlite_fk(*, nullable: bool, ondelete: str | None) -> None:
    bind = op.get_bind()
    foreign_key = _user_fk(sa.inspect(bind))

    with op.batch_alter_table(
        "hotel_audit_events",
        recreate="always",
        naming_convention=_SQLITE_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            existing_nullable=not nullable,
            nullable=nullable,
        )
        if foreign_key is not None:
            batch_op.drop_constraint(
                foreign_key.get("name") or _FK_NAME,
                type_="foreignkey",
            )
        batch_op.create_foreign_key(
            _FK_NAME,
            "users",
            ["user_id"],
            ["id"],
            ondelete=ondelete,
        )


def _alter_user_column(nullable: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _replace_sqlite_fk(nullable=nullable, ondelete="SET NULL" if nullable else None)
        return

    op.alter_column(
        "hotel_audit_events",
        "user_id",
        existing_type=sa.Integer(),
        existing_nullable=not nullable,
        nullable=nullable,
    )
    _replace_postgresql_fk("SET NULL" if nullable else None)


def upgrade() -> None:
    _alter_user_column(nullable=True)


def downgrade() -> None:
    _alter_user_column(nullable=False)
