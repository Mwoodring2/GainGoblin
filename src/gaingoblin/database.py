from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

from gaingoblin.models import Account, Holding, ImportBatch

DEFAULT_DB_PATH = Path("data") / "gaingoblin.sqlite"
DEFAULT_ACCOUNT_NAME = "Manual Hoard"


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
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    institution_label TEXT NOT NULL DEFAULT '',
                    account_type TEXT NOT NULL DEFAULT '',
                    last_four TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER,
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
            self._ensure_column(connection, "holdings", "account_id", "INTEGER")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS import_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    accepted_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO accounts (
                    name, institution_label, account_type, last_four, notes
                )
                VALUES (?, '', '', '', '')
                """,
                (DEFAULT_ACCOUNT_NAME,),
            )

    def list_accounts(self) -> list[Account]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, institution_label, account_type, last_four, notes
                FROM accounts
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    def get_or_create_account(self, name: str = DEFAULT_ACCOUNT_NAME) -> Account:
        clean_name = (name or DEFAULT_ACCOUNT_NAME).strip() or DEFAULT_ACCOUNT_NAME
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, institution_label, account_type, last_four, notes
                FROM accounts
                WHERE lower(name) = lower(?)
                """,
                (clean_name,),
            ).fetchone()
            if row is not None:
                return self._row_to_account(row)

            cursor = connection.execute(
                """
                INSERT INTO accounts (
                    name, institution_label, account_type, last_four, notes
                )
                VALUES (?, '', '', '', '')
                """,
                (clean_name,),
            )
            account_id = int(cursor.lastrowid)
            row = connection.execute(
                """
                SELECT id, name, institution_label, account_type, last_four, notes
                FROM accounts
                WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Created account could not be loaded.")
            return self._row_to_account(row)

    def list_holdings(self, account_id: int | None = None) -> list[Holding]:
        query = """
            SELECT h.id, h.account_id, h.symbol_name, h.shares, h.buy_price,
                   h.buy_fees, h.target_sell_price, h.sell_fees, h.notes,
                   COALESCE(a.name, ?) AS account_name
            FROM holdings h
            LEFT JOIN accounts a ON a.id = h.account_id
        """
        params: list[object] = [DEFAULT_ACCOUNT_NAME]
        if account_id is not None:
            query += " WHERE h.account_id = ?"
            params.append(account_id)
        query += " ORDER BY account_name COLLATE NOCASE, h.symbol_name COLLATE NOCASE, h.id"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_holding(row) for row in rows]

    def add_holding(self, holding: Holding) -> int:
        account_id = holding.account_id
        if account_id is None:
            account_id = self.get_or_create_account(holding.account_name).id

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO holdings (
                    account_id, symbol_name, shares, buy_price, buy_fees,
                    target_sell_price, sell_fees, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._holding_values(holding, account_id),
            )
            return int(cursor.lastrowid)

    def update_holding(self, holding: Holding) -> None:
        if holding.id is None:
            raise ValueError("Cannot update a holding without an id.")

        account_id = holding.account_id
        if account_id is None:
            account_id = self.get_or_create_account(holding.account_name).id

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE holdings
                SET account_id = ?,
                    symbol_name = ?,
                    shares = ?,
                    buy_price = ?,
                    buy_fees = ?,
                    target_sell_price = ?,
                    sell_fees = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*self._holding_values(holding, account_id), holding.id),
            )

    def add_holding_to_account(self, holding: Holding, account_id: int) -> int:
        return self.add_holding(
            Holding(
                id=holding.id,
                account_id=account_id,
                account_name=holding.account_name,
                symbol_name=holding.symbol_name,
                shares=holding.shares,
                buy_price=holding.buy_price,
                buy_fees=holding.buy_fees,
                target_sell_price=holding.target_sell_price,
                sell_fees=holding.sell_fees,
                notes=holding.notes,
            )
        )

    def holding_exists(self, account_id: int | None, symbol_name: str) -> bool:
        symbol = symbol_name.strip()
        if not symbol:
            return False
        with self.connect() as connection:
            if account_id is None:
                row = connection.execute(
                    """
                    SELECT 1 FROM holdings
                    WHERE account_id IS NULL AND lower(symbol_name) = lower(?)
                    LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT 1 FROM holdings
                    WHERE account_id = ? AND lower(symbol_name) = lower(?)
                    LIMIT 1
                    """,
                    (account_id, symbol),
                ).fetchone()
        return row is not None

    def find_account_by_name(self, name: str) -> Account | None:
        clean_name = (name or DEFAULT_ACCOUNT_NAME).strip() or DEFAULT_ACCOUNT_NAME
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, institution_label, account_type, last_four, notes
                FROM accounts
                WHERE lower(name) = lower(?)
                """,
                (clean_name,),
            ).fetchone()
        return self._row_to_account(row) if row is not None else None

    def holding_exists_in_account_name(self, account_name: str, symbol_name: str) -> bool:
        account = self.find_account_by_name(account_name)
        if account is None:
            return False
        return self.holding_exists(account.id, symbol_name)

    def record_import_batch(
        self,
        source_path: str,
        source_type: str,
        row_count: int,
        accepted_count: int,
        skipped_count: int,
        notes: str = "",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_batches (
                    source_path, source_type, row_count, accepted_count, skipped_count, notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_path, source_type, row_count, accepted_count, skipped_count, notes),
            )
            return int(cursor.lastrowid)

    def list_import_batches(self) -> list[ImportBatch]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, source_path, source_type, row_count, accepted_count, skipped_count, notes
                FROM import_batches
                ORDER BY id DESC
                """
            ).fetchall()
        return [
            ImportBatch(
                id=int(row["id"]),
                source_path=row["source_path"],
                source_type=row["source_type"],
                row_count=int(row["row_count"]),
                accepted_count=int(row["accepted_count"]),
                skipped_count=int(row["skipped_count"]),
                notes=row["notes"],
            )
            for row in rows
        ]

    def delete_holding(self, holding_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))

    def replace_all(self, holdings: Iterable[Holding]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM holdings")
            connection.executemany(
                """
                INSERT INTO holdings (
                    account_id, symbol_name, shares, buy_price, buy_fees,
                    target_sell_price, sell_fees, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    self._holding_values(
                        holding,
                        holding.account_id or self.get_or_create_account(holding.account_name).id,
                    )
                    for holding in holdings
                ],
            )

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table})")]
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _holding_values(holding: Holding, account_id: int | None) -> tuple[object, str, str, str, str, str, str, str]:
        return (
            account_id,
            holding.symbol_name.strip(),
            str(holding.shares),
            str(holding.buy_price),
            str(holding.buy_fees),
            str(holding.target_sell_price),
            str(holding.sell_fees),
            holding.notes,
        )

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> Account:
        return Account(
            id=int(row["id"]),
            name=row["name"],
            institution_label=row["institution_label"],
            account_type=row["account_type"],
            last_four=row["last_four"],
            notes=row["notes"],
        )

    @staticmethod
    def _row_to_holding(row: sqlite3.Row) -> Holding:
        return Holding(
            id=int(row["id"]),
            account_id=int(row["account_id"]) if row["account_id"] is not None else None,
            account_name=row["account_name"] or DEFAULT_ACCOUNT_NAME,
            symbol_name=row["symbol_name"],
            shares=Decimal(row["shares"]),
            buy_price=Decimal(row["buy_price"]),
            buy_fees=Decimal(row["buy_fees"]),
            target_sell_price=Decimal(row["target_sell_price"]),
            sell_fees=Decimal(row["sell_fees"]),
            notes=row["notes"],
        )
