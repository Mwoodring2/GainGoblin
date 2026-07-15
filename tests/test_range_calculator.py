from decimal import Decimal

import pytest

from gaingoblin.range_calculator import (
    RangeScenarioInput,
    calculate_range_scenario,
    validate_range_scenario,
)


def test_range_scenario_profit_math() -> None:
    result = calculate_range_scenario(
        RangeScenarioInput(
            symbol_name="ORC",
            shares=Decimal("100"),
            planned_buy_price=Decimal("7.50"),
            average_low_price=Decimal("6.90"),
            average_high_price=Decimal("8.25"),
            buy_fees=Decimal("0"),
            sell_fees=Decimal("0"),
        )
    )

    assert result.entry_cost == Decimal("750.00")
    assert result.low_value == Decimal("690.00")
    assert result.high_value == Decimal("825.00")
    assert result.low_profit == Decimal("-60.00")
    assert result.high_profit == Decimal("75.00")
    assert result.high_roi_percent == Decimal("10.00")


def test_range_scenario_low_roi_and_break_even_math() -> None:
    result = calculate_range_scenario(
        RangeScenarioInput(
            symbol_name="ORC",
            shares=Decimal("100"),
            planned_buy_price=Decimal("7.50"),
            average_low_price=Decimal("6.90"),
            average_high_price=Decimal("8.25"),
        )
    )

    assert result.low_roi_percent == Decimal("-8.00")
    assert result.break_even_price == Decimal("7.50")
    assert result.price_spread == Decimal("1.35")
    assert result.spread_percent == Decimal("18.00")
    assert result.gain_per_share_at_high == Decimal("0.75")
    assert result.loss_per_share_at_low == Decimal("-0.60")


def test_range_scenario_includes_fees() -> None:
    result = calculate_range_scenario(
        RangeScenarioInput(
            symbol_name="ORC",
            shares=Decimal("10"),
            planned_buy_price=Decimal("10"),
            average_low_price=Decimal("9"),
            average_high_price=Decimal("12"),
            buy_fees=Decimal("5"),
            sell_fees=Decimal("2"),
        )
    )

    assert result.entry_cost == Decimal("105.00")
    assert result.low_value == Decimal("88.00")
    assert result.high_value == Decimal("118.00")
    assert result.high_profit == Decimal("13.00")
    assert result.break_even_price == Decimal("10.70")


def test_zero_shares_returns_validation_error_without_crashing() -> None:
    scenario = RangeScenarioInput(
        symbol_name="ORC",
        shares=Decimal("0"),
        planned_buy_price=Decimal("7.50"),
        average_low_price=Decimal("6.90"),
        average_high_price=Decimal("8.25"),
    )

    assert "Shares must be greater than zero." in validate_range_scenario(scenario)
    with pytest.raises(ValueError, match="Shares must be greater than zero"):
        calculate_range_scenario(scenario)


def test_zero_entry_cost_returns_validation_error_without_crashing() -> None:
    scenario = RangeScenarioInput(
        symbol_name="ORC",
        shares=Decimal("10"),
        planned_buy_price=Decimal("0"),
        average_low_price=Decimal("1"),
        average_high_price=Decimal("2"),
    )

    assert "Planned buy price must be greater than zero." in validate_range_scenario(scenario)
    with pytest.raises(ValueError, match="Planned buy price"):
        calculate_range_scenario(scenario)


def test_average_high_below_average_low_returns_validation_error() -> None:
    scenario = RangeScenarioInput(
        symbol_name="ORC",
        shares=Decimal("10"),
        planned_buy_price=Decimal("7.50"),
        average_low_price=Decimal("8.25"),
        average_high_price=Decimal("6.90"),
    )

    assert "Average high price must be greater than or equal to average low price." in validate_range_scenario(scenario)


def test_negative_numbers_are_rejected() -> None:
    scenario = RangeScenarioInput(
        symbol_name="ORC",
        shares=Decimal("-1"),
        planned_buy_price=Decimal("-7.50"),
        average_low_price=Decimal("-6.90"),
        average_high_price=Decimal("-8.25"),
        buy_fees=Decimal("-1"),
        sell_fees=Decimal("-1"),
    )

    errors = validate_range_scenario(scenario)

    assert "Shares must be greater than zero." in errors
    assert "Planned buy price must be greater than zero." in errors
    assert "Average low price cannot be negative." in errors
    assert "Average high price cannot be negative." in errors
    assert "Buy fees cannot be negative." in errors
    assert "Sell fees cannot be negative." in errors


def test_blank_symbol_is_rejected() -> None:
    errors = validate_range_scenario(
        RangeScenarioInput(
            symbol_name=" ",
            shares=Decimal("10"),
            planned_buy_price=Decimal("7.50"),
            average_low_price=Decimal("6.90"),
            average_high_price=Decimal("8.25"),
        )
    )

    assert "Enter a ticker or symbol." in errors


def test_fees_greater_than_sale_value_are_handled() -> None:
    result = calculate_range_scenario(
        RangeScenarioInput(
            symbol_name="FEE",
            shares=Decimal("1"),
            planned_buy_price=Decimal("1"),
            average_low_price=Decimal("0.50"),
            average_high_price=Decimal("0.75"),
            sell_fees=Decimal("2"),
        )
    )

    assert result.low_value == Decimal("-1.50")
    assert result.high_value == Decimal("-1.25")
    assert result.high_profit == Decimal("-2.25")


def test_range_goblin_note_does_not_contain_recommendation_language() -> None:
    result = calculate_range_scenario(
        RangeScenarioInput(
            symbol_name="ORC",
            shares=Decimal("100"),
            planned_buy_price=Decimal("7.50"),
            average_low_price=Decimal("6.90"),
            average_high_price=Decimal("8.25"),
        )
    )

    note = result.goblin_note.lower()
    forbidden = ("recommend", "prediction", "forecast", "should", "buy", "sell")
    assert all(word not in note for word in forbidden)
