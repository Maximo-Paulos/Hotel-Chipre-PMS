"""
Allocation, solver and LLM policy models.

The deterministic solver remains the source of truth. LLM-generated content is
stored as drafts and feedback so hotels can evolve policies without hidden
runtime changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AllocationRunStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class AllocationAssignmentStatusEnum(str, enum.Enum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    LOCKED = "locked"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class LLMPolicySuggestionStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class AllocationPolicyProfile(Base):
    __tablename__ = "allocation_policy_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    versions = relationship(
        "AllocationPolicyVersion",
        back_populates="profile",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_allocation_policy_profile_code_hotel"),
        Index("ix_allocation_policy_profiles_hotel_id", "hotel_id"),
    )


class AllocationPolicyVersion(Base):
    __tablename__ = "allocation_policy_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(Integer, ForeignKey("allocation_policy_profiles.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    source = Column(String(30), nullable=False, default="manual")
    constraints_json = Column(Text, nullable=True)
    weights_json = Column(Text, nullable=True)
    prompt_summary = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    profile = relationship("AllocationPolicyProfile", back_populates="versions", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "version_number",
            name="uq_allocation_policy_version_profile_version",
        ),
        Index("ix_allocation_policy_versions_hotel_id", "hotel_id"),
    )


class AllocationRun(Base):
    __tablename__ = "allocation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    policy_version_id = Column(Integer, ForeignKey("allocation_policy_versions.id", ondelete="SET NULL"), nullable=True)
    trigger_type = Column(String(50), nullable=False)
    horizon_start = Column(DateTime, nullable=True)
    horizon_end = Column(DateTime, nullable=True)
    status = Column(
        Enum(
            AllocationRunStatusEnum,
            name="allocation_run_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=AllocationRunStatusEnum.PENDING,
    )
    objective_score = Column(Float, nullable=True)
    solver_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    policy_version = relationship("AllocationPolicyVersion", lazy="joined")
    assignments = relationship(
        "AllocationAssignment",
        back_populates="allocation_run",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_allocation_runs_hotel_id", "hotel_id"),
        Index("ix_allocation_runs_status", "status"),
    )


class AllocationAssignment(Base):
    __tablename__ = "allocation_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    allocation_run_id = Column(Integer, ForeignKey("allocation_runs.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    sellable_product_id = Column(Integer, ForeignKey("sellable_products.id", ondelete="SET NULL"), nullable=True)
    status = Column(
        Enum(
            AllocationAssignmentStatusEnum,
            name="allocation_assignment_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=AllocationAssignmentStatusEnum.PROPOSED,
    )
    objective_delta = Column(Float, nullable=True)
    explanation_summary = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    allocation_run = relationship("AllocationRun", back_populates="assignments", lazy="joined")
    reservation = relationship("Reservation", lazy="joined")
    room = relationship("Room", lazy="joined")
    sellable_product = relationship("SellableProduct", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "allocation_run_id",
            "reservation_id",
            name="uq_allocation_assignment_run_reservation",
        ),
        Index("ix_allocation_assignments_hotel_id", "hotel_id"),
        Index("ix_allocation_assignments_reservation_id", "reservation_id"),
    )


class ReservationAllocationLock(Base):
    __tablename__ = "reservation_allocation_locks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    locked_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    lock_reason_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    released_at = Column(DateTime, nullable=True)

    reservation = relationship("Reservation", lazy="joined")
    locked_room = relationship("Room", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            "is_active",
            name="uq_reservation_allocation_lock_reservation_active",
        ),
        Index("ix_reservation_allocation_locks_hotel_id", "hotel_id"),
    )


class AllocationExplanation(Base):
    __tablename__ = "allocation_explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    allocation_run_id = Column(Integer, ForeignKey("allocation_runs.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    explanation_type = Column(String(50), nullable=False, default="solver")
    summary = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    allocation_run = relationship("AllocationRun", lazy="joined")
    reservation = relationship("Reservation", lazy="joined")

    __table_args__ = (
        Index("ix_allocation_explanations_hotel_id", "hotel_id"),
        Index("ix_allocation_explanations_reservation_id", "reservation_id"),
    )


class SolverMetric(Base):
    __tablename__ = "solver_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    allocation_run_id = Column(Integer, ForeignKey("allocation_runs.id", ondelete="CASCADE"), nullable=False)
    metric_key = Column(String(80), nullable=False)
    metric_value = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    allocation_run = relationship("AllocationRun", lazy="joined")

    __table_args__ = (
        Index("ix_solver_metrics_hotel_id", "hotel_id"),
        Index("ix_solver_metrics_run_id", "allocation_run_id"),
    )


class ManualOverrideReason(Base):
    __tablename__ = "manual_override_reasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    override_type = Column(String(50), nullable=False)
    reason_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    reservation = relationship("Reservation", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_manual_override_reasons_hotel_id", "hotel_id"),
        Index("ix_manual_override_reasons_reservation_id", "reservation_id"),
    )


class LLMPolicySuggestion(Base):
    __tablename__ = "llm_policy_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(Integer, ForeignKey("allocation_policy_profiles.id", ondelete="SET NULL"), nullable=True)
    suggestion_type = Column(String(50), nullable=False)
    status = Column(
        Enum(
            LLMPolicySuggestionStatusEnum,
            name="llm_policy_suggestion_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=LLMPolicySuggestionStatusEnum.DRAFT,
    )
    source_model = Column(String(100), nullable=True)
    input_summary = Column(Text, nullable=True)
    suggested_policy_json = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    profile = relationship("AllocationPolicyProfile", lazy="joined")
    reviewed_by = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_llm_policy_suggestions_hotel_id", "hotel_id"),
        Index("ix_llm_policy_suggestions_status", "status"),
    )


class LLMFeedbackEvent(Base):
    __tablename__ = "llm_feedback_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)
    allocation_run_id = Column(Integer, ForeignKey("allocation_runs.id", ondelete="SET NULL"), nullable=True)
    manual_override_reason_id = Column(
        Integer,
        ForeignKey("manual_override_reasons.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type = Column(String(50), nullable=False)
    payload_json = Column(Text, nullable=True)
    source_model = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    reservation = relationship("Reservation", lazy="joined")
    allocation_run = relationship("AllocationRun", lazy="joined")
    manual_override_reason = relationship("ManualOverrideReason", lazy="joined")

    __table_args__ = (
        Index("ix_llm_feedback_events_hotel_id", "hotel_id"),
        Index("ix_llm_feedback_events_reservation_id", "reservation_id"),
    )
