"""Harden core hotel-scoped relationships with tenant-leading keys.

The application already scopes these records with ``hotel_id`` and PostgreSQL
RLS.  A scalar FK can nevertheless point at a record belonging to another
hotel.  These composite constraints make the database reject that mismatch at
the write boundary.  The migration is intentionally PostgreSQL-only: the
production authority is Supabase/PostgreSQL, while SQLite remains a local
test dialect whose schema is created from the ORM metadata.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_core_tenant_composite_fks"
down_revision: Union[str, None] = "20260724_payment_proof_blobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UNIQUE_TARGETS = (
    ("room_categories", "uq_room_category_hotel_id_id"),
    ("rooms", "uq_room_hotel_id_id"),
    ("guests", "uq_guest_hotel_id_id"),
    ("companies", "uq_companies_hotel_id_id"),
    ("sellable_products", "uq_sellable_product_hotel_id_id"),
    ("rate_plans", "uq_rate_plan_hotel_id_id"),
    ("tax_policies", "uq_tax_policy_hotel_id_id"),
    ("reservations", "uq_reservation_hotel_id_id"),
    ("transactions", "uq_transaction_hotel_id_id"),
    ("cash_sessions", "uq_cash_sessions_hotel_id_id"),
    ("cash_close_reports", "uq_cash_close_reports_hotel_id_id"),
    ("stock_items", "uq_stock_items_hotel_id_id"),
    ("stock_locations", "uq_stock_locations_hotel_id_id"),
    ("payment_links", "uq_payment_link_hotel_id_id"),
    ("payments", "uq_payment_hotel_id_id"),
    ("payment_proofs", "uq_payment_proofs_hotel_id_id"),
    ("payment_proof_blobs", "uq_payment_proof_blobs_hotel_id_id"),
)


COMPOSITE_FKS = (
    ("rooms", "fk_rooms_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), None),
    ("sellable_products", "fk_sellable_products_hotel_primary_category", ("hotel_id", "primary_room_category_id"), "room_categories", ("hotel_id", "id"), None),
    ("product_room_compatibility", "fk_product_room_compatibility_hotel_product", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id"), "CASCADE"),
    ("product_room_compatibility", "fk_product_room_compatibility_hotel_category", ("hotel_id", "room_category_id"), "room_categories", ("hotel_id", "id"), "CASCADE"),
    ("rate_plans", "fk_rate_plans_hotel_sellable_product", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id"), "CASCADE"),
    ("rate_plan_prices", "fk_rate_plan_prices_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), "CASCADE"),
    ("tax_rules", "fk_tax_rules_hotel_tax_policy", ("hotel_id", "tax_policy_id"), "tax_policies", ("hotel_id", "id"), "CASCADE"),
    ("reservations", "fk_reservations_hotel_guest", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_company", ("hotel_id", "company_id"), "companies", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_sellable_product", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), None),
    ("reservations", "fk_reservations_hotel_tax_policy", ("hotel_id", "tax_policy_id"), "tax_policies", ("hotel_id", "id"), None),
    ("transactions", "fk_transactions_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("payments", "fk_payments_hotel_payment_link", ("hotel_id", "payment_link_id"), "payment_links", ("hotel_id", "id"), None),
    ("payment_proofs", "fk_payment_proofs_hotel_transaction", ("hotel_id", "transaction_id"), "transactions", ("hotel_id", "id"), None),
    ("payment_proof_blobs", "fk_payment_proof_blobs_hotel_proof", ("hotel_id", "proof_id"), "payment_proofs", ("hotel_id", "id"), "CASCADE"),
    ("cash_movements", "fk_cash_movements_hotel_session", ("hotel_id", "session_id"), "cash_sessions", ("hotel_id", "id"), "CASCADE"),
    ("cash_movements", "fk_cash_movements_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("cash_movements", "fk_cash_movements_hotel_transaction", ("hotel_id", "transaction_id"), "transactions", ("hotel_id", "id"), None),
    ("cash_close_reports", "fk_cash_close_reports_hotel_session", ("hotel_id", "session_id"), "cash_sessions", ("hotel_id", "id"), "CASCADE"),
    ("cash_close_reports", "fk_cash_close_reports_hotel_successor_session", ("hotel_id", "successor_session_id"), "cash_sessions", ("hotel_id", "id"), None),
    ("cash_custody_handoffs", "fk_cash_custody_handoffs_hotel_close_report", ("hotel_id", "close_report_id"), "cash_close_reports", ("hotel_id", "id"), "CASCADE"),
    ("stock_movements", "fk_stock_movements_hotel_item", ("hotel_id", "item_id"), "stock_items", ("hotel_id", "id"), "CASCADE"),
    ("stock_movements", "fk_stock_movements_hotel_location", ("hotel_id", "location_id"), "stock_locations", ("hotel_id", "id"), None),
    ("stock_movements", "fk_stock_movements_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("guest_tags", "fk_guest_tags_hotel_guest", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id"), "CASCADE"),
    ("fact_reservation_daily", "fk_fact_reservation_daily_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("fact_reservation_daily", "fk_fact_reservation_daily_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("fact_reservation_daily", "fk_fact_reservation_daily_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), None),
    ("fact_reservation_daily", "fk_fact_reservation_daily_hotel_company", ("hotel_id", "company_id"), "companies", ("hotel_id", "id"), None),
    ("fact_room_occupancy_daily", "fk_fact_room_occupancy_daily_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("fact_room_occupancy_daily", "fk_fact_room_occupancy_daily_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), None),
    ("fact_room_occupancy_daily", "fk_fact_room_occupancy_daily_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
)


def _has_unique(inspector, table_name: str, columns: tuple[str, ...]) -> bool:
    wanted = list(columns)
    return any(item.get("column_names") == wanted for item in inspector.get_unique_constraints(table_name)) or any(
        item.get("unique") and item.get("column_names") == wanted
        for item in inspector.get_indexes(table_name)
    )


def _has_fk(inspector, table_name: str, columns: tuple[str, ...], referred_table: str, referred_columns: tuple[str, ...]) -> bool:
    return any(
        item.get("constrained_columns") == list(columns)
        and item.get("referred_table") == referred_table
        and item.get("referred_columns") == list(referred_columns)
        for item in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table_name, constraint_name in UNIQUE_TARGETS:
        if not _has_unique(inspector, table_name, ("hotel_id", "id")):
            op.create_unique_constraint(constraint_name, table_name, ["hotel_id", "id"])

    for table_name, constraint_name, columns, referred_table, referred_columns, ondelete in COMPOSITE_FKS:
        if _has_fk(inspector, table_name, columns, referred_table, referred_columns):
            continue
        kwargs = {"ondelete": ondelete} if ondelete else {}
        op.create_foreign_key(
            constraint_name,
            table_name,
            referred_table,
            list(columns),
            list(referred_columns),
            **kwargs,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table_name, constraint_name, columns, referred_table, referred_columns, _ in reversed(COMPOSITE_FKS):
        for item in inspector.get_foreign_keys(table_name):
            if (
                item.get("name") == constraint_name
                and item.get("constrained_columns") == list(columns)
                and item.get("referred_table") == referred_table
                and item.get("referred_columns") == list(referred_columns)
            ):
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
                break

    inspector = sa.inspect(bind)
    for table_name, constraint_name in reversed(UNIQUE_TARGETS):
        if any(item.get("name") == constraint_name for item in inspector.get_unique_constraints(table_name)):
            op.drop_constraint(constraint_name, table_name, type_="unique")
