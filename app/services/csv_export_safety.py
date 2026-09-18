"""Spreadsheet-safe serialization helpers for user-controlled CSV cells."""


_FORMULA_PREFIXES = ("=", "+", "-", "@")


def spreadsheet_safe_value(value):
    """Prefix formula-like text so spreadsheet software treats it as text."""

    if not isinstance(value, str) or not value:
        return value
    if value.lstrip().startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def spreadsheet_safe_row(row: dict):
    """Apply formula protection consistently to every text cell in a CSV row."""

    return {key: spreadsheet_safe_value(value) for key, value in row.items()}
