from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from gaingoblin.models import Holding

DEFAULT_DB_PATH = Path("data") / "gaingoblin.sqlite"


class HoldingRepository:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol_name TEXT NOT NULL,
                    shares TEXT NOT NULL,
                    buy_price TEXT NOT NULL,
                    buy_fees TEXT NOT NULL,
                    target_sell_price TEXT NOT NULL,
                    sell_fees TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def list_holdings(self) -> list[Holding]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, symbol_name, shares, buy_price, buy_fees,
                       target_sell_price, sell_fees, notes
                FROM holdings
                ORDER BY symbol_name COLLATE NOCASE, id
                """
            ).fetchall()
        return [self._row_to_holding(row) for row in rows]

    def add_holding(self, holding: Holding) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO holdings (
                    symbol_name, shares, buy_price, buy_fees,
                    target_sell_price, sell_fees, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._holding_values(holding),
            )
            return int(cursor.lastrowid)

    def update_holding(self, holding: Holding) -> None:
        if holding.id is None:
            raise ValueError("Cannot update a holding without an id.")

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE holdings
                SET symbol_name = ?,
                    shares = ?,
                    buy_price = ?,
                    buy_fees = ?,
                    target_sell_price = ?,
                    sell_fees = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*self._holding_values(holding), holding.id),
            )

    def delete_holding(self, holding_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))

    def replace_all(self, holdings: Iterable[Holding]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM holdings")
            connection.executemany(
                """
                INSERT INTO holdings (
                    symbol_name, shares, buy_price, buy_fees,
                    target_sell_price, sell_fees, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [self._holding_values(holding) for holding in holdings],
            )

    @staticmethod
    def _holding_values(holding: Holding) -> tuple[str, str, str, str, str, str, str]:
        return (
            holding.symbol_name.strip(),
            str(holding.shares),
            str(holding.buy_price),
            str(holding.buy_fees),
            str(holding.target_sell_price),
            str(holding.sell_fees),
            holding.notes,
        )

    @staticmethod
    def _row_to_holding(row: sqlite3.Row) -> Holding:
        return Holding(
            id=int(row["id"]),
            symbol_name=row["symbol_name"],
            shares=Decimal(row["shares"]),
            buy_price=Decimal(row["buy_price"]),
            buy_fees=Decimal(row["buy_fees"]),
            target_sell_price=Decimal(row["target_sell_price"]),
            sell_fees=Decimal(row["sell_fees"]),
            notes=row["notes"],
        )
