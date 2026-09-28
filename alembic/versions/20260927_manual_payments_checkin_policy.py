"""Add check-in policy, manual receipt references, and auditable refunds."""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


revision: str = "20260927_manual_payments_checkin_policy"
down_revision: Union[str, None] = "20260927_master_admin_session_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _has_columns(table_name: str, expected: set[str]) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names() and expected.issubset(
        {column["name"] for column in inspector.get_columns(table_name)}
    )


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    if op.get_bind().dialect.name == "sqlite":
        return {
            row[0]
            for row in op.get_bind().execute(
                sa.text("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = :table_name"),
                {"table_name": table_name},
            )
        }
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "hotel_configuration" in inspector.get_table_names() and "checkin_payment_policy" not in {
        column["name"] for column in inspector.get_columns("hotel_configuration")
    }:
        op.add_column(
            "hotel_configuration",
            sa.Column(
                "checkin_payment_policy",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'deposit'"),
            ),
        )
    inspector = sa.inspect(op.get_bind())
    if "hotel_configuration" in inspector.get_table_names() and not any(
        constraint.get("name") == "ck_hotel_configuration_checkin_payment_policy"
        for constraint in inspector.get_check_constraints("hotel_configuration")
    ):
        with op.batch_alter_table("hotel_configuration") as batch_op:
            batch_op.create_check_constraint(
                "ck_hotel_configuration_checkin_payment_policy",
                "checkin_payment_policy IN ('deposit', 'total', 'free')",
            )

    reservation_columns = (
        {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reservations")}
        if "reservations" in sa.inspect(op.get_bind()).get_table_names()
        else set()
    )
    if "reservations" in sa.inspect(op.get_bind()).get_table_names():
        new_columns = (
            ("external_paid_amount", sa.Column("external_paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00")),
            ("external_paid_reference", sa.Column("external_paid_reference", sa.String(length=120), nullable=True)),
            ("external_paid_confirmed", sa.Column("external_paid_confirmed", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("external_paid_ever_confirmed", sa.Column("external_paid_ever_confirmed", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("external_paid_confirmed_by_user_id", sa.Column("external_paid_confirmed_by_user_id", sa.Integer(), nullable=True)),
            ("external_paid_confirmed_at", sa.Column("external_paid_confirmed_at", sa.DateTime(), nullable=True)),
        )
        for column_name, column in new_columns:
            if column_name not in reservation_columns:
                op.add_column("reservations", column)
        if not any(
            constraint.get("name") == "ck_reservation_external_paid_nonnegative"
            for constraint in sa.inspect(op.get_bind()).get_check_constraints("reservations")
        ):
            if op.get_bind().dialect.name == "sqlite":
                with op.batch_alter_table("reservations") as batch_op:
                    batch_op.create_check_constraint(
                        "ck_reservation_external_paid_nonnegative",
                        "external_paid_amount >= 0",
                    )
            else:
                op.create_check_constraint(
                    "ck_reservation_external_paid_nonnegative",
                    "reservations",
                    "external_paid_amount >= 0",
                )
    inspector = sa.inspect(op.get_bind())
    if "transactions" in inspector.get_table_names():
        transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "manual_reference" not in transaction_columns:
            op.add_column("transactions", sa.Column("manual_reference", sa.String(length=120), nullable=True))
        if "refund_of_transaction_id" not in transaction_columns:
            op.add_column("transactions", sa.Column("refund_of_transaction_id", sa.Integer(), nullable=True))
        if "refund_reason" not in transaction_columns:
            op.add_column("transactions", sa.Column("refund_reason", sa.String(length=240), nullable=True))

    inspector = sa.inspect(op.get_bind())
    if (
        op.get_bind().dialect.name == "postgresql"
        and _has_columns("transactions", {"hotel_id", "refund_of_transaction_id"})
        and not any(
            foreign_key.get("name") == "fk_transactions_refund_source_same_hotel"
            for foreign_key in inspector.get_foreign_keys("transactions")
        )
    ):
        # The production migration chain guarantees the composite target key.
        # Keep this FK PostgreSQL-only: SQLite requires a table rebuild, and a
        # self-referential FK during that rebuild makes DROP TABLE fail when
        # foreign_keys enforcement is enabled. SQLite tests create their schema
        # from ORM metadata, which includes the same FK.
        op.create_foreign_key(
            "fk_transactions_refund_source_same_hotel",
            "transactions",
            "transactions",
            ["hotel_id", "refund_of_transaction_id"],
            ["hotel_id", "id"],
            ondelete="RESTRICT",
        )

    if (
        _has_columns("transactions", {"hotel_id", "refund_of_transaction_id", "status"})
        and "ix_transactions_refund_source_status" not in _indexes("transactions")
    ):
        op.create_index(
            "ix_transactions_refund_source_status",
            "transactions",
            ["hotel_id", "refund_of_transaction_id", "status"],
        )

    if (
        _has_columns("transactions", {"hotel_id", "reservation_id", "manual_reference"})
        and "uq_transactions_manual_reference_hotel_method" not in _indexes("transactions")
    ):
        op.create_index(
            "uq_transactions_manual_reference_hotel_method",
            "transactions",
            ["hotel_id", "payment_method", sa.text("lower(manual_reference)")],
            unique=True,
            sqlite_where=sa.text("manual_reference IS NOT NULL"),
            postgresql_where=sa.text("manual_reference IS NOT NULL"),
        )


def downgrade() -> None:
    reservation_columns = (
        {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reservations")}
        if "reservations" in sa.inspect(op.get_bind()).get_table_names()
        else set()
    )
    if "external_paid_amount" in reservation_columns:
        has_external_credit = op.get_bind().execute(
            sa.text(
                "SELECT 1 FROM reservations WHERE external_paid_amount > 0 "
                "OR external_paid_reference IS NOT NULL OR external_paid_confirmed = TRUE "
                "OR external_paid_ever_confirmed = TRUE LIMIT 1"
            )
        ).first()
        if has_external_credit:
            raise RuntimeError(
                "Refusing downgrade: external OTA payment evidence exists; restore a verified backup instead."
            )

    transaction_columns_for_loss_check = (
        {column["name"] for column in sa.inspect(op.get_bind()).get_columns("transactions")}
        if "transactions" in sa.inspect(op.get_bind()).get_table_names()
        else set()
    )
    if {"manual_reference", "refund_of_transaction_id", "refund_reason"}.issubset(transaction_columns_for_loss_check):
        has_payment_audit = op.get_bind().execute(
            sa.text(
                "SELECT 1 FROM transactions WHERE manual_reference IS NOT NULL "
                "OR refund_of_transaction_id IS NOT NULL OR refund_reason IS NOT NULL LIMIT 1"
            )
        ).first()
        if has_payment_audit:
            raise RuntimeError(
                "Refusing downgrade: manual payment or refund audit data exists; restore a verified backup instead."
            )

    if "ix_transactions_refund_source_status" in _indexes("transactions"):
        op.drop_index("ix_transactions_refund_source_status", table_name="transactions")
    if "uq_transactions_manual_reference_hotel_method" in _indexes("transactions"):
        op.drop_index("uq_transactions_manual_reference_hotel_method", table_name="transactions")

    inspector = sa.inspect(op.get_bind())
    transaction_columns = (
        {column["name"] for column in inspector.get_columns("transactions")}
        if "transactions" in inspector.get_table_names()
        else set()
    )
    transaction_fks = (
        inspector.get_foreign_keys("transactions") if "transactions" in inspector.get_table_names() else []
    )
    if "transactions" in inspector.get_table_names() and (
        "fk_transactions_refund_source_same_hotel" in {fk.get("name") for fk in transaction_fks}
        or {"refund_of_transaction_id", "refund_reason", "manual_reference"} & transaction_columns
    ):
        with op.batch_alter_table("transactions") as batch_op:
            if (
                op.get_bind().dialect.name == "postgresql"
                and "fk_transactions_refund_source_same_hotel" in {fk.get("name") for fk in transaction_fks}
            ):
                batch_op.drop_constraint("fk_transactions_refund_source_same_hotel", type_="foreignkey")
            for column_name in ("refund_of_transaction_id", "refund_reason", "manual_reference"):
                if column_name in transaction_columns:
                    batch_op.drop_column(column_name)

    inspector = sa.inspect(op.get_bind())
    if "hotel_configuration" in inspector.get_table_names() and any(
        constraint.get("name") == "ck_hotel_configuration_checkin_payment_policy"
        for constraint in inspector.get_check_constraints("hotel_configuration")
    ):
        with op.batch_alter_table("hotel_configuration") as batch_op:
            batch_op.drop_constraint("ck_hotel_configuration_checkin_payment_policy", type_="check")
    inspector = sa.inspect(op.get_bind())
    if "hotel_configuration" in inspector.get_table_names() and "checkin_payment_policy" in {
        column["name"] for column in inspector.get_columns("hotel_configuration")
    }:
        op.drop_column("hotel_configuration", "checkin_payment_policy")
    if "reservations" in sa.inspect(op.get_bind()).get_table_names():
        reservation_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reservations")}
        if "ck_reservation_external_paid_nonnegative" in {
            constraint.get("name") for constraint in sa.inspect(op.get_bind()).get_check_constraints("reservations")
        }:
            if op.get_bind().dialect.name == "sqlite":
                with op.batch_alter_table("reservations") as batch_op:
                    batch_op.drop_constraint("ck_reservation_external_paid_nonnegative", type_="check")
            else:
                op.drop_constraint("ck_reservation_external_paid_nonnegative", "reservations", type_="check")
        if reservation_columns & {
            "external_paid_amount", "external_paid_reference", "external_paid_confirmed",
            "external_paid_ever_confirmed", "external_paid_confirmed_by_user_id",
            "external_paid_confirmed_at",
        }:
            with op.batch_alter_table("reservations") as batch_op:
                for column_name in (
                    "external_paid_confirmed_at", "external_paid_confirmed_by_user_id",
                    "external_paid_ever_confirmed", "external_paid_confirmed",
                    "external_paid_reference", "external_paid_amount",
                ):
                    if column_name in reservation_columns:
                        batch_op.drop_column(column_name)
