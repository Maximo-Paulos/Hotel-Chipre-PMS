import pytest

from app.services.csv_export_safety import spreadsheet_safe_row, spreadsheet_safe_value
from app.services.analytics_exports import _rows_to_csv_bytes


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1:A2)", "-1+2", "@cmd", "  =1+1", "\t=1+1", "\r\n=1+1"])
def test_formula_like_csv_text_is_forced_to_text(value):
    assert spreadsheet_safe_value(value) == f"'{value}"


def test_normal_csv_values_and_numeric_values_are_preserved():
    row = {"actor": "Night Lead", "amount": -5, "empty": ""}

    assert spreadsheet_safe_row(row) == row


@pytest.mark.parametrize("value", ["-123.45", "+99", "0", "1e3"])
def test_plain_numeric_csv_cells_are_not_converted_to_text(value):
    assert spreadsheet_safe_value(value) == value


def test_analytics_csv_quotes_formula_like_user_controlled_text():
    csv_bytes = _rows_to_csv_bytes(
        [["section", "key", "value"], ["company", "notes", "=HYPERLINK(\"https://evil.test\")"]]
    )
    assert b"'=HYPERLINK" in csv_bytes
