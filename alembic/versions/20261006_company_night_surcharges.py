"""Add auditable per-night company extras and payment allocations."""
from alembic import op
import sqlalchemy as sa


revision = "20261006_company_night_surcharges"
down_revision = "20261005_merge_day1_migration_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("extra_person_nightly_surcharge", sa.Numeric(12, 2), nullable=True),
    )
    with op.batch_alter_table("companies") as batch_op:
        batch_op.create_check_constraint(
            "ck_companies_extra_person_surcharge_nonnegative",
            "extra_person_nightly_surcharge IS NULL OR extra_person_nightly_surcharge >= 0",
        )

    op.create_table(
        "company_night_charges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("billing_adjustment_id", sa.Integer(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_company_night_charges_amount_positive"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"], name="fk_company_night_charges_hotel_reservation", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"], name="fk_company_night_charges_hotel_company", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["billing_adjustment_id"], ["billing_adjustments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hotel_id", "reservation_id", "stay_date", name="uq_company_night_charges_reservation_date"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_company_night_charges_hotel_id_id"),
        sa.UniqueConstraint("billing_adjustment_id"),
    )
    op.create_index(
        "ix_company_night_charges_hotel_reservation",
        "company_night_charges",
        ["hotel_id", "reservation_id", "stay_date"],
    )

    op.create_table(
        "company_night_charge_payment_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("company_night_charge_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_company_night_charge_allocations_amount_positive"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id", "transaction_id"], ["transactions.hotel_id", "transactions.id"], name="fk_company_night_charge_allocations_hotel_transaction", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id", "company_night_charge_id"], ["company_night_charges.hotel_id", "company_night_charges.id"], name="fk_company_night_charge_allocations_hotel_charge", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", "company_night_charge_id", name="uq_company_night_charge_payment_allocation"),
    )
    op.create_index(
        "ix_company_night_charge_allocations_hotel_charge",
        "company_night_charge_payment_allocations",
        ["hotel_id", "company_night_charge_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_night_charge_allocations_hotel_charge", table_name="company_night_charge_payment_allocations")
    op.drop_table("company_night_charge_payment_allocations")
    op.drop_index("ix_company_night_charges_hotel_reservation", table_name="company_night_charges")
    op.drop_table("company_night_charges")
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_constraint("ck_companies_extra_person_surcharge_nonnegative", type_="check")
        batch_op.drop_column("extra_person_nightly_surcharge")
