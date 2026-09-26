"""Restrict direct execution of the Supabase RLS DDL event trigger.

Revision ID: 20260927_revoke_public_rls_auto_enable
Revises: 20260927_payment_proof_capabilities
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260927_revoke_public_rls_auto_enable"
down_revision: Union[str, None] = "20260927_payment_proof_capabilities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supabase installs this SECURITY DEFINER function as an event-trigger
    # handler. PostgreSQL invokes it through the registered event trigger,
    # independently of EXECUTE grants; it should not be exposed to API roles.
    op.execute(
        """
        DO $migration$
        DECLARE
            grantee text;
        BEGIN
            IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
                EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC';

                FOR grantee IN
                    SELECT rolname
                    FROM pg_roles
                    WHERE rolname IN ('anon', 'authenticated', 'service_role')
                LOOP
                    EXECUTE format(
                        'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM %I',
                        grantee
                    );
                END LOOP;
            END IF;
        END;
        $migration$
        """
    )


def downgrade() -> None:
    # Do not re-expose the internal DDL trigger when rolling back application
    # schema changes; restoring broad EXECUTE grants is not a safe downgrade.
    pass
