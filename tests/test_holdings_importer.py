from decimal import Decimal

from gaingoblin.database import HoldingRepository
from gaingoblin.importers.holdings_importer import create_import_preview, import_preview_rows
from gaingoblin.importers.import_models import RawImportRow
from gaingoblin.models import Holding


def row(number: int, **values: str) -> RawImportRow:
    return RawImportRow(row_number=number, values=values)


def test_preview_imports_decimal_values_and_blank_target_defaults_to_zero() -> None:
    preview = create_import_preview(
        [
            row(
                2,
                Ticker="orc",
                Quantity="10.5",
                **{"Average Cost": "$1,234.56"},
                Target="",
                Account="Robinhood Main",
                Memo="needs target",
            )
        ]
    )

    assert len(preview) == 1
    assert preview[0].status == "accepted"
    assert preview[0].symbol_name == "ORC"
    assert preview[0].shares == Decimal("10.5")
    assert preview[0].buy_price == Decimal("1234.56")
    assert preview[0].target_sell_price == Decimal("0")
    assert preview[0].account_name == "Robinhood Main"


def test_missing_required_fields_are_skipped() -> None:
    preview = create_import_preview(
        [
            row(2, Ticker="", Quantity="10", **{"Average Cost": "1"}),
            row(3, Ticker="VTI", Quantity="", **{"Average Cost": "1"}),
        ]
    )

    assert preview[0].status == "skipped"
    assert preview[0].message == "Missing symbol."
    assert preview[1].status == "skipped"
    assert "Required numeric value" in preview[1].message


def test_duplicate_rows_and_existing_holdings_are_skipped(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    account = repository.get_or_create_account("Robinhood Main")
    repository.add_holding_to_account(
        Holding(
            account_id=account.id,
            account_name=account.name,
            symbol_name="ORC",
            shares=Decimal("1"),
            buy_price=Decimal("1"),
            buy_fees=Decimal("0"),
            target_sell_price=Decimal("2"),
            sell_fees=Decimal("0"),
        ),
        account.id,
    )

    preview = create_import_preview(
        [
            row(2, Ticker="ORC", Quantity="10", **{"Average Cost": "1"}, Account="Robinhood Main"),
            row(3, Ticker="VTI", Quantity="2", **{"Average Cost": "250"}, Account="Fidelity IRA"),
            row(4, Ticker="VTI", Quantity="3", **{"Average Cost": "251"}, Account="Fidelity IRA"),
        ],
        repository,
    )

    assert preview[0].status == "skipped"
    assert preview[0].message == "Already exists in this account."
    assert preview[1].status == "accepted"
    assert preview[2].status == "skipped"
    assert preview[2].message == "Duplicate row in import file."


def test_preview_duplicate_check_does_not_create_accounts(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")

    create_import_preview(
        [row(2, Ticker="VTI", Quantity="2", **{"Average Cost": "250"}, Account="Schwab Brokerage")],
        repository,
    )

    assert repository.find_account_by_name("Schwab Brokerage") is None


def test_import_preview_creates_account_holding_and_batch(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    preview = create_import_preview(
        [
            row(
                2,
                Ticker="VTI",
                Quantity="2",
                **{"Average Cost": "250.25"},
                Target="300",
                Account="Fidelity IRA",
                Memo="index fund",
            )
        ],
        repository,
    )

    result = import_preview_rows(repository, preview, "holdings.csv", "csv")

    assert result.imported_count == 1
    assert result.skipped_count == 0
    account = repository.find_account_by_name("Fidelity IRA")
    assert account is not None
    holdings = repository.list_holdings(account.id)
    assert len(holdings) == 1
    assert holdings[0].symbol_name == "VTI"
    assert holdings[0].shares == Decimal("2")
    assert holdings[0].buy_price == Decimal("250.25")
    assert holdings[0].target_sell_price == Decimal("300")
    assert holdings[0].notes == "index fund"
    batches = repository.list_import_batches()
    assert batches[0].row_count == 1
    assert batches[0].accepted_count == 1
