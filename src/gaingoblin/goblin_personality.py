from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PortfolioPersonalityState:
    total_cost_basis: Decimal
    target_net_value: Decimal
    projected_profit: Decimal
    roi_percent: Decimal
    missing_target_count: int = 0


def goblin_note_for_roi(roi_percent: Decimal, projected_profit: Decimal) -> str:
    if projected_profit < Decimal("0"):
        return "Goblin stepped on a rake"
    if roi_percent <= Decimal("5"):
        return "Tiny snack"
    if roi_percent <= Decimal("20"):
        return "Respectable loot"
    if roi_percent <= Decimal("50"):
        return "Goblin is interested"
    if roi_percent <= Decimal("100"):
        return "Shiny pile"
    return "Dragon-hoard territory"


def mood_for_state(state: PortfolioPersonalityState) -> str:
    if state.missing_target_count > 0:
        return "thinking"
    if state.projected_profit < Decimal("0"):
        return "worried"
    if state.roi_percent >= Decimal("100"):
        return "greedy"
    if state.projected_profit > Decimal("0"):
        return "happy"
    return "idle"


def speech_for_state(state: PortfolioPersonalityState) -> str:
    if state.missing_target_count > 0:
        if state.missing_target_count == 1:
            return "One treasure lacks an exit plan."
        return f"{state.missing_target_count} treasures lack exit plans."

    if state.projected_profit < Decimal("0"):
        return "Oof. Bad loot."

    if state.total_cost_basis <= Decimal("0"):
        return "Your hoard is empty. Feed it numbers."

    if state.roi_percent <= Decimal("5"):
        return "Tiny snack."

    if state.roi_percent <= Decimal("20"):
        return "Respectable loot."

    if state.roi_percent <= Decimal("50"):
        return "Goblin likes this pile."

    if state.roi_percent <= Decimal("100"):
        return "Oho, shiny pile!"

    return "Dragon-hoard territory!"
