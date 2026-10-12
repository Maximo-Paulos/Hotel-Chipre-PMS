"""Hotel-specific deposit policy must be explicit before reservation pricing."""

import pytest
from pydantic import ValidationError

from app.models.hotel_config import HotelConfiguration
from app.schemas.hotel_config import HotelConfigUpdate
from app.services.hotel_configuration_service import (
    apply_configuration_update,
    set_deposit_policy,
)


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
