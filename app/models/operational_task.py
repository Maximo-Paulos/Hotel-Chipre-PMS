"""Shared operational tasks and shift handoffs.

Tasks are deliberately separate from reservation pending-action projections:
the same task survives a shift change and can be linked to either a room,
reservation, or both. Financial custody remains owned by CashCloseReport;
handoffs only reference that record.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import foreign, relationship

from app.database import Base
from app.models.reservation import Reservation
from app.models.room import Room


class OperationalTaskTypeEnum(str, enum.Enum):
    GENERAL = "general"
    RECEPTION = "reception"
    HOUSEKEEPING = "housekeeping"
    MAINTENANCE = "maintenance"


class OperationalTaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    RESOLVED = "resolved"


class OperationalTaskPriorityEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ShiftHandoffStatusEnum(str, enum.Enum):
    PENDING_ACKNOWLEDGEMENT = "pending_acknowledgement"
    ACKNOWLEDGED = "acknowledged"


shift_handoff_tasks = Table(
    "shift_handoff_tasks",
    Base.metadata,
    Column("hotel_id", Integer, nullable=False),
    Column("handoff_id", Integer, primary_key=True),
    Column("task_id", Integer, primary_key=True),
    ForeignKeyConstraint(
        ["hotel_id", "handoff_id"],
        ["shift_handoffs.hotel_id", "shift_handoffs.id"],
        name="fk_shift_handoff_tasks_hotel_handoff",
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["hotel_id", "task_id"],
        ["operational_tasks.hotel_id", "operational_tasks.id"],
        name="fk_shift_handoff_tasks_hotel_task",
        ondelete="CASCADE",
    ),
)


class OperationalTask(Base):
    __tablename__ = "operational_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, nullable=True)
    reservation_id = Column(Integer, nullable=True)
    room_block_id = Column(Integer, nullable=True)
    task_type = Column(
        Enum(
            OperationalTaskTypeEnum,
            name="operational_task_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OperationalTaskTypeEnum.GENERAL,
    )
    status = Column(
        Enum(
            OperationalTaskStatusEnum,
            name="operational_task_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OperationalTaskStatusEnum.PENDING,
    )
    priority = Column(
        Enum(
            OperationalTaskPriorityEnum,
            name="operational_task_priority_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=OperationalTaskPriorityEnum.MEDIUM,
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    version = Column(Integer, nullable=False, default=0)

    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id], lazy="joined")
    created_by = relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id], lazy="joined")
    room = relationship(
        Room,
        primaryjoin=lambda: (foreign(OperationalTask.room_id) == Room.id)
        & (OperationalTask.hotel_id == Room.hotel_id),
        foreign_keys=[room_id],
        viewonly=True,
        lazy="joined",
    )
    reservation = relationship(
        Reservation,
        primaryjoin=lambda: (foreign(OperationalTask.reservation_id) == Reservation.id)
        & (OperationalTask.hotel_id == Reservation.hotel_id),
        foreign_keys=[reservation_id],
        viewonly=True,
        lazy="joined",
    )
    events = relationship("OperationalTaskEvent", back_populates="task", lazy="selectin", cascade="all, delete-orphan")
    handoffs = relationship(
        "ShiftHandoff",
        secondary=shift_handoff_tasks,
        primaryjoin=lambda: (OperationalTask.hotel_id == foreign(shift_handoff_tasks.c.hotel_id))
        & (OperationalTask.id == foreign(shift_handoff_tasks.c.task_id)),
        secondaryjoin=lambda: (ShiftHandoff.hotel_id == foreign(shift_handoff_tasks.c.hotel_id))
        & (ShiftHandoff.id == foreign(shift_handoff_tasks.c.handoff_id)),
        back_populates="tasks",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "id", name="uq_operational_tasks_hotel_id_id"),
        Index("ix_operational_tasks_hotel_status_due", "hotel_id", "status", "due_at"),
        Index("ix_operational_tasks_hotel_room", "hotel_id", "room_id"),
        Index("ix_operational_tasks_hotel_reservation", "hotel_id", "reservation_id"),
    )


class OperationalTaskEvent(Base):
    __tablename__ = "operational_task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    task_id = Column(Integer, nullable=False)
    from_status = Column(String(40), nullable=True)
    to_status = Column(String(40), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "task_id"],
            ["operational_tasks.hotel_id", "operational_tasks.id"],
            name="fk_operational_task_events_hotel_task",
            ondelete="CASCADE",
        ),
        Index("ix_operational_task_events_hotel_task_created", "hotel_id", "task_id", "created_at"),
    )

    task = relationship("OperationalTask", back_populates="events")
    actor = relationship("User", lazy="joined")


class ShiftHandoff(Base):
    __tablename__ = "shift_handoffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    delivered_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cash_close_report_id = Column(Integer, nullable=True)
    status = Column(
        Enum(
            ShiftHandoffStatusEnum,
            name="shift_handoff_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ShiftHandoffStatusEnum.PENDING_ACKNOWLEDGEMENT,
    )
    notes = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    version = Column(Integer, nullable=False, default=0)

    delivered_by = relationship("User", foreign_keys=[delivered_by_user_id], lazy="joined")
    received_by = relationship("User", foreign_keys=[received_by_user_id], lazy="joined")
    tasks = relationship(
        "OperationalTask",
        secondary=shift_handoff_tasks,
        primaryjoin=lambda: (ShiftHandoff.hotel_id == foreign(shift_handoff_tasks.c.hotel_id))
        & (ShiftHandoff.id == foreign(shift_handoff_tasks.c.handoff_id)),
        secondaryjoin=lambda: (OperationalTask.hotel_id == foreign(shift_handoff_tasks.c.hotel_id))
        & (OperationalTask.id == foreign(shift_handoff_tasks.c.task_id)),
        back_populates="handoffs",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "id", name="uq_shift_handoffs_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "cash_close_report_id"],
            ["cash_close_reports.hotel_id", "cash_close_reports.id"],
            name="fk_shift_handoffs_hotel_cash_close",
            ondelete="SET NULL",
        ),
        Index("ix_shift_handoffs_hotel_delivered", "hotel_id", "delivered_at"),
    )
