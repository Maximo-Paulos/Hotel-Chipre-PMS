"""
Room and RoomCategory models.
"""
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    Enum,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RoomStatusEnum(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    BLOCKED = "blocked"
    CLEANING = "cleaning"


class RoomCategory(Base):
    """Room category/type â€” e.g. Standard, Superior, Suite, Penthouse."""

    __tablename__ = "room_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    name = Column(String(100), nullable=False)  # "Standard Double"
    code = Column(String(20), nullable=False)  # "STD_DBL"
    description = Column(Text, nullable=True)
    base_price_per_night = Column(Float, nullable=False)
    max_occupancy = Column(Integer, nullable=False, default=2)
    amenities = Column(Text, nullable=True)  # JSON string of amenities

    # Relationships
    rooms = relationship("Room", back_populates="category", lazy="selectin")

    __table_args__ = (
        CheckConstraint("base_price_per_night > 0", name="ck_category_price_positive"),
        CheckConstraint("max_occupancy > 0", name="ck_category_max_occ_positive"),
        UniqueConstraint("hotel_id", "code", name="uq_room_category_code_hotel"),
        UniqueConstraint("hotel_id", "name", name="uq_room_category_name_hotel"),
        Index("ix_room_category_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return f"<RoomCategory(id={self.id}, name='{self.name}', code='{self.code}')>"


class Room(Base):
    """Physical room in the hotel."""

    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    room_number = Column(String(10), nullable=False)  # "101", "PH-1"
    floor = Column(Integer, nullable=False, default=1)
    category_id = Column(Integer, ForeignKey("room_categories.id"), nullable=False)
    status = Column(
        Enum(RoomStatusEnum, name="room_status_enum", create_constraint=True),
        nullable=False,
        default=RoomStatusEnum.AVAILABLE,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)

    # Relationships
    category = relationship("RoomCategory", back_populates="rooms", lazy="joined")
    reservations = relationship("Reservation", back_populates="room", lazy="selectin")

    __table_args__ = (
        CheckConstraint("floor >= 0", name="ck_room_floor_positive"),
        UniqueConstraint("hotel_id", "room_number", name="uq_room_number_hotel"),
        Index("ix_room_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return f"<Room(id={self.id}, number='{self.room_number}', category_id={self.category_id})>"
