"""expand RBAC catalog and add tenant-scoped user overrides

Revision ID: 20260813_rbac_overrides
Revises: 20260812_external_effects
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_rbac_overrides"
down_revision: Union[str, None] = "20260812_external_effects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS: dict[str, str] = {
    "guest:read": "Read guest profile data",
    "guest:update": "Update guest profiles",
    "guest:tags_manage": "Manage guest tags",
    "guest:prohibition_read": "Read lodging prohibition status",
    "guest:prohibition_manage": "Create and resolve lodging prohibitions",
    "reservation:read": "Read reservations",
    "reservation:update": "Update reservations",
    "reservation:cancel": "Cancel reservations",
    "reservation:move": "Move reservations between rooms",
    "reservation:prohibition_override": "Override a lodging prohibition with reason",
    "room:read": "Read rooms and operational state",
    "room:status_update": "Update room cleaning status",
    "room:block_create": "Create room blocks",
    "room:block_release": "Release room blocks",
    "checkout:perform": "Perform checkout",
    "checkout:force": "Force an exceptional checkout",
    "stock:read": "Read stock",
    "stock:movement": "Record stock movements",
    "stock:admin": "Manage stock catalog and locations",
    "laundry:read": "Read laundry operation",
    "laundry:movement": "Record linen movements",
    "laundry:vendor_manage": "Manage laundry vendors",
    "laundry:remito_manage": "Create and receive laundry remitos",
    "laundry:price_manage": "Manage vendor prices",
    "rates:read": "Read hotel rates",
    "rates:update": "Update hotel rates",
    "promotions:read": "Read promotions",
    "promotions:manage": "Manage promotions",
    "hotel_settings:read": "Read hotel settings",
    "hotel_settings:update": "Update operational hotel settings",
    "hotel_settings:property_manage": "Transfer or change property ownership",
    "hotel_settings:security_manage": "Manage security secrets and connections",
}

# One legacy decision may safely feed several narrower capabilities. The old
# row remains readable during the transition; canonical routes use the new row.
LEGACY_SPLITS: dict[str, tuple[str, ...]] = {
    "config:manage": ("hotel_settings:read", "hotel_settings:update"),
    "guest:view": ("guest:read",),
    "guest:edit": ("guest:update",),
    "guest:tags": ("guest:tags_manage",),
    "reservation:create": ("reservation:read", "reservation:update", "reservation:cancel"),
    "reservation:room_move": ("reservation:move",),
    "room:cleaning_status": ("room:status_update",),
    "room_block:create": ("room:read", "room:block_create"),
    "room_block:release": ("room:block_release",),
    "checkin:perform": ("checkout:perform",),
    "checkin:override_prohibido": ("reservation:prohibition_override",),
    "stock:operate": ("stock:read", "stock:movement", "stock:admin"),
    "laundry:manage_vendors": ("laundry:read", "laundry:vendor_manage", "laundry:price_manage"),
    "laundry:operate_remitos": ("laundry:read", "laundry:movement", "laundry:remito_manage"),
}

ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")


def _insert_permission_rows(connection) -> None:
    permission = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    existing = set(connection.execute(sa.text("SELECT code FROM permissions")).scalars())
    rows = [
        {"code": code, "description": description}
        for code, description in NEW_PERMISSIONS.items()
        if code not in existing
    ]
    if rows:
        op.bulk_insert(permission, rows)


def _upsert_default(connection, role: str, code: str, allowed: bool) -> None:
    existing = connection.execute(
        sa.text(
            "SELECT id FROM role_permission_defaults "
            "WHERE role = :role AND permission_code = :code"
        ),
        {"role": role, "code": code},
    ).scalar()
    if existing is None:
        connection.execute(
            sa.text(
                "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
                "VALUES (:role, :code, :allowed)"
            ),
            {"role": role, "code": code, "allowed": allowed},
        )


def _backfill_defaults(connection) -> None:
    for role in ROLES:
        for legacy, targets in LEGACY_SPLITS.items():
            allowed = connection.execute(
                sa.text(
                    "SELECT allowed FROM role_permission_defaults "
                    "WHERE role = :role AND permission_code = :code"
                ),
                {"role": role, "code": legacy},
            ).scalar()
            if allowed is not None:
                for target in targets:
                    _upsert_default(connection, role, target, bool(allowed))

    agreed_additions = {
        "owner": set(NEW_PERMISSIONS),
        "co_owner": set(NEW_PERMISSIONS)
        - {"hotel_settings:property_manage", "hotel_settings:security_manage"},
        "manager": {
            "guest:read", "guest:update", "guest:tags_manage",
            "guest:prohibition_read", "guest:prohibition_manage",
            "reservation:read", "reservation:update", "reservation:cancel",
            "reservation:move", "reservation:prohibition_override",
            "room:read", "room:status_update", "room:block_create",
            "room:block_release", "checkout:perform", "stock:read",
            "stock:movement", "stock:admin", "laundry:read",
            "laundry:movement", "laundry:vendor_manage",
            "laundry:remito_manage", "laundry:price_manage", "rates:read",
            "rates:update", "promotions:read", "promotions:manage",
        },
        "receptionist": {
            "guest:read", "guest:update", "guest:tags_manage",
            "guest:prohibition_read", "reservation:read",
            "reservation:update", "reservation:cancel", "room:read",
            "room:block_create", "checkout:perform",
        },
        "housekeeping": {
            "room:read", "room:status_update", "laundry:read",
            "laundry:movement", "laundry:remito_manage",
        },
    }
    for role in ROLES:
        for code in NEW_PERMISSIONS:
            existing = connection.execute(
                sa.text(
                    "SELECT id FROM role_permission_defaults "
                    "WHERE role = :role AND permission_code = :code"
                ),
                {"role": role, "code": code},
            ).scalar()
            if existing is None:
                _upsert_default(connection, role, code, code in agreed_additions[role])


def _copy_role_overrides(connection) -> None:
    for legacy, targets in LEGACY_SPLITS.items():
        rows = connection.execute(
            sa.text(
                "SELECT hotel_id, role, allowed, updated_by_user_id, updated_at "
                "FROM hotel_permission_overrides WHERE permission_code = :code"
            ),
            {"code": legacy},
        ).mappings()
        for row in rows:
            for target in targets:
                exists = connection.execute(
                    sa.text(
                        "SELECT id FROM hotel_permission_overrides "
                        "WHERE hotel_id = :hotel_id AND role = :role "
                        "AND permission_code = :code"
                    ),
                    {"hotel_id": row["hotel_id"], "role": row["role"], "code": target},
                ).scalar()
                if exists is None:
                    connection.execute(
                        sa.text(
                            "INSERT INTO hotel_permission_overrides "
                            "(hotel_id, role, permission_code, allowed, updated_by_user_id, updated_at) "
                            "VALUES (:hotel_id, :role, :code, :allowed, :actor, :updated_at)"
                        ),
                        {
                            "hotel_id": row["hotel_id"],
                            "role": row["role"],
                            "code": target,
                            "allowed": bool(row["allowed"]),
                            "actor": row["updated_by_user_id"],
                            "updated_at": row["updated_at"],
                        },
                    )


def upgrade() -> None:
    connection = op.get_bind()
    _insert_permission_rows(connection)
    _backfill_defaults(connection)
    _copy_role_overrides(connection)

    op.create_table(
        "user_permission_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hotel_id", "user_id"],
            ["hotel_memberships.hotel_id", "hotel_memberships.user_id"],
            name="fk_user_permission_overrides_hotel_user_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_code"], ["permissions.code"],
            name="fk_user_permission_overrides_permission_code_permissions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"],
            name="fk_user_permission_overrides_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id", "user_id", "permission_code",
            name="uq_user_permission_overrides_hotel_user_permission",
        ),
    )
    op.create_index(
        "ix_user_permission_overrides_hotel_user",
        "user_permission_overrides",
        ["hotel_id", "user_id"],
    )
    _install_user_override_rls(connection)


def _install_user_override_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "user_permission_overrides" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "user_permission_overrides" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_user_permission_overrides" '
        'ON "user_permission_overrides"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_user_permission_overrides"
           ON "user_permission_overrides"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_user_override_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping its table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_user_permission_overrides" '
        'ON "user_permission_overrides"'
    )
    op.execute('ALTER TABLE "user_permission_overrides" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "user_permission_overrides" DISABLE ROW LEVEL SECURITY')


def _contract_legacy_rows(connection, table: str, key_columns: tuple[str, ...]) -> None:
    for legacy, targets in LEGACY_SPLITS.items():
        target_list = ", ".join(f":target_{index}" for index, _ in enumerate(targets))
        params = {f"target_{index}": target for index, target in enumerate(targets)}
        group_columns = ", ".join(key_columns)
        rows = connection.execute(
            sa.text(
                f"SELECT {group_columns}, MIN(CASE WHEN allowed THEN 1 ELSE 0 END) AS allowed "
                f"FROM {table} WHERE permission_code IN ({target_list}) GROUP BY {group_columns}"
            ),
            params,
        ).mappings()
        for row in rows:
            where = " AND ".join(f"{column} = :{column}" for column in key_columns)
            values = {column: row[column] for column in key_columns}
            values.update({"legacy": legacy, "allowed": bool(row["allowed"])})
            connection.execute(
                sa.text(
                    f"UPDATE {table} SET allowed = :allowed "
                    f"WHERE {where} AND permission_code = :legacy"
                ),
                values,
            )


def downgrade() -> None:
    connection = op.get_bind()
    # Contract canonical decisions back into still-present legacy rows. When a
    # split permission diverged, deny wins so downgrade cannot broaden access.
    _contract_legacy_rows(connection, "role_permission_defaults", ("role",))
    _contract_legacy_rows(connection, "hotel_permission_overrides", ("hotel_id", "role"))

    _remove_user_override_rls(connection)
    op.drop_index("ix_user_permission_overrides_hotel_user", table_name="user_permission_overrides")
    op.drop_table("user_permission_overrides")
    codes = tuple(NEW_PERMISSIONS)
    placeholders = ", ".join(f":code_{index}" for index, _ in enumerate(codes))
    params = {f"code_{index}": code for index, code in enumerate(codes)}
    connection.execute(
        sa.text(f"DELETE FROM hotel_permission_overrides WHERE permission_code IN ({placeholders})"),
        params,
    )
    connection.execute(
        sa.text(f"DELETE FROM role_permission_defaults WHERE permission_code IN ({placeholders})"),
        params,
    )
    connection.execute(
        sa.text(f"DELETE FROM permissions WHERE code IN ({placeholders})"),
        params,
    )
