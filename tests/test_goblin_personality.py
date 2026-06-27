from decimal import Decimal

from gaingoblin.goblin_personality import (
    PortfolioPersonalityState,
    goblin_note_for_roi,
    mood_for_state,
    speech_for_state,
)


def test_negative_profit_note() -> None:
    assert goblin_note_for_roi(Decimal("-10"), Decimal("-100")) == "Goblin stepped on a rake"


def test_tiny_snack_note() -> None:
    assert goblin_note_for_roi(Decimal("5"), Decimal("10")) == "Tiny snack"


def test_respectable_loot_note() -> None:
    assert goblin_note_for_roi(Decimal("12"), Decimal("100")) == "Respectable loot"


def test_dragon_hoard_note() -> None:
    assert goblin_note_for_roi(Decimal("150"), Decimal("1000")) == "Dragon-hoard territory"


def test_missing_targets_mood_is_thinking() -> None:
    state = PortfolioPersonalityState(
        total_cost_basis=Decimal("100"),
        target_net_value=Decimal("150"),
        projected_profit=Decimal("50"),
        roi_percent=Decimal("50"),
        missing_target_count=1,
    )

    assert mood_for_state(state) == "thinking"
    assert "exit plan" in speech_for_state(state)


def test_negative_profit_mood_is_worried() -> None:
    state = PortfolioPersonalityState(
        total_cost_basis=Decimal("100"),
        target_net_value=Decimal("80"),
        projected_profit=Decimal("-20"),
        roi_percent=Decimal("-20"),
        missing_target_count=0,
    )

    assert mood_for_state(state) == "worried"


def test_high_roi_mood_is_greedy() -> None:
    state = PortfolioPersonalityState(
        total_cost_basis=Decimal("100"),
        target_net_value=Decimal("250"),
        projected_profit=Decimal("150"),
        roi_percent=Decimal("150"),
        missing_target_count=0,
    )

    assert mood_for_state(state) == "greedy"
    assert speech_for_state(state) == "Dragon-hoard territory!"
