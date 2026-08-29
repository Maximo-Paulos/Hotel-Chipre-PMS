from sqlalchemy import Column, Integer, Float, ForeignKey
from app.database import Base

class CategoryPricing(Base):
    """Archived legacy pricing shape kept for migration/test compatibility.

    Runtime pricing no longer reads this table. Existing rows are renamed and
    folded into ``price_periods`` by the retirement migration.
    """
    __tablename__ = "category_pricing_legacy"

    category_id = Column(Integer, ForeignKey("room_categories.id"), primary_key=True)
    
    # Venta Directa
    price_cash = Column(Float, nullable=True)
    price_transfer = Column(Float, nullable=True)
    price_mercadopago = Column(Float, nullable=True)
    price_paypal = Column(Float, nullable=True)
    price_credit_card = Column(Float, nullable=True)
    price_debit_card = Column(Float, nullable=True)
    
    # OTAs
    price_booking = Column(Float, nullable=True)
    price_expedia = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<CategoryPricing(category_id={self.category_id})>"
