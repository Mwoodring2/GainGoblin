"""Tests for neutral current-quote comparison math."""

from decimal import Decimal

from gaingoblin.quote_comparison import calculate_quote_comparison


def test_current_quote_comparison_math() -> None:
    comparison = calculate_quote_comparison(
        shares="432",
        planned_buy_price="230.61",
        buy_fees="0",
        sell_fees="0",
        current_quote="253.85",
    )

    assert comparison.current_quote == Decimal("253.85")
    assert comparison.per_share_difference == Decimal("23.24")
    assert comparison.position_difference == Decimal("10039.68")
    assert comparison.roi_percent == Decimal("10.08")


def test_current_quote_comparison_includes_fees() -> None:
    comparison = calculate_quote_comparison(
        shares=10,
        planned_buy_price="10",
        buy_fees="1",
        sell_fees="1",
        current_quote="12",
    )

    assert comparison.entry_cost == Decimal("101.00")
    assert comparison.position_difference == Decimal("18.00")
    assert comparison.roi_percent == Decimal("17.82")
