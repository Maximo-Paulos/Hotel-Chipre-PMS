import pytest

from scripts.scale.staged_realtime_load import validate_target


def test_realtime_load_runner_rejects_shared_production_hosts():
    with pytest.raises(ValueError, match="production"):
        validate_target("https://api.hotels-pms.com")


def test_realtime_load_runner_accepts_isolated_preview():
    validate_target("https://hotel-chipre-pms-api-pr-123.onrender.com")
