"""Spreadsheet-safe serialization helpers for user-controlled CSV cells."""

from decimal import Decimal, InvalidOperation


_FORMULA_PREFIXES = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
_CONTROL_PREFIXES = ("\x00", "\t", "\r", "\n")


def spreadsheet_safe_value(value):
    """Prefix formula-like text so spreadsheet software treats it as text."""

    if not isinstance(value, str) or not value:
        return value
    stripped = value.lstrip()
    if stripped.startswith(_CONTROL_PREFIXES):
        return f"'{value}"
    if stripped.startswith(("+", "-")):
        try:
            if Decimal(stripped).is_finite():
                return value
        except InvalidOperation:
            pass
    if stripped.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def spreadsheet_safe_row(row: dict):
    """Apply formula protection consistently to every text cell in a CSV row."""

    return {key: spreadsheet_safe_value(value) for key, value in row.items()}
