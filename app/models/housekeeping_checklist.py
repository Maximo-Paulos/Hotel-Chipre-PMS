"""Fixed, auditable housekeeping checklists created at reservation checkout."""
from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from app.database import Base


class HousekeepingChecklistStatusEnum(str, enum.Enum):
    OPEN = "open"
    COMPLETED = "completed"


class HousekeepingChecklistItemCodeEnum(str, enum.Enum):
    """Stable item codes consumed by the housekeeping API and frontend."""

    CHANGE_SHEETS = "change_sheets"
    CLEAN_BATHROOM = "clean_bathroom"
    REPLENISH_TOWELS = "replenish_towels"
    EMPTY_WASTE = "empty_waste"
    CHECK_AMENITIES = "check_amenities"


class HousekeepingChecklist(Base):
    __tablename__ = "housekeeping_checklists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    room_id = Column(Integer, nullable=False)
    reservation_id = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default=HousekeepingChecklistStatusEnum.OPEN.value)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'completed')", name="ck_housekeeping_checklist_status"),
        CheckConstraint("version >= 1", name="ck_housekeeping_checklist_version_positive"),
        CheckConstraint(
            "(status = 'open' AND completed_at IS NULL AND completed_by_user_id IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_housekeeping_checklist_completion_consistent",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_housekeeping_checklists_hotel_id_id"),
        UniqueConstraint("hotel_id", "reservation_id", name="uq_housekeeping_checklists_reservation"),
        ForeignKeyConstraint(
            ["hotel_id", "room_id"],
            ["rooms.hotel_id", "rooms.id"],
            name="fk_housekeeping_checklists_hotel_room",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_housekeeping_checklists_hotel_reservation",
            ondelete="RESTRICT",
        ),
        Index("ix_housekeeping_checklists_hotel_status_room", "hotel_id", "status", "room_id"),
        Index(
            "uq_housekeeping_checklists_one_open_per_room",
            "hotel_id",
            "room_id",
            unique=True,
            sqlite_where=(status == HousekeepingChecklistStatusEnum.OPEN.value),
            postgresql_where=(status == HousekeepingChecklistStatusEnum.OPEN.value),
        ),
    )


class HousekeepingChecklistItem(Base):
    __tablename__ = "housekeeping_checklist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    checklist_id = Column(Integer, nullable=False)
    code = Column(String(32), nullable=False)
    label = Column(String(120), nullable=False)
    completed = Column(Boolean, nullable=False, default=False, server_default="false")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "code IN ('change_sheets', 'clean_bathroom', 'replenish_towels', 'empty_waste', 'check_amenities')",
            name="ck_housekeeping_checklist_item_code",
        ),
        CheckConstraint(
            "length(trim(label)) BETWEEN 1 AND 120",
            name="ck_housekeeping_checklist_item_label",
        ),
        CheckConstraint(
            "(completed = false AND completed_at IS NULL AND completed_by_user_id IS NULL) OR "
            "(completed = true AND completed_at IS NOT NULL)",
            name="ck_housekeeping_checklist_item_completion_consistent",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "checklist_id"],
            ["housekeeping_checklists.hotel_id", "housekeeping_checklists.id"],
            name="fk_housekeeping_checklist_items_hotel_checklist",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("hotel_id", "checklist_id", "code", name="uq_housekeeping_checklist_item_code"),
        Index("ix_housekeeping_checklist_items_hotel_checklist", "hotel_id", "checklist_id"),
    )
