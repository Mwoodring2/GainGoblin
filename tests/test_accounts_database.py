from decimal import Decimal

from gaingoblin.database import DEFAULT_ACCOUNT_NAME, HoldingRepository
from gaingoblin.models import Holding


def test_accounts_database_and_import_batches(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")

    accounts = repository.list_accounts()
    assert any(account.name == DEFAULT_ACCOUNT_NAME for account in accounts)

    account = repository.get_or_create_account("Fidelity IRA")
    assert repository.get_or_create_account("fidelity ira").id == account.id

    holding_id = repository.add_holding_to_account(
        Holding(
            account_id=account.id,
            account_name=account.name,
            symbol_name="ACME",
            shares=Decimal("4"),
            buy_price=Decimal("25"),
            buy_fees=Decimal("1.50"),
            target_sell_price=Decimal("30"),
            sell_fees=Decimal("0"),
            notes="imported",
        ),
        account.id,
    )

    assert repository.holding_exists(account.id, "acme")
    ira_holdings = repository.list_holdings(account.id)
    assert len(ira_holdings) == 1
    assert ira_holdings[0].id == holding_id
    assert ira_holdings[0].account_name == "Fidelity IRA"

    batch_id = repository.record_import_batch(
        source_path="holdings.csv",
        source_type="csv",
        row_count=3,
        accepted_count=2,
        skipped_count=1,
        notes="test batch",
    )
    batches = repository.list_import_batches()
    assert batches[0].id == batch_id
    assert batches[0].accepted_count == 2
    assert batches[0].skipped_count == 1
