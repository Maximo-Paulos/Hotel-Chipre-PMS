"""Auditable custody records for linen differences reported on laundry remitos.

Discrepancy rows are intentionally separate from ``LinenMovement``. A quantity
reported as missing or returned in excess is not available hotel stock until a
person with the dedicated permission confirms how it should be reconciled.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class LaundryRemitoDiscrepancy(Base):
    __tablename__ = "laundry_remito_discrepancies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", name="fk_laundry_discrepancies_hotel_id"),
        nullable=False,
    )
    remito_id = Column(Integer, nullable=False)
    remito_line_id = Column(Integer, nullable=False)
    vendor_id = Column(Integer, nullable=False)
    linen_item_id = Column(Integer, nullable=False)
    discrepancy_type = Column(String(24), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    remaining_quantity = Column(Numeric(12, 2), nullable=False)
    # For a shortage this is the ledger location whose balance is disputed,
    # not a claim that the linen is physically there. custody_location_id is
    # null until an authorized reviewer confirms physical custody.
    source_location_id = Column(Integer, nullable=False)
    custody_location_id = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_reason = Column(Text, nullable=True)
    resolution_code = Column(String(80), nullable=True)
    resolution_reason = Column(Text, nullable=True)
    resolution_amount = Column(Numeric(12, 2), nullable=True)
    resolution_currency_code = Column(String(3), nullable=True)
    resolution_recorded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_recorded_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    returned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    returned_at = Column(DateTime, nullable=True)
    return_reason = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "discrepancy_type IN ('excess_return', 'short_return')",
            name="ck_laundry_discrepancy_type_valid",
        ),
        CheckConstraint(
            "status IN ('pending_approval', 'pending_identification', 'pending_review', "
            "'pending_resolution', 'pending_claim', 'awaiting_replacement', 'resolved', "
            "'return_to_laundry', 'returned_to_laundry')",
            name="ck_laundry_discrepancy_status_valid",
        ),
        CheckConstraint("quantity > 0", name="ck_laundry_discrepancy_quantity_positive"),
        CheckConstraint(
            "remaining_quantity >= 0 AND remaining_quantity <= quantity",
            name="ck_laundry_discrepancy_remaining_quantity_valid",
        ),
        CheckConstraint(
            "(resolution_amount IS NULL AND resolution_currency_code IS NULL) OR "
            "(resolution_amount > 0 AND length(resolution_currency_code) = 3 "
            "AND resolution_currency_code = upper(resolution_currency_code))",
            name="ck_laundry_discrepancy_resolution_credit_valid",
        ),
        CheckConstraint(
            "(discrepancy_type = 'excess_return' AND status NOT IN ('pending_review', 'pending_resolution', "
            "'pending_claim', 'awaiting_replacement')) "
            "OR (discrepancy_type = 'short_return' AND status NOT IN "
            "('pending_approval', 'pending_identification', 'return_to_laundry', 'returned_to_laundry'))",
            name="ck_laundry_discrepancy_type_status_compatible",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_laundry_discrepancies_hotel_id_id"),
        UniqueConstraint(
            "hotel_id", "remito_line_id", "discrepancy_type",
            name="uq_laundry_discrepancies_line_type",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "remito_id"],
            ["laundry_remitos.hotel_id", "laundry_remitos.id"],
            name="fk_laundry_discrepancies_hotel_remito",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "remito_line_id"],
            ["laundry_remito_lines.hotel_id", "laundry_remito_lines.id"],
            name="fk_laundry_discrepancies_hotel_remito_line",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "vendor_id"],
            ["laundry_vendors.hotel_id", "laundry_vendors.id"],
            name="fk_laundry_discrepancies_hotel_vendor",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "linen_item_id"],
            ["linen_items.hotel_id", "linen_items.id"],
            name="fk_laundry_discrepancies_hotel_item",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "source_location_id"],
            ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_laundry_discrepancies_hotel_source_location",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "custody_location_id"],
            ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_laundry_discrepancies_hotel_custody_location",
        ),
        Index("ix_laundry_discrepancies_hotel_status", "hotel_id", "status"),
        Index("ix_laundry_discrepancies_hotel_item", "hotel_id", "linen_item_id"),
    )


class LaundryDiscrepancyAction(Base):
    """Immutable action history and hotel-scoped idempotency for discrepancy decisions."""

    __tablename__ = "laundry_discrepancy_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", name="fk_laundry_discrepancy_actions_hotel_id"),
        nullable=False,
    )
    discrepancy_id = Column(Integer, nullable=False)
    action_type = Column(String(32), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=True)
    resolution_code = Column(String(80), nullable=True)
    resolution_amount = Column(Numeric(12, 2), nullable=True)
    resolution_currency_code = Column(String(3), nullable=True)
    remito_id = Column(Integer, nullable=True)
    remito_line_id = Column(Integer, nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('approval', 'resolution', 'return_to_laundry', 'claim_return', 'replacement_receipt')",
            name="ck_laundry_discrepancy_action_type_valid",
        ),
        CheckConstraint("length(trim(idempotency_key)) > 0", name="ck_laundry_discrepancy_action_key_nonempty"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_laundry_discrepancy_action_reason_nonempty"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_laundry_discrepancy_action_quantity_positive"),
        CheckConstraint(
            "(resolution_amount IS NULL AND resolution_currency_code IS NULL) OR "
            "(resolution_amount > 0 AND length(resolution_currency_code) = 3 "
            "AND resolution_currency_code = upper(resolution_currency_code))",
            name="ck_laundry_discrepancy_action_credit_valid",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "discrepancy_id"],
            ["laundry_remito_discrepancies.hotel_id", "laundry_remito_discrepancies.id"],
            name="fk_laundry_discrepancy_actions_hotel_discrepancy",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "remito_id"],
            ["laundry_remitos.hotel_id", "laundry_remitos.id"],
            name="fk_laundry_discrepancy_actions_hotel_remito",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "remito_line_id"],
            ["laundry_remito_lines.hotel_id", "laundry_remito_lines.id"],
            name="fk_laundry_discrepancy_actions_hotel_remito_line",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_laundry_discrepancy_actions_hotel_id_id"),
        UniqueConstraint("hotel_id", "idempotency_key", name="uq_laundry_discrepancy_actions_hotel_key"),
        Index("ix_laundry_discrepancy_actions_hotel_discrepancy", "hotel_id", "discrepancy_id", "created_at"),
    )
