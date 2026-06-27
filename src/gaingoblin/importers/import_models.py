from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RawImportRow:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class ImportPreviewRow:
    row_number: int
    symbol_name: str
    shares: Decimal
    buy_price: Decimal
    buy_fees: Decimal
    target_sell_price: Decimal
    sell_fees: Decimal
    notes: str
    account_name: str
    status: str
    message: str


@dataclass(frozen=True, slots=True)
class ImportResult:
    imported_count: int
    skipped_count: int
    messages: list[str]
    batch_id: int | None = None
