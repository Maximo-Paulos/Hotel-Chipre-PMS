"""Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, and task photos.

Revision ID: d2a7e93f4c2b
Revises: 20261017_manual_ota_paid_currency
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d2a7e93f4c2b"
down_revision: Union[str, None] = "20261017_manual_ota_paid_currency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RLS_TABLES = (
    "reservation_group_payment_batches",
    "reservation_group_payment_allocations",
    "cash_expenses",
    "rate_change_drafts",
    "operational_task_attachments",
)


def _install_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table_name in _RLS_TABLES:
        op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(
            f'''CREATE POLICY "tenant_isolation_{table_name}" ON "{table_name}"
               USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
               WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def _remove_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table_name in reversed(_RLS_TABLES):
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
        op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def _assert_no_duplicate_remitos(connection) -> None:
    # Keep this normalization frozen with the migration. Do not import the
    # runtime helper: future service refactors must not change old migrations.
    tables = set(sa.inspect(connection).get_table_names())
    if "laundry_remitos" not in tables:
        return
    rows = connection.execute(
        sa.text(
            "SELECT id, hotel_id, vendor_id, direction, remito_number "
            "FROM laundry_remitos ORDER BY hotel_id, vendor_id, direction, id"
        )
    ).mappings().all()
    grouped: dict[tuple[object, object, object, str], list[dict[str, object]]] = {}
    for row in rows:
        number = str(row["remito_number"]).strip()
        grouped.setdefault((row["hotel_id"], row["vendor_id"], row["direction"], number), []).append(dict(row))
    report = []
    for key, matching_rows in sorted(grouped.items(), key=lambda item: item[0]):
        number = key[3]
        if len(matching_rows) < 2 and all(str(row["remito_number"]) == number for row in matching_rows):
            continue
        report.append((key, [row["id"] for row in matching_rows]))
    if report:
        lines = [
            "Hay remitos duplicados o números con espacios externos. "
            "Corregí los registros informados antes de aplicar la unicidad:",
            "hotel_id | vendor_id | direction | remito_number | count | row_ids",
        ]
        lines.extend(
            "{} | {} | {} | {} | {} | {}".format(
                key[0], key[1], key[2], key[3], len(row_ids), ",".join(str(row_id) for row_id in row_ids)
            )
            for key, row_ids in report
        )
        raise RuntimeError("\n".join(lines))


def _guard_day2_downgrade_data(bind) -> None:
    """Refuse rollback when it would discard operational data or session state."""
    if bind.dialect.name == "postgresql":
        # FORCE RLS must not make a destructive downgrade guard see an empty
        # table. PostgreSQL raises if the migration role cannot inspect rows.
        bind.execute(sa.text("SET LOCAL row_security = off"))

    checks = (
        ("reservation_group_payment_batches", "SELECT 1 FROM reservation_group_payment_batches LIMIT 1"),
        ("reservation_group_payment_allocations", "SELECT 1 FROM reservation_group_payment_allocations LIMIT 1"),
        ("cash_expenses", "SELECT 1 FROM cash_expenses LIMIT 1"),
        ("rate_change_drafts", "SELECT 1 FROM rate_change_drafts LIMIT 1"),
        ("operational_task_attachments", "SELECT 1 FROM operational_task_attachments LIMIT 1"),
        (
            "group payment transaction links",
            "SELECT 1 FROM transactions WHERE group_payment_batch_id IS NOT NULL LIMIT 1",
        ),
        (
            "session recovery state",
            "SELECT 1 FROM user_sessions WHERE previous_session_token_hash IS NOT NULL "
            "OR previous_token_rotated_at IS NOT NULL LIMIT 1",
        ),
        (
            "fiscal hotel profile",
            "SELECT 1 FROM hotel_configuration WHERE fiscal_legal_name IS NOT NULL "
            "OR fiscal_tax_id IS NOT NULL OR fiscal_vat_condition IS NOT NULL "
            "OR fiscal_address IS NOT NULL OR fiscal_point_of_sale IS NOT NULL LIMIT 1",
        ),
    )
    losses = [label for label, query in checks if bind.execute(sa.text(query)).first() is not None]
    if losses:
        raise RuntimeError(
            "Refusing to downgrade Day 2 schema because it would discard persisted data: "
            + ", ".join(losses)
            + ". Preserve or export this operational data before rollback."
        )


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "hotel_configuration" in existing_tables:
        existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
        for name, column in (
            ("fiscal_legal_name", sa.Column("fiscal_legal_name", sa.String(200), nullable=True)),
            ("fiscal_tax_id", sa.Column("fiscal_tax_id", sa.String(20), nullable=True)),
            ("fiscal_vat_condition", sa.Column("fiscal_vat_condition", sa.String(40), nullable=True)),
            ("fiscal_address", sa.Column("fiscal_address", sa.String(300), nullable=True)),
            ("fiscal_point_of_sale", sa.Column("fiscal_point_of_sale", sa.Integer(), nullable=True)),
        ):
            if name not in existing_columns:
                op.add_column("hotel_configuration", column)

    if "user_sessions" in existing_tables:
        user_session_columns = {column["name"] for column in sa.inspect(bind).get_columns("user_sessions")}
        if "previous_session_token_hash" not in user_session_columns:
            op.add_column("user_sessions", sa.Column("previous_session_token_hash", sa.String(64), nullable=True))
        if "previous_token_rotated_at" not in user_session_columns:
            op.add_column("user_sessions", sa.Column("previous_token_rotated_at", sa.DateTime(timezone=True), nullable=True))
        user_session_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("user_sessions")}
        if "ix_user_sessions_previous_token" not in user_session_indexes:
            op.create_index(
                "ix_user_sessions_previous_token",
                "user_sessions",
                ["previous_session_token_hash", "previous_token_rotated_at"],
            )

    if "reservation_group_payment_batches" not in existing_tables:
        op.create_table(
            "reservation_group_payment_batches",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(100), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("received_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "currency",
                sa.String(3),
                nullable=False,
            ),
            sa.Column(
                "payment_method",
                sa.Enum(
                    "cash", "mercado_pago", "paypal", "credit_card", "debit_card", "bank_transfer",
                    name="reservation_group_payment_method_enum",
                    native_enum=True,
                    create_constraint=True,
                ),
                nullable=False,
            ),
            sa.Column("manual_reference", sa.String(120), nullable=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "group_id"], ["reservation_groups.hotel_id", "reservation_groups.id"],
                name="fk_reservation_group_payment_batches_hotel_group", ondelete="CASCADE",
            ),
            sa.UniqueConstraint("hotel_id", "id", name="uq_reservation_group_payment_batches_hotel_id_id"),
            sa.UniqueConstraint(
                "hotel_id", "idempotency_key", name="uq_reservation_group_payment_batches_idempotency"
            ),
        )
        op.create_index(
            "ix_reservation_group_payment_batches_group_created",
            "reservation_group_payment_batches",
            ["hotel_id", "group_id", "created_at"],
        )

    if "transactions" in existing_tables:
        transaction_columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
        if "group_payment_batch_id" not in transaction_columns:
            with op.batch_alter_table("transactions") as batch:
                batch.add_column(sa.Column("group_payment_batch_id", sa.Integer(), nullable=True))
                batch.create_foreign_key(
                    "fk_transactions_hotel_group_payment_batch",
                    "reservation_group_payment_batches",
                    ["hotel_id", "group_payment_batch_id"],
                    ["hotel_id", "id"],
                    ondelete="RESTRICT",
                )

    if "reservation_group_payment_allocations" not in existing_tables:
        op.create_table(
            "reservation_group_payment_allocations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("batch_id", sa.Integer(), nullable=False),
            sa.Column("reservation_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("received_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["hotel_id", "batch_id"],
                ["reservation_group_payment_batches.hotel_id", "reservation_group_payment_batches.id"],
                name="fk_reservation_group_payment_allocations_hotel_batch", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
                name="fk_reservation_group_payment_allocations_hotel_reservation", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "transaction_id"], ["transactions.hotel_id", "transactions.id"],
                name="fk_reservation_group_payment_allocations_hotel_transaction", ondelete="CASCADE",
            ),
            sa.UniqueConstraint("hotel_id", "batch_id", "reservation_id", name="uq_group_payment_batch_reservation"),
            sa.UniqueConstraint("hotel_id", "transaction_id", name="uq_group_payment_allocation_transaction"),
        )
        op.create_index(
            "ix_group_payment_allocations_hotel_batch",
            "reservation_group_payment_allocations",
            ["hotel_id", "batch_id"],
        )

    if "cash_movements" in existing_tables:
        cash_movement_uniques = {
            tuple(constraint.get("column_names", []))
            for constraint in sa.inspect(bind).get_unique_constraints("cash_movements")
        }
        if ("hotel_id", "id") not in cash_movement_uniques:
            with op.batch_alter_table("cash_movements") as batch:
                batch.create_unique_constraint("uq_cash_movements_hotel_id_id", ["hotel_id", "id"])

    # Some older SQLite migration chains did not materialize this model-level
    # key. The new cash_expenses composite FK needs it on every supported DB.
    if "cash_sessions" in existing_tables:
        cash_session_uniques = {
            tuple(constraint.get("column_names", []))
            for constraint in sa.inspect(bind).get_unique_constraints("cash_sessions")
        }
        if ("hotel_id", "id") not in cash_session_uniques:
            with op.batch_alter_table("cash_sessions") as batch:
                batch.create_unique_constraint("uq_cash_sessions_hotel_id_id", ["hotel_id", "id"])

    if "cash_expenses" not in existing_tables:
        op.create_table(
            "cash_expenses",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency_code", sa.String(3), nullable=False),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("vendor", sa.String(120), nullable=False),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("receipt_reference", sa.String(120), nullable=True),
            sa.Column("receipt_filename", sa.String(255), nullable=True),
            sa.Column("receipt_object_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("cash_movement_id", sa.Integer(), nullable=True),
            sa.Column("recorded_by_user_id", sa.Integer(), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("rejected_by_user_id", sa.Integer(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("amount > 0", name="ck_cash_expenses_amount_positive"),
            sa.CheckConstraint("length(category) > 0", name="ck_cash_expenses_category_nonempty"),
            sa.CheckConstraint("length(vendor) > 0", name="ck_cash_expenses_vendor_nonempty"),
            sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_cash_expenses_status"),
            sa.CheckConstraint(
                "receipt_reference IS NOT NULL OR receipt_object_id IS NOT NULL",
                name="ck_cash_expenses_receipt_required",
            ),
            sa.CheckConstraint(
                "(status = 'approved' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND cash_movement_id IS NOT NULL) OR "
                "(status != 'approved' AND approved_at IS NULL AND approved_by_user_id IS NULL AND cash_movement_id IS NULL)",
                name="ck_cash_expenses_approval_consistent",
            ),
            sa.CheckConstraint(
                "(status = 'rejected' AND rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL AND rejection_reason IS NOT NULL) OR "
                "(status != 'rejected' AND rejected_at IS NULL AND rejected_by_user_id IS NULL AND rejection_reason IS NULL)",
                name="ck_cash_expenses_rejection_consistent",
            ),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "session_id"], ["cash_sessions.hotel_id", "cash_sessions.id"],
                name="fk_cash_expenses_hotel_session", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "receipt_object_id"], ["stored_objects.hotel_id", "stored_objects.id"],
                name="fk_cash_expenses_hotel_receipt_object",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "cash_movement_id"], ["cash_movements.hotel_id", "cash_movements.id"],
                name="fk_cash_expenses_hotel_cash_movement",
            ),
            sa.UniqueConstraint("hotel_id", "id", name="uq_cash_expenses_hotel_id_id"),
            sa.UniqueConstraint("cash_movement_id", name="uq_cash_expenses_cash_movement_id"),
        )
        op.create_index("ix_cash_expenses_hotel_status_created", "cash_expenses", ["hotel_id", "status", "created_at"])
        op.create_index("ix_cash_expenses_hotel_session", "cash_expenses", ["hotel_id", "session_id", "created_at"])

    if "rate_change_drafts" not in existing_tables:
        op.create_table(
            "rate_change_drafts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("draft_type", sa.String(16), nullable=False, server_default="daily_rates"),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("changes", sa.JSON(), nullable=False),
            sa.Column("period_operation", sa.JSON(), nullable=True),
            sa.Column("impact", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
            sa.CheckConstraint("draft_type IN ('daily_rates', 'price_period')", name="ck_rate_change_drafts_type"),
            sa.CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="ck_rate_change_drafts_status"),
            sa.CheckConstraint("version > 0", name="ck_rate_change_drafts_version_positive"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "category_id"], ["room_categories.hotel_id", "room_categories.id"],
                name="fk_rate_change_drafts_hotel_category", ondelete="CASCADE",
            ),
        )
        op.create_index("ix_rate_change_drafts_hotel_status_created", "rate_change_drafts", ["hotel_id", "status", "created_at"])
        op.create_index("ix_rate_change_drafts_hotel_category", "rate_change_drafts", ["hotel_id", "category_id", "created_at"])
        op.create_index(
            "uq_rate_change_drafts_one_open_per_category",
            "rate_change_drafts",
            ["hotel_id", "category_id"],
            unique=True,
            sqlite_where=sa.text("status = 'draft'"),
            postgresql_where=sa.text("status = 'draft'"),
        )

    if "operational_task_attachments" not in existing_tables:
        op.create_table(
            "operational_task_attachments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.Column("stored_object_id", sa.String(36), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(80), nullable=False),
            sa.Column("byte_size", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("byte_size > 0", name="ck_operational_task_attachments_byte_size_positive"),
            sa.CheckConstraint(
                "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
                name="ck_operational_task_attachments_content_type_image",
            ),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["hotel_id", "task_id"], ["operational_tasks.hotel_id", "operational_tasks.id"],
                name="fk_operational_task_attachments_hotel_task", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["hotel_id", "stored_object_id"], ["stored_objects.hotel_id", "stored_objects.id"],
                name="fk_operational_task_attachments_hotel_stored_object", ondelete="CASCADE",
            ),
            sa.UniqueConstraint("hotel_id", "id", name="uq_operational_task_attachments_hotel_id_id"),
        )
        op.create_index(
            "ix_operational_task_attachments_hotel_task_created",
            "operational_task_attachments",
            ["hotel_id", "task_id", "created_at"],
        )

    _assert_no_duplicate_remitos(bind)
    if "laundry_remitos" in existing_tables:
        remito_uniques = {
            tuple(constraint.get("column_names", []))
            for constraint in sa.inspect(bind).get_unique_constraints("laundry_remitos")
        }
        unique_key = ("hotel_id", "vendor_id", "direction", "remito_number")
        if unique_key not in remito_uniques:
            with op.batch_alter_table("laundry_remitos") as batch:
                batch.create_unique_constraint(
                    "uq_laundry_remitos_hotel_vendor_direction_number",
                    list(unique_key),
                )

    _install_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _remove_rls(bind)
    tables = set(sa.inspect(bind).get_table_names())
    _guard_day2_downgrade_data(bind)

    # Remove the transaction reference before dropping its target table. On
    # SQLite, batch_alter_table reflects referenced tables while rebuilding.
    if "transactions" in tables and "group_payment_batch_id" in {
        column["name"] for column in sa.inspect(bind).get_columns("transactions")
    }:
        with op.batch_alter_table("transactions") as batch:
            batch.drop_constraint("fk_transactions_hotel_group_payment_batch", type_="foreignkey")
            batch.drop_column("group_payment_batch_id")

    if "operational_task_attachments" in tables:
        op.drop_table("operational_task_attachments")
    if "rate_change_drafts" in tables:
        op.drop_table("rate_change_drafts")
    if "cash_expenses" in tables:
        op.drop_table("cash_expenses")
    if "reservation_group_payment_allocations" in tables:
        op.drop_table("reservation_group_payment_allocations")
    if "reservation_group_payment_batches" in tables:
        op.drop_table("reservation_group_payment_batches")
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS reservation_group_payment_method_enum")

    if "laundry_remitos" in tables:
        remito_uniques = {
            tuple(constraint.get("column_names", []))
            for constraint in sa.inspect(bind).get_unique_constraints("laundry_remitos")
        }
        if ("hotel_id", "vendor_id", "direction", "remito_number") in remito_uniques:
            with op.batch_alter_table("laundry_remitos") as batch:
                batch.drop_constraint("uq_laundry_remitos_hotel_vendor_direction_number", type_="unique")

    if "hotel_configuration" in tables:
        fiscal_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
        to_drop = [
            column for column in (
                "fiscal_point_of_sale",
                "fiscal_address",
                "fiscal_vat_condition",
                "fiscal_tax_id",
                "fiscal_legal_name",
            ) if column in fiscal_columns
        ]
        if to_drop:
            with op.batch_alter_table("hotel_configuration") as batch:
                for column in to_drop:
                    batch.drop_column(column)

    if "user_sessions" in tables:
        user_session_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("user_sessions")}
        if "ix_user_sessions_previous_token" in user_session_indexes:
            op.drop_index("ix_user_sessions_previous_token", table_name="user_sessions")
        user_session_columns = {column["name"] for column in sa.inspect(bind).get_columns("user_sessions")}
        if {"previous_session_token_hash", "previous_token_rotated_at"} & user_session_columns:
            with op.batch_alter_table("user_sessions") as batch:
                for column in ("previous_token_rotated_at", "previous_session_token_hash"):
                    if column in user_session_columns:
                        batch.drop_column(column)
