from __future__ import annotations

from pathlib import Path

from gaingoblin.database import DEFAULT_ACCOUNT_NAME, HoldingRepository
from gaingoblin.importers.column_mapper import build_column_mapping, parse_decimal
from gaingoblin.importers.import_models import ImportPreviewRow, ImportResult, RawImportRow
from gaingoblin.models import Holding

ACCEPTED = "accepted"
SKIPPED = "skipped"


def create_import_preview(
    rows: list[RawImportRow],
    repository: HoldingRepository | None = None,
    default_account_name: str = DEFAULT_ACCOUNT_NAME,
) -> list[ImportPreviewRow]:
    if not rows:
        return []

    headers = list(rows[0].values.keys())
    mapping = build_column_mapping(headers)
    preview: list[ImportPreviewRow] = []
    seen_keys: set[tuple[str, str]] = set()

    for row in rows:
        preview_row = _row_to_preview(row, mapping, default_account_name)
        account_key = preview_row.account_name.strip().lower()
        symbol_key = preview_row.symbol_name.strip().lower()
        duplicate_key = (account_key, symbol_key)

        if preview_row.status == ACCEPTED and duplicate_key in seen_keys:
            preview_row = _replace_status(preview_row, SKIPPED, "Duplicate row in import file.")
        elif (
            preview_row.status == ACCEPTED
            and repository is not None
            and repository.holding_exists_in_account_name(preview_row.account_name, preview_row.symbol_name)
        ):
            preview_row = _replace_status(preview_row, SKIPPED, "Already exists in this account.")

        if preview_row.status == ACCEPTED:
            seen_keys.add(duplicate_key)
        preview.append(preview_row)

    return preview


def import_preview_rows(
    repository: HoldingRepository,
    preview_rows: list[ImportPreviewRow],
    source_path: str,
    source_type: str,
) -> ImportResult:
    imported = 0
    skipped = 0
    messages: list[str] = []

    for row in preview_rows:
        if row.status != ACCEPTED:
            skipped += 1
            messages.append(f"Row {row.row_number}: {row.message}")
            continue

        account = repository.get_or_create_account(row.account_name)
        if repository.holding_exists(account.id, row.symbol_name):
            skipped += 1
            messages.append(f"Row {row.row_number}: Already exists in this account.")
            continue

        repository.add_holding_to_account(
            Holding(
                account_id=account.id,
                account_name=account.name,
                symbol_name=row.symbol_name,
                shares=row.shares,
                buy_price=row.buy_price,
                buy_fees=row.buy_fees,
                target_sell_price=row.target_sell_price,
                sell_fees=row.sell_fees,
                notes=row.notes,
            ),
            account.id,
        )
        imported += 1

    skipped += sum(1 for row in preview_rows if row.status == ACCEPTED) - imported
    batch_id = repository.record_import_batch(
        source_path=source_path,
        source_type=source_type,
        row_count=len(preview_rows),
        accepted_count=imported,
        skipped_count=len(preview_rows) - imported,
        notes="; ".join(messages[:10]),
    )
    return ImportResult(
        imported_count=imported,
        skipped_count=len(preview_rows) - imported,
        messages=messages,
        batch_id=batch_id,
    )


def import_spreadsheet(
    repository: HoldingRepository,
    path: Path | str,
    rows: list[RawImportRow],
    default_account_name: str = DEFAULT_ACCOUNT_NAME,
) -> ImportResult:
    source = Path(path)
    preview = create_import_preview(rows, repository, default_account_name)
    return import_preview_rows(repository, preview, str(source), source.suffix.lower().lstrip("."))


def _row_to_preview(
    row: RawImportRow,
    mapping: dict[str, str],
    default_account_name: str,
) -> ImportPreviewRow:
    def value_for(key: str) -> str:
        mapped = mapping.get(key)
        return row.values.get(mapped, "") if mapped else ""

    symbol = value_for("symbol_name").strip().upper()
    account_name = value_for("account_name").strip() or default_account_name
    notes = value_for("notes").strip()

    try:
        shares = parse_decimal(value_for("shares"), required=True)
        buy_price = parse_decimal(value_for("buy_price"), required=True)
        buy_fees = parse_decimal(value_for("buy_fees"))
        target_sell_price = parse_decimal(value_for("target_sell_price"))
        sell_fees = parse_decimal(value_for("sell_fees"))
    except ValueError as exc:
        return ImportPreviewRow(
            row_number=row.row_number,
            symbol_name=symbol,
            shares=parse_decimal("0"),
            buy_price=parse_decimal("0"),
            buy_fees=parse_decimal("0"),
            target_sell_price=parse_decimal("0"),
            sell_fees=parse_decimal("0"),
            notes=notes,
            account_name=account_name,
            status=SKIPPED,
            message=str(exc),
        )

    if not symbol:
        status = SKIPPED
        message = "Missing symbol."
    else:
        status = ACCEPTED
        message = "Ready to import."

    return ImportPreviewRow(
        row_number=row.row_number,
        symbol_name=symbol,
        shares=shares,
        buy_price=buy_price,
        buy_fees=buy_fees,
        target_sell_price=target_sell_price,
        sell_fees=sell_fees,
        notes=notes,
        account_name=account_name,
        status=status,
        message=message,
    )


def _replace_status(row: ImportPreviewRow, status: str, message: str) -> ImportPreviewRow:
    return ImportPreviewRow(
        row_number=row.row_number,
        symbol_name=row.symbol_name,
        shares=row.shares,
        buy_price=row.buy_price,
        buy_fees=row.buy_fees,
        target_sell_price=row.target_sell_price,
        sell_fees=row.sell_fees,
        notes=row.notes,
        account_name=row.account_name,
        status=status,
        message=message,
    )
