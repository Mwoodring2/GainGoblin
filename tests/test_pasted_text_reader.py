from decimal import Decimal

from gaingoblin.database import HoldingRepository
from gaingoblin.importers.holdings_importer import create_import_preview, import_preview_rows
from gaingoblin.importers.pasted_text_reader import read_pasted_text


def test_pasted_tabular_text_with_headers_imports() -> None:
    rows = read_pasted_text(
        "Ticker\tShares\tAverage Cost\tAccount\n"
        "AAPL\t10\t150.00\tRobinhood Main\n"
    )

    preview = create_import_preview(rows)

    assert len(preview) == 1
    assert preview[0].status == "accepted"
    assert preview[0].symbol_name == "AAPL"
    assert preview[0].shares == Decimal("10")
    assert preview[0].buy_price == Decimal("150.00")
    assert preview[0].account_name == "Robinhood Main"


def test_pasted_robinhood_like_rows_parse_cautiously() -> None:
    rows = read_pasted_text(
        "AAPL\nApple Inc.\n10 shares\nAverage cost $150.00\n\n"
        "MSFT Microsoft 5 shares Avg cost $320.00\n"
    )

    preview = create_import_preview(rows)

    assert [row.symbol_name for row in preview] == ["AAPL", "MSFT"]
    assert preview[0].shares == Decimal("10")
    assert preview[0].buy_price == Decimal("150.00")
    assert preview[0].target_sell_price == Decimal("0")
    assert "Apple Inc." in preview[0].notes


def test_missing_buy_price_skips_row() -> None:
    rows = read_pasted_text("AAPL\n10 shares\n")

    preview = create_import_preview(rows)

    assert len(preview) == 1
    assert preview[0].status == "skipped"
    assert "Required numeric value" in preview[0].message


def test_unlabeled_money_does_not_become_buy_price() -> None:
    rows = read_pasted_text("AAPL 10 shares $150.00")

    preview = create_import_preview(rows)

    assert len(preview) == 1
    assert preview[0].status == "skipped"
    assert "Required numeric value" in preview[0].message


def test_non_holding_pasted_lines_are_ignored() -> None:
    rows = read_pasted_text("Portfolio value\nBuying power\nNo positions here")

    assert rows == []


def test_pasted_activity_rows_are_ignored() -> None:
    rows = read_pasted_text(
        "Cash Div: R/D 06/01 P/D 06/15 4 shares at $0.11 Margin CDIV\n"
        "Bought AAPL 2 shares at $150.00 order executed\n"
    )

    assert rows == []


def test_duplicate_account_symbol_is_skipped_for_paste(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    rows = read_pasted_text(
        "Ticker\tShares\tAverage Cost\tAccount\n"
        "AAPL\t10\t150.00\tRobinhood Main\n"
        "AAPL\t12\t155.00\tRobinhood Main\n"
    )

    preview = create_import_preview(rows, repository)

    assert preview[0].status == "accepted"
    assert preview[1].status == "skipped"
    assert preview[1].message == "Duplicate row in import file."


def test_import_batch_source_type_supports_pasted_text(tmp_path) -> None:
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    preview = create_import_preview(read_pasted_text("AAPL 10 shares Average cost $150.00"), repository)

    result = import_preview_rows(repository, preview, "Pasted text/table", "pasted_text")

    assert result.imported_count == 1
    assert repository.list_import_batches()[0].source_type == "pasted_text"
