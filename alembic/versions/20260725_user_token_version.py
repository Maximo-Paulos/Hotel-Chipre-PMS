"""Add users.token_version for server-side JWT revocation.

JWTs were fully stateless with no revocation mechanism: a password reset
(the standard remediation after a suspected credential/token leak) did not
invalidate tokens issued before it, so a stolen token kept working for up
to JWT_EXPIRES_MINUTES regardless. token_version is bumped on password
reset and embedded in newly issued tokens; a mismatch is treated as an
invalid/revoked session.

Revision ID: 20260725_user_token_version
Revises: 20260725_stock_adjustment_out
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260725_user_token_version"
down_revision: Union[str, None] = "20260725_stock_adjustment_out"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already have this column
    # out-of-band via an old startup self-heal pass while alembic_version
    # stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    if "token_version" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column(
            "users",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("users", "token_version")
