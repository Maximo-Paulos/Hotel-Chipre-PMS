from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
)

from app.database import Base


class IntegrationCatalog(Base):
    __tablename__ = "integration_catalog"
    __table_args__ = (UniqueConstraint("provider", name="uq_integration_provider"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    display_name = Column(String(100), nullable=False)
    auth_type = Column(String(30), nullable=False)
    scopes = Column(String(500), nullable=True)
    doc_url = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("hotel_id", "integration_id", name="uq_connection_hotel_integration"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    integration_id = Column(Integer, ForeignKey("integration_catalog.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    auth_payload = Column(JSON, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class IntegrationEvent(Base):
    __tablename__ = "integration_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("integration_connections.id"), nullable=False)
    kind = Column(String(30), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
