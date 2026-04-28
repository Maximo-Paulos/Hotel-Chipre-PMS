"""analytics r1 base schema

Revision ID: 20260424_analytics_r1_base
Revises: 20260421_master_admin_system_owner
Create Date: 2026-04-24 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "20260424_analytics_r1_base"
down_revision: Union[str, Sequence[str], None] = "20260421_master_admin_system_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _analytics_enum(*values: str, name: str, dialect_name: str) -> sa.Enum:
    if dialect_name == "postgresql":
        return pg.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name, create_constraint=True)


def _reservation_status_enum_old(dialect_name: str = "sqlite") -> sa.Enum:
    return _analytics_enum(
        "pending",
        "deposit_paid",
        "fully_paid",
        "checked_in",
        "checked_out",
        "cancelled",
        name="reservation_status_enum",
        dialect_name=dialect_name,
    )


def _reservation_status_enum_new(dialect_name: str = "sqlite") -> sa.Enum:
    return _analytics_enum(
        "pending",
        "deposit_paid",
        "fully_paid",
        "checked_in",
        "checked_out",
        "cancelled",
        "no_show",
        name="reservation_status_enum",
        dialect_name=dialect_name,
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "sqlite"

    def _ensure_enum(enum_type: sa.Enum) -> None:
        if dialect_name == "postgresql":
            enum_type.create(bind, checkfirst=True)

    def enum_(*values: str, name: str) -> sa.Enum:
        return _analytics_enum(*values, name=name, dialect_name=dialect_name)

    _ensure_enum(
        enum_(
            "pending",
            "checked_in",
            "completed",
            "cancelled",
            "no_show",
            name="reservation_outcome_enum",
        )
    )
    _ensure_enum(
        enum_(
            "leisure",
            "business",
            name="reservation_guest_segment_enum",
        )
    )
    _ensure_enum(
        enum_(
            "manual",
            "inferred_from_company",
            "system_default",
            name="reservation_guest_segment_source_enum",
        )
    )
    _ensure_enum(
        enum_(
            "website_direct",
            "whatsapp",
            "phone",
            "walk_in",
            "booking",
            "expedia",
            "despegar",
            "other_ota",
            "other_direct",
            name="reservation_channel_code_enum",
        )
    )
    _ensure_enum(
        enum_(
            "guest_request",
            "payment_failure",
            "overbooking",
            "hotel_issue",
            "weather",
            "other",
            name="reservation_cancellation_reason_code_enum",
        )
    )
    _ensure_enum(
        enum_(
            "none",
            "full_charge",
            "partial_charge",
            "waived",
            name="reservation_no_show_policy_applied_enum",
        )
    )
    _ensure_enum(
        enum_(
            "out_of_service",
            "maintenance",
            "housekeeping_block",
            "renovation",
            name="room_state_event_type_enum",
        )
    )
    _ensure_enum(
        enum_(
            "plumbing",
            "electrical",
            "furniture",
            "deep_clean",
            "inspection",
            "other",
            name="room_state_event_reason_code_enum",
        )
    )
    _ensure_enum(
        enum_(
            "website_direct",
            "whatsapp",
            "phone",
            "walk_in",
            "booking",
            "expedia",
            "despegar",
            "other_ota",
            "other_direct",
            name="fact_reservation_daily_channel_code_enum",
        )
    )
    _ensure_enum(enum_("leisure", "business", name="fact_reservation_daily_guest_segment_enum"))
    _ensure_enum(
        enum_(
            "pending",
            "deposit_paid",
            "fully_paid",
            "checked_in",
            "checked_out",
            "cancelled",
            "no_show",
            name="fact_reservation_daily_status_enum",
        )
    )
    _ensure_enum(
        enum_(
            "pending",
            "checked_in",
            "completed",
            "cancelled",
            "no_show",
            name="fact_reservation_daily_outcome_enum",
        )
    )
    _ensure_enum(
        enum_(
            "occupied",
            "no_show_chargeable",
            "no_show_waived",
            name="fact_reservation_daily_row_kind_enum",
        )
    )
    _ensure_enum(
        enum_(
            "available",
            "occupied",
            "out_of_service",
            "maintenance",
            "housekeeping_block",
            "renovation",
            name="fact_room_occupancy_daily_status_at_night_enum",
        )
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["deactivated_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("hotel_id", "display_name", name="uq_companies_hotel_display_name"),
    )
    op.create_index("ix_companies_hotel_id", "companies", ["hotel_id"], unique=False)
    op.create_index("ix_companies_hotel_active", "companies", ["hotel_id", "is_active"], unique=False)
    op.create_index(
        "uq_companies_hotel_tax_id_not_null",
        "companies",
        ["hotel_id", "tax_id"],
        unique=True,
        sqlite_where=sa.text("tax_id IS NOT NULL"),
        postgresql_where=sa.text("tax_id IS NOT NULL"),
    )

    op.add_column(
        "room_categories",
        sa.Column("variable_cost_per_night", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "hotel_configuration",
        sa.Column("analytics_ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    if dialect_name == "postgresql":
        op.execute("ALTER TYPE reservation_status_enum ADD VALUE IF NOT EXISTS 'no_show'")
        reservation_columns = [
            sa.Column("company_id", sa.Integer(), nullable=True),
            sa.Column(
                "outcome",
                enum_("pending", "checked_in", "completed", "cancelled", "no_show", name="reservation_outcome_enum"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "guest_segment",
                enum_("leisure", "business", name="reservation_guest_segment_enum"),
                nullable=False,
                server_default="leisure",
            ),
            sa.Column(
                "guest_segment_source",
                enum_("manual", "inferred_from_company", "system_default", name="reservation_guest_segment_source_enum"),
                nullable=False,
                server_default="system_default",
            ),
            sa.Column(
                "channel_code",
                enum_(
                    "website_direct",
                    "whatsapp",
                    "phone",
                    "walk_in",
                    "booking",
                    "expedia",
                    "despegar",
                    "other_ota",
                    "other_direct",
                    name="reservation_channel_code_enum",
                ),
                nullable=False,
                server_default="other_direct",
            ),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "cancellation_reason_code",
                enum_("guest_request", "payment_failure", "overbooking", "hotel_issue", "weather", "other", name="reservation_cancellation_reason_code_enum"),
                nullable=True,
            ),
            sa.Column("cancellation_reason_note", sa.String(length=500), nullable=True),
            sa.Column("no_show_confirmed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "no_show_policy_applied",
                enum_("none", "full_charge", "partial_charge", "waived", name="reservation_no_show_policy_applied_enum"),
                nullable=False,
                server_default="none",
            ),
        ]
        for column in reservation_columns:
            op.add_column("reservations", column)
        op.create_foreign_key(
            "fk_reservations_company_id_companies",
            "reservations",
            "companies",
            ["company_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_reservations_cancelled_by_user_id_users",
            "reservations",
            "users",
            ["cancelled_by_user_id"],
            ["id"],
        )
    else:
        with op.batch_alter_table("reservations", recreate="always") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=_reservation_status_enum_old(dialect_name),
                type_=_reservation_status_enum_new(dialect_name),
                existing_nullable=False,
            )
            batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "outcome",
                    enum_("pending", "checked_in", "completed", "cancelled", "no_show", name="reservation_outcome_enum"),
                    nullable=False,
                    server_default="pending",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "guest_segment",
                    enum_("leisure", "business", name="reservation_guest_segment_enum"),
                    nullable=False,
                    server_default="leisure",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "guest_segment_source",
                    enum_("manual", "inferred_from_company", "system_default", name="reservation_guest_segment_source_enum"),
                    nullable=False,
                    server_default="system_default",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "channel_code",
                    enum_(
                        "website_direct",
                        "whatsapp",
                        "phone",
                        "walk_in",
                        "booking",
                        "expedia",
                        "despegar",
                        "other_ota",
                        "other_direct",
                        name="reservation_channel_code_enum",
                    ),
                    nullable=False,
                    server_default="other_direct",
                )
            )
            batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
            batch_op.add_column(sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "cancellation_reason_code",
                    enum_("guest_request", "payment_failure", "overbooking", "hotel_issue", "weather", "other", name="reservation_cancellation_reason_code_enum"),
                    nullable=True,
                )
            )
            batch_op.add_column(sa.Column("cancellation_reason_note", sa.String(length=500), nullable=True))
            batch_op.add_column(sa.Column("no_show_confirmed_at", sa.DateTime(), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "no_show_policy_applied",
                    enum_("none", "full_charge", "partial_charge", "waived", name="reservation_no_show_policy_applied_enum"),
                    nullable=False,
                    server_default="none",
                )
            )
            batch_op.create_foreign_key(
                "fk_reservations_company_id_companies",
                "companies",
                ["company_id"],
                ["id"],
            )
            batch_op.create_foreign_key(
                "fk_reservations_cancelled_by_user_id_users",
                "users",
                ["cancelled_by_user_id"],
                ["id"],
            )

    op.create_table(
        "analytics_alert_settings",
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("cancellation_rate_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default="15.00"),
        sa.Column("commission_gap_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default="25.00"),
        sa.Column("subutilization_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default="40.00"),
        sa.Column("pickup_drop_threshold_pct", sa.Numeric(5, 2), nullable=False, server_default="20.00"),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("hotel_id"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
    )

    op.create_table(
        "analytics_alert_snoozes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("alert_code", sa.String(length=60), nullable=False),
        sa.Column("scope_key", sa.String(length=120), nullable=False),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("hotel_id", "alert_code", "scope_key", name="uq_analytics_alert_snoozes_hotel_alert_scope"),
    )
    op.create_index(
        "ix_analytics_alert_snoozes_hotel_until",
        "analytics_alert_snoozes",
        ["hotel_id", "snooze_until"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_alert_snoozes_hotel_alert_scope",
        "analytics_alert_snoozes",
        ["hotel_id", "alert_code", "scope_key"],
        unique=False,
    )

    _ensure_enum(enum_("xlsx", name="analytics_export_format_enum"))
    _ensure_enum(enum_("ARS", "USD", "BOTH", name="analytics_currency_display_enum"))
    _ensure_enum(enum_("pending", "running", "completed", "failed", "expired", name="analytics_export_status_enum"))

    op.create_table(
        "analytics_export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entity_code", sa.String(length=60), nullable=False),
        sa.Column("card_code", sa.String(length=60), nullable=True),
        sa.Column(
            "format",
            enum_("xlsx", name="analytics_export_format_enum"),
            nullable=False,
        ),
        sa.Column(
            "currency_display",
            enum_("ARS", "USD", "BOTH", name="analytics_currency_display_enum"),
            nullable=False,
        ),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("compare_previous", sa.Boolean(), nullable=False),
        sa.Column("compare_yoy", sa.Boolean(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column(
            "status",
            enum_("pending", "running", "completed", "failed", "expired", name="analytics_export_status_enum"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256_hex", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    op.create_table(
        "analytics_ai_usage_monthly",
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("year_month", sa.CHAR(length=7), nullable=False),
        sa.Column("calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.PrimaryKeyConstraint("hotel_id", "year_month"),
    )

    op.create_table(
        "hotel_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_code", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_hotel_audit_events_hotel_created", "hotel_audit_events", ["hotel_id", "created_at"], unique=False)
    op.create_index("ix_hotel_audit_events_hotel_action", "hotel_audit_events", ["hotel_id", "action_code"], unique=False)
    op.create_index("ix_hotel_audit_events_entity", "hotel_audit_events", ["entity_type", "entity_id"], unique=False)

    op.create_table(
        "room_state_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            enum_(
                "out_of_service",
                "maintenance",
                "housekeeping_block",
                "renovation",
                name="room_state_event_type_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "reason_code",
            enum_(
                "plumbing",
                "electrical",
                "furniture",
                "deep_clean",
                "inspection",
                "other",
                name="room_state_event_reason_code_enum",
            ),
            nullable=False,
        ),
        sa.Column("reason_note", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"]),
    )

    op.create_table(
        "fact_reservation_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column(
            "channel_code",
            enum_(
                "website_direct",
                "whatsapp",
                "phone",
                "walk_in",
                "booking",
                "expedia",
                "despegar",
                "other_ota",
                "other_direct",
                name="fact_reservation_daily_channel_code_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "guest_segment",
            enum_("leisure", "business", name="fact_reservation_daily_guest_segment_enum"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum_(
                "pending",
                "deposit_paid",
                "fully_paid",
                "checked_in",
                "checked_out",
                "cancelled",
                "no_show",
                name="fact_reservation_daily_status_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            enum_(
                "pending",
                "checked_in",
                "completed",
                "cancelled",
                "no_show",
                name="fact_reservation_daily_outcome_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "row_kind",
            enum_(
                "occupied",
                "no_show_chargeable",
                "no_show_waived",
                name="fact_reservation_daily_row_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column("occupied_night", sa.Boolean(), nullable=False),
        sa.Column("chargeable_night", sa.Boolean(), nullable=False),
        sa.Column("revenue_gross_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("revenue_gross_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("revenue_net_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("revenue_net_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("variable_cost_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("variable_cost_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("margin_operating_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("margin_operating_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("source_currency", sa.String(length=3), nullable=False),
        sa.Column("fx_rate_snapshot", sa.Numeric(12, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.UniqueConstraint("hotel_id", "reservation_id", "stay_date", name="uq_fact_reservation_daily_hotel_reservation_date"),
    )
    op.create_index("ix_fact_reservation_daily_hotel_date", "fact_reservation_daily", ["hotel_id", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_reservation", "fact_reservation_daily", ["hotel_id", "reservation_id"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_category_date", "fact_reservation_daily", ["hotel_id", "category_id", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_room_date", "fact_reservation_daily", ["hotel_id", "room_id", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_company_date", "fact_reservation_daily", ["hotel_id", "company_id", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_channel_date", "fact_reservation_daily", ["hotel_id", "channel_code", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_segment_date", "fact_reservation_daily", ["hotel_id", "guest_segment", "stay_date"], unique=False)
    op.create_index("ix_fact_reservation_daily_hotel_outcome_date", "fact_reservation_daily", ["hotel_id", "outcome", "stay_date"], unique=False)

    op.create_table(
        "fact_room_occupancy_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("stay_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column(
            "status_at_night",
            enum_(
                "available",
                "occupied",
                "out_of_service",
                "maintenance",
                "housekeeping_block",
                "renovation",
                name="fact_room_occupancy_daily_status_at_night_enum",
            ),
            nullable=False,
        ),
        sa.Column("is_sellable_night", sa.Boolean(), nullable=False),
        sa.Column("is_occupied", sa.Boolean(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("revenue_net_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("revenue_net_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("margin_operating_ars", sa.Numeric(12, 2), nullable=False),
        sa.Column("margin_operating_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.UniqueConstraint("hotel_id", "room_id", "stay_date", name="uq_fact_room_occupancy_daily_hotel_room_date"),
    )
    op.create_index("ix_fact_room_occupancy_daily_hotel_date", "fact_room_occupancy_daily", ["hotel_id", "stay_date"], unique=False)
    op.create_index("ix_fact_room_occupancy_daily_hotel_room_date", "fact_room_occupancy_daily", ["hotel_id", "room_id", "stay_date"], unique=False)
    op.create_index("ix_fact_room_occupancy_daily_hotel_category_date", "fact_room_occupancy_daily", ["hotel_id", "category_id", "stay_date"], unique=False)
    op.create_index("ix_fact_room_occupancy_daily_hotel_status_date", "fact_room_occupancy_daily", ["hotel_id", "status_at_night", "stay_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fact_room_occupancy_daily_hotel_status_date", table_name="fact_room_occupancy_daily")
    op.drop_index("ix_fact_room_occupancy_daily_hotel_category_date", table_name="fact_room_occupancy_daily")
    op.drop_index("ix_fact_room_occupancy_daily_hotel_room_date", table_name="fact_room_occupancy_daily")
    op.drop_index("ix_fact_room_occupancy_daily_hotel_date", table_name="fact_room_occupancy_daily")
    op.drop_table("fact_room_occupancy_daily")

    op.drop_index("ix_fact_reservation_daily_hotel_outcome_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_segment_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_channel_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_company_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_room_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_category_date", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_reservation", table_name="fact_reservation_daily")
    op.drop_index("ix_fact_reservation_daily_hotel_date", table_name="fact_reservation_daily")
    op.drop_table("fact_reservation_daily")

    op.drop_table("room_state_events")

    op.drop_index("ix_hotel_audit_events_entity", table_name="hotel_audit_events")
    op.drop_index("ix_hotel_audit_events_hotel_action", table_name="hotel_audit_events")
    op.drop_index("ix_hotel_audit_events_hotel_created", table_name="hotel_audit_events")
    op.drop_table("hotel_audit_events")

    op.drop_table("analytics_ai_usage_monthly")

    op.drop_table("analytics_export_jobs")

    op.drop_index("ix_analytics_alert_snoozes_hotel_alert_scope", table_name="analytics_alert_snoozes")
    op.drop_index("ix_analytics_alert_snoozes_hotel_until", table_name="analytics_alert_snoozes")
    op.drop_table("analytics_alert_snoozes")

    op.drop_table("analytics_alert_settings")

    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "sqlite"
    if dialect_name == "postgresql":
        op.drop_constraint("fk_reservations_cancelled_by_user_id_users", "reservations", type_="foreignkey")
        op.drop_constraint("fk_reservations_company_id_companies", "reservations", type_="foreignkey")
        op.drop_column("reservations", "no_show_policy_applied")
        op.drop_column("reservations", "no_show_confirmed_at")
        op.drop_column("reservations", "cancellation_reason_note")
        op.drop_column("reservations", "cancellation_reason_code")
        op.drop_column("reservations", "cancelled_by_user_id")
        op.drop_column("reservations", "cancelled_at")
        op.drop_column("reservations", "channel_code")
        op.drop_column("reservations", "guest_segment_source")
        op.drop_column("reservations", "guest_segment")
        op.drop_column("reservations", "outcome")
        op.drop_column("reservations", "company_id")
    else:
        with op.batch_alter_table("reservations", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_reservations_cancelled_by_user_id_users", type_="foreignkey")
            batch_op.drop_constraint("fk_reservations_company_id_companies", type_="foreignkey")
            batch_op.drop_column("no_show_policy_applied")
            batch_op.drop_column("no_show_confirmed_at")
            batch_op.drop_column("cancellation_reason_note")
            batch_op.drop_column("cancellation_reason_code")
            batch_op.drop_column("cancelled_by_user_id")
            batch_op.drop_column("cancelled_at")
            batch_op.drop_column("channel_code")
            batch_op.drop_column("guest_segment_source")
            batch_op.drop_column("guest_segment")
            batch_op.drop_column("outcome")
            batch_op.drop_column("company_id")

    op.drop_index("uq_companies_hotel_tax_id_not_null", table_name="companies")
    op.drop_index("ix_companies_hotel_active", table_name="companies")
    op.drop_index("ix_companies_hotel_id", table_name="companies")
    op.drop_table("companies")

    op.drop_column("hotel_configuration", "analytics_ai_enabled")
    op.drop_column("room_categories", "variable_cost_per_night")
