from __future__ import annotations

import csv
import re
from io import StringIO

from gaingoblin.importers.column_mapper import build_column_mapping
from gaingoblin.importers.import_models import RawImportRow

CANONICAL_EXPORT_HEADERS = {
    "symbol_name": "Ticker",
    "shares": "Quantity",
    "buy_price": "Average Cost",
    "target_sell_price": "Target",
    "account_name": "Account",
    "notes": "Notes",
}

HOLDINGS_SECTION_HEADINGS = (
    "holdings",
    "positions",
    "portfolio holdings",
    "account holdings",
    "equities",
    "stocks",
    "securities held",
)
STOP_SECTION_HEADINGS = (
    "account activity",
    "activity",
    "history",
    "transactions",
    "dividends",
    "cash management",
    "margin",
    "disclosures",
)

_TICKER_RE = re.compile(r"\b[A-Z]{1,6}(?:\.[A-Z])?\b")
_SHARES_RE = re.compile(
    r"(?:(?:shares?|quantity|qty|position|units)\s*:?\s*)"
    r"(-?\d+(?:,\d{3})*(?:\.\d+)?)"
    r"|(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:shares?|sh)\b",
    re.IGNORECASE,
)
_PRICE_LABEL_RE = re.compile(
    r"(?:average\s+cost|avg\s+cost|average\s+price|avg\s+price|"
    r"cost\s+basis\s+per\s+share|price\s+paid|buy\s+price)"
    r"\s*(?:/share|per\s+share)?\s*:?\s*\$?\s*"
    r"(-?\d+(?:,\d{3})*(?:\.\d+)?)",
    re.IGNORECASE,
)
_ACCOUNT_RE = re.compile(r"\b(?:account|portfolio)\s*:?\s*(.+)", re.IGNORECASE)
_IGNORE_SYMBOLS = {
    "ACCOUNT",
    "ACH",
    "ATM",
    "AVERAGE",
    "AVG",
    "BALANCE",
    "BUY",
    "CASH",
    "CDIV",
    "COST",
    "CURRENT",
    "D",
    "DESCRIPTION",
    "DIV",
    "EQUITY",
    "GAIN",
    "HOLDINGS",
    "IRA",
    "LOSS",
    "MARGIN",
    "MARKET",
    "NAME",
    "P",
    "PORTFOLIO",
    "PRICE",
    "QUANTITY",
    "R",
    "SHARES",
    "SYMBOL",
    "TOTAL",
    "USD",
    "VALUE",
}
_ACTIVITY_TERMS = (
    "cash div",
    "cdiv",
    "r/d",
    "p/d",
    "dividend",
    "interest",
    "margin interest",
    "transfer",
    "deposit",
    "withdrawal",
    "cash sweep",
    "fee",
    "reversal",
    "journal",
    "bought",
    "sold",
    "order",
    "executed",
    "trade confirmation",
    "pending",
    "canceled",
    "cancelled",
    "assigned",
    "expired",
)


def parse_tabular_text(text: str) -> list[RawImportRow]:
    lines = _non_empty_lines(text)
    if len(lines) < 2:
        return []

    delimiter = _detect_delimiter(lines[0])
    rows = _split_rows(lines, delimiter)
    if len(rows) < 2:
        return []

    headers = rows[0]
    mapping = build_column_mapping(headers)
    if not {"symbol_name", "shares", "buy_price"}.issubset(mapping):
        return []

    results: list[RawImportRow] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(value.strip() for value in values):
            continue
        if is_activity_or_transaction_line(" ".join(values)):
            continue
        padded = values + [""] * max(0, len(headers) - len(values))
        row_values = {
            header: value.strip()
            for header, value in zip(headers, padded)
            if header.strip()
        }
        if any(value for value in row_values.values()):
            results.append(RawImportRow(row_number=row_number, values=row_values))
    return results


def parse_robinhood_text(text: str) -> list[RawImportRow]:
    lines = _non_empty_lines(text)
    if not lines:
        return []

    line_rows: list[RawImportRow] = []
    for row_number, line in enumerate(lines, start=1):
        parsed = _parse_block(row_number, [line])
        if parsed is not None:
            line_rows.append(parsed)
    if len(line_rows) > 1:
        return line_rows

    blocks = _blocks(text)
    if blocks:
        parsed_blocks = [_parse_block(index + 1, block) for index, block in enumerate(blocks)]
        rows = [row for row in parsed_blocks if row is not None]
        if rows:
            return rows

    return line_rows


def extract_holdings_section_text(text: str) -> str | None:
    selected: list[str] = []
    collecting = False
    found_section = False

    for line in _non_empty_lines(text):
        if _is_holdings_section_heading(line):
            collecting = True
            found_section = True
            selected.append(line)
            continue
        if _is_stop_section_heading(line):
            collecting = False
            continue
        if collecting:
            selected.append(line)

    if not found_section:
        return None
    return "\n".join(selected).strip()


def is_activity_or_transaction_line(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not normalized:
        return False

    for term in _ACTIVITY_TERMS:
        if "/" in term or " " in term:
            if term in normalized:
                return True
        elif re.search(rf"\b{re.escape(term)}\b", normalized):
            return True
    return False


def raw_row_from_detected_values(
    row_number: int,
    *,
    symbol: str,
    shares: str = "",
    buy_price: str = "",
    account_name: str = "",
    original_text: str,
) -> RawImportRow:
    values = {
        CANONICAL_EXPORT_HEADERS["symbol_name"]: symbol.upper(),
        CANONICAL_EXPORT_HEADERS["shares"]: _clean_number(shares),
        CANONICAL_EXPORT_HEADERS["buy_price"]: _clean_number(buy_price),
        CANONICAL_EXPORT_HEADERS["target_sell_price"]: "0",
        CANONICAL_EXPORT_HEADERS["account_name"]: account_name.strip(),
        CANONICAL_EXPORT_HEADERS["notes"]: original_text.strip(),
    }
    return RawImportRow(row_number=row_number, values=values)


def _parse_block(row_number: int, block_lines: list[str]) -> RawImportRow | None:
    clean_lines = [line.strip() for line in block_lines if line.strip()]
    original = " | ".join(clean_lines)
    if not original or is_activity_or_transaction_line(original):
        return None

    symbol = _find_symbol(original)
    shares = _find_shares(original)
    buy_price = _find_buy_price(original)
    account_name = _find_account_name(clean_lines)

    if symbol is None:
        return None
    if shares is None and buy_price is None:
        return None

    return raw_row_from_detected_values(
        row_number,
        symbol=symbol,
        shares=shares or "",
        buy_price=buy_price or "",
        account_name=account_name,
        original_text=original,
    )


def _find_symbol(text: str) -> str | None:
    for match in _TICKER_RE.finditer(text):
        value = match.group(0).upper()
        start, end = match.span()
        previous_char = text[start - 1] if start > 0 else ""
        next_char = text[end] if end < len(text) else ""
        if previous_char == "/" or next_char == "/":
            continue
        if value not in _IGNORE_SYMBOLS and not value.isdigit():
            return value
    return None


def _find_shares(text: str) -> str | None:
    match = _SHARES_RE.search(text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _find_buy_price(text: str) -> str | None:
    match = _PRICE_LABEL_RE.search(text)
    if match:
        return match.group(1)
    return None


def _find_account_name(lines: list[str]) -> str:
    for line in lines:
        match = _ACCOUNT_RE.search(line)
        if match:
            return match.group(1).strip()
    return ""


def _blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(clean)
    if current:
        blocks.append(current)
    return blocks


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _detect_delimiter(header_line: str) -> str | None:
    if "\t" in header_line:
        return "\t"
    if "," in header_line:
        return ","
    return None


def _split_rows(lines: list[str], delimiter: str | None) -> list[list[str]]:
    if delimiter == ",":
        reader = csv.reader(StringIO("\n".join(lines)))
        return [[cell.strip() for cell in row] for row in reader]
    if delimiter == "\t":
        return [[cell.strip() for cell in line.split("\t")] for line in lines]
    return [[cell.strip() for cell in re.split(r"\s{2,}", line.strip())] for line in lines]


def _is_holdings_section_heading(line: str) -> bool:
    normalized = _normalize_heading(line)
    if len(normalized.split()) > 5:
        return False
    return any(term in normalized for term in HOLDINGS_SECTION_HEADINGS)


def _is_stop_section_heading(line: str) -> bool:
    normalized = _normalize_heading(line)
    if len(normalized.split()) > 5:
        return False
    return any(term == normalized or normalized.startswith(term) for term in STOP_SECTION_HEADINGS)


def _normalize_heading(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9& ]+", " ", line.lower())).strip()


def _clean_number(value: str) -> str:
    return value.replace("$", "").replace(",", "").strip()
