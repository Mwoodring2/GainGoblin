from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class RangeScenarioInput:
    symbol_name: str
    shares: Decimal
    planned_buy_price: Decimal
    average_low_price: Decimal
    average_high_price: Decimal
    buy_fees: Decimal = Decimal("0")
    sell_fees: Decimal = Decimal("0")
    notes: str = ""


@dataclass(frozen=True, slots=True)
class RangeScenarioResult:
    symbol_name: str
    shares: Decimal
    entry_cost: Decimal
    low_value: Decimal
    high_value: Decimal
    low_profit: Decimal
    high_profit: Decimal
    low_roi_percent: Decimal
    high_roi_percent: Decimal
    break_even_price: Decimal
    price_spread: Decimal
    spread_percent: Decimal
    gain_per_share_at_high: Decimal
    loss_per_share_at_low: Decimal
    goblin_note: str


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def validate_range_scenario(scenario: RangeScenarioInput) -> list[str]:
    errors: list[str] = []

    if not scenario.symbol_name.strip():
        errors.append("Enter a ticker or symbol.")
    if scenario.shares <= ZERO:
        errors.append("Shares must be greater than zero.")
    if scenario.planned_buy_price <= ZERO:
        errors.append("Planned buy price must be greater than zero.")
    if scenario.average_low_price < ZERO:
        errors.append("Average low price cannot be negative.")
    if scenario.average_high_price < ZERO:
        errors.append("Average high price cannot be negative.")
    if scenario.buy_fees < ZERO:
        errors.append("Buy fees cannot be negative.")
    if scenario.sell_fees < ZERO:
        errors.append("Sell fees cannot be negative.")
    if scenario.average_high_price < scenario.average_low_price:
        errors.append("Average high price must be greater than or equal to average low price.")

    return errors


def calculate_range_scenario(scenario: RangeScenarioInput) -> RangeScenarioResult:
    errors = validate_range_scenario(scenario)
    if errors:
        raise ValueError(" ".join(errors))

    entry_cost_raw = scenario.shares * scenario.planned_buy_price + scenario.buy_fees
    low_value_raw = scenario.shares * scenario.average_low_price - scenario.sell_fees
    high_value_raw = scenario.shares * scenario.average_high_price - scenario.sell_fees
    low_profit_raw = low_value_raw - entry_cost_raw
    high_profit_raw = high_value_raw - entry_cost_raw

    low_roi_raw = Decimal("0")
    high_roi_raw = Decimal("0")
    if entry_cost_raw > ZERO:
        low_roi_raw = low_profit_raw / entry_cost_raw * ONE_HUNDRED
        high_roi_raw = high_profit_raw / entry_cost_raw * ONE_HUNDRED

    break_even_raw = Decimal("0")
    if scenario.shares > ZERO:
        break_even_raw = (entry_cost_raw + scenario.sell_fees) / scenario.shares

    price_spread_raw = scenario.average_high_price - scenario.average_low_price
    spread_percent_raw = Decimal("0")
    if scenario.planned_buy_price > ZERO:
        spread_percent_raw = price_spread_raw / scenario.planned_buy_price * ONE_HUNDRED

    result = RangeScenarioResult(
        symbol_name=scenario.symbol_name.strip(),
        shares=scenario.shares,
        entry_cost=money(entry_cost_raw),
        low_value=money(low_value_raw),
        high_value=money(high_value_raw),
        low_profit=money(low_profit_raw),
        high_profit=money(high_profit_raw),
        low_roi_percent=percent(low_roi_raw),
        high_roi_percent=percent(high_roi_raw),
        break_even_price=money(break_even_raw),
        price_spread=money(price_spread_raw),
        spread_percent=percent(spread_percent_raw),
        gain_per_share_at_high=money(scenario.average_high_price - scenario.planned_buy_price),
        loss_per_share_at_low=money(scenario.average_low_price - scenario.planned_buy_price),
        goblin_note="",
    )
    return replace(result, goblin_note=range_goblin_note(result))


def range_goblin_note(result: RangeScenarioResult) -> str:
    if result.entry_cost <= ZERO:
        return "Goblin needs real numbers."
    if result.high_profit <= ZERO:
        return "No shiny upside in this range."
    if result.low_profit < ZERO and result.high_profit > ZERO:
        return "Risk below, loot above. Count carefully."
    if result.low_profit >= ZERO:
        return "Whole range is above your entry math."
    if result.spread_percent >= Decimal("25"):
        return "Wide range. Volatile treasure."
    return "Range math tallied."
