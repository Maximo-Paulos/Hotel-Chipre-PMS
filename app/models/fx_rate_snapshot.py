from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String

from app.database import Base


class FxRateSnapshot(Base):
    __tablename__ = "fx_rate_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="SET NULL"),
        nullable=True,
    )
    rate_type = Column(String(30), nullable=False)
    moneda = Column(String(10), nullable=False, default="USD")
    compra = Column(Float, nullable=True)
    venta = Column(Float, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    source = Column(String(50), nullable=False, default="dolarapi.com")

    __table_args__ = (
        Index("ix_fx_snapshot_type_date", "rate_type", "fetched_at"),
        Index("ix_fx_snapshot_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<FxRateSnapshot(id={self.id}, type={self.rate_type!r}, "
            f"moneda={self.moneda!r}, venta={self.venta}, fetched_at={self.fetched_at})>"
        )
