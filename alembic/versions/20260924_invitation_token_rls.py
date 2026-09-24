"""Allow a bearer invitation token to resolve only its own row under RLS."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260924_invitation_token_rls"
down_revision: Union[str, None] = "20260924_pg_enum_values"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_POLICY = "tenant_isolation_staff_invitations"
_TOKEN_POLICY = "invitation_token_staff_invitation_read"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(f'DROP POLICY IF EXISTS "{_TENANT_POLICY}" ON "staff_invitations"')
    op.execute(
        f'''CREATE POLICY "{_TENANT_POLICY}" ON "staff_invitations"
            FOR ALL
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )
    # Public invitation previews/acceptance do not yet have an authenticated
    # tenant identity. A high-entropy token is already a bearer capability;
    # exposing only the row with its SHA-256 digest permits lookup without
    # granting token-based UPDATE or DELETE access.
    op.execute(
        f'''CREATE POLICY "{_TOKEN_POLICY}" ON "staff_invitations"
            FOR SELECT
            USING (token_hash = NULLIF(current_setting('app.invitation_token_hash', true), ''))'''
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(f'DROP POLICY IF EXISTS "{_TOKEN_POLICY}" ON "staff_invitations"')
    op.execute(f'DROP POLICY IF EXISTS "{_TENANT_POLICY}" ON "staff_invitations"')
    op.execute(
        f'''CREATE POLICY "{_TENANT_POLICY}" ON "staff_invitations"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )
