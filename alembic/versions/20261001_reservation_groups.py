"""Add tenant-scoped groups for multi-room reservations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_reservation_groups"
down_revision: Union[str, None] = "41d66acfb13a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reservation_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_reservation_groups_hotel_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_reservation_groups_created_by_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_reservation_groups_hotel_guest",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_reservation_groups_hotel_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_reservation_groups_hotel_id_id"),
    )
    op.create_index(
        "ix_reservation_groups_hotel_created",
        "reservation_groups",
        ["hotel_id", "created_at"],
    )
    _install_rls()

    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_reservations_hotel_group",
            "reservation_groups",
            ["hotel_id", "group_id"],
            ["hotel_id", "id"],
        )
        batch_op.create_index("ix_reservations_hotel_group", ["hotel_id", "group_id"])


def downgrade() -> None:
    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.drop_index("ix_reservations_hotel_group")
        batch_op.drop_constraint("fk_reservations_hotel_group", type_="foreignkey")
        batch_op.drop_column("group_id")
    _remove_rls()
    op.drop_index("ix_reservation_groups_hotel_created", table_name="reservation_groups")
    op.drop_table("reservation_groups")


def _install_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "reservation_groups" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "reservation_groups" FORCE ROW LEVEL SECURITY')
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_reservation_groups" ON "reservation_groups"')
    op.execute(
        '''CREATE POLICY "tenant_isolation_reservation_groups" ON "reservation_groups"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute('DROP POLICY IF EXISTS "tenant_isolation_reservation_groups" ON "reservation_groups"')
    op.execute('ALTER TABLE "reservation_groups" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "reservation_groups" DISABLE ROW LEVEL SECURITY')
