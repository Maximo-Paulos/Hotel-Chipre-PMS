"""Add tenant-scoped custom hotel roles and custom visibility-window codes."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_custom_hotel_roles"
down_revision: Union[str, None] = "20260918_member_alias_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BUILTIN_ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")
_RLS_POLICY = "tenant_isolation_hotel_roles"


def _install_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "hotel_roles" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "hotel_roles" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{_RLS_POLICY}" ON "hotel_roles"')
    op.execute(
        f'''CREATE POLICY "{_RLS_POLICY}" ON "hotel_roles"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "{_RLS_POLICY}" ON "hotel_roles"')
    op.execute('ALTER TABLE "hotel_roles" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "hotel_roles" DISABLE ROW LEVEL SECURITY')


def _assert_downgrade_lossless(bind) -> None:
    """Refuse rollback while custom role state cannot be represented by built-ins."""
    if bind.dialect.name == "postgresql":
        try:
            # FORCE ROW LEVEL SECURITY on tenant tables must not turn a partial
            # view into a false zero-count during this destructive-schema check.
            # PostgreSQL raises if this role cannot inspect every row.
            bind.execute(sa.text("SET LOCAL row_security = off"))
        except Exception as exc:
            raise RuntimeError(
                "Downgrade cancelado: no se pudo verificar la visibilidad completa "
                "de los datos por RLS; no se realizaron cambios. Ejecutá la "
                "migración con un rol que pueda inspeccionar todos los tenants."
            ) from exc

    checks = (
        ("hotel_roles", "code", True),
        ("hotel_memberships", "role", False),
        ("staff_invitations", "role", False),
        ("hotel_permission_overrides", "role", False),
        ("hotel_role_visibility_window", "role", False),
        ("role_permission_defaults", "role", False),
    )
    counts: dict[str, int] = {}
    try:
        for table_name, role_column, count_all in checks:
            table = sa.table(
                table_name,
                sa.column(role_column, sa.String(50)),
            )
            query = sa.select(sa.func.count()).select_from(table)
            if not count_all:
                query = query.where(table.c[role_column].not_in(_BUILTIN_ROLES))
            counts[table_name] = int(bind.execute(query).scalar_one())
    except Exception as exc:
        raise RuntimeError(
            "Downgrade cancelado: no se pudo comprobar si hay datos de roles "
            "custom no representables; no se realizaron cambios. Verificá permisos "
            "de lectura global y reintentá."
        ) from exc

    blocking = {name: count for name, count in counts.items() if count}
    if blocking:
        details = ", ".join(f"{name}={count}" for name, count in blocking.items())
        raise RuntimeError(
            "Downgrade cancelado: hay roles custom o referencias que no pueden "
            f"representarse sin pérdida ({details}). No se realizaron cambios. "
            "Exportá o migrá esos datos de forma explícita y lossless antes de reintentar."
        )


def upgrade() -> None:
    op.create_table(
        "hotel_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_key", sa.String(length=240), nullable=False),
        sa.Column("base_role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "base_role IN ('manager', 'receptionist', 'housekeeping')",
            name="ck_hotel_roles_base_role",
        ),
        sa.CheckConstraint(
            "length(code) <= 20 AND substr(code, 1, 3) = 'cr_'",
            name="ck_hotel_roles_custom_code",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_hotel_roles_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_hotel_roles_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_hotel_roles_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "code", name="uq_hotel_roles_hotel_code"),
        sa.UniqueConstraint("hotel_id", "name_key", name="uq_hotel_roles_hotel_name_key"),
    )
    op.create_index("ix_hotel_roles_hotel_id", "hotel_roles", ["hotel_id"])
    op.create_index("ix_hotel_roles_hotel_active", "hotel_roles", ["hotel_id", "is_active"])
    _install_rls()

    with op.batch_alter_table("hotel_role_visibility_window", recreate="auto") as batch_op:
        batch_op.drop_constraint("ck_hotel_role_visibility_window_role", type_="check")


def downgrade() -> None:
    bind = op.get_bind()
    _assert_downgrade_lossless(bind)
    _remove_rls()
    op.drop_table("hotel_roles")
    with op.batch_alter_table("hotel_role_visibility_window", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            "ck_hotel_role_visibility_window_role",
            "role IN ('owner', 'co_owner', 'manager', 'receptionist', 'housekeeping')",
        )
