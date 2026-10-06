"""Track neutral supplier follow-up for declared laundry shortages.

Revision ID: 20261017_laundry_missing_follow_up
Revises: 11be7c9387c4
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20261017_laundry_missing_follow_up"
down_revision = "11be7c9387c4"
branch_labels = None
depends_on = None

TABLE = "laundry_remito_lines"
STATUS_CHECK = "ck_laundry_remito_lines_follow_up_status"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("follow_up_status", sa.String(length=24), nullable=True))
    op.add_column(TABLE, sa.Column("follow_up_note", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("supplier_reference", sa.String(length=120), nullable=True))
    op.add_column(TABLE, sa.Column("supplier_contacted_on", sa.Date(), nullable=True))
    op.add_column(TABLE, sa.Column("supplier_contact_note", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("supplier_response_on", sa.Date(), nullable=True))
    op.add_column(TABLE, sa.Column("supplier_response_note", sa.Text(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "follow_up_updated_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(TABLE, sa.Column("follow_up_updated_at", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE laundry_remito_lines SET follow_up_status = 'open' WHERE missing_quantity > 0"
        )
    )
    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.create_check_constraint(
            STATUS_CHECK,
            "(missing_quantity = 0 AND follow_up_status IS NULL) OR "
            "(missing_quantity > 0 AND follow_up_status IS NOT NULL AND follow_up_status IN "
            "('open', 'contacted', 'response_recorded', 'closed'))",
        )
        batch_op.create_foreign_key(
            "fk_laundry_remito_lines_follow_up_updated_by",
            "users",
            ["follow_up_updated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    has_follow_ups = bind.execute(
        sa.text(
            "SELECT 1 FROM laundry_remito_lines "
            "WHERE missing_quantity > 0 OR follow_up_status IS NOT NULL "
            "OR follow_up_note IS NOT NULL OR supplier_reference IS NOT NULL "
            "OR supplier_contacted_on IS NOT NULL OR supplier_contact_note IS NOT NULL "
            "OR supplier_response_on IS NOT NULL OR supplier_response_note IS NOT NULL "
            "OR follow_up_updated_at IS NOT NULL LIMIT 1"
        )
    ).first()
    if has_follow_ups:
        raise RuntimeError(
            "Cannot downgrade laundry missing follow-up while shortage or follow-up data exists; "
            "preserve the operational records first."
        )

    with op.batch_alter_table(TABLE) as batch_op:
        batch_op.drop_constraint("fk_laundry_remito_lines_follow_up_updated_by", type_="foreignkey")
        batch_op.drop_constraint(STATUS_CHECK, type_="check")
        batch_op.drop_column("follow_up_updated_at")
        batch_op.drop_column("follow_up_updated_by_user_id")
        batch_op.drop_column("supplier_response_note")
        batch_op.drop_column("supplier_response_on")
        batch_op.drop_column("supplier_contact_note")
        batch_op.drop_column("supplier_contacted_on")
        batch_op.drop_column("supplier_reference")
        batch_op.drop_column("follow_up_note")
        batch_op.drop_column("follow_up_status")
