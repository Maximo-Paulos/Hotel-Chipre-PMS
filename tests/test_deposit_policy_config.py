"""Hotel-specific deposit policy must be explicit before reservation pricing."""

import pytest
from pydantic import ValidationError

from app.models.hotel_config import HotelConfiguration
from app.schemas.onboarding import DepositPolicyPayload
from app.schemas.hotel_config import HotelConfigUpdate
from app.schemas.deposit_policy import DepositPolicyRule
from app.services.hotel_configuration_service import (
    apply_configuration_update,
    set_deposit_policy,
)
from app.services.reservation_service import _compute_deposit_amount


def test_confirmation_requires_all_deposit_and_cancellation_values():
    with pytest.raises(ValidationError, match="Para confirmar las reglas del hotel"):
        HotelConfigUpdate(deposit_policy_configured=True)
    with pytest.raises(ValidationError, match="Para confirmar las reglas del hotel"):
        HotelConfigUpdate(
            deposit_policy_configured=True,
            deposit_percentage=None,
            free_cancellation_hours=0,
            cancellation_penalty_percentage=0,
        )

    payload = HotelConfigUpdate(
        deposit_policy_configured=True,
        deposit_percentage=0,
        free_cancellation_hours=0,
        cancellation_penalty_percentage=0,
    )
    assert payload.deposit_policy_configured is True
    with pytest.raises(ValidationError):
        HotelConfigUpdate(checkin_payment_policy="free")


def test_policy_edits_revoke_confirmation_until_explicitly_saved_again():
    config = HotelConfiguration(
        id=8123,
        deposit_percentage=30,
        free_cancellation_hours=48,
        cancellation_penalty_percentage=0,
        deposit_policy_configured=True,
    )

    apply_configuration_update(config, {"deposit_percentage": 25})
    assert config.deposit_percentage == 25
    assert config.deposit_policy_configured is False

    set_deposit_policy(
        config,
        deposit_percentage=0,
        free_cancellation_hours=24,
        cancellation_penalty_percentage=10,
    )
    assert config.deposit_policy_configured is True
    assert config.deposit_percentage == 0


def test_saving_duration_rules_persists_json_and_requires_reconfirmation(db, hotel_config):
    hotel_config.deposit_policy_configured = True
    rules = [
        DepositPolicyRule(max_nights=1, calculation="percentage", value=30),
        DepositPolicyRule(max_nights=None, calculation="nights", value=1),
    ]

    apply_configuration_update(hotel_config, {"deposit_policy_rules": rules})
    db.flush()
    db.refresh(hotel_config)

    assert hotel_config.deposit_policy_rules == [
        {"max_nights": 1, "calculation": "percentage", "value": 30.0},
        {"max_nights": None, "calculation": "nights", "value": 1.0},
    ]
    assert hotel_config.deposit_policy_configured is False


def test_deposit_rules_support_percentages_and_night_value_bands(db, hotel_config):
    hotel_config.deposit_policy_configured = True
    hotel_config.deposit_percentage = 30
    hotel_config.deposit_policy_rules = [
        {"max_nights": 1, "calculation": "percentage", "value": 30},
        {"max_nights": None, "calculation": "nights", "value": 1},
    ]
    db.flush()

    assert _compute_deposit_amount(
        db,
        hotel_id=hotel_config.id,
        gross_total=400,
        nights=1,
        nightly_amounts=[100],
    ) == 120.0
    # The night-based rule uses the dated nightly breakdown, not an average.
    assert _compute_deposit_amount(
        db,
        hotel_id=hotel_config.id,
        gross_total=400,
        nights=3,
        nightly_amounts=[100, 150, 150],
    ) == 100.0


def test_deposit_rules_validate_order_open_ended_last_band_and_nights_value():
    payload = DepositPolicyPayload(
        deposit_percentage=30,
        deposit_policy_rules=[
            {"max_nights": 1, "calculation": "percentage", "value": 30},
            {"max_nights": None, "calculation": "nights", "value": 1},
        ],
        free_cancellation_hours=48,
        cancellation_penalty_percentage=0,
    )
    assert payload.deposit_policy_rules[-1].max_nights is None

    with pytest.raises(ValidationError, match="última regla"):
        DepositPolicyPayload(
            deposit_percentage=30,
            deposit_policy_rules=[{"max_nights": 2, "calculation": "percentage", "value": 30}],
            free_cancellation_hours=48,
            cancellation_penalty_percentage=0,
        )
    with pytest.raises(ValidationError, match="entero positivo"):
        DepositPolicyPayload(
            deposit_percentage=30,
            deposit_policy_rules=[{"max_nights": None, "calculation": "nights", "value": 1.5}],
            free_cancellation_hours=48,
            cancellation_penalty_percentage=0,
        )
