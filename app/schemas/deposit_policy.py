"""Validated, ordered deposit rules shared by onboarding and hotel settings."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DepositPolicyRule(BaseModel):
    """Rule applies through ``max_nights``; ``None`` means no upper bound.

    Rules are ordered by their upper bound. The first rule starts at night one,
    and every later rule starts the night after the preceding bound.
    """

    max_nights: int | None = Field(default=None, ge=1, le=3650)
    calculation: Literal["percentage", "nights"]
    value: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_value_for_calculation(self):
        if self.calculation == "nights":
            if not self.value.is_integer() or self.value < 1:
                raise ValueError("La cantidad de noches de seña debe ser un entero positivo")
        return self


def validate_deposit_policy_rules(rules: list[DepositPolicyRule] | None) -> list[DepositPolicyRule] | None:
    if rules is None:
        return None
    if not 1 <= len(rules) <= 10:
        raise ValueError("Configurá entre una y diez reglas de seña")
    bounds = [rule.max_nights for rule in rules]
    if bounds[-1] is not None:
        raise ValueError("La última regla de seña debe cubrir las estadías restantes")
    if any(bound is None for bound in bounds[:-1]):
        raise ValueError("Solo la última regla puede no tener límite de noches")
    finite_bounds = [bound for bound in bounds if bound is not None]
    if any(left >= right for left, right in zip(finite_bounds, finite_bounds[1:])):
        raise ValueError("Los límites de noches deben aumentar en orden")
    return rules


def normalize_deposit_policy_rules(
    rules: list[dict] | list[DepositPolicyRule] | None,
    *,
    legacy_percentage: float,
) -> list[dict]:
    """Return JSON-ready rules, mapping legacy percentage settings safely."""
    if not rules:
        return [{"max_nights": None, "calculation": "percentage", "value": float(legacy_percentage)}]
    validated = [rule if isinstance(rule, DepositPolicyRule) else DepositPolicyRule.model_validate(rule) for rule in rules]
    validate_deposit_policy_rules(validated)
    return [rule.model_dump() for rule in validated]
