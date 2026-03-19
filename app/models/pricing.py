from sqlalchemy import Column, Integer, Float, ForeignKey
from app.database import Base

class CategoryPricing(Base):
    """Specific pricing configuration for a room category based on payment method and channel."""
    __tablename__ = "category_pricing"

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
