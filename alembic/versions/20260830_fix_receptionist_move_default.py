"""Grant receptionist the same-category room move default.

Phase A narrowed reservation:move to same-category moves and gave it to
receptionists by default in DEFAULT_MATRIX. The tier migration only seeded
the two brand-new codes, so reservation:move kept the row it already had --
allowed=False, from when receptionists could not move a reservation at all.

Runtime reads role_permission_defaults, not DEFAULT_MATRIX, so on every
pre-existing database the intended default was never in effect.

Only the global default row is touched. Hotels that deliberately set their
own value keep it: per-hotel choices live in hotel_permission_overrides.
"""
import sqlalchemy as sa
from alembic import op

revision = "20260830_fix_receptionist_move_default"
down_revision = "20260830_guest_room_avoidance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'receptionist' AND permission_code = 'reservation:move'"
        ),
        {"allowed": True},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'receptionist' AND permission_code = 'reservation:move'"
        ),
        {"allowed": False},
    )
