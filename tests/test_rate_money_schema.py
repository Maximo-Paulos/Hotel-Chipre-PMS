"""Exact-money storage contracts for the active room-rate tables."""
from sqlalchemy import Numeric

from app.models.daily_rate import DailyRate, PricePeriod


def test_active_rate_price_columns_use_numeric_cents():
    active_money_columns = {
        DailyRate: (
            "price",
            "price_cash",
            "price_transfer",
            "price_mercadopago",
            "price_paypal",
            "price_credit_card",
        ),
        PricePeriod: (
            "price_per_night",
            "price_cash",
            "price_transfer",
            "price_mercadopago",
            "price_paypal",
            "price_credit_card",
            "price_debit_card",
            "price_booking",
            "price_expedia",
        ),
    }

    for model, column_names in active_money_columns.items():
        for name in column_names:
            column_type = model.__table__.c[name].type
            assert isinstance(column_type, Numeric)
            assert column_type.precision == 12
            assert column_type.scale == 2
