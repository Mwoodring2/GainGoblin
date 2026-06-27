from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from gaingoblin.goblin_personality import goblin_note_for_roi
from gaingoblin.models import Holding, HoldingCalculations

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


def to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip() or "0")
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def calculate_holding(holding: Holding) -> HoldingCalculations:
    cost_basis = holding.shares * holding.buy_price + holding.buy_fees
    target_gross_value = holding.shares * holding.target_sell_price
    target_net_value = target_gross_value - holding.sell_fees
    projected_profit = target_net_value - cost_basis
    roi_percent = ZERO

    if cost_basis != ZERO:
        roi_percent = projected_profit / cost_basis * ONE_HUNDRED

    roi_percent = percent(roi_percent)
    return HoldingCalculations(
        cost_basis=money(cost_basis),
        target_gross_value=money(target_gross_value),
        target_net_value=money(target_net_value),
        projected_profit=money(projected_profit),
        roi_percent=roi_percent,
        goblin_note=goblin_note(projected_profit, roi_percent),
    )


def goblin_note(projected_profit: Decimal, roi_percent: Decimal) -> str:
    return goblin_note_for_roi(roi_percent, projected_profit)


def portfolio_summary(holdings: list[Holding]) -> dict[str, Decimal]:
    total_cost_basis = ZERO
    target_net_value = ZERO
    projected_profit = ZERO

    for holding in holdings:
        calculated = calculate_holding(holding)
        total_cost_basis += calculated.cost_basis
        target_net_value += calculated.target_net_value
        projected_profit += calculated.projected_profit

    roi_percent = ZERO
    if total_cost_basis != ZERO:
        roi_percent = projected_profit / total_cost_basis * ONE_HUNDRED

    return {
        "total_cost_basis": money(total_cost_basis),
        "target_net_value": money(target_net_value),
        "projected_profit": money(projected_profit),
        "roi_percent": percent(roi_percent),
    }
