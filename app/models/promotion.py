"""
Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first
pricing/promotions task, Task 3).

Design decisions (see knowledge/10-context/backend.md for the wider pricing
context pack):

- Typed conditions only. Rather than a separate ``PromotionCondition`` child
  table (join + its own versioning) or a JSON blob of arbitrary logic, every
  condition is a nullable, typed column directly on the promotion row. A NULL
  column is a wildcard ("no restriction on this dimension"); every non-NULL
  column must match for the promotion to apply to a given night. This is the
  simplest typed representation that still forbids free-form
  formulas/expressions.
- Versioning: a promotion row is immutable once created. Editing a promotion
  creates a NEW row with ``version`` incremented and ``previous_version_id``
  pointing at the row it replaces; the previous row is deactivated. Existing
  reservations reference a promotion by its concrete row id (frozen into the
  reservation's pricing_snapshot JSON), so later edits/deactivations can never
  change an already-booked reservation's stored total.
- ``priority``: higher wins on conflict, matching the existing
  ``PricePeriod.priority`` convention in app/models/daily_rate.py (higher
  number = higher priority).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PromotionBenefitTypeEnum(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class PromotionScopeEnum(str, enum.Enum):
    FULL_STAY = "full_stay"
    FROM_NIGHT_N = "from_night_n"


class Promotion(Base):
    """A versioned, hotel-scoped promotional discount rule.

    One row = one immutable version. ``code`` is the stable identity shared
    across versions of the same promotion within a hotel.
    """

    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)

    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    benefit_type = Column(
        Enum(
            PromotionBenefitTypeEnum,
            name="promotion_benefit_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    # For PERCENTAGE, 0-100. For FIXED, a money amount in the hotel's currency.
    benefit_value = Column(Numeric(12, 4), nullable=False)

    scope = Column(
        Enum(
            PromotionScopeEnum,
            name="promotion_scope_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PromotionScopeEnum.FULL_STAY,
    )
    # Required (>=1) when scope == FROM_NIGHT_N: the promo applies from the
    # Nth night of the stay onward (1-based).
    from_night_number = Column(Integer, nullable=True)

    priority = Column(Integer, nullable=False, default=0)  # higher wins on conflict
    stackable = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # --- Versioning -------------------------------------------------------
    version = Column(Integer, nullable=False, default=1)
    # Composite (hotel_id, previous_version_id), not a scalar FK: a promotion
    # must never claim to supersede a version belonging to another hotel.
    previous_version_id = Column(Integer, nullable=True)

    # --- Typed conditions (NULL = wildcard, all non-NULL must match) ------
    booking_from = Column(Date, nullable=True)  # reservation creation date range
    booking_to = Column(Date, nullable=True)
    stay_from = Column(Date, nullable=True)     # stay/night date range
    stay_to = Column(Date, nullable=True)
    min_nights = Column(Integer, nullable=True)
    max_nights = Column(Integer, nullable=True)
    weekdays_mask = Column(Integer, nullable=True)  # bit0=Mon .. bit6=Sun
    category_id = Column(Integer, nullable=True)
    room_id = Column(Integer, nullable=True)
    sales_channel_code = Column(String(50), nullable=True)
    guest_id = Column(Integer, nullable=True)
    company_id = Column(Integer, nullable=True)
    guest_tag_type = Column(String(30), nullable=True)  # matches GuestTagTypeEnum value
    payment_currency = Column(String(3), nullable=True)
    payment_method = Column(String(50), nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", "version", name="uq_promotion_hotel_code_version"),
        UniqueConstraint("hotel_id", "id", name="uq_promotion_hotel_id_id"),
        Index("ix_promotion_hotel_code", "hotel_id", "code"),
        Index("ix_promotion_hotel_active", "hotel_id", "is_active"),
        ForeignKeyConstraint(
            ["hotel_id", "previous_version_id"], ["promotions.hotel_id", "promotions.id"],
            name="fk_promotions_hotel_previous_version", ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "category_id"], ["room_categories.hotel_id", "room_categories.id"],
            name="fk_promotions_hotel_category", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "room_id"], ["rooms.hotel_id", "rooms.id"],
            name="fk_promotions_hotel_room", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_promotions_hotel_guest", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_promotions_hotel_company", ondelete="CASCADE",
        ),
    )

    def __repr__(self) -> str:
        return f"<Promotion(id={self.id}, hotel_id={self.hotel_id}, code={self.code!r}, v{self.version})>"
