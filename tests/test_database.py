from decimal import Decimal

from gaingoblin.database import HoldingRepository
from gaingoblin.models import Holding


def make_holding(symbol_name: str = "ACME") -> Holding:
    return Holding(
        symbol_name=symbol_name,
        shares=Decimal("12.5"),
        buy_price=Decimal("8.25"),
        buy_fees=Decimal("1.10"),
        target_sell_price=Decimal("11.75"),
        sell_fees=Decimal("1.25"),
        notes="manual test holding",
    )


def test_database_insert_load_update_delete(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")

    holding_id = repository.add_holding(make_holding())
    holdings = repository.list_holdings()

    assert len(holdings) == 1
    assert holdings[0].id == holding_id
    assert holdings[0].symbol_name == "ACME"
    assert holdings[0].shares == Decimal("12.5")
    assert holdings[0].buy_price == Decimal("8.25")
    assert holdings[0].buy_fees == Decimal("1.10")
    assert holdings[0].target_sell_price == Decimal("11.75")
    assert holdings[0].sell_fees == Decimal("1.25")
    assert holdings[0].notes == "manual test holding"

    updated = Holding(
        id=holding_id,
        symbol_name="WIDGET",
        shares=Decimal("3"),
        buy_price=Decimal("100"),
        buy_fees=Decimal("2"),
        target_sell_price=Decimal("125"),
        sell_fees=Decimal("2.50"),
        notes="updated",
    )
    repository.update_holding(updated)

    holdings = repository.list_holdings()
    assert len(holdings) == 1
    assert holdings[0].symbol_name == "WIDGET"
    assert holdings[0].shares == Decimal("3")
    assert holdings[0].notes == "updated"

    repository.delete_holding(holding_id)

    assert repository.list_holdings() == []
