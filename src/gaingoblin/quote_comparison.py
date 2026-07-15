"""Neutral current-quote comparison helpers for the Range Calculator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from gaingoblin.calculations import ONE_HUNDRED, ZERO, money, percent, to_decimal


@dataclass(frozen=True, slots=True)
class QuoteComparison:
    """Informational comparison of a quote versus the planned buy cost."""

    current_quote: Decimal
    per_share_difference: Decimal
    position_difference: Decimal
    roi_percent: Decimal
    entry_cost: Decimal


def calculate_quote_comparison(
    shares: Decimal | int | str,
    planned_buy_price: Decimal | int | str,
    buy_fees: Decimal | int | str,
    sell_fees: Decimal | int | str,
    current_quote: Decimal | int | str,
) -> QuoteComparison:
    """Compare an optional current quote to the entered buy plan using fees.

    This is informational only and does not alter range-scenario math.
    """
    share_count = to_decimal(shares)
    buy_price = to_decimal(planned_buy_price)
    buy_fee = to_decimal(buy_fees)
    sell_fee = to_decimal(sell_fees)
    quote = to_decimal(current_quote)
    entry_cost = money(share_count * buy_price + buy_fee)
    current_net = money(share_count * quote - sell_fee)
    position_difference = money(current_net - entry_cost)
    per_share_difference = money(quote - buy_price)
    roi = ZERO
    if entry_cost != ZERO:
        roi = percent(position_difference / entry_cost * ONE_HUNDRED)
    return QuoteComparison(
        current_quote=money(quote),
        per_share_difference=per_share_difference,
        position_difference=position_difference,
        roi_percent=roi,
        entry_cost=entry_cost,
    )
