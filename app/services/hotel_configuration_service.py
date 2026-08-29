"""Shared writes for hotel configuration concepts."""
from __future__ import annotations

from collections.abc import Mapping

from app.models.hotel_config import HotelConfiguration


def apply_configuration_update(config: HotelConfiguration, values: Mapping[str, object]) -> None:
    """Apply a validated Settings payload to one hotel configuration row."""
    for field, value in values.items():
        if hasattr(type(config), field):
            setattr(config, field, value)


def set_identity(config: HotelConfiguration, *, name: str, timezone: str, currency: str, languages: list[str], jurisdiction_code: str) -> None:
    apply_configuration_update(
        config,
        {
            "hotel_name": name,
            "hotel_timezone": timezone,
            "default_currency": currency,
            "languages": languages,
            "jurisdiction_code": jurisdiction_code,
        },
    )


def set_deposit_policy(config: HotelConfiguration, *, deposit_percentage: float, free_cancellation_hours: int, cancellation_penalty_percentage: float) -> None:
    apply_configuration_update(
        config,
        {
            "deposit_percentage": deposit_percentage,
            "free_cancellation_hours": free_cancellation_hours,
            "cancellation_penalty_percentage": cancellation_penalty_percentage,
        },
    )


def set_payment_methods(config: HotelConfiguration, *, mercado_pago: bool, paypal: bool, credit_card: bool) -> None:
    apply_configuration_update(
        config,
        {
            "enable_mercado_pago": mercado_pago,
            "enable_paypal": paypal,
            "enable_credit_card": credit_card,
        },
    )


def set_ota_channels(config: HotelConfiguration, *, booking: bool, expedia: bool, despegar: bool) -> None:
    apply_configuration_update(
        config,
        {
            "enable_booking_sync": booking,
            "enable_expedia_sync": expedia,
            "enable_despegar_sync": despegar,
        },
    )
