import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gaingoblin.models import Holding
from gaingoblin.widgets.range_calculator_dialog import MARKET_DATA_WARNING, RangeCalculatorDialog


def test_range_calculator_dialog_has_responsive_pinned_button_layout() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = RangeCalculatorDialog()

    assert dialog.isSizeGripEnabled()
    assert dialog.scroll_area.widgetResizable()
    assert dialog.layout().itemAt(dialog.layout().count() - 1).widget() is dialog.buttons
    assert dialog.calculate_button.text() == "Calculate"
    assert dialog.copy_button.text() == "Copy Result Summary"
    assert dialog.fetch_button.text() == "Fetch Market Numbers"
    assert dialog.use_average_button.text() == "Use Average High/Low"
    assert dialog.clear_fetch_button.text() == "Clear Fetched Data"
    assert dialog.open_settings_button.text() == "Open Market Data Settings"
    assert dialog.market_warning.text() == MARKET_DATA_WARNING

    dialog.close()


def test_range_calculator_dialog_loads_selected_holding() -> None:
    app = QApplication.instance() or QApplication([])
    holding = Holding(
        symbol_name="ORC",
        shares=Decimal("100"),
        buy_price=Decimal("7.50"),
        buy_fees=Decimal("1.25"),
        target_sell_price=Decimal("0"),
        sell_fees=Decimal("0.75"),
        notes="manual note",
    )
    dialog = RangeCalculatorDialog(selected_holding=holding)

    assert dialog.load_selected_button.isEnabled()
    dialog.load_selected_holding()

    assert dialog.symbol_name.text() == "ORC"
    assert dialog.shares.text() == "100"
    assert dialog.planned_buy_price.text() == "7.50"
    assert dialog.buy_fees.text() == "1.25"
    assert dialog.sell_fees.text() == "0.75"

    dialog.close()


def test_range_calculator_dialog_calculates_and_populates_results() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = RangeCalculatorDialog()
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("100")
    dialog.planned_buy_price.setText("7.50")
    dialog.average_low_price.setText("6.90")
    dialog.average_high_price.setText("8.25")
    dialog.buy_fees.setText("0")
    dialog.sell_fees.setText("0")

    result = dialog.calculate_current_scenario()

    assert result is not None
    assert result.high_profit == Decimal("75.00")
    assert dialog.result_labels["entry_cost"].text() == "$750.00"
    assert dialog.result_labels["high_roi_percent"].text() == "10.00%"
    assert dialog.copy_button.isEnabled()

    dialog.close()


def test_range_calculator_dialog_validation_uses_inline_warning() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = RangeCalculatorDialog()
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("100")
    dialog.planned_buy_price.setText("7.50")
    dialog.average_low_price.setText("8.25")
    dialog.average_high_price.setText("6.90")

    result = dialog.calculate_current_scenario()

    assert result is None
    assert "Average high price" in dialog.status_label.text()
    assert not dialog.copy_button.isEnabled()

    dialog.close()
