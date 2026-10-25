"""Add tenant-scoped per-guest arrival records and hotel status policy.

Revision ID: 20261025_guest_arrivals
Revises: 20261025_stock_count_sessions
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261025_guest_arrivals"
down_revision: str | None = "20261025_stock_count_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLE = "reservation_guest_arrivals"
_STATUSES = (
    "pending", "deposit_paid", "fully_paid", "pre_check_in", "partial_checkin",
    "checked_in", "checked_out", "cancelled", "no_show",
)


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


def _status_check() -> str:
    return "status IN ({})".format(", ".join(repr(value) for value in _STATUSES))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE reservation_status_enum ADD VALUE IF NOT EXISTS 'partial_checkin'")

    reservation_columns = {column["name"] for column in sa.inspect(bind).get_columns("reservations")}
    if bind.dialect.name == "sqlite":
        # SQLite stores SQLAlchemy enums as a CHECK constraint. Rebuild using
        # the expanded state list so local SQLite tests follow PostgreSQL.
        with op.batch_alter_table("reservations", recreate="always") as batch:
            existing_checks = {
                constraint.get("name")
                for constraint in sa.inspect(bind).get_check_constraints("reservations")
            }
            if "reservation_status_enum" in existing_checks:
                batch.drop_constraint("reservation_status_enum", type_="check")
            batch.create_check_constraint("reservation_status_enum", _status_check())
            if "checkin_reservation_status_policy_snapshot" not in reservation_columns:
                batch.add_column(sa.Column("checkin_reservation_status_policy_snapshot", sa.String(32), nullable=True))
    elif "checkin_reservation_status_policy_snapshot" not in reservation_columns:
        op.add_column(
            "reservations",
            sa.Column("checkin_reservation_status_policy_snapshot", sa.String(32), nullable=True),
        )

    hotel_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
    with op.batch_alter_table("hotel_configuration") as batch:
        if "checkin_reservation_status_policy" not in hotel_columns:
            batch.add_column(
                sa.Column(
                    "checkin_reservation_status_policy",
                    sa.String(32),
                    server_default="partial_checkin",
                    nullable=False,
                )
            )
        existing_checks = {
            constraint.get("name")
            for constraint in sa.inspect(bind).get_check_constraints("hotel_configuration")
        }
        if "ck_hotel_configuration_checkin_reservation_status_policy" not in existing_checks:
            batch.create_check_constraint(
                "ck_hotel_configuration_checkin_reservation_status_policy",
                "checkin_reservation_status_policy IN ('partial_checkin', 'checked_in_on_first_guest')",
            )

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "length(trim(actor_role)) > 0",
            name="ck_reservation_guest_arrival_actor_role",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_guest_arrivals_hotel_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_guest_arrivals_hotel_reservation", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_reservation_guest_arrivals_hotel_guest", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name="fk_reservation_guest_arrivals_actor_user_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservation_guest_arrivals"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_reservation_guest_arrivals_hotel_id_id"),
        sa.UniqueConstraint(
            "hotel_id", "reservation_id", "guest_id",
            name="uq_reservation_guest_arrivals_guest",
        ),
    )
    op.create_index(
        "ix_reservation_guest_arrivals_hotel_reservation_arrived",
        _TABLE,
        ["hotel_id", "reservation_id", "arrived_at", "id"],
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO reservation_guest_arrivals
                (hotel_id, reservation_id, guest_id, arrived_at, actor_user_id, actor_role)
            SELECT hotel_id, id, guest_id,
                   COALESCE(actual_check_in AT TIME ZONE 'UTC',
                            check_in_date::timestamp AT TIME ZONE 'UTC'),
                   NULL, 'legacy'
            FROM reservations
            WHERE status IN ('checked_in', 'checked_out')
            ON CONFLICT (hotel_id, reservation_id, guest_id) DO NOTHING
            """
        )
        op.execute(
            """
            UPDATE reservations
            SET checkin_reservation_status_policy_snapshot = 'checked_in_on_first_guest'
            WHERE status IN ('checked_in', 'checked_out')
              AND checkin_reservation_status_policy_snapshot IS NULL
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_reservation_guest_arrival_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'reservation guest arrival records are append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_reservation_guest_arrivals_append_only
            BEFORE UPDATE OR DELETE ON reservation_guest_arrivals
            FOR EACH ROW EXECUTE FUNCTION reject_reservation_guest_arrival_mutation()
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            INSERT OR IGNORE INTO reservation_guest_arrivals
                (hotel_id, reservation_id, guest_id, arrived_at, actor_user_id, actor_role)
            SELECT hotel_id, id, guest_id,
                   datetime(COALESCE(actual_check_in, check_in_date || ' 00:00:00')),
                   NULL, 'legacy'
            FROM reservations
            WHERE status IN ('checked_in', 'checked_out')
            """
        )
        op.execute(
            """
            UPDATE reservations
            SET checkin_reservation_status_policy_snapshot = 'checked_in_on_first_guest'
            WHERE status IN ('checked_in', 'checked_out')
              AND checkin_reservation_status_policy_snapshot IS NULL
            """
        )
    _install_tenant_rls()


def downgrade() -> None:
    _remove_tenant_rls()
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_reservation_guest_arrivals_append_only ON reservation_guest_arrivals")
        op.execute("DROP FUNCTION IF EXISTS reject_reservation_guest_arrival_mutation()")
    op.drop_index("ix_reservation_guest_arrivals_hotel_reservation_arrived", table_name=_TABLE)
    op.drop_table(_TABLE)
    with op.batch_alter_table("hotel_configuration") as batch:
        batch.drop_constraint("ck_hotel_configuration_checkin_reservation_status_policy", type_="check")
        batch.drop_column("checkin_reservation_status_policy")
    op.drop_column("reservations", "checkin_reservation_status_policy_snapshot")
    # PostgreSQL enum values cannot be removed safely. Keep partial_checkin
    # available on SQLite too, so existing reservations can be downgraded
    # without failing a CHECK constraint.
