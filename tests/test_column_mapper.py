from decimal import Decimal

import pytest

from gaingoblin.importers.column_mapper import build_column_mapping, parse_decimal


def test_column_aliases_map_common_export_headers() -> None:
    mapping = build_column_mapping(
        [
            "Ticker Symbol",
            "Quantity",
            "Average Cost",
            "Commission",
            "Target",
            "Account Name",
            "Memo",
        ]
    )

    assert mapping["symbol_name"] == "Ticker Symbol"
    assert mapping["shares"] == "Quantity"
    assert mapping["buy_price"] == "Average Cost"
    assert mapping["buy_fees"] == "Commission"
    assert mapping["target_sell_price"] == "Target"
    assert mapping["account_name"] == "Account Name"
    assert mapping["notes"] == "Memo"


def test_money_strings_parse_to_decimal() -> None:
    assert parse_decimal("$1,234.56") == Decimal("1234.56")
    assert parse_decimal("1,234.56") == Decimal("1234.56")
    assert parse_decimal("") == Decimal("0")
    assert parse_decimal("N/A") == Decimal("0")
    assert parse_decimal("($12.50)") == Decimal("-12.50")


def test_required_decimal_raises_for_blank_or_invalid() -> None:
    with pytest.raises(ValueError):
        parse_decimal("", required=True)
    with pytest.raises(ValueError):
        parse_decimal("not money", required=True)
