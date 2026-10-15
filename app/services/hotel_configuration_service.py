"""Shared writes for hotel configuration concepts."""
from __future__ import annotations

from collections.abc import Mapping

from app.models.hotel_config import HotelConfiguration


def apply_configuration_update(config: HotelConfiguration, values: Mapping[str, object]) -> None:
    """Apply a validated Settings payload to one hotel configuration row."""
    values = dict(values)
    if "deposit_policy_rules" in values and values["deposit_policy_rules"] is not None:
        values["deposit_policy_rules"] = [
            rule.model_dump() if hasattr(rule, "model_dump") else dict(rule)
            for rule in values["deposit_policy_rules"]
        ]
    policy_fields = (
        "deposit_percentage",
        "deposit_policy_rules",
        "free_cancellation_hours",
        "cancellation_penalty_percentage",
    )
    policy_changed = any(
        field in values and values[field] != getattr(config, field)
        for field in policy_fields
    )
    for field, value in values.items():
        if hasattr(type(config), field):
            setattr(config, field, value)
    if policy_changed and values.get("deposit_policy_configured") is not True:
        config.deposit_policy_configured = False


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


def set_deposit_policy(
    config: HotelConfiguration,
    *,
    deposit_percentage: float,
    free_cancellation_hours: int,
    cancellation_penalty_percentage: float,
    deposit_policy_rules: list[dict] | None = None,
) -> None:
    apply_configuration_update(
        config,
        {
            "deposit_percentage": deposit_percentage,
            "deposit_policy_rules": deposit_policy_rules,
            "deposit_policy_configured": True,
            "free_cancellation_hours": free_cancellation_hours,
            "cancellation_penalty_percentage": cancellation_penalty_percentage,
        },
    )


def set_payment_methods(
    config: HotelConfiguration,
    *,
    cash: bool,
    bank_transfer: bool,
    debit_card: bool,
    mercado_pago: bool,
    paypal: bool,
    credit_card: bool,
) -> None:
    apply_configuration_update(
        config,
        {
            "enable_cash": cash,
            "enable_bank_transfer": bank_transfer,
            "enable_debit_card": debit_card,
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
