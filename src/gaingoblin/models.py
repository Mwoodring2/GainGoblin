from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class Account:
    name: str
    institution_label: str = ""
    account_type: str = ""
    last_four: str = ""
    notes: str = ""
    id: int | None = None


@dataclass(slots=True)
class Holding:
    symbol_name: str
    shares: Decimal
    buy_price: Decimal
    buy_fees: Decimal
    target_sell_price: Decimal
    sell_fees: Decimal
    notes: str = ""
    id: int | None = None
    account_id: int | None = None
    account_name: str = "Manual Hoard"


@dataclass(frozen=True, slots=True)
class HoldingCalculations:
    cost_basis: Decimal
    target_gross_value: Decimal
    target_net_value: Decimal
    projected_profit: Decimal
    roi_percent: Decimal
    goblin_note: str


@dataclass(frozen=True, slots=True)
class ImportBatch:
    source_path: str
    source_type: str
    row_count: int
    accepted_count: int
    skipped_count: int
    notes: str = ""
    id: int | None = None
