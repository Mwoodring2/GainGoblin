from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")

COLUMN_ALIASES = {
    "symbol_name": [
        "symbol_name",
        "symbol name",
        "symbol",
        "ticker",
        "ticker symbol",
        "asset",
        "security",
        "name",
        "instrument",
    ],
    "shares": [
        "shares",
        "quantity",
        "qty",
        "position",
        "units",
    ],
    "buy_price": [
        "buy_price",
        "average cost",
        "avg cost",
        "cost basis per share",
        "purchase price",
        "buy price",
        "average price",
        "avg price",
        "price paid",
    ],
    "buy_fees": [
        "buy_fees",
        "fees",
        "commission",
        "buy fees",
        "purchase fees",
    ],
    "target_sell_price": [
        "target_sell_price",
        "target sell price",
        "target",
        "sell target",
        "planned sell",
    ],
    "sell_fees": [
        "sell_fees",
        "sell fees",
        "sale fees",
        "estimated sell fees",
        "exit fees",
    ],
    "account_name": [
        "account_name",
        "account",
        "account name",
        "portfolio",
        "brokerage",
    ],
    "notes": [
        "notes",
        "memo",
        "comment",
    ],
}


def normalize_column_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " ")).strip()


def build_column_mapping(headers: list[str]) -> dict[str, str]:
    normalized_headers = {normalize_column_name(header): header for header in headers if header}
    mapping: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_column_name(alias)
            if normalized_alias in normalized_headers:
                mapping[canonical] = normalized_headers[normalized_alias]
                break
    return mapping


def parse_decimal(value: object, *, required: bool = False) -> Decimal:
    text = "" if value is None else str(value).strip()
    if text == "" or text.upper() in {"N/A", "NA", "NONE", "--"}:
        if required:
            raise ValueError("Required numeric value is missing.")
        return ZERO

    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace("$", "").replace(",", "").replace("%", "").strip()
    if negative:
        cleaned = "-" + cleaned.strip("()")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        if required:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc
        return ZERO
