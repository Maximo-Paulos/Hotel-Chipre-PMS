"""Regression contracts for routes migrated from the legacy role dependency.

These assertions deliberately compare the legacy role set with the seeded
canonical permission matrix.  They prevent a future permission substitution
from silently broadening or narrowing the default role contract.
"""

import ast
from pathlib import Path

import pytest

from app.services.permission_service import (
    DEFAULT_MATRIX,
    ROLE_CODES,
    canonical_permission_code,
)


ROUTE_CONTRACTS = (
    ("app/api/bookings.py", "price_quote", "PERMISSION_RESERVATION_CREATE", "reservation:create", {"owner", "co_owner", "manager", "receptionist"}),
    ("app/api/onboarding.py", "onboarding_status", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_owner", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_identity", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_categories", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_rooms", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_policy", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_payments", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_ota", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_subscription_choice", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "set_staff", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/onboarding.py", "finish", "PERMISSION_HOTEL_SETTINGS_UPDATE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "create_version", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "publish_version", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "create_suggestion", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "review_suggestion", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "apply_suggestion", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "create_questionnaire_draft", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/allocation_policy.py", "create_feedback_draft", "PERMISSION_CONFIG_MANAGE", "hotel_settings:update", {"owner", "co_owner"}),
    ("app/api/movement_groups.py", "revert_movement_group", "PERMISSION_RESERVATION_MOVE", "reservation:move", {"owner", "co_owner", "manager"}),
    ("app/api/users.py", "transfer_primary_owner_endpoint", "PERMISSION_HOTEL_PROPERTY_MANAGE", "hotel_settings:property_manage", {"owner"}),
)


def _function(path: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"No se encontró {name} en {path}")


@pytest.mark.parametrize("path,function,source_permission,canonical,legacy_roles", ROUTE_CONTRACTS)
def test_migrated_route_keeps_legacy_role_contract(path, function, source_permission, canonical, legacy_roles):
    node = _function(path, function)
    permission_calls = []
    legacy_calls = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Name):
            continue
        if child.func.id == "require_permission":
            permission_calls.append(child)
        if child.func.id == "require_roles":
            legacy_calls.append(child)

    assert not legacy_calls, f"{path}:{function} todavía usa require_roles"
    assert len(permission_calls) == 1
    assert ast.unparse(permission_calls[0].args[0]) == source_permission

    resolved = canonical_permission_code(canonical)
    catalog_roles = {role for role in ROLE_CODES if DEFAULT_MATRIX[role].get(resolved, False)}
    assert catalog_roles == legacy_roles
