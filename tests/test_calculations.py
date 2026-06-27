from decimal import Decimal

from gaingoblin.calculations import calculate_holding, goblin_note
from gaingoblin.models import Holding


def make_holding(**overrides) -> Holding:
    values = {
        "symbol_name": "ACME",
        "shares": Decimal("10"),
        "buy_price": Decimal("20"),
        "buy_fees": Decimal("5"),
        "target_sell_price": Decimal("30"),
        "sell_fees": Decimal("3"),
        "notes": "",
    }
    values.update(overrides)
    return Holding(**values)


def test_cost_basis_math() -> None:
    calculated = calculate_holding(make_holding())

    assert calculated.cost_basis == Decimal("205.00")


def test_target_net_value_math() -> None:
    calculated = calculate_holding(make_holding())

    assert calculated.target_gross_value == Decimal("300.00")
    assert calculated.target_net_value == Decimal("297.00")


def test_projected_profit_math() -> None:
    calculated = calculate_holding(make_holding())

    assert calculated.projected_profit == Decimal("92.00")


def test_roi_math() -> None:
    calculated = calculate_holding(make_holding())

    assert calculated.roi_percent == Decimal("44.88")


def test_zero_cost_basis_does_not_crash() -> None:
    calculated = calculate_holding(
        make_holding(
            shares=Decimal("0"),
            buy_price=Decimal("0"),
            buy_fees=Decimal("0"),
            target_sell_price=Decimal("10"),
            sell_fees=Decimal("0"),
        )
    )

    assert calculated.cost_basis == Decimal("0.00")
    assert calculated.roi_percent == Decimal("0.00")


def test_negative_profit() -> None:
    calculated = calculate_holding(make_holding(target_sell_price=Decimal("10")))

    assert calculated.projected_profit == Decimal("-108.00")
    assert calculated.goblin_note == "Goblin stepped on a rake"


def test_goblin_note_categories() -> None:
    assert goblin_note(Decimal("-1"), Decimal("-1")) == "Goblin stepped on a rake"
    assert goblin_note(Decimal("0"), Decimal("0")) == "Tiny snack"
    assert goblin_note(Decimal("1"), Decimal("5")) == "Tiny snack"
    assert goblin_note(Decimal("1"), Decimal("5.01")) == "Respectable loot"
    assert goblin_note(Decimal("1"), Decimal("20")) == "Respectable loot"
    assert goblin_note(Decimal("1"), Decimal("20.01")) == "Goblin is interested"
    assert goblin_note(Decimal("1"), Decimal("50")) == "Goblin is interested"
    assert goblin_note(Decimal("1"), Decimal("50.01")) == "Shiny pile"
    assert goblin_note(Decimal("1"), Decimal("100")) == "Shiny pile"
    assert goblin_note(Decimal("1"), Decimal("100.01")) == "Dragon-hoard territory"
