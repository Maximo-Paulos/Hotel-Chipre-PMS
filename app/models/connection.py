"""
Connection model for external provider integrations.
Stores credentials/settings as JSON to preserve structure.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint

from app.database import Base


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("provider", name="uq_connection_provider"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="connected")
    credentials = Column(JSON, nullable=False)
    settings = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Connection(provider='{self.provider}', status='{self.status}')>"
