from pathlib import Path

from scripts.agent_ops.validate_gcp_readiness import validate


def test_gcp_readiness_validator_is_static_and_green_for_repository():
    root = Path(__file__).resolve().parents[1]
    assert validate(root) == []
