"""Persist fixed post-checkout housekeeping checklists.

Revision ID: 20261023_housekeeping_checklists
Revises: 20261023_cash_tender_change
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20261023_housekeeping_checklists"
down_revision: str | None = "20261023_cash_tender_change"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHECKLISTS = "housekeeping_checklists"
ITEMS = "housekeeping_checklist_items"


def _enable_tenant_rls(table_name: str) -> None:
    quoted = f'"{table_name}"'
    policy = f'"tenant_isolation_{table_name}"'
    op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
    op.execute(
        f"CREATE POLICY {policy} ON {quoted} "
        "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer) "
        "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)"
    )


def upgrade() -> None:
    op.create_table(
        CHECKLISTS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('open', 'completed')", name="ck_housekeeping_checklist_status"),
        sa.CheckConstraint("version >= 1", name="ck_housekeeping_checklist_version_positive"),
        sa.CheckConstraint(
            "(status = 'open' AND completed_at IS NULL AND completed_by_user_id IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_housekeeping_checklist_completion_consistent",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "room_id"],
            ["rooms.hotel_id", "rooms.id"],
            name="fk_housekeeping_checklists_hotel_room",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_housekeeping_checklists_hotel_reservation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_housekeeping_checklists_hotel_id_id"),
        sa.UniqueConstraint("hotel_id", "reservation_id", name="uq_housekeeping_checklists_reservation"),
    )
    op.create_index(
        "ix_housekeeping_checklists_hotel_status_room",
        CHECKLISTS,
        ["hotel_id", "status", "room_id"],
    )
    op.create_index(
        "uq_housekeeping_checklists_one_open_per_room",
        CHECKLISTS,
        ["hotel_id", "room_id"],
        unique=True,
        sqlite_where=sa.text("status = 'open'"),
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        ITEMS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("checklist_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "code IN ('change_sheets', 'clean_bathroom', 'replenish_towels', 'empty_waste', 'check_amenities')",
            name="ck_housekeeping_checklist_item_code",
        ),
        sa.CheckConstraint("length(trim(label)) BETWEEN 1 AND 120", name="ck_housekeeping_checklist_item_label"),
        sa.CheckConstraint(
            "(completed = false AND completed_at IS NULL AND completed_by_user_id IS NULL) OR "
            "(completed = true AND completed_at IS NOT NULL)",
            name="ck_housekeeping_checklist_item_completion_consistent",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "checklist_id"],
            ["housekeeping_checklists.hotel_id", "housekeeping_checklists.id"],
            name="fk_housekeeping_checklist_items_hotel_checklist",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "checklist_id", "code", name="uq_housekeeping_checklist_item_code"),
    )
    op.create_index(
        "ix_housekeeping_checklist_items_hotel_checklist",
        ITEMS,
        ["hotel_id", "checklist_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        _enable_tenant_rls(CHECKLISTS)
        _enable_tenant_rls(ITEMS)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # FORCE RLS also applies to the table owner. Temporarily remove FORCE
        # inside this migration transaction so the data-retention check sees
        # every tenant; raising rolls the DDL back and restores the policy.
        for table_name in (ITEMS, CHECKLISTS):
            op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')

    existing_rows = bind.execute(
        sa.text(
            f"SELECT 1 FROM {ITEMS} UNION ALL SELECT 1 FROM {CHECKLISTS} LIMIT 1"
        )
    ).first()
    if existing_rows:
        raise RuntimeError(
            "Cannot downgrade housekeeping checklist migration while checklist history exists; "
            "preserve operational and audit history first."
        )

    if bind.dialect.name == "postgresql":
        for table_name in (ITEMS, CHECKLISTS):
            op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
            op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')

    op.drop_index("ix_housekeeping_checklist_items_hotel_checklist", table_name=ITEMS)
    op.drop_table(ITEMS)
    op.drop_index("uq_housekeeping_checklists_one_open_per_room", table_name=CHECKLISTS)
    op.drop_index("ix_housekeeping_checklists_hotel_status_room", table_name=CHECKLISTS)
    op.drop_table(CHECKLISTS)
