"""Add audited cancellation review queue and approval permission.

Revision ID: 20261025_reservation_cancellation_review
Revises: 20261025_laundry_discrepancy_workflow
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261025_reservation_cancellation_review"
down_revision: Union[str, None] = "20261025_laundry_discrepancy_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "reservation_cancellation_reviews"
_PERMISSION = "reservation:cancel_penalty_approve"
_DESCRIPTION = "Approve reservation cancellation penalties"
_ROOM_OVERRIDE_PERMISSION = "reservation:room_dirty_override"
_ROOM_OVERRIDE_DESCRIPTION = "Move an in-house guest into a room with an open housekeeping checklist"


def _install_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{_TABLE}" ON "{_TABLE}"')
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{_TABLE}" ON "{_TABLE}"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_tenant_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{_TABLE}" ON "{_TABLE}"')
    op.execute(f'ALTER TABLE "{_TABLE}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("review_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("reservation_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("reservation_currency_code", sa.String(length=3), nullable=True),
        sa.Column("free_cancellation_hours", sa.Integer(), nullable=True),
        sa.Column("check_in_time", sa.String(length=5), nullable=True),
        sa.Column("hotel_timezone", sa.String(length=100), nullable=True),
        sa.Column("cancellation_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("penalty_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("penalty_currency_code", sa.String(length=3), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "review_type IN ('penalty', 'historical_policy_missing', 'policy_needs_review')",
            name="ck_reservation_cancellation_review_type_valid",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_reservation_cancellation_review_status_valid",
        ),
        sa.CheckConstraint(
            "(penalty_amount IS NULL AND penalty_currency_code IS NULL) OR "
            "(penalty_amount >= 0 AND length(penalty_currency_code) = 3 "
            "AND penalty_currency_code = upper(penalty_currency_code))",
            name="ck_reservation_cancellation_review_penalty_valid",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_cancellation_reviews_hotel_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"],
            name="fk_reservation_cancellation_reviews_requested_by_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"],
            name="fk_reservation_cancellation_reviews_reviewed_by_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_cancellation_reviews_hotel_reservation", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservation_cancellation_reviews"),
        sa.UniqueConstraint(
            "hotel_id", "id", name="uq_reservation_cancellation_reviews_hotel_id_id",
        ),
    )
    op.create_index(
        "ix_reservation_cancellation_reviews_hotel_status_requested",
        _TABLE,
        ["hotel_id", "status", "requested_at"],
    )
    op.create_index(
        "uq_reservation_cancellation_reviews_pending_reservation",
        _TABLE,
        ["hotel_id", "reservation_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
    _install_tenant_rls()

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
            "VALUES (:code, :description, false, false, true) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _PERMISSION, "description": _DESCRIPTION},
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
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
            "VALUES (:code, :description, false, false, true) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _ROOM_OVERRIDE_PERMISSION, "description": _ROOM_OVERRIDE_DESCRIPTION},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) VALUES "
            "('owner', :code, true), ('co_owner', :code, true), ('manager', :code, true), "
            "('receptionist', :code, false), ('housekeeping', :code, false) "
            "ON CONFLICT (role, permission_code) DO NOTHING"
        ),
        {"code": _ROOM_OVERRIDE_PERMISSION},
    )


def downgrade() -> None:
    _remove_tenant_rls()
    op.drop_index(
        "uq_reservation_cancellation_reviews_pending_reservation",
        table_name=_TABLE,
    )
    op.drop_index(
        "ix_reservation_cancellation_reviews_hotel_status_requested",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
    # Permission rows and role defaults stay in place to preserve hotel
    # overrides if this migration is applied again later.
