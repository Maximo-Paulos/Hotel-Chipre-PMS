"""Default hotel check-in to full settlement and honor company credit terms."""
from alembic import op
import sqlalchemy as sa


revision = "20261004_checkin_full_payment_default"
down_revision = "20261003_manual_rate_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The former implicit deposit default was not recorded separately from an
    # operator-selected deposit policy. Apply the owner's new default once to
    # existing implicit values; hotels can explicitly reselect "deposit" in
    # Settings after upgrade if that policy is intentional for their property.
    op.execute(
        sa.text(
            "UPDATE hotel_configuration "
            "SET checkin_payment_policy = 'total' "
            "WHERE checkin_payment_policy = 'deposit'"
        )
    )
    with op.batch_alter_table("hotel_configuration") as batch_op:
        batch_op.alter_column(
            "checkin_payment_policy",
            existing_type=sa.String(length=16),
            existing_nullable=False,
            server_default=sa.text("'total'"),
        )


def downgrade() -> None:
    # Preserve intentional per-hotel settings. Rollback only restores the old
    # default for newly created rows; migrated values remain explicit.
    with op.batch_alter_table("hotel_configuration") as batch_op:
        batch_op.alter_column(
            "checkin_payment_policy",
            existing_type=sa.String(length=16),
            existing_nullable=False,
            server_default=sa.text("'deposit'"),
        )
