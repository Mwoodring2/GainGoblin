import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gaingoblin.database import HoldingRepository
from gaingoblin.importers.import_models import ImportPreviewRow
from gaingoblin.widgets.import_dialog import ImportDialog


def test_import_button_disabled_when_zero_rows_are_accepted(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    dialog = ImportDialog(repository)
    dialog.preview_rows = [
        ImportPreviewRow(
            row_number=1,
            symbol_name="AAPL",
            shares=Decimal("10"),
            buy_price=Decimal("0"),
            buy_fees=Decimal("0"),
            target_sell_price=Decimal("0"),
            sell_fees=Decimal("0"),
            notes="AAPL 10 shares",
            account_name="Manual Hoard",
            status="skipped",
            message="Required numeric value is missing.",
        )
    ]

    dialog._populate_preview_table()

    assert not dialog.import_button.isEnabled()
    assert "No importable holdings found" in dialog.summary_label.text()
    assert dialog.preview_table.item(0, 1).foreground().color().name() == "#b7aa8a"

    dialog.close()


def test_import_preview_styles_accepted_and_skipped_rows_differently(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    dialog = ImportDialog(repository)
    dialog.preview_rows = [
        ImportPreviewRow(
            row_number=1,
            symbol_name="AAPL",
            shares=Decimal("10"),
            buy_price=Decimal("150"),
            buy_fees=Decimal("0"),
            target_sell_price=Decimal("0"),
            sell_fees=Decimal("0"),
            notes="ok",
            account_name="Manual Hoard",
            status="accepted",
            message="Ready to import.",
        ),
        ImportPreviewRow(
            row_number=2,
            symbol_name="MSFT",
            shares=Decimal("5"),
            buy_price=Decimal("0"),
            buy_fees=Decimal("0"),
            target_sell_price=Decimal("0"),
            sell_fees=Decimal("0"),
            notes="missing",
            account_name="Manual Hoard",
            status="skipped",
            message="Required numeric value is missing.",
        ),
    ]

    dialog._populate_preview_table()

    accepted = dialog.preview_table.item(0, 1)
    skipped = dialog.preview_table.item(1, 1)
    assert accepted.background().color().name() != skipped.background().color().name()
    assert skipped.foreground().color().name() == "#b7aa8a"

    dialog.close()
