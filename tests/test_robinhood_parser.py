from gaingoblin.importers.robinhood_parser import (
    extract_holdings_section_text,
    is_activity_or_transaction_line,
    parse_robinhood_text,
)


def test_cash_dividend_activity_lines_produce_no_rows() -> None:
    rows = parse_robinhood_text(
        "Cash Div: R/D 06/01 P/D 06/15 4 shares at $0.11 Margin CDIV"
    )

    assert rows == []


def test_transaction_history_block_produces_no_rows() -> None:
    rows = parse_robinhood_text(
        "Account Activity\n"
        "Bought AAPL 2 shares at $150.00 order executed\n"
        "Sold MSFT 1 shares at $320.00 trade confirmation\n"
        "ACH deposit pending\n"
    )

    assert rows == []


def test_r_d_tokens_do_not_create_symbol_r() -> None:
    rows = parse_robinhood_text("R/D 06/01 P/D 06/15 CDIV 10 shares")

    assert rows == []


def test_simple_holdings_section_rows_parse() -> None:
    section = extract_holdings_section_text(
        "Account Summary\n"
        "Portfolio Holdings\n"
        "AAPL Apple Inc. 10 shares Average cost $150.00\n"
        "MSFT Microsoft 5 shares Average cost $320.00\n"
        "Account Activity\n"
        "Cash Div: R/D 06/01 P/D 06/15 CDIV\n"
    )

    assert section is not None
    rows = parse_robinhood_text(section)
    assert len(rows) == 2
    assert rows[0].values["Ticker"] == "AAPL"
    assert rows[1].values["Ticker"] == "MSFT"


def test_activity_helper_flags_known_transaction_terms() -> None:
    assert is_activity_or_transaction_line("Margin interest fee reversal")
    assert is_activity_or_transaction_line("cash sweep transfer")
    assert is_activity_or_transaction_line("order canceled")
