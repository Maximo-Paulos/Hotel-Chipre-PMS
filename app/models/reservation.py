"""
Reservation model with strict state machine.
States: pending â†’ deposit_paid â†’ fully_paid â†’ checked_in â†’ checked_out
                                                â†— (skip deposit)
Also supports: cancelled (from any pre-checkin state)
"""
import enum
from sqlalchemy import (
    Column, Integer, Float, Numeric, String, ForeignKey, Enum, Text, DateTime, Date, Boolean,
    CheckConstraint, ForeignKeyConstraint, UniqueConstraint, Index, Table
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timezone

from app.database import Base


class ReservationStatusEnum(str, enum.Enum):
    PENDING = "pending"
    DEPOSIT_PAID = "deposit_paid"
    FULLY_PAID = "fully_paid"
    PRE_CHECK_IN = "pre_check_in"   # v72 §7.2: docs loaded, waiting for room entry confirmation
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReservationSourceEnum(str, enum.Enum):
    DIRECT = "direct"            # Walk-in or website
    BOOKING = "booking"          # Booking.com
    EXPEDIA = "expedia"          # Expedia
    OTHER_OTA = "other_ota"


class ReservationOutcomeEnum(str, enum.Enum):
    PENDING = "pending"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReservationGuestSegmentEnum(str, enum.Enum):
    LEISURE = "leisure"
    BUSINESS = "business"


class ReservationGuestSegmentSourceEnum(str, enum.Enum):
    MANUAL = "manual"
    INFERRED_FROM_COMPANY = "inferred_from_company"
    SYSTEM_DEFAULT = "system_default"


class ReservationChannelCodeEnum(str, enum.Enum):
    WEBSITE_DIRECT = "website_direct"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    WALK_IN = "walk_in"
    BOOKING = "booking"
    EXPEDIA = "expedia"
    DESPEGAR = "despegar"
    COMPANY = "company"          # v72 §16.2: corporate / empresa channel
    OTHER_OTA = "other_ota"
    OTHER_DIRECT = "other_direct"


class ReportableOriginEnum(str, enum.Enum):
    """v72 §16.2 reportable origin — the 7 business-level booking origins.

    Derived (not stored) from channel_code + company_id + source. A reservation
    with a company_id is always reported as ``empresa`` regardless of channel.
    """
    MANUAL_RECEPCION = "manual_recepcion"   # Manual recepción (walk-in / phone front-desk)
    TELEFONO = "telefono"                   # Teléfono
    WHATSAPP_BOT = "whatsapp_bot"           # WhatsApp Bot
    WEB_PROPIA = "web_propia"               # Web propia
    BOOKING_MANUAL = "booking_manual"       # Booking manual
    EXPEDIA_MANUAL = "expedia_manual"       # Expedia manual
    EMPRESA = "empresa"                     # Empresa (corporate / company_id set)


def reportable_origin(reservation) -> "ReportableOriginEnum":
    """Derive the BRM §16.2 reportable origin for a reservation.

    Precedence:
      1. If ``company_id`` is set → EMPRESA (overrides channel).
      2. Otherwise map ``channel_code`` to the reportable origin.
      3. Fall back on ``source`` for OTA values when channel is generic.
    """
    if getattr(reservation, "company_id", None):
        return ReportableOriginEnum.EMPRESA

    channel = getattr(reservation, "channel_code", None)
    mapping = {
        ReservationChannelCodeEnum.WALK_IN: ReportableOriginEnum.MANUAL_RECEPCION,
        ReservationChannelCodeEnum.PHONE: ReportableOriginEnum.TELEFONO,
        ReservationChannelCodeEnum.WHATSAPP: ReportableOriginEnum.WHATSAPP_BOT,
        ReservationChannelCodeEnum.WEBSITE_DIRECT: ReportableOriginEnum.WEB_PROPIA,
        ReservationChannelCodeEnum.BOOKING: ReportableOriginEnum.BOOKING_MANUAL,
        ReservationChannelCodeEnum.EXPEDIA: ReportableOriginEnum.EXPEDIA_MANUAL,
        ReservationChannelCodeEnum.COMPANY: ReportableOriginEnum.EMPRESA,
    }
    if channel in mapping:
        return mapping[channel]

    # Generic / OTA channels: fall back on source provider for OTA origins.
    source = getattr(reservation, "source", None)
    if source == ReservationSourceEnum.BOOKING:
        return ReportableOriginEnum.BOOKING_MANUAL
    if source == ReservationSourceEnum.EXPEDIA:
        return ReportableOriginEnum.EXPEDIA_MANUAL

    # other_ota / other_direct / despegar / unknown → default to manual reception.
    return ReportableOriginEnum.MANUAL_RECEPCION


class ReservationCancellationReasonCodeEnum(str, enum.Enum):
    GUEST_REQUEST = "guest_request"
    PAYMENT_FAILURE = "payment_failure"
    OVERBOOKING = "overbooking"
    HOTEL_ISSUE = "hotel_issue"
    WEATHER = "weather"
    OTHER = "other"


class ReservationNoShowPolicyAppliedEnum(str, enum.Enum):
    NONE = "none"
    FULL_CHARGE = "full_charge"
    PARTIAL_CHARGE = "partial_charge"
    WAIVED = "waived"


# Valid state transitions
VALID_TRANSITIONS: dict[ReservationStatusEnum, set[ReservationStatusEnum]] = {
    ReservationStatusEnum.PENDING: {
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.CANCELLED,
    },
    ReservationStatusEnum.DEPOSIT_PAID: {
        ReservationStatusEnum.FULLY_PAID,
        ReservationStatusEnum.CANCELLED,
    },
    ReservationStatusEnum.FULLY_PAID: {
        ReservationStatusEnum.PRE_CHECK_IN,     # v72 §7.2: docs loaded, awaiting room entry
        ReservationStatusEnum.CHECKED_IN,       # skip pre_check_in if entry confirmed immediately
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    },
    ReservationStatusEnum.PRE_CHECK_IN: {       # v72 §7.2: "Huésped ingresó al cuarto"
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CANCELLED,        # guest no-shows after pre-check-in
    },
    ReservationStatusEnum.CHECKED_IN: {
        ReservationStatusEnum.CHECKED_OUT,
    },
    ReservationStatusEnum.CHECKED_OUT: set(),
    ReservationStatusEnum.CANCELLED: set(),     # Terminal state
    ReservationStatusEnum.NO_SHOW: set(),
}


reservation_additional_guests = Table(
    "reservation_additional_guests",
    Base.metadata,
    Column("reservation_id", Integer, ForeignKey("reservations.id", ondelete="CASCADE"), primary_key=True),
    Column("guest_id", Integer, ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True)
)


class Reservation(Base):
    """
    Core reservation entity.
    Tracks the full lifecycle from booking to checkout, including financial state.
    """
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    confirmation_code = Column(String(30), nullable=False, unique=True, index=True)
    # Default single-hotel context for tests; explicit in multi-hotel flows.
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)

    # Guest and Room linkage
    guest_id = Column(Integer, nullable=False)
    room_id = Column(Integer, nullable=True)  # Nullable until assigned
    category_id = Column(Integer, nullable=False)
    company_id = Column(Integer, nullable=True)
    sellable_product_id = Column(Integer, nullable=True)
    rate_plan_id = Column(Integer, nullable=True)
    tax_policy_id = Column(Integer, nullable=True)

    # Dates
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    actual_check_in = Column(DateTime, nullable=True)
    actual_check_out = Column(DateTime, nullable=True)
    pre_check_in_at = Column(DateTime, nullable=True)   # v72 §7.2: timestamp of pre-finalization
    arrival_time_hint = Column(String(80), nullable=True)

    # Financial
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(12, 2), nullable=False, default=0)
    deposit_amount = Column(Numeric(12, 2), nullable=False, default=0)
    subtotal_amount = Column(Numeric(12, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(12, 2), nullable=False, default=0)
    fee_amount = Column(Numeric(12, 2), nullable=False, default=0)
    commission_amount = Column(Numeric(12, 2), nullable=False, default=0)
    net_amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency_code = Column(String(3), nullable=False, default="ARS")
    fx_rate_snapshot = Column(Float, nullable=True)

    # Two independently-entered "quotable" amounts for manual OTA loads --
    # NOT a conversion of one into the other (the OTA's negotiated price in
    # ARS and in USD can differ from the official FX rate). Separate from
    # total_amount/currency_code, which stay the canonical billing amount
    # used everywhere else in the system. So the receptionist can answer
    # "how much in pesos" / "how much in dollars" without doing math.
    quoted_amount_ars = Column(Numeric(12, 2), nullable=True)
    quoted_amount_usd = Column(Numeric(12, 2), nullable=True)

    # Status
    status = Column(
        Enum(
            ReservationStatusEnum,
            name="reservation_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationStatusEnum.PENDING,
    )
    outcome = Column(
        Enum(
            ReservationOutcomeEnum,
            name="reservation_outcome_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationOutcomeEnum.PENDING,
    )
    guest_segment = Column(
        Enum(
            ReservationGuestSegmentEnum,
            name="reservation_guest_segment_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationGuestSegmentEnum.LEISURE,
    )
    guest_segment_source = Column(
        Enum(
            ReservationGuestSegmentSourceEnum,
            name="reservation_guest_segment_source_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
    )
    channel_code = Column(
        Enum(
            ReservationChannelCodeEnum,
            name="reservation_channel_code_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationChannelCodeEnum.OTHER_DIRECT,
    )
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cancellation_reason_code = Column(
        Enum(
            ReservationCancellationReasonCodeEnum,
            name="reservation_cancellation_reason_code_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    cancellation_reason_note = Column(String(500), nullable=True)
    no_show_confirmed_at = Column(DateTime, nullable=True)
    no_show_policy_applied = Column(
        Enum(
            ReservationNoShowPolicyAppliedEnum,
            name="reservation_no_show_policy_applied_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationNoShowPolicyAppliedEnum.NONE,
    )

    # Source tracking (OTA or direct)
    source = Column(
        Enum(
            ReservationSourceEnum,
            name="reservation_source_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationSourceEnum.DIRECT,
    )
    source_provider_code = Column(String(50), nullable=True, index=True)
    external_id = Column(String(100), nullable=True, index=True)  # OTA booking ID
    external_confirmation_code = Column(String(120), nullable=True)
    requested_attributes_json = Column(Text, nullable=True)
    pricing_snapshot = Column(Text, nullable=True)
    allocation_status = Column(String(30), nullable=False, default="unassigned")
    allocation_locked = Column(Boolean, nullable=False, default=False)
    requires_manual_review = Column(Boolean, nullable=False, default=False)
    mobility_restriction = Column(Boolean, nullable=False, default=False)
    payment_collection_model = Column(String(40), nullable=False, default="hotel_collect")
    settlement_status = Column(String(40), nullable=False, default="not_applicable")
    # Corporate deferred billing (v72 §3.5): due date = check_out + company.deferred_days.
    # Set when a company reservation with payment_deferred is created/confirmed.
    settlement_due_date = Column(Date, nullable=True)

    # Number of guests
    num_adults = Column(Integer, nullable=False, default=1)
    num_children = Column(Integer, nullable=False, default=0)

    # Waitlist / overbooking (v72 §9) — denormalized flags kept in sync with
    # WaitlistEntry by the service layer. A wait-listed reservation has
    # room_id=None so availability queries never count it as occupying a room.
    is_wait_listed = Column(Boolean, nullable=False, default=False, server_default="0")
    wait_list_reason = Column(String(255), nullable=True)

    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # Optimistic locking — increment on every update; reject if version mismatch (v72 security-audit §6)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    version = Column(Integer, nullable=False, default=0)

    # Relationships
    guest = relationship("Guest", back_populates="reservations", lazy="joined")
    additional_guests = relationship("Guest", secondary=reservation_additional_guests, lazy="selectin")
    room = relationship("Room", back_populates="reservations", lazy="joined")
    category = relationship("RoomCategory", lazy="joined")
    sellable_product = relationship("SellableProduct", lazy="joined")
    rate_plan = relationship("RatePlan", lazy="joined")
    tax_policy = relationship("TaxPolicy", lazy="joined")
    transactions = relationship("Transaction", back_populates="reservation", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date", name="ck_reservation_dates"),
        CheckConstraint("total_amount >= 0", name="ck_reservation_total_positive"),
        CheckConstraint("amount_paid >= 0", name="ck_reservation_paid_positive"),
        CheckConstraint("subtotal_amount >= 0", name="ck_reservation_subtotal_positive"),
        CheckConstraint("tax_amount >= 0", name="ck_reservation_tax_positive"),
        CheckConstraint("fee_amount >= 0", name="ck_reservation_fee_positive"),
        CheckConstraint("num_adults > 0", name="ck_reservation_adults_positive"),
        CheckConstraint("num_children >= 0", name="ck_reservation_children_positive"),
        Index("ix_reservation_dates", "check_in_date", "check_out_date"),
        Index("ix_reservation_hotel_id", "hotel_id"),
        # A2: recent-order paging (created_at DESC) scoped per hotel.
        Index("ix_reservation_hotel_created_at", "hotel_id", "created_at"),
        # B2: occupancy grid overlap query (hotel_id + date range), room_id
        # included so per-room lookups can use it too.
        Index("ix_reservation_hotel_room_dates", "hotel_id", "room_id", "check_in_date", "check_out_date"),
        Index("ix_reservation_sellable_product_id", "sellable_product_id"),
        Index("ix_reservation_rate_plan_id", "rate_plan_id"),
        # OTA deduplication (v72 §10.1): same channel+ID must not produce duplicate reservations
        UniqueConstraint(
            "hotel_id", "source_provider_code", "external_id",
            name="uq_reservation_ota_external_id",
        ),
        # Composite FK target for payments/payment_links (hotel_id, reservation_id)
        UniqueConstraint("hotel_id", "id", name="uq_reservation_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
            name="fk_reservations_hotel_guest",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "room_id"], ["rooms.hotel_id", "rooms.id"],
            name="fk_reservations_hotel_room",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "category_id"], ["room_categories.hotel_id", "room_categories.id"],
            name="fk_reservations_hotel_category",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"], ["companies.hotel_id", "companies.id"],
            name="fk_reservations_hotel_company",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "sellable_product_id"], ["sellable_products.hotel_id", "sellable_products.id"],
            name="fk_reservations_hotel_sellable_product",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "rate_plan_id"], ["rate_plans.hotel_id", "rate_plans.id"],
            name="fk_reservations_hotel_rate_plan",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "tax_policy_id"], ["tax_policies.hotel_id", "tax_policies.id"],
            name="fk_reservations_hotel_tax_policy",
        ),
    )

    @property
    def balance_due(self):
        """Outstanding balance on the reservation."""
        from decimal import Decimal
        def _d(v): return Decimal(str(v)) if v is not None else Decimal("0")
        return max(Decimal("0"), _d(self.total_amount) - _d(self.amount_paid))

    @property
    def nights(self) -> int:
        """Number of nights for the stay."""
        return (self.check_out_date - self.check_in_date).days

    def can_transition_to(self, new_status: ReservationStatusEnum) -> bool:
        """Check if a state transition is valid."""
        if (
            self.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT)
            and new_status in (ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW)
        ):
            # Defensive guard: never allow terminal pre-check-in outcomes after check-in/checkout
            return False
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def __repr__(self) -> str:
        return (
            f"<Reservation(id={self.id}, code='{self.confirmation_code}', "
            f"status={self.status}, room_id={self.room_id})>"
        )
