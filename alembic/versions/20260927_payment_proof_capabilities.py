"""Separate payment-proof reading/review from financial reports.

Revision ID: 20260927_payment_proof_capabilities
Revises: 20260926_legal_retention_holds
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927_payment_proof_capabilities"
down_revision: Union[str, None] = "20260926_legal_retention_holds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_READ = "payment:proof:view"
_REVIEW = "payment:proof:review"
_LEGACY = "reports:financial:view"


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES
                (:read_code, 'Read transfer payment proofs', false, false, true),
                (:review_code, 'Review transfer payment proofs', false, false, true)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"read_code": _READ, "review_code": _REVIEW},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permission_defaults (role, permission_code, allowed)
            VALUES
                ('owner', :read_code, true), ('owner', :review_code, true),
                ('co_owner', :read_code, true), ('co_owner', :review_code, true),
                ('manager', :read_code, true), ('manager', :review_code, true),
                ('receptionist', :read_code, false), ('receptionist', :review_code, false),
                ('housekeeping', :read_code, false), ('housekeeping', :review_code, false)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"read_code": _READ, "review_code": _REVIEW},
    )

    # Before these capabilities existed, the financial-report permission was
    # the only explicit hotel/user override affecting proof reads and review.
    # Carry each saved decision forward to both capabilities, but never replace
    # a newer explicit decision already stored under the new permission code.
    connection.execute(
        sa.text(
            """
            INSERT INTO hotel_permission_overrides
                (hotel_id, role, permission_code, allowed, version, updated_by_user_id, updated_at)
            SELECT old.hotel_id, old.role, target.permission_code, old.allowed, 1,
                   old.updated_by_user_id, old.updated_at
            FROM hotel_permission_overrides AS old
            CROSS JOIN (
                SELECT :read_code AS permission_code
                UNION ALL
                SELECT :review_code AS permission_code
            ) AS target
            WHERE old.permission_code = :legacy_code
              AND NOT EXISTS (
                  SELECT 1 FROM hotel_permission_overrides AS current
                  WHERE current.hotel_id = old.hotel_id
                    AND current.role = old.role
                    AND current.permission_code = target.permission_code
              )
            ON CONFLICT (hotel_id, role, permission_code) DO NOTHING
            """
        ),
        {"read_code": _READ, "review_code": _REVIEW, "legacy_code": _LEGACY},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO user_permission_overrides
                (hotel_id, user_id, permission_code, allowed, version, updated_by_user_id, updated_at)
            SELECT old.hotel_id, old.user_id, target.permission_code, old.allowed, 1,
                   old.updated_by_user_id, old.updated_at
            FROM user_permission_overrides AS old
            CROSS JOIN (
                SELECT :read_code AS permission_code
                UNION ALL
                SELECT :review_code AS permission_code
            ) AS target
            WHERE old.permission_code = :legacy_code
              AND NOT EXISTS (
                  SELECT 1 FROM user_permission_overrides AS current
                  WHERE current.hotel_id = old.hotel_id
                    AND current.user_id = old.user_id
                    AND current.permission_code = target.permission_code
              )
            ON CONFLICT (hotel_id, user_id, permission_code) DO NOTHING
            """
        ),
        {"read_code": _READ, "review_code": _REVIEW, "legacy_code": _LEGACY},
    )


def downgrade() -> None:
    # Permission overrides may have been edited after deployment. Keep the
    # catalog entries and choices rather than deleting live authorization data.
    pass
