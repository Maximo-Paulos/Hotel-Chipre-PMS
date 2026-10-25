"""Track laundry remito discrepancies and explicit linen retirements.

Revision ID: 20261025_laundry_discrepancy_workflow
Revises: 20261025_company_documents_read
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261025_laundry_discrepancy_workflow"
down_revision: Union[str, None] = "20261025_company_documents_read"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "laundry:discrepancy_approve"
_PERMISSION_DESCRIPTION = "Approve and reconcile laundry discrepancies"
_TABLE = "laundry_remito_discrepancies"
_ACTIONS_TABLE = "laundry_discrepancy_actions"


def _install_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in (_TABLE, _ACTIONS_TABLE):
        op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(
            f'''CREATE POLICY "tenant_isolation_{table_name}" ON "{table_name}"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def _remove_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name in (_ACTIONS_TABLE, _TABLE):
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    # Composite tenant FKs below must target a unique parent key. Line IDs are
    # globally unique already, so this adds no data rewrite or behavior change.
    with op.batch_alter_table("laundry_remito_lines") as batch_op:
        batch_op.create_unique_constraint("uq_laundry_remito_lines_hotel_id_id", ["hotel_id", "id"])

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("remito_id", sa.Integer(), nullable=False),
        sa.Column("remito_line_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("linen_item_id", sa.Integer(), nullable=False),
        sa.Column("discrepancy_type", sa.String(length=24), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("source_location_id", sa.Integer(), nullable=False),
        sa.Column("custody_location_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("resolution_code", sa.String(length=80), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolution_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("resolution_currency_code", sa.String(length=3), nullable=True),
        sa.Column("resolution_recorded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution_recorded_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("returned_by_user_id", sa.Integer(), nullable=True),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "discrepancy_type IN ('excess_return', 'short_return')",
            name="ck_laundry_discrepancy_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending_approval', 'pending_identification', 'pending_review', "
            "'pending_resolution', 'pending_claim', 'awaiting_replacement', 'resolved', "
            "'return_to_laundry', 'returned_to_laundry')",
            name="ck_laundry_discrepancy_status_valid",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_laundry_discrepancy_quantity_positive"),
        sa.CheckConstraint(
            "remaining_quantity >= 0 AND remaining_quantity <= quantity",
            name="ck_laundry_discrepancy_remaining_quantity_valid",
        ),
        sa.CheckConstraint(
            "(resolution_amount IS NULL AND resolution_currency_code IS NULL) OR "
            "(resolution_amount > 0 AND length(resolution_currency_code) = 3 "
            "AND resolution_currency_code = upper(resolution_currency_code))",
            name="ck_laundry_discrepancy_resolution_credit_valid",
        ),
        sa.CheckConstraint(
            "(discrepancy_type = 'excess_return' AND status NOT IN ('pending_review', 'pending_resolution', "
            "'pending_claim', 'awaiting_replacement')) OR (discrepancy_type = 'short_return' AND status NOT IN "
            "('pending_approval', 'pending_identification', 'return_to_laundry', 'returned_to_laundry'))",
            name="ck_laundry_discrepancy_type_status_compatible",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_discrepancies_hotel_id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolution_recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["returned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "remito_id"], ["laundry_remitos.hotel_id", "laundry_remitos.id"],
            name="fk_laundry_discrepancies_hotel_remito", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "remito_line_id"], ["laundry_remito_lines.hotel_id", "laundry_remito_lines.id"],
            name="fk_laundry_discrepancies_hotel_remito_line", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "vendor_id"], ["laundry_vendors.hotel_id", "laundry_vendors.id"],
            name="fk_laundry_discrepancies_hotel_vendor", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "linen_item_id"], ["linen_items.hotel_id", "linen_items.id"],
            name="fk_laundry_discrepancies_hotel_item",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "source_location_id"], ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_laundry_discrepancies_hotel_source_location",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "custody_location_id"], ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_laundry_discrepancies_hotel_custody_location",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_laundry_remito_discrepancies"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_laundry_discrepancies_hotel_id_id"),
        sa.UniqueConstraint(
            "hotel_id", "remito_line_id", "discrepancy_type", name="uq_laundry_discrepancies_line_type"
        ),
    )
    op.create_index("ix_laundry_discrepancies_hotel_status", _TABLE, ["hotel_id", "status"])
    op.create_index("ix_laundry_discrepancies_hotel_item", _TABLE, ["hotel_id", "linen_item_id"])

    op.create_table(
        _ACTIONS_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("discrepancy_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("resolution_code", sa.String(length=80), nullable=True),
        sa.Column("resolution_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("resolution_currency_code", sa.String(length=3), nullable=True),
        sa.Column("remito_id", sa.Integer(), nullable=True),
        sa.Column("remito_line_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action_type IN ('approval', 'resolution', 'return_to_laundry', 'claim_return', 'replacement_receipt')",
            name="ck_laundry_discrepancy_action_type_valid",
        ),
        sa.CheckConstraint("length(trim(idempotency_key)) > 0", name="ck_laundry_discrepancy_action_key_nonempty"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_laundry_discrepancy_action_reason_nonempty"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_laundry_discrepancy_action_quantity_positive"),
        sa.CheckConstraint(
            "(resolution_amount IS NULL AND resolution_currency_code IS NULL) OR "
            "(resolution_amount > 0 AND length(resolution_currency_code) = 3 "
            "AND resolution_currency_code = upper(resolution_currency_code))",
            name="ck_laundry_discrepancy_action_credit_valid",
        ),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_discrepancy_actions_hotel_id"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "discrepancy_id"], [f"{_TABLE}.hotel_id", f"{_TABLE}.id"],
            name="fk_laundry_discrepancy_actions_hotel_discrepancy", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "remito_id"], ["laundry_remitos.hotel_id", "laundry_remitos.id"],
            name="fk_laundry_discrepancy_actions_hotel_remito",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "remito_line_id"], ["laundry_remito_lines.hotel_id", "laundry_remito_lines.id"],
            name="fk_laundry_discrepancy_actions_hotel_remito_line",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_laundry_discrepancy_actions"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_laundry_discrepancy_actions_hotel_id_id"),
        sa.UniqueConstraint("hotel_id", "idempotency_key", name="uq_laundry_discrepancy_actions_hotel_key"),
    )
    op.create_index(
        "ix_laundry_discrepancy_actions_hotel_discrepancy",
        _ACTIONS_TABLE,
        ["hotel_id", "discrepancy_id", "created_at"],
    )
    _install_tenant_rls()

    with op.batch_alter_table("linen_movements") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.drop_constraint("ck_linen_movements_type_valid", type_="check")
        batch_op.create_check_constraint(
            "ck_linen_movements_type_valid",
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out', 'retirement')",
        )
    op.create_index(
        "uq_linen_movement_hotel_idempotency_key",
        "linen_movements",
        ["hotel_id", "idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
            "VALUES (:code, :description, false, false, true) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _PERMISSION, "description": _PERMISSION_DESCRIPTION},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) VALUES "
            "('owner', :code, true), ('co_owner', :code, true), ('manager', :code, true), "
            "('receptionist', :code, false), ('housekeeping', :code, false) "
            "ON CONFLICT (role, permission_code) DO NOTHING"
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text(f"SELECT 1 FROM {_ACTIONS_TABLE} LIMIT 1")).first() is not None:
        raise RuntimeError("laundry discrepancy action history exists; preserve before downgrade")
    if connection.execute(sa.text(f"SELECT 1 FROM {_TABLE} LIMIT 1")).first() is not None:
        raise RuntimeError("laundry discrepancy history exists; preserve before downgrade")
    if connection.execute(
        sa.text("SELECT 1 FROM linen_movements WHERE movement_type = 'retirement' OR idempotency_key IS NOT NULL LIMIT 1")
    ).first() is not None:
        raise RuntimeError("linen retirement history exists; preserve before downgrade")
    _remove_tenant_rls()
    op.drop_index("uq_linen_movement_hotel_idempotency_key", table_name="linen_movements")
    with op.batch_alter_table("linen_movements") as batch_op:
        batch_op.drop_constraint("ck_linen_movements_type_valid", type_="check")
        batch_op.create_check_constraint(
            "ck_linen_movements_type_valid",
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out')",
        )
        batch_op.drop_column("idempotency_key")
    op.drop_index("ix_laundry_discrepancy_actions_hotel_discrepancy", table_name=_ACTIONS_TABLE)
    op.drop_table(_ACTIONS_TABLE)
    op.drop_index("ix_laundry_discrepancies_hotel_item", table_name=_TABLE)
    op.drop_index("ix_laundry_discrepancies_hotel_status", table_name=_TABLE)
    op.drop_table(_TABLE)
    with op.batch_alter_table("laundry_remito_lines") as batch_op:
        batch_op.drop_constraint("uq_laundry_remito_lines_hotel_id_id", type_="unique")
    # Keep permission rows/defaults so a rollback never erases role settings.
