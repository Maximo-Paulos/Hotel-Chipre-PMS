"""Add per-hotel bounded manual reservation rates and their audit fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261003_manual_rate_policy"
down_revision: Union[str, None] = "20261002_stock_transfers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_LIMITED_PERMISSION = "reservation:manual_rate_limited"
_POLICY_PERMISSION = "reservation:manual_rate_policy_manage"


def upgrade() -> None:
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("manual_rate_min_adjustment_pct", sa.Numeric(7, 2), nullable=True))
        batch_op.add_column(sa.Column("manual_rate_max_adjustment_pct", sa.Numeric(7, 2), nullable=True))
        batch_op.create_check_constraint(
            "ck_hotel_configuration_manual_rate_bounds",
            "(manual_rate_min_adjustment_pct IS NULL AND manual_rate_max_adjustment_pct IS NULL) "
            "OR (manual_rate_min_adjustment_pct IS NOT NULL AND manual_rate_max_adjustment_pct IS NOT NULL "
            "AND manual_rate_min_adjustment_pct >= -100 "
            "AND manual_rate_min_adjustment_pct <= manual_rate_max_adjustment_pct)",
        )

    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("manual_rate_reason", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("manual_rate_scope", sa.String(length=16), nullable=True))
        batch_op.create_check_constraint(
            "ck_reservation_manual_rate_scope",
            "manual_rate_scope IS NULL OR manual_rate_scope IN ('bounded', 'unbounded')",
        )
        batch_op.create_check_constraint(
            "ck_reservation_manual_rate_reason_required",
            "manual_rate_scope IS NULL OR (manual_rate_reason IS NOT NULL AND length(trim(manual_rate_reason)) > 0)",
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES (:code, :description, false, false, true)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "code": _LIMITED_PERMISSION,
            "description": "Set a reservation rate within the hotel's configured range",
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES (:code, :description, true, true, false)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "code": _POLICY_PERMISSION,
            "description": "Configure the permitted manual reservation rate range",
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permission_defaults (role, permission_code, allowed)
            VALUES
                ('owner', :limited, true),
                ('co_owner', :limited, true),
                ('manager', :limited, true),
                ('receptionist', :limited, false),
                ('housekeeping', :limited, false),
                ('owner', :policy, true),
                ('co_owner', :policy, false),
                ('manager', :policy, false),
                ('receptionist', :policy, false),
                ('housekeeping', :policy, false)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"limited": _LIMITED_PERMISSION, "policy": _POLICY_PERMISSION},
    )


def downgrade() -> None:
    # Keep the permission catalog/defaults intact so rolling application code
    # back cannot erase owner-managed authorization state.
    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.drop_constraint("ck_reservation_manual_rate_reason_required", type_="check")
        batch_op.drop_constraint("ck_reservation_manual_rate_scope", type_="check")
        batch_op.drop_column("manual_rate_scope")
        batch_op.drop_column("manual_rate_reason")
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch_op:
        batch_op.drop_constraint("ck_hotel_configuration_manual_rate_bounds", type_="check")
        batch_op.drop_column("manual_rate_max_adjustment_pct")
        batch_op.drop_column("manual_rate_min_adjustment_pct")
